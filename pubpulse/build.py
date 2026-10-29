"""Build the static site bundle (dist/), the Atom feed and the weekly digest (email + Teams card)."""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from .groups import role_group, role_groups, role_title
from .social import CHAT_PROMPT
from .sync import DATA_DIR, NOTIFIED_PATH, OUT_DIR, ROOT, load_config, load_pending, load_publications

SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"
site_url_for_draft = "https://maastrichtu-cds.github.io/pubpulse/"


def work_link(w: dict) -> str:
    return w.get("doi") or w.get("landing_url") or w.get("openalex_url")


def new_works(pubs: dict, pending_ids: list[str] | None = None) -> list[dict]:
    """Works to announce: this run's new ids plus anything still pending from earlier runs."""
    last = pubs.get("last_run") or {}
    if last.get("baseline"):
        return []
    ids = set(last.get("new_ids") or []) | set(pending_ids or [])
    return [w for w in pubs.get("works", []) if w["id"] in ids]


def people_names(pubs: dict) -> dict[str, str]:
    return {p["slug"]: p["name"] for p in pubs.get("people", [])}


# ---------------------------------------------------------------------------------------------- feed

def build_feed(pubs: dict, cfg: dict, max_items: int = 50) -> str:
    names = people_names(pubs)
    site = cfg.get("site_url", "")
    works = sorted(pubs.get("works", []), key=lambda w: (w.get("first_seen", ""), w.get("publication_date") or ""), reverse=True)
    updated = pubs.get("generated") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"<title>{escape(cfg.get('group_name', 'pubpulse'))} — new publications</title>",
        f'<link href="{escape(site)}"/>',
        f'<link rel="self" href="{escape(site)}feed.xml"/>',
        f"<id>{escape(site)}</id>",
        f"<updated>{escape(updated)}</updated>",
    ]
    for w in works[:max_items]:
        members = ", ".join(names.get(s, s) for s in w.get("group_members", []))
        summary = f"{w.get('journal') or ''} · {w.get('publication_date') or ''} · group authors: {members}"
        if w.get("abstract"):
            summary += "\n\n" + w["abstract"]
        parts += [
            "<entry>",
            f"<title>{escape(w['title'])}</title>",
            f'<link href="{escape(work_link(w))}"/>',
            f"<id>{escape(w['openalex_url'])}</id>",
            f"<updated>{escape(w.get('first_seen', ''))}T00:00:00Z</updated>",
            f"<summary>{escape(summary)}</summary>",
            "</entry>",
        ]
    parts.append("</feed>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------------------------- digest

def _draft_for(w: dict) -> dict | None:
    p = DATA_DIR / "social" / f"{w['id']}.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def scholar_summary() -> dict | None:
    path = DATA_DIR / "scholar_check.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        r = json.load(f)
    if not (r.get("total_missing") or r.get("total_not_attributed")):
        return None
    return {"checked_at": r.get("checked_at", ""), "missing": r.get("total_missing", 0), "not_attributed": r.get("total_not_attributed", 0)}


def recent_cutoff(recent_days: int, today: str | None = None) -> str:
    from datetime import date, timedelta
    today_d = date.fromisoformat(today) if today else date.today()
    return (today_d - timedelta(days=recent_days)).isoformat()


def split_recent(items: list[dict], recent_days: int, today: str | None = None) -> tuple[list[dict], list[dict]]:
    """News = published within recent_days; the rest are older papers that only now got linked to a group member
    (newly identified person, late indexing). Those are not news and stay out of the newsletter."""
    cutoff = recent_cutoff(recent_days, today)
    recent = [w for w in items if (w.get("publication_date") or "") >= cutoff]
    older = [w for w in items if (w.get("publication_date") or "") < cutoff]
    return recent, older


# Newsletter look: the site's palette, email-safe markup (tables, inline styles, absolute image URLs).
NAVY, ACCENT, MUTED, LINE = "#001c3d", "#0e71bb", "#607087", "#dfe5ec"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
TYPE_PILLS = {"article": ("#e3eefb", "#1b4f91"), "review": ("#fde9df", "#8a3a16"), "preprint": ("#dff5ec", "#0f6a49"),
              "conference-paper": ("#fff1d1", "#7a5400"), "conference-abstract": ("#fff1d1", "#7a5400")}


def _summary(w: dict, draft: dict | None) -> str:
    """The draft's short version when it has no open [check] marks, else the opening of the abstract."""
    if draft and draft.get("short") and "[check" not in draft["short"]:
        return re.sub(r"\s*https?://\S+", "", draft["short"]).strip()
    label = r"(background|introduction|purpose|objectives?|aims?|context|rationale)"
    text = re.sub(rf"^\s*(abstract\s*[:.]?\s*)?({label}(\s*(&|and)\s*{label})?\s*[:.]?\s+)?", "", w.get("abstract") or "", flags=re.I)
    if not text:
        return ""
    out = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if out and len(out) + len(sentence) > 280:
            break
        out = f"{out} {sentence}".strip()
    return out if len(out) <= 320 else out[:300].rsplit(" ", 1)[0] + " …"


def _published(day: str | None) -> str:
    from datetime import date
    try:
        return "published " + date.fromisoformat(day or "").strftime("%-d %B %Y")
    except ValueError:
        return ""


def _button(href: str, label: str, dark: bool = False) -> str:
    bg, fg, border = (NAVY, "#ffffff", NAVY) if dark else ("#ffffff", NAVY, "#c4d4e4")
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="display:inline-table;vertical-align:middle;margin:0 12px 8px 0">'
            f'<tr><td bgcolor="{bg}" style="padding:11px 16px;background:{bg};border:1px solid {border};border-radius:5px">'
            f'<a href="{html.escape(href)}" style="display:block;color:{fg};font:600 13px/18px {SANS};text-decoration:none">'
            f'{html.escape(label)}</a></td></tr></table>')


