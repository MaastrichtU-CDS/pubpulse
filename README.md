# pubpulse

Weekly overview of publications by the **Clinical Data Science** group (Maastro / Maastricht University).

- **Website with filters:** https://maastrichtu-cds.github.io/pubpulse/
- **RSS feed:** https://maastrichtu-cds.github.io/pubpulse/feed.xml
- **Weekly digest:** every Monday morning by email and in Teams, only when there is something new.

Every Monday a small robot reads the [staff page](https://www.clinicaldatascience.nl/staff), looks up every current
staff member in [OpenAlex](https://openalex.org) (a free, open catalogue that merges Crossref, PubMed, ORCID and
preprint servers), stores the publications it finds here, refreshes the website and sends the digest.

## For group members (no technical knowledge needed)

**I am not on the list / my papers are missing.**
Make sure your profile on the staff page links to your ORCID. The robot picks that up automatically the next Monday.
If you have no ORCID, it tries to find you in OpenAlex by name, but only accepts a match that is affiliated with
Maastricht/Maastro. People it cannot match are listed in a yellow "Needs attention" box on the website and in the digest.

**A paper is marked "unverified".**
OpenAlex did not record a Maastricht/Maastro/MUMC+ affiliation for you on that paper. The paper is still shown, just
marked. Usually this means the publisher did not send affiliations to Crossref. Nothing to do unless it is not your paper.

**How papers are attributed (and why some are marked).**
- People with an ORCID: OpenAlex is queried by ORCID. If OpenAlex attached that ORCID to several author records
  (it sometimes merges namesakes), the record whose current institution is in Maastricht wins.
- People without an ORCID: matched by exact name *and* a Maastricht/Maastro affiliation on the OpenAlex record. For
  them a paper only counts when the paper itself carries a verified group affiliation for that author.
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
The digest goes to one group address. Ask a maintainer to change the `DIGEST_TO` secret. You can also subscribe to the
RSS feed in Outlook: right-click *RSS Feeds* → *Add a New RSS Feed* → paste the feed link above.

**Refresh now instead of waiting for Monday.**
Go to [Actions → weekly](https://github.com/MaastrichtU-CDS/pubpulse/actions/workflows/weekly.yml) → *Run workflow*.

## For maintainers

### Files you may edit

| File | What |
| --- | --- |
| `config.yml` | group name, site URL, `since_year`, `track_sections` (`current`, add `previous` for former staff), institution keywords, `affiliation_policy` (`flag` or `require`) |
| `overrides.yml` | manual decisions per paper: `confirm:` / `reject:` lists of OpenAlex ids |
| `people.yml` | refreshed from the staff page on every run. Hand-edited fields that are never overwritten: `openalex_id` (one id, or a list when OpenAlex split a person into several records), `orcid` (when the staff page has none), `exclude: true`, `notes`. To track someone who is not on the staff page, add an entry with `source: manual`. People who disappear from the page are kept with an `active_until` date so their papers stay on the site. |

Edit either file in the GitHub web editor and commit to `main`; the workflow runs automatically on that commit.

### Secrets (Settings → Secrets and variables → Actions)

| Secret | Purpose |
| --- | --- |
| `OPENALEX_API_KEY` | free key from https://openalex.org/settings/api. Strongly recommended: without it OpenAlex shares one small daily budget per IP address (GitHub's runners share addresses) |
| `GMAIL_USER` | Gmail address the digest is sent from |
| `GMAIL_APP_PASSWORD` | a Gmail [app password](https://myaccount.google.com/apppasswords) (needs 2-step verification on that account) |
| `DIGEST_TO` | recipient(s), comma separated (a group distribution list works well) |
| `TEAMS_WEBHOOK_URL` | URL from a Teams *Workflows* flow "Post to a channel when a webhook request is received" |

A notification channel whose secret is missing is simply skipped; the site and feed always update.

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
