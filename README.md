# pubpulse

Weekly overview of publications by the **Clinical Data Science** group (Maastro / Maastricht University).

- **Website with filters:** https://maastrichtu-cds.github.io/pubpulse/
- **RSS feed:** https://maastrichtu-cds.github.io/pubpulse/feed.xml
- **Weekly digest:** every Monday morning by email and in Teams, only when there is something new.
  **[This week's newsletter](https://maastrichtu-cds.github.io/pubpulse/digest.html)** on the web (refreshed daily, past issues below it).
- **Authorship statistics** (on the website, under *Statistics*): papers, % first author, % last author per person and per
  research group, following the website filters.

## Lists you can edit (Google login, no GitHub needed)

| What | Where | Who can edit |
| --- | --- | --- |
| Research groups and seniors (for the statistics) | [groups sheet](GROUPS_SHEET_EDIT_LINK) | invited editors, Google login |
| "CDS authored" yes/no per paper | [review sheet](REVIEW_SHEET_EDIT_LINK) | invited editors, Google login |
| Your ORCID / Google Scholar link | your own profile on the [staff page](https://www.clinicaldatascience.nl/staff) | website login |
| Membership start/end dates (private) | ask a maintainer | maintainers only |

Changes are picked up by the next run (daily for the sheets, Mondays for the staff page). To ask for edit access, contact
a maintainer.

## When is what updated?

| What | When |
| --- | --- |
| New papers from OpenAlex | daily (Mon–Fri, 06:00 UTC); OpenAlex itself indexes papers days to weeks after publication |
| Digest email and Teams post | Mondays only, and only when there are new papers; [preview](https://maastrichtu-cds.github.io/pubpulse/digest.html) |
| Staff list (who is a member, who left) | Mondays, from the staff page list |
| ORCID / Scholar links on staff profiles | when someone is new, otherwise every 30 days per profile |
| OpenAlex author matching per person | every 30 days, or immediately after an edit of people.yml |
| Automatic search for missing ORCID / Scholar profiles | every 30 days per person (Mondays) |
| Google Scholar cross-check | first day of the month |
| Groups sheet, review sheet | every run |

Every Monday a small robot reads the [staff page](https://www.clinicaldatascience.nl/staff), looks up every current
staff member and follows recent former-staff collaborations in [OpenAlex](https://openalex.org) (a free, open catalogue that merges Crossref, PubMed, ORCID and
preprint servers), stores the publications it finds here, refreshes the website and sends the digest.

## For group members (no technical knowledge needed)

**How do I add or change my ORCID or Google Scholar link?**
On the [staff page](https://www.clinicaldatascience.nl/staff): make sure your own profile page links to your ORCID
(and, if you like, your Google Scholar profile). That is all. Every Monday the robot re-reads every profile, so the
change is picked up automatically. Nobody needs a GitHub account for this.
If you cannot edit the staff page, use the form at *Issues → New issue → "Add or correct my ORCID / Scholar / OpenAlex id"*
(needs a free GitHub account); a robot applies it within minutes.

**I am not on the list / my papers are missing.**
Your profile needs an ORCID link (see above). Without one, the robot tries to find you in OpenAlex by name, but only
accepts a match affiliated with Maastro/Maastricht, and then only counts papers that carry a group affiliation for you.
The website’s *Data sources & coverage* section explains profiles without a confirmed match.

**A paper is marked "unverified".**
OpenAlex did not record a Maastricht/Maastro/MUMC+ affiliation for you on that paper. The paper is still shown, just
marked. Usually this means the publisher did not send affiliations to Crossref. Nothing to do unless it is not your paper.

**How papers are attributed (and why some are marked).**
- People with an ORCID: OpenAlex is queried by ORCID. If OpenAlex attached that ORCID to several author records
  (it sometimes merges namesakes), the record whose current institution is in Maastricht wins.
- People without an ORCID: matched by full name *and* a Maastricht/Maastro affiliation on the OpenAlex record.
  Name matching allows accents, hyphens and extra middle initials, but not a first initial alone or ambiguous names. For
  them a paper only counts when the paper itself carries a verified group affiliation for that author.
- Author highlighting and researcher filters include known CDS coauthors on papers already in the collection, even
  when their authorship lists another department or has no affiliation. A unique full-name match is accepted within
  a collaboration with an identified CDS coauthor, or with that author’s own group affiliation. This does not relax collection eligibility.
- Split OpenAlex author IDs and missing reported ORCIDs can be recovered from affiliated authorships. The originating
  work and IDs are retained in `people.yml` under `publication_identity_sources`. Reported ORCIDs remain separate from
  confirmed ORCIDs; conflicting IDs are retained for review and are not used as profile links. Google Scholar profile
  IDs come from explicit profile links, never from a name-based Scholar search URL.

**Former staff and continuing collaborations.**
All people in the CDS staff page’s *Previous staff* section are kept as former staff, including those whose
departure date is unknown. Every weekly sync reviews them against the publication collection. A paper with an
identified current CDS coauthor can establish a unique full-first-and-last-name match and record observed name
variants. The review covers every former person; no match means *no evidence in this collection*, not that they
have stopped publishing.

Collaborations in the last 24 months renew follow-up for another 24 months from the latest paper. This is separate
from the original departure grace period. Follow-up searches collect their papers with current CDS coauthors,
without importing their entire subsequent career. They remain labelled **Former staff** in the researcher list and
profile panel; the hero’s member count includes current staff only. The date window is configurable under
`former_staff.recent_collaboration_months`. Actual departure dates are never inferred from publication dates.

Run `python -m pubpulse review-former` to refresh the audit in `data/former_staff_review.json`. A saved staff-page
snapshot can be imported with `--staff-snapshot <file>`. `discover-identifiers --former` searches missing profiles
across all alumni; `--recent-former` prioritises those with recent group collaborations. Both retain source evidence
and respect the search budget. The weekly workflow runs the roster review and a bounded all-former profile pass
before the regular identifier and publication syncs. Newly observed collaborations reopen identifier checks.

**Automatic discovery of missing profiles.**
The scheduled weekly run searches all tracked researchers with a missing ORCID or Google Scholar profile, without
person-specific rules. It searches the public ORCID registry (including shared DOI queries for common names), follows
the full known Scholar coauthor lists and searches the web for actual Scholar profile URLs. When a full-name search
finds no Scholar profile, a second query uses first/last names and known coauthors. Candidates must have the same
full first and last name, plus a shared publication with a known CDS coauthor, two known Scholar coauthors, or one
known Scholar coauthor and matching institution. An ORCID record may also link directly to a verified Scholar profile. Names and affiliations alone
are insufficient. Multiple supported profiles stay in the report for review.

Run `python -m pubpulse discover-identifiers --dry-run` to inspect proposals in `out/`, or omit `--dry-run` to apply
verified matches. `--only <slug>`, `--max-searches <n>` and `--force` control a run. Evidence, source URLs, shared papers,
known coauthors and unresolved candidates are saved in `data/identifier_discovery.json` and accepted evidence in
`people.yml`. Discovered ORCIDs remain separate from supplied ORCIDs, and do not relax affiliation checks when
collecting papers. Existing supplied profile IDs are preserved. Negative results and provider responses are cached
for 30 days. A configurable SerpAPI search cap preserves quota for the monthly publication cross-check.
- Verified means the authorship on that paper mentions Maastro, Radiation Oncology, GROW or Medical Data Works.
  "Maastricht University" alone is deliberately not enough. Every paper shows, per group author: verified, other
  affiliation, or no affiliation data. Papers with no verified group author are marked *unverified* and wait for the
  manual check below. Set `affiliation_policy: require` in `config.yml` to hide them instead.

**Manual check of unverified papers.**
On the website choose *Group affiliation → Unverified only*. For each paper decide: ours or not. Then put its OpenAlex id
(the `W…` shown under the paper) in [`overrides.yml`](overrides.yml) under `confirm:` or `reject:` and commit.
Rejected papers disappear, confirmed ones lose the marker. The weekly digest links straight to this view when needed.

**A paper is not mine (same name, different person).**
Reject it in `overrides.yml` (see above). If it keeps happening, ask a maintainer to set your `openalex_id` in
`people.yml`, or add your ORCID to the staff profile.

**I want the digest / to stop it.**
On the website, choose **Join the mailing list** or **Get the weekly digest**. If self-service signup is
configured, follow the link and complete the list provider’s joining steps. Otherwise, ask a CDS group maintainer to
add your email address to the group mailing list. The digest arrives on Mondays, only when there are new papers.
To leave, use the website’s **Unsubscribe** link when available, or contact a maintainer.

**Can I follow the RSS feed?**
Yes, but not in most Outlooks any more: the new Outlook for Windows and Outlook for Mac have no RSS support; only
classic Outlook for Windows still has *RSS Feeds → Add a New RSS Feed*. Alternatives: a free reader such as
NetNewsWire (Mac), Feedly or Inoreader; Thunderbird; or in Teams, *Workflows → "Post to a channel when an RSS feed is
published"* with the feed link, which posts every new paper to a channel without any secret.

**Refresh now instead of waiting for Monday.**
Go to [Actions → weekly](https://github.com/MaastrichtU-CDS/pubpulse/actions/workflows/weekly.yml) → *Run workflow*.
This refreshes everything and updates the digest preview; it does not send mail unless you tick *send_now*.

## For maintainers

### Files you may edit

| File | What |
| --- | --- |
| `config.yml` | group name, site URL, `since_year`, `track_sections` for active staff, former-staff collaboration window, institution keywords, `affiliation_policy` (`flag` or `require`) |
| `overrides.yml` | manual decisions per paper: `confirm:` / `reject:` lists of OpenAlex ids |
| `people.yml` | refreshed from the staff page on every run. Hand-edited fields that are never overwritten: `openalex_id` (one id, or a list when OpenAlex split a person into several records), `orcid` (when the staff page has none), `exclude: true`, `notes`. To track someone who is not on the staff page, add an entry with `source: manual`. People who disappear from the page get an `active_until` date; they are still tracked for `departed_grace_months` (papers in the pipeline), but only papers with a verified group affiliation count. Their earlier papers stay on the site. |
| `data/former_staff_review.json` | audit of every former staff member: shared papers, current coauthors, last collaboration, profile identifiers and follow-up status. A person without evidence remains explicitly unconfirmed. |

Edit either file in the GitHub web editor and commit to `main`; the workflow runs automatically on that commit.

### Secrets (Settings → Secrets and variables → Actions)

| Secret | Purpose |
| --- | --- |
| `OPENALEX_API_KEY` | free key from https://openalex.org/settings/api. Strongly recommended: without it OpenAlex shares one small daily budget per IP address (GitHub's runners share addresses) |
| `GMAIL_USER` | Gmail address the digest is sent from |
| `GMAIL_APP_PASSWORD` | a Gmail [app password](https://myaccount.google.com/apppasswords) (needs 2-step verification on that account) |
| `DIGEST_TO` | test recipient(s) only: used solely by manual runs with *force_notify* ticked; real sends go to the Brevo list |
| `SUBSCRIBERS_KEY` | the SECRET printed by the Apps Script `setup` (see mailing list section) |
| `BREVO_API_KEY` | Brevo API key: subscriber list + weekly campaign (see mailing list section) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | optional: any other SMTP relay instead of Gmail (e.g. Brevo free tier: `smtp-relay.brevo.com`, port 587, your Brevo login + SMTP key, a verified sender address) |
| `TEAMS_WEBHOOK_URL` | URL from a Teams *Workflows* flow "Post to a channel when a webhook request is received" |

A notification channel whose secret is missing is simply skipped; the site and feed always update.

### Mailing list with subscribe / unsubscribe (website form)

Self-service, no maintainer involved. The list lives in **Brevo** (the same account that sends the mail):

- **Sign-up form** on the website (inside the "Get the weekly digest" dialog): Brevo's hosted form with double opt-in.
- **Unsubscribe**: Brevo puts an unsubscribe link at the bottom of every digest, because the digest is sent as a Brevo
  *campaign* to the list "pubpulse weekly" (created automatically on the first send).
- **Fixed recipients** (optional, `DIGEST_TO`) still get the digest over plain SMTP.

One-time setup in Brevo (about 5 minutes):

1. *Settings → SMTP & API → API keys → Generate a new API key* → GitHub secret `BREVO_API_KEY` (and `.env` locally).
2. *Contacts → Forms → Create a subscription form*: field "Email" only; in *List* choose (or create) **pubpulse weekly**;
   switch on **double opt-in**; finish. Under *Share* copy the **form link**.
3. `config.yml` → `digest.subscribe_form_url:` = that link. Commit; the form appears in the website dialog.
4. Make sure the sender address (`SMTP_FROM`) is a *verified sender* in Brevo (*Senders & IP*).

Note: Brevo's free plan adds a small Brevo footer to campaigns and allows 300 mails a day; new accounts may be asked
to validate before the first larger campaign. (An alternative backend, Google Apps Script + Sheet in
[appsscript/Code.gs](appsscript/Code.gs), is kept for reference and selected with `digest.subscribe_endpoint`.)

To test delivery without waiting for a new paper: *Actions → weekly → Run workflow* and tick *force_notify*.

### Authorship statistics and the groups sheet

The website's *Authorship statistics* panel counts, over the current filters, per person: papers, first author, last
author and other positions (with percentages), and per group: papers with a member, papers with a member as first or as
last author. Positions come from the author order in OpenAlex; equal-contribution (shared first/last) authorship is not
recorded there. "All CDS" is always shown; seniors and research groups come from a Google Sheet:

1. `python -m pubpulse groups-template` writes `groups-template.csv`: current staff, `senior` pre-filled "yes" for
   professors (check it), `group` empty.
2. Create a Google Sheet, *File → Import* that CSV. Fill `senior` (yes/no) and `group`: the group name per person, usually
   the senior's name or the research line; several groups separated by `;`. Rows for people not on the staff page are
   reported as "not found" and ignored.
3. Share the sheet with the editors only (*Share → add people*); editing then needs a Google login.
4. *File → Share → Publish to web* → choose that tab → *Comma-separated values (.csv)* → *Publish*, copy the link.
5. `config.yml` → `groups.sheet_csv_url:` = that link, `groups.edit_url:` = the normal sheet link (shown on the
   website for editors). Replace `GROUPS_SHEET_EDIT_LINK` at the top of this README with the same link. Commit.

Every build reads the published CSV and keeps the last good copy in `data/groups.json`. Group composition is public on
the website (it is shown in the statistics); the sheet itself stays editable only by invited people.

### Digest preview and archive

`digest.html` on the website shows the mail as the next Monday run would send it right now: papers found by the daily
refreshes since the last digest (`data/pending.json`). Every digest that actually went out is kept in `data/digests/`
and listed under the preview. The newsletter lists only papers that are new since the last issue and published in
the last `digest.recent_days` (120); older papers that only now got linked to a member (a newly identified person, late
indexing) are left out, they just appear on the website. Each paper gets its LinkedIn card image, headline and short
text when a draft exists (needs `ANTHROPIC_API_KEY`), otherwise the title and the opening of the abstract. Mail goes out on the Monday schedule only; push-triggered runs and the Tue–Fri refreshes queue.

### Social posts: what goes where (design decisions)

- **Card image**: one idea only. A catchy headline (max ~60 characters), a proof line "Published in <journal> · <year>",
  a byline with the group authors, and quiet branding (eyebrow, emblem watermark, footer logos). The paper title and the
  DOI are deliberately *not* on the card: at feed size they are unreadable and they compete with the headline.
- **Post text**: the finding as first line, the group authors second (to tag), what/why/limitation in plain words,
  the journal last. No links in the body (LinkedIn reduces reach of posts with external links).
- **First comment**: the full paper title, the DOI and the open-access link. That is where readers look things up.
- **Which papers**: counted journal articles and reviews with an abstract of at least 80 words (shorter ones are
  teasers or repository descriptions). `python -m pubpulse social-draft --person <slug>` drafts all of one member's papers.
- **Figure** (only CC BY papers): the one that shows the main finding, with a plain-language caption; methods figures are
  rejected. Figure first, card second when both exist.

### Google Scholar cross-check (monthly)

Scholar has no API and forbids scraping, so pubpulse never imports from it. Once a month (and on demand via
*Actions → scholar-check*) the profiles of people with a Scholar link on the staff page are read through
[SerpAPI](https://serpapi.com) (free plan: 250 searches/month; one search per 100 papers per profile) and compared with
pubpulse. Papers that are on Scholar but not in pubpulse show up on the website and in the digest as "possibly missing",
with the person's name. Typical causes: the publisher did not send the author's ORCID (fix: add the paper in the ORCID
record, OpenAlex follows), or grey literature OpenAlex does not index (nothing to do). Secret: `SERPAPI_KEY`.

### Status, limitations and open decisions (background)

pubpulse is a first setup. Everything it shows is produced by simple rules, not by a person checking each paper:

- **Who is a member** comes from scraping the group's staff page; identities come from ORCIDs on the profiles or, for
  people without one, from a name match with a group affiliation.
- **What counts** follows the team-window rule: current members' papers count without an affiliation check, former
  members' papers only with a verified group affiliation, plus a short list of named exceptions whose papers always
  need a verified affiliation.

Known limits of this logic, discussed internally:

- An affiliation rule cannot be right for everyone. Some members publish with several affiliations at once, so "team
  member = no check" over-counts for them and "always check" under-counts for others; the exception list covers only
  the clear cases.
- Start and end dates of membership do not solve this either: papers stay in the pipeline long after someone joins
  or leaves, so a date cut-off is wrong in both directions.
- A manual check per paper is the only watertight method. The review sheet makes that possible for invited members,
  but it is extra work and has not been adopted as a process yet.

Until that process is decided, the website and the digest carry a **disclaimer**: the numbers are automated, not
manually verified, and contain mistakes. Treat the overview as internal and indicative, not as a reporting figure.

### Review sheet: manual "CDS authored" decisions in a private Google Sheet

For members who prefer a spreadsheet to editing overrides.yml: a private Google Sheet in the pubpulse Google account
mirrors the Excel export and adds the columns **CDS authored (manual)** (yes / no) and **Review note**. Only invited
editors can see or edit it. A small Apps Script ([appsscript/ReviewSheet.gs](appsscript/ReviewSheet.gs)) refreshes
the data columns every Monday from the site export, keeps the manual columns, stamps who decided when, and hands the
decisions to the weekly run through a key-protected endpoint. "yes" counts the paper (marked *confirmed*), "no"
removes it; entries in overrides.yml win on conflict. Setup is in the script header (5 steps, about 5 minutes);
secrets: `REVIEW_SHEET_URL`, `REVIEW_SHEET_KEY`.

### The team-window rule

A paper counts when a group member was in the team at publication time: current staff count for the whole window,
no affiliation check. Former staff count only with a verified group affiliation. **Exceptions by name** go in
[overrides.yml](overrides.yml) under `verify_affiliation:` (member ids from people.yml): their papers count only with a
verified affiliation. Papers you never want counted: `reject:`. That is the whole rule.

### Optional: membership periods in a private Google Sheet

Who counts as a member, and from when to when, is kept in a **private Google Sheet**, not in the repo: start and end
dates are personal data. Setup once:

1. `python -m pubpulse members-template` writes `members-template.csv` (names, roles, empty start/end columns; gitignored).
2. Create a Google Sheet, *File → Import* that CSV. Fill `start` and `end` (YYYY-MM-DD, YYYY-MM or YYYY; leave end
   empty for current members). Add rows for members who are not on the staff page.
3. *Share → Anyone with the link → Viewer*. Build the CSV link: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv`.
4. GitHub → Settings → Secrets: `MEMBERS_SHEET_CSV_URL` = that link. Locally, put it in `.env`.

Every run reads the sheet in memory. The **team-window rule**: a paper counts when a group member was in the team at
publication time, no affiliation check.
"In the team" means current staff on the staff page, or inside the start/end period given in the sheet (the sheet is
the exception list: only people whose period differs from "current staff = all of it" need a row). Outside the team
(former staff, papers before a start date or after an end date plus the grace period) a paper counts only with a
verified group affiliation. People matched by name only (no ORCID) also need a verified affiliation, because their
identity is uncertain. A paper you do not want counted is one line in overrides.yml (`reject`). The website, digest
and LinkedIn drafts use "counted"; "verified affiliation only" remains as a stricter filter. Dates never appear in
people.yml, the published data or the site.

### How a run works

```
staff page ──► 0. people   scrape staff page → merge into people.yml (new/left people, ORCIDs, roles)
               1. sync     OpenAlex works per person since `since_year`; one record per paper even with several group
                           authors; affiliation check per group author; diff against data/publications.json
               2. commit   people.yml + data/ (publications.json, runs.json, feed.xml)
               3. deploy   dist/ → GitHub Pages
               4. notify   if new papers: email (Gmail SMTP) + Teams card
```

The very first run is a *baseline*: everything is recorded, nothing is announced. From then on only papers that were
not in `data/publications.json` before count as new, no matter their publication date (late indexing is common).

### Run locally

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python -m pubpulse sync --dry-run     # writes out/publications.json, out/people.yml; touches nothing else
python -m pubpulse sync               # updates people.yml and data/
python -m pubpulse build              # dist/ (site), data/feed.xml, out/digest.html, out/teams.json
python -m http.server -d dist 8000    # open http://localhost:8000
pytest
```

### Why OpenAlex and not ORCID or Google Scholar

ORCID records are only as complete as each person keeps them; OpenAlex merges Crossref, PubMed, ORCID, arXiv/medRxiv
and more, and is queried *by* ORCID, so ORCID stays the identity key. Google Scholar has no API and forbids automated
access. OpenAlex is free, needs no key and its data is CC0.