def _item_html(w: dict, names: dict[str, str], site: str) -> str:
    d = _draft_for(w)
    headline = (d or {}).get("headline") or ""
    members = ", ".join(html.escape(names.get(s, s)) for s in w.get("group_members", []))
    bg, fg = TYPE_PILLS.get(w.get("type") or "", ("#fbe4ee", "#8a2a55"))
    pill = (f'<span style="background:{bg};color:{fg};border-radius:4px;padding:2px 7px;font:600 11px/1.6 {SANS};'
            f'text-transform:uppercase;letter-spacing:.4px">{html.escape((w.get("type") or "paper").replace("-", " "))}</span>')
    oa = (f' <span style="background:#eaf3e5;color:#27623d;border-radius:4px;padding:2px 7px;font:600 11px/1.6 {SANS};'
          'text-transform:uppercase;letter-spacing:.4px">open access</span>') if w.get("is_oa") else ""
    meta = " · ".join(html.escape(x) for x in (w.get("journal"), _published(w.get("publication_date"))) if x)
    card = ""
    if d and d.get("card"):
        card = (f'<p style="margin:0 0 18px"><a href="{html.escape(work_link(w))}"><img src="{html.escape(site + d["card"])}" width="568" alt="{html.escape(headline or w["title"])}" '
                f'style="display:block;width:100%;max-width:568px;height:auto;border:0;border-radius:6px;color:{NAVY};font:14px/20px {SANS}"></a></p>')
    buttons = _button(work_link(w), "Read the paper →", dark=True)
    secondary = []
    if w.get("oa_url"):
        secondary.append(f'<a href="{html.escape(w["oa_url"])}" style="display:inline-block;margin:0 14px 8px 0;color:{ACCENT};font:600 13px/20px {SANS};text-decoration:underline">Full text</a>')
    if d and d.get("post"):
        secondary.append(f'<a href="{html.escape(site)}social.html?id={html.escape(w["id"])}" style="display:inline-block;margin:0 0 8px;color:{ACCENT};font:600 13px/20px {SANS};text-decoration:underline">LinkedIn post</a>')
    title_block = (
        f'<h2 style="margin:12px 0 8px;font:600 22px/29px {SANS};letter-spacing:-.4px;color:{NAVY}"><a href="{html.escape(work_link(w))}" style="color:{NAVY};text-decoration:none">{html.escape(headline)}</a></h2>'
        f'<p style="margin:0 0 10px;font:14px/21px {SANS};color:{MUTED}">{html.escape(w["title"])}</p>'
        if headline else
        f'<h2 style="margin:12px 0 10px;font:600 22px/29px {SANS};letter-spacing:-.4px;color:{NAVY}"><a href="{html.escape(work_link(w))}" style="color:{NAVY};text-decoration:none">{html.escape(w["title"])}</a></h2>'
    )
    summary = _summary(w, d)
    return (
        f'<tr><td class="email-pad email-paper" style="padding:28px 36px 24px;border-top:1px solid {LINE};overflow-wrap:anywhere">'
        f'<p style="margin:0;line-height:22px">{pill}{oa}</p>{title_block}'
        f'<p style="margin:0 0 18px;font:12px/19px {SANS};color:{MUTED}">{meta}</p>{card}'
        + (f'<p style="margin:0 0 14px;font:15px/24px {SANS};color:#213449">{html.escape(summary)}</p>' if summary else "")
        + f'<p style="margin:0 0 18px;font:13px/21px {SANS};color:{MUTED}">From the group: <b style="color:#213449">{members}</b></p>'
        f'<div>{buttons}<span style="display:inline-block;vertical-align:middle">{"".join(secondary)}</span></div></td></tr>'
    )


