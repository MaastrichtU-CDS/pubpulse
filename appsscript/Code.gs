/**
 * pubpulse subscriber list — Google Apps Script web app.
 *
 * Runs under the pubpulse Gmail account. Stores subscribers in a private Google Sheet in that account's Drive,
 * sends confirmation mails (double opt-in) and handles confirm/unsubscribe links. The weekly GitHub job fetches
 * the confirmed list with a secret key.
 *
 * Setup (once, ~5 minutes):
 *   1. https://script.google.com (logged in as the pubpulse Gmail account) → New project → paste this file.
 *   2. Run → setup   (grant permissions; then View → Logs: copy the SECRET it prints)
 *   3. Deploy → New deployment → type "Web app" → Execute as: Me → Who has access: Anyone → Deploy. Copy the URL.
 *   4. In GitHub: secret SUBSCRIBERS_KEY = the SECRET; in config.yml: digest.subscribe_endpoint = the web app URL.
 *   After editing this file later: Deploy → Manage deployments → edit → New version.
 */

const SHEET_NAME = 'subscribers';
const LIST_NAME = 'pubpulse weekly publications';       // shown in mails
const ALLOWED_DOMAINS = [];                              // e.g. ['maastrichtuniversity.nl', 'maastro.nl']; empty = any
const FROM_NAME = 'pubpulse';

function setup() {
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('SECRET')) props.setProperty('SECRET', Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, ''));
  sheet_();
  Logger.log('SECRET (put this in the GitHub secret SUBSCRIBERS_KEY):\n' + props.getProperty('SECRET'));
  Logger.log('Sheet: https://docs.google.com/spreadsheets/d/' + props.getProperty('SHEET_ID'));
}

function sheet_() {
  const props = PropertiesService.getScriptProperties();
  let ss;
  const id = props.getProperty('SHEET_ID');
  if (id) {
    ss = SpreadsheetApp.openById(id);
  } else {
    ss = SpreadsheetApp.create('pubpulse subscribers');
    props.setProperty('SHEET_ID', ss.getId());
  }
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(['email', 'status', 'token', 'created', 'updated']);
  }
  return sh;
}

function rows_() {
  const sh = sheet_();
  const values = sh.getDataRange().getValues();
  const out = [];
  for (let i = 1; i < values.length; i++) {
    out.push({ row: i + 1, email: String(values[i][0]).toLowerCase(), status: String(values[i][1]), token: String(values[i][2]) });
  }
  return out;
}

function find_(email) { return rows_().find(r => r.email === email) || null; }
function byToken_(token) { return token ? rows_().find(r => r.token === token) || null : null; }

function setStatus_(rec, status, newToken) {
  const sh = sheet_();
  const token = newToken || rec.token;
  sh.getRange(rec.row, 2, 1, 4).setValues([[status, token, sh.getRange(rec.row, 4).getValue() || new Date(), new Date()]]);
  rec.status = status; rec.token = token;
}

function add_(email, status) {
  const sh = sheet_();
  const token = Utilities.getUuid().replace(/-/g, '');
  sh.appendRow([email, status, token, new Date(), new Date()]);
  return { row: sh.getLastRow(), email: email, status: status, token: token };
}

function normalize_(email) { return String(email || '').trim().toLowerCase(); }
function valid_(email) {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return false;
  if (ALLOWED_DOMAINS.length && !ALLOWED_DOMAINS.some(d => email.endsWith('@' + d))) return false;
  return true;
}

function url_(action, token) { return ScriptApp.getService().getUrl() + '?action=' + action + '&token=' + token; }

function json_(obj) { return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON); }
function page_(title, text) {
  const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + title +
    '</title><style>body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:560px;margin:60px auto;padding:0 20px;color:#222;line-height:1.5}h1{font-size:22px}</style></head><body><h1>' +
    title + '</h1><p>' + text + '</p></body></html>';
  return HtmlService.createHtmlOutput(html).setTitle(title);
}

/** Website form posts here as text/plain JSON: {action: 'subscribe'|'unsubscribe', email}. */
function doPost(e) {
  let data = {};
  try { data = JSON.parse((e.postData && e.postData.contents) || '{}'); } catch (err) { return json_({ ok: false, error: 'bad request' }); }
  const email = normalize_(data.email);
  if (!valid_(email)) return json_({ ok: false, error: ALLOWED_DOMAINS.length ? 'Please use an address of ' + ALLOWED_DOMAINS.join(' / ') : 'That does not look like an email address.' });
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    if (data.action === 'subscribe') {
      let rec = find_(email);
      if (rec && rec.status === 'confirmed') return json_({ ok: true, status: 'already', message: 'You are already subscribed.' });
      const token = Utilities.getUuid().replace(/-/g, '');
      if (rec) setStatus_(rec, 'pending', token); else rec = add_(email, 'pending');
      MailApp.sendEmail({
        to: email, name: FROM_NAME,
        subject: 'Confirm your subscription to ' + LIST_NAME,
        htmlBody: '<p>Click to confirm that you want the weekly publication overview:</p><p><a href="' + url_('confirm', rec.token) + '">Confirm subscription</a></p><p style="color:#888;font-size:12px">If you did not request this, ignore this mail.</p>',
        body: 'Confirm your subscription: ' + url_('confirm', rec.token),
      });
      return json_({ ok: true, status: 'pending', message: 'Check your inbox and click the confirmation link.' });
    }
    if (data.action === 'unsubscribe') {
      const rec = find_(email);
      if (rec && rec.status === 'confirmed') {
        MailApp.sendEmail({
          to: email, name: FROM_NAME,
          subject: 'Unsubscribe from ' + LIST_NAME,
          htmlBody: '<p>Click to unsubscribe:</p><p><a href="' + url_('unsubscribe', rec.token) + '">Unsubscribe</a></p>',
          body: 'Unsubscribe: ' + url_('unsubscribe', rec.token),
        });
      }
      return json_({ ok: true, status: 'sent', message: 'If that address is subscribed, an unsubscribe link has been mailed to it.' });
    }
    return json_({ ok: false, error: 'unknown action' });
  } finally { lock.releaseLock(); }
}

/** Links in mails (confirm / unsubscribe) and the list endpoint for the GitHub job. */
function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.action === 'confirm') {
    const rec = byToken_(p.token);
    if (!rec) return page_('Link not valid', 'This confirmation link is not valid any more. Subscribe again on the website.');
    setStatus_(rec, 'confirmed');
    return page_('Subscribed', 'You will receive the weekly publication overview at <b>' + rec.email + '</b>. Every mail has an unsubscribe link.');
  }
  if (p.action === 'unsubscribe') {
    const rec = byToken_(p.token);
    if (!rec) return page_('Link not valid', 'This unsubscribe link is not valid. Request a new one on the website.');
    setStatus_(rec, 'unsubscribed');
    return page_('Unsubscribed', '<b>' + rec.email + '</b> will no longer receive the weekly overview.');
  }
  if (p.action === 'list') {
    const secret = PropertiesService.getScriptProperties().getProperty('SECRET');
    if (!secret || p.key !== secret) return json_({ ok: false, error: 'forbidden' });
    return json_({ ok: true, subscribers: rows_().filter(r => r.status === 'confirmed').map(r => ({ email: r.email, token: r.token })) });
  }
  return page_(LIST_NAME, 'Subscribe on the <a href="https://maastrichtu-cds.github.io/pubpulse/">pubpulse website</a>.');
}
