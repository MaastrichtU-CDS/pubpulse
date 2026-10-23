/**
 * pubpulse review sheet — a private Google Sheet where invited members mark papers as CDS-authored (yes/no).
 *
 * Runs under the pubpulse Google account. Every week it refreshes the data columns from the public export on the
 * website and keeps the manual columns. The weekly GitHub job reads the decisions back through doGet with a key.
 *
 * Setup (once):
 *   1. Logged in as the pubpulse Google account: create a Google Sheet, Extensions → Apps Script, paste this file.
 *   2. Run → setup   (grant permissions; View → Logs shows the SECRET and installs the weekly refresh trigger)
 *   3. Deploy → New deployment → Web app → Execute as: Me → Who has access: Anyone → Deploy. Copy the URL.
 *   4. GitHub secrets: REVIEW_SHEET_URL = the web app URL, REVIEW_SHEET_KEY = the SECRET.
 *   5. Share the sheet with the invited editors (Editor). Nobody else can see it.
 * Columns the editors use: "CDS authored (manual)" = yes / no (blank = no decision), "Review note".
 */

const EXPORT_CSV = 'https://maastrichtu-cds.github.io/pubpulse/data/pubpulse-publications.csv';
const SHEET_NAME = 'Publications';
const MANUAL_COLS = ['CDS authored (manual)', 'Review note', 'Reviewed by', 'Reviewed on'];
const ID_HEADER = 'OpenAlex work id';

function setup() {
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('SECRET')) props.setProperty('SECRET', Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, ''));
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('refresh').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(9).create();
  refresh();
  Logger.log('SECRET (GitHub secret REVIEW_SHEET_KEY):\n' + props.getProperty('SECRET'));
}

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
}

/** Pull the export, keep manual columns keyed by OpenAlex id, rewrite the sheet. */
function refresh() {
  const resp = UrlFetchApp.fetch(EXPORT_CSV, { muteHttpExceptions: true });
  if (resp.getResponseCode() !== 200) throw new Error('export not reachable: ' + resp.getResponseCode());
  const rows = Utilities.parseCsv(resp.getContentText('UTF-8'));
  const header = rows[0];
  const idCol = header.indexOf(ID_HEADER);
  if (idCol < 0) throw new Error('export has no "' + ID_HEADER + '" column');
  const sh = sheet_();
  // existing manual values
  const manual = {};
  if (sh.getLastRow() > 1) {
    const old = sh.getDataRange().getValues();
    const oh = old[0];
    const oid = oh.indexOf(ID_HEADER);
    const mcols = MANUAL_COLS.map(c => oh.indexOf(c));
    if (oid >= 0) for (let i = 1; i < old.length; i++) manual[String(old[i][oid])] = mcols.map(c => (c >= 0 ? old[i][c] : ''));
  }
  const out = [header.concat(MANUAL_COLS)];
  for (let i = 1; i < rows.length; i++) {
    const r = rows[i];
    if (!r[idCol]) continue;
    out.push(r.concat(manual[r[idCol]] || MANUAL_COLS.map(() => '')));
  }
  sh.clearContents();
  sh.getRange(1, 1, out.length, out[0].length).setValues(out);
  sh.setFrozenRows(1);
  const mStart = header.length + 1;
  sh.getRange(1, 1, 1, out[0].length).setFontWeight('bold');
  sh.getRange(1, mStart, 1, MANUAL_COLS.length).setBackground('#fff4dd');
  const rule = SpreadsheetApp.newDataValidation().requireValueInList(['yes', 'no'], true).setAllowInvalid(false).build();
  sh.getRange(2, mStart, Math.max(out.length - 1, 1), 1).setDataValidation(rule);
  // protect the data columns: only the manual columns are editable by editors
  sh.getProtections(SpreadsheetApp.ProtectionType.RANGE).forEach(p => p.remove());
  const prot = sh.getRange(1, 1, Math.max(out.length, 2), header.length).protect().setDescription('data from pubpulse (refreshed weekly)');
  prot.setWarningOnly(true);
  Logger.log('refreshed ' + (out.length - 1) + ' papers, kept ' + Object.keys(manual).length + ' manual rows');
}

/** Decisions for the GitHub job: ?key=SECRET -> {"ok":true,"decisions":{"W123":{"cds":"yes","note":"..."}}} */
function doGet(e) {
  const p = (e && e.parameter) || {};
  const secret = PropertiesService.getScriptProperties().getProperty('SECRET');
  if (!secret || p.key !== secret) return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'forbidden' })).setMimeType(ContentService.MimeType.JSON);
  const sh = sheet_();
  const vals = sh.getDataRange().getValues();
  const h = vals[0];
  const idc = h.indexOf(ID_HEADER), cds = h.indexOf(MANUAL_COLS[0]), note = h.indexOf(MANUAL_COLS[1]);
  const decisions = {};
  for (let i = 1; i < vals.length; i++) {
    const v = String(vals[i][cds] || '').trim().toLowerCase();
    if (v === 'yes' || v === 'no') decisions[String(vals[i][idc])] = { cds: v, note: note >= 0 ? String(vals[i][note] || '') : '' };
  }
  return ContentService.createTextOutput(JSON.stringify({ ok: true, decisions: decisions, count: Object.keys(decisions).length })).setMimeType(ContentService.MimeType.JSON);
}

/** Stamp who/when on edits of the manual column. */
function onEdit(e) {
  try {
    const sh = e.range.getSheet();
    if (sh.getName() !== SHEET_NAME) return;
    const h = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
    const cds = h.indexOf(MANUAL_COLS[0]) + 1;
    if (e.range.getColumn() !== cds || e.range.getRow() === 1) return;
    const by = h.indexOf(MANUAL_COLS[2]) + 1, on = h.indexOf(MANUAL_COLS[3]) + 1;
    if (by) sh.getRange(e.range.getRow(), by).setValue(Session.getActiveUser().getEmail() || 'editor');
    if (on) sh.getRange(e.range.getRow(), on).setValue(new Date());
  } catch (err) { /* ignore */ }
}