def build_digest(pubs: dict, cfg: dict, pending_ids: list[str] | None = None, issue_date: str | None = None, test_note: str | None = None) -> dict:
    """Newsletter (subject, html, text, Teams card) for the works not announced yet. Only papers published within
    digest.recent_days are news; older papers that only now got linked to a member are left out."""
    from datetime import date
    names = people_names(pubs)
    last = pubs.get("last_run") or {}
    dg = cfg.get("digest") or {}
    all_items = sorted(new_works(pubs, pending_ids), key=lambda w: w.get("publication_date") or "", reverse=True)
    recent, _older = split_recent(all_items, int(dg.get("recent_days", 120)), last.get("date"))
    # The newsletter follows the team-window rule: only counted papers are listed.
    counted = lambda w: bool(w.get("counted", w.get("verified", True)))  # noqa: E731
    skip_types = set(dg.get("exclude_types", ["dataset"]))  # data deposits are not news; they stay on the website
    recent = [w for w in recent if w.get("type") not in skip_types]
    items = [w for w in recent if counted(w)]
    # Papers with a LinkedIn draft (headline and card) lead the issue.
    items.sort(key=lambda w: _draft_for(w) is None)
    site = cfg.get("site_url", "")
    group = cfg.get("group_name", "the group")
    prefix = dg.get("subject_prefix", "pubpulse")
    n = len(items)
    lead = ((_draft_for(items[0]) or {}).get("headline") or items[0]["title"]) if items else ""
    lead = lead if len(lead) <= 70 else lead[:67].rsplit(" ", 1)[0] + "…"
    # "New" = found since the previous newsletter (OpenAlex indexes with a delay), not published this week.
    subject = f"{prefix}: {n} new publication{'s' if n != 1 else ''}" + (f" · {lead}" if lead else "")
    try:
        day = date.fromisoformat(issue_date or last.get("date") or "")
    except ValueError:
        day = date.today()
    issue = f"Week {day.isocalendar()[1]} · {day.strftime('%A %-d %B %Y')}"

    per_person: dict[str, int] = {}
    for w in items:
        for s in w.get("group_members", []):
            per_person[s] = per_person.get(s, 0) + 1
    person_line = ", ".join(f"{names.get(s, s)}" + (f" ({c})" if c > 1 else "") for s, c in sorted(per_person.items(), key=lambda x: (-x[1], names.get(x[0], x[0]))))
    review = last.get("needs_review", [])
    errors = last.get("errors") or []
    sc = scholar_summary()

    notes = []
    if sc:
        parts = [f'{sc["missing"]} paper{"s" if sc["missing"] != 1 else ""} on Google Scholar profiles {"are" if sc["missing"] != 1 else "is"} not in pubpulse' if sc["missing"] else "",
                 f'{sc["not_attributed"]} {"are" if sc["not_attributed"] != 1 else "is"} in pubpulse but not linked to the person' if sc["not_attributed"] else ""]
        notes.append(f'Monthly Google Scholar check ({html.escape(sc["checked_at"])}): ' + " and ".join(x for x in parts if x)
                     + f'. <a href="{html.escape(site)}#scholar" style="color:{ACCENT}">Details</a>.')
    if review:
        notes.append(f'{len(review)} staff profile{"s have" if len(review) != 1 else " has"} no confirmed author match yet, so their papers may be missing. '
                     f'<a href="{html.escape(site)}#coverage-notes" style="color:{ACCENT}">Who and why</a>.')
    if errors:
        notes.append('<span style="color:#a00">Errors during this run: ' + html.escape("; ".join(errors)) + "</span>")

    banner = (f'<tr><td class="email-pad" style="background:#fff4dd;padding:14px 36px;font:600 13px/20px {SANS};color:#805615">{html.escape(test_note)}</td></tr>'
              if test_note else "")
    body = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">'
        f'<title>{html.escape(subject)}</title>'
        '<!--[if mso]><noscript><xml><o:OfficeDocumentSettings xmlns:o="urn:schemas-microsoft-com:office:office">'
        '<o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->'
        '<style>.email-shell {border-collapse:separate;} '
        '@media only screen and (max-width:600px) {'
        '.email-canvas {padding:12px 8px!important;} .email-pad {padding-left:20px!important;padding-right:20px!important;} '
        '.email-title {font-size:26px!important;line-height:32px!important;} '
        '.email-cds {width:104px!important;height:auto!important;} '
        '.email-partners {padding-left:16px!important;padding-right:16px!important;} '
        '.email-partners img {max-width:100%!important;height:auto!important;} '
        '}</style></head>'
        f'<body style="margin:0;padding:0;background:#eef2f7;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%">'
        f'<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all" aria-hidden="true">{html.escape(subject)}</div>'
        '<div class="email-canvas" style="background:#eef2f7;padding:28px 12px;margin:0">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td align="center">',
        '<!--[if mso]><table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->',
        '<table class="email-shell" role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:640px;table-layout:fixed;background:#ffffff;border-spacing:0;text-align:left">',
        f'<tr><td class="email-pad" bgcolor="{NAVY}" style="background:{NAVY};padding:28px 36px 30px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout:fixed"><tr>'
        f'<td width="140" valign="middle"><a href="{html.escape(site)}"><img class="email-cds" src="{html.escape(site)}assets/cds-email.png" width="128" height="64" alt="Clinical Data Science" style="display:block;width:128px;height:64px;border:0;color:#ffffff;font:12px/18px {SANS}"></a></td>'
        f'<td align="right" valign="middle"><p style="margin:0;color:#ffffff;font:600 13px/21px {SANS}">pubpulse newsletter</p>'
        f'<p style="margin:3px 0 0;color:#b7cce0;font:12px/19px {SANS}">Week {day.isocalendar()[1]}<br>{html.escape(day.strftime("%-d %B %Y"))}</p></td></tr></table>'
        f'<h1 class="email-title" style="margin:28px 0 8px;color:#ffffff;font:600 30px/37px {SANS};letter-spacing:-.7px">New from<br>Clinical Data Science</h1>'
        f'<p style="margin:0;color:#b7cce0;font:14px/22px {SANS}">Research from our team, in one place.</p></td></tr>' + banner,
        f'<tr><td class="email-pad" style="padding:28px 36px;font:15px/24px {SANS};color:#213449">'
        + (f'<p style="margin:0 0 10px;color:{NAVY};font:600 19px/27px {SANS}">{n} new paper{"s" if n != 1 else ""} since the last newsletter.</p>'
           f'<p style="margin:0 0 12px;font:14px/22px {SANS}">With {html.escape(person_line)}.</p>'
           f'<p style="margin:0;color:{MUTED};font:13px/21px {SANS}">Papers can take weeks to reach OpenAlex, our source, so some were published a while ago.</p>' if n else
           f'<p style="margin:0 0 8px;color:{NAVY};font:600 19px/27px {SANS}">Nothing new since the last newsletter.</p>'
           f'<p style="margin:0;color:{MUTED};font:14px/22px {SANS}">The next issue will appear when new publications are ready to share.</p>')
        + "</td></tr>",
        "".join(_item_html(w, names, site) for w in items),
        f'<tr><td class="email-pad" bgcolor="#f5f8fb" style="padding:24px 36px 18px;background:#f5f8fb;border-top:1px solid {LINE}">'
        f'<p style="margin:0 0 6px;color:{NAVY};font:600 16px/24px {SANS}">Explore the full collection</p>'
        f'<p style="margin:0 0 16px;color:{MUTED};font:14px/22px {SANS}">Find more research, people and topics in pubpulse.</p>'
        f'{_button(site, "Browse all publications")}<a href="{html.escape(site)}digest.html" style="display:inline-block;margin:0 0 8px;color:{ACCENT};font:600 13px/20px {SANS}">View in your browser →</a></td></tr>',
    ]
    if notes:
        body.append(f'<tr><td class="email-pad" style="padding:22px 36px;font:12px/20px {SANS};color:{MUTED}">'
                    f'<p style="margin:0 0 8px;color:#213449;font:600 13px/20px {SANS}">Collection notes</p>'
                    + "".join(f'<p style="margin:6px 0;font:12px/20px {SANS}">{x}</p>' for x in notes) + "</td></tr>")
    body.append(
        f'<tr><td class="email-partners" bgcolor="{NAVY}" style="background:{NAVY};padding:22px 36px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout:fixed"><tr>'
        f'<td width="40%" valign="middle" style="padding-right:16px"><a href="https://www.maastrichtuniversity.nl/"><img src="{html.escape(site)}assets/maastricht-university-email.png" width="154" height="24" alt="Maastricht University" style="display:block;width:154px;max-width:100%;height:auto;border:0;color:#ffffff;font:10px/14px {SANS}"></a></td>'
        f'<td width="25%" align="center" valign="middle" style="padding:0 12px"><a href="https://www.maastro.nl/"><img src="{html.escape(site)}assets/maastro-email.png" width="86" height="18" alt="Maastro" style="display:block;width:86px;max-width:100%;height:auto;border:0;color:#ffffff;font:10px/14px {SANS}"></a></td>'
        f'<td width="35%" align="right" valign="middle" style="padding-left:16px"><a href="https://www.mumc.nl/"><img src="{html.escape(site)}assets/maastricht-umc-email.png" width="136" height="25" alt="Maastricht UMC+" style="display:block;width:136px;max-width:100%;height:auto;border:0;color:#ffffff;font:10px/14px {SANS}"></a></td>'
        '</tr></table></td></tr>'
        f'<tr><td class="email-pad" style="background:#f5f7fa;padding:22px 36px;font:12px/20px {SANS};color:{MUTED}">'
        f'<p style="margin:0 0 10px;font:12px/20px {SANS}">Sent by pubpulse to {html.escape(dg.get("list_name") or "the group list")} on Mondays when there is something new.</p>'
        f'<p style="margin:0 0 14px;font:12px/20px {SANS}">Automated overview, not manually verified: papers are matched by simple rules and mistakes are expected. Data: OpenAlex.</p>'
        f'<p style="margin:0;font:12px/20px {SANS}"><a href="{{{{UNSUBSCRIBE_URL}}}}" style="color:#445d78">Unsubscribe</a> &nbsp;·&nbsp; <a href="{html.escape(site)}#subscribe" style="color:#445d78">Subscribe</a> &nbsp;·&nbsp; '
        f'<a href="{html.escape(site)}feed.xml" style="color:#445d78">RSS</a></p></td></tr>'
        '</table><!--[if mso]></td></tr></table><![endif]--></td></tr></table></div></body></html>'
    )
    html_body = "\n".join(body)

    text_lines = [f"THE PUBPULSE NEWSLETTER · {issue}"] + ([test_note] if test_note else []) + [
        f"{group}: {n} new paper(s) since the last newsletter" + (f", with {person_line}" if n else ""), ""]
    for i, w in enumerate(items, 1):
        d = _draft_for(w)
        members = ", ".join(names.get(s, s) for s in w.get("group_members", []))
        flag = "" if w.get("counted", w.get("verified", True)) else "  [not in the group totals]"
        text_lines += [f"{i}. {(d or {}).get('headline') or w['title']}"]
        if (d or {}).get("headline"):
            text_lines.append(f"   {w['title']}")
        text_lines += [f"   {w.get('journal') or ''} · {_published(w.get('publication_date'))}", f"   From the group: {members}{flag}"]
        if summary := _summary(w, d):
            text_lines.append(f"   {summary}")
        text_lines += [f"   {work_link(w)}", ""]
    text_lines += [f"All publications: {site}", f"Newsletter on the web: {site}digest.html"]
    if review:
        text_lines += ["", f"{len(review)} staff profiles without a confirmed author match: {site}#coverage-notes"]
    text_lines += ["", "Unsubscribe: {{UNSUBSCRIBE_URL}}"]

    teams_max = int(dg.get("teams_max_items", 10))
    card_body = [
        {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": f"📚 {n} new publication{'s' if n != 1 else ''} since the last newsletter", "wrap": True},
        {"type": "TextBlock", "text": html.escape(group), "isSubtle": True, "wrap": True},
    ]
    for w in items[:teams_max]:
        members = ", ".join(names.get(s, s) for s in w.get("group_members", []))
        headline = (_draft_for(w) or {}).get("headline")
        card_body.append(
            {"type": "TextBlock", "wrap": True, "spacing": "Medium",
             "text": (f"**{headline}**  \n" if headline else "")
                     + f"[{w['title']}]({work_link(w)})  \n{w.get('journal') or ''} · {w.get('publication_date') or ''}  \n_{members}_"
                     + ("" if w.get("counted", w.get("verified", True)) else "  ⚠ not in the group totals")}
        )
    if n > teams_max:
        card_body.append({"type": "TextBlock", "text": f"… and {n - teams_max} more on the website.", "isSubtle": True, "wrap": True})
    teams = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": card_body,
                "actions": [{"type": "Action.OpenUrl", "title": "Read the newsletter", "url": site + "digest.html"},
                            {"type": "Action.OpenUrl", "title": "Open pubpulse", "url": site}],
            },
        }],
    }
    return {"subject": subject, "html": html_body, "text": "\n".join(text_lines), "teams": teams, "new_count": n, "pending_count": len(all_items)}


# ---------------------------------------------------------------------------------------------- newsletter page

DIGESTS_DIR = DATA_DIR / "digests"


def next_monday(generated: str | None) -> str:
    """The Monday the queued issue goes out: today when built on a Monday (the send run), else the coming one."""
    from datetime import date, timedelta
    try:
        d = date.fromisoformat((generated or "")[:10])
    except ValueError:
        d = date.today()
    return (d + timedelta(days=(7 - d.weekday()) % 7)).isoformat()


def archive_digest(html_body: str, day: str, digests_dir: Path | None = None) -> Path:
    """Keep a copy of a newsletter that was actually sent (called after a successful send)."""
    folder = digests_dir or DIGESTS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day}.html"
    path.write_text(html_body.replace("{{UNSUBSCRIBE_URL}}", "#"), encoding="utf-8")
    return path


def _long_date(day: str) -> str:
    from datetime import date
    try:
        return date.fromisoformat(day).strftime("%A %-d %B %Y")
    except ValueError:
        return day


def _digest_preview(body: str, site: str, prefix: str) -> tuple[str, str]:
    """Embed complete emails and older archived fragments in the same web shell."""
    match = re.search(r"<body\b[^>]*>(.*?)</body\s*>", body, flags=re.I | re.S)
    styles = "".join(re.findall(r"<style\b[^>]*>.*?</style\s*>", body[:match.start()], flags=re.I | re.S)) if match else ""
    content = match.group(1) if match else body
    home = prefix or "./"
    content = content.replace("{{UNSUBSCRIBE_URL}}", home + "#unsubscribe")
    content = re.sub(r"(href=[\"'])#([\"'])", rf"\g<1>{home}#unsubscribe\2", content)
    # Keep the web preview on this deployment, including unpublished local assets.
    if site:
        for attr in ("href", "src"):
            for quote in ('"', "'"):
                content = content.replace(f"{attr}={quote}{html.escape(site)}", f"{attr}={quote}{home}")
    return styles, content


def build_version(repo_url: str = "") -> str:
    """Footer line with the code commit and build time, so a visitor can tell whether the page is the latest deploy."""
    import os
    import subprocess

    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sha = os.environ.get("GITHUB_SHA", "")
    try:
        from zoneinfo import ZoneInfo
        built = datetime.now(ZoneInfo("Europe/Amsterdam"))
    except Exception:  # no tz database: fall back to UTC
        built = datetime.now(timezone.utc)
    when = f"{built.day} {built:%b %Y, %H:%M} {built.tzname()}"
    if not sha:
        return f'<p class="build-version">Built {when}</p>'
    label = html.escape(sha[:7])
    commit = f'<a href="{html.escape(repo_url.rstrip("/"))}/commit/{html.escape(sha)}">{label}</a>' if repo_url else label
    return f'<p class="build-version">Version {commit} · built {when}</p>'


def digest_page(heading: str, status: str, body: str, archive: list[str], site: str, prefix: str = "", version: str = "") -> str:
    import hashlib

    def asset(name: str) -> str:
        path = SITE_DIR / name
        version = "?v=" + hashlib.sha1(path.read_bytes()).hexdigest()[:10] if path.exists() else ""
        return prefix + name + version

    email_styles, preview = _digest_preview(body, site, prefix)
    issues = "".join(
        f'<a class="digest-issue" href="{prefix}digests/{d}.html"><span>Week {__import__("datetime").date.fromisoformat(d).isocalendar()[1]}</span>{html.escape(_long_date(d))}<span aria-hidden="true">→</span></a>'
        for d in archive)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#001c3d">
<title>{html.escape(heading)} · pubpulse</title>
<link rel="icon" type="image/svg+xml" href="{prefix}assets/cds-icon.svg?v=cds-3">
<link rel="icon" href="{prefix}favicon.ico?v=cds-3">
<link rel="stylesheet" href="{asset('style.css')}">
{email_styles}<link rel="stylesheet" href="{asset('digest.css')}"></head>
<body class="digest-page">
<a class="skip-link" href="#newsletter">Skip to newsletter</a>
<header class="top"><div class="wrap nav">
<a class="brand" href="{prefix}./" aria-label="pubpulse home"><img src="{prefix}assets/cds-icon.svg?v=cds-3" width="36" height="36" alt=""><span>pub<span class="brand-light">pulse</span><small>RESEARCH UPDATES</small></span></a>
<nav aria-label="Main navigation"><a href="{prefix}./#publications">Publications</a><a href="{prefix}./#stats">Statistics</a><a href="{prefix}social.html">Social posts</a><a class="button button-small" href="{prefix}digest.html" aria-current="page">Newsletter <span aria-hidden="true">→</span></a></nav>
</div></header>
<section class="digest-hero"><div class="wrap digest-hero-inner"><div>
<p class="eyebrow">THE PUBPULSE NEWSLETTER</p><h1>{html.escape(heading)}</h1><p class="digest-status">{status}</p></div>
<div class="digest-actions"><a class="button button-dark" href="{prefix}./#subscribe">Get the newsletter <span aria-hidden="true">→</span></a><a href="{prefix}./#publications">Browse all publications</a></div>
</div></section>
<main class="digest-content" id="newsletter">
<div class="digest-preview-heading"><h2>Newsletter preview</h2><p>Weekly research updates</p></div>
<div class="digest-preview">{preview}</div>
{f'<section class="digest-past"><h2>Past issues</h2><div class="digest-issues">{issues}</div></section>' if archive else ''}
</main>
<footer class="digest-footer">Clinical Data Science <span aria-hidden="true">·</span> Maastro, Maastricht University &amp; Maastricht UMC+{version}</footer>
</body></html>
"""


def write_digest_pages(pubs: dict, cfg: dict, pending: list[str], dist: Path, digests_dir: Path | None = None,
                       version: str = "") -> None:
    """dist/digest.html = the current issue: the one queued for the coming Monday, or the last one sent when nothing is
    queued yet. dist/digests/<date>.html = every issue that was sent."""
    folder = digests_dir or DIGESTS_DIR
    site = cfg.get("site_url", "")
    monday = next_monday(pubs.get("generated"))
    queued = build_digest({**pubs, "last_run": {**(pubs.get("last_run") or {}), "new_ids": []}}, cfg, pending, issue_date=monday)
    archive = sorted((p.stem for p in folder.glob("*.html")), reverse=True) if folder.exists() else []
    if queued["new_count"] or not archive:
        heading = "This week's newsletter" if queued["new_count"] else "The next newsletter"
        status = (f"Preview of the issue for <b>{html.escape(_long_date(monday))}</b>. Papers that turn up before then are added; "
                  "nothing is sent when there is nothing new." if queued["new_count"] else
                  f"Nothing queued yet for <b>{html.escape(_long_date(monday))}</b>. New papers appear here as they are found (every weekday).")
        body = queued["html"]
    else:
        heading = "This week's newsletter"
        status = (f"Sent <b>{html.escape(_long_date(archive[0]))}</b>. Nothing new queued yet for {html.escape(_long_date(monday))}; "
                  "new papers appear here as they are found (every weekday).")
        body = (folder / f"{archive[0]}.html").read_text(encoding="utf-8")
    (dist / "digest.html").write_text(digest_page(heading, status, body, archive, site, version=version), encoding="utf-8")
    if archive:
        (dist / "digests").mkdir(exist_ok=True)
        for day in archive:
            page = digest_page(f"Issue of {_long_date(day)}", f"Sent {html.escape(_long_date(day))}.",
                               (folder / f"{day}.html").read_text(encoding="utf-8"), [d for d in archive if d != day], site, prefix="../", version=version)
            (dist / "digests" / f"{day}.html").write_text(page.replace('href="../digests/', 'href="'), encoding="utf-8")


# ---------------------------------------------------------------------------------------------- run

def run(config_path: Path | None = None) -> dict:
    global site_url_for_draft
    cfg = load_config(config_path) if config_path else load_config()
    site_url_for_draft = cfg.get("site_url") or site_url_for_draft
    pubs = load_publications()
    OUT_DIR.mkdir(exist_ok=True)

    feed = build_feed(pubs, cfg, max_items=int((cfg.get("feed") or {}).get("max_items", 50)))
    (DATA_DIR / "feed.xml").write_text(feed, encoding="utf-8")

    digest = build_digest(pubs, cfg, load_pending() if NOTIFIED_PATH.exists() else None)
    (OUT_DIR / "digest.html").write_text(digest["html"], encoding="utf-8")
    (OUT_DIR / "digest.txt").write_text(digest["text"], encoding="utf-8")
    (OUT_DIR / "subject.txt").write_text(digest["subject"], encoding="utf-8")
    (OUT_DIR / "teams.json").write_text(json.dumps(digest["teams"], ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "new_count.txt").write_text(str(digest["new_count"]), encoding="utf-8")
    (OUT_DIR / "pending_count.txt").write_text(str(digest.get("pending_count", digest["new_count"])), encoding="utf-8")

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    shutil.copytree(SITE_DIR, DIST_DIR)
    (DIST_DIR / "data").mkdir()
    # Mailing-list settings may change between syncs; publish the current configuration.
    site_pubs = {
        **pubs,
        "list": {k: (cfg.get("digest") or {}).get(k) or "" for k in ("subscribe_endpoint", "subscribe_form_url", "list_name")},
        "site": cfg.get("site") or {},
        "pending_ids": load_pending() if NOTIFIED_PATH.exists() else [],
        "recent_days": int((cfg.get("digest") or {}).get("recent_days", 120)),
        "social_prompt": CHAT_PROMPT,
        "groups": role_groups(pubs.get("people", [])),
        # Staff-page roles normalised for display and grouping (the raw role stays in people.yml).
        "people": [{**p, "role_title": role_title(p.get("role")), "role_group": role_group(p.get("role"))} for p in pubs.get("people", [])],
    }
    (DIST_DIR / "data" / "publications.json").write_text(
        json.dumps(site_pubs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy(DATA_DIR / "feed.xml", DIST_DIR / "feed.xml")
    from .export import write_csv, write_xlsx
    write_xlsx(pubs, cfg, DIST_DIR / "data" / "pubpulse-publications.xlsx")
    write_csv(pubs, DIST_DIR / "data" / "pubpulse-publications.csv")
    if (DATA_DIR / "social" / "index.json").exists():
        (DIST_DIR / "data" / "social").mkdir(exist_ok=True)
        shutil.copy(DATA_DIR / "social" / "index.json", DIST_DIR / "data" / "social" / "index.json")
        if (DATA_DIR / "social" / "images").exists():
            shutil.copytree(DATA_DIR / "social" / "images", DIST_DIR / "data" / "social" / "images")
    # Cache-busting: browsers and GitHub Pages cache app.js/style.css for a while; a content hash in the URL
    # makes every deploy pick up the new files immediately.
    import hashlib
    version = build_version(cfg.get("repo_url") or "")
    for page in ("index.html", "social.html"):
        path = DIST_DIR / page
        if not path.exists():
            continue
        html_text = path.read_text(encoding="utf-8").replace("<!-- build-version -->", version)
        for asset in ("app.js", "style.css", "library.css", "studio.css", "social-editor.js", "social.js"):
            if (DIST_DIR / asset).exists():
                digest_hex = hashlib.sha1((DIST_DIR / asset).read_bytes()).hexdigest()[:10]
                html_text = html_text.replace(f'"{asset}"', f'"{asset}?v={digest_hex}"')
        path.write_text(html_text, encoding="utf-8")
    if (DATA_DIR / "scholar_check.json").exists():
        shutil.copy(DATA_DIR / "scholar_check.json", DIST_DIR / "data" / "scholar_check.json")
    pending = load_pending() if NOTIFIED_PATH.exists() else list((pubs.get("last_run") or {}).get("new_ids") or [])
    write_digest_pages(pubs, cfg, pending, DIST_DIR, version=version)
    (DIST_DIR / ".nojekyll").write_text("")
    print(f"built dist/ ({len(pubs.get('works', []))} works), out/digest.html, out/teams.json; new this run: {digest['new_count']}")
    return digest


if __name__ == "__main__":
    run()
