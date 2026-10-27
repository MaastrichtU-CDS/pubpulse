"""Build the static site bundle (dist/), the Atom feed and the weekly digest (email + Teams card)."""

from __future__ import annotations

import html
import json
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
NAVY, ACCENT, SKY, MUTED, LINE = "#001c3d", "#0e71bb", "#049fd8", "#607087", "#dfe5ec"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"
TYPE_PILLS = {"article": ("#e3eefb", "#1b4f91"), "review": ("#fde9df", "#8a3a16"), "preprint": ("#dff5ec", "#0f6a49"),
              "conference-paper": ("#fff1d1", "#7a5400"), "conference-abstract": ("#fff1d1", "#7a5400")}


def _summary(w: dict, draft: dict | None) -> str:
    """The draft's short version when it has no open [check] marks, else the opening of the abstract."""
    import re
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
    style = (f"background:{NAVY};color:#ffffff;border:1px solid {NAVY};" if dark else f"background:#ffffff;color:{NAVY};border:1px solid #c4d4e4;")
    return (f'<a href="{html.escape(href)}" style="{style}display:inline-block;padding:9px 14px;border-radius:6px;font:600 13px/1.2 {SANS};'
            f'text-decoration:none;margin:0 6px 6px 0">{html.escape(label)}</a>')


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
        card = (f'<a href="{html.escape(work_link(w))}"><img src="{html.escape(site + d["card"])}" width="536" alt="{html.escape(headline or w["title"])}" '
                f'style="display:block;width:100%;max-width:536px;height:auto;border:0;border-radius:8px;margin:0 0 14px"></a>')
    flag = "" if w.get("counted", w.get("verified", True)) else f' <span style="color:#8a5a00">· not in the group totals (no group affiliation recorded)</span>'
    buttons = _button(work_link(w), "Read the paper →", dark=True)
    if w.get("oa_url"):
        buttons += _button(w["oa_url"], "Full text")
    if d and d.get("post"):
        buttons += _button(f"{site}#q={w['id']}", "Share on LinkedIn")
    title_block = (
        f'<h2 style="margin:10px 0 4px;font:400 23px/1.25 {SERIF};color:{NAVY}"><a href="{html.escape(work_link(w))}" style="color:{NAVY};text-decoration:none">{html.escape(headline)}</a></h2>'
        f'<div style="font:13px/1.45 {SANS};color:{MUTED};margin:0 0 10px">{html.escape(w["title"])}</div>'
        if headline else
        f'<h2 style="margin:10px 0 10px;font:400 21px/1.3 {SERIF};color:{NAVY}"><a href="{html.escape(work_link(w))}" style="color:{NAVY};text-decoration:none">{html.escape(w["title"])}</a></h2>'
    )
    summary = _summary(w, d)
    return (
        f'<tr><td style="padding:22px 32px 18px;border-top:1px solid {LINE}">'
        f"{card}<div>{pill}{oa} <span style=\"font:13px {SANS};color:{MUTED}\">{meta}</span></div>{title_block}"
        + (f'<p style="margin:0 0 12px;font:15px/1.6 {SANS};color:#182f4b">{html.escape(summary)}</p>' if summary else "")
        + f'<p style="margin:0 0 14px;font:13px/1.5 {SANS};color:#182f4b">From the group: <b>{members}</b>{flag}</p>'
        f"<div>{buttons}</div></td></tr>"
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
    # The newsletter follows the team-window rule: only counted papers are listed; the rest is one note for maintainers.
    counted = lambda w: bool(w.get("counted", w.get("verified", True)))  # noqa: E731
    skip_types = set(dg.get("exclude_types", ["dataset"]))  # data deposits are not news; they stay on the website
    recent = [w for w in recent if w.get("type") not in skip_types]
    items = [w for w in recent if counted(w)]
    uncounted_new = len(recent) - len(items)
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
    if uncounted_new:
        notes.append(f'{uncounted_new} more new paper{"s are" if uncounted_new != 1 else " is"} not listed: outside the team window and no group affiliation recorded. '
                     f'<a href="{html.escape(site)}#when=queued&amp;verify=uncounted" style="color:{ACCENT}">Check them</a> and confirm or reject them in overrides.yml.')
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

    banner = (f'<tr><td style="background:#fff4dd;padding:12px 32px;font:600 13px/1.5 {SANS};color:#805615">{html.escape(test_note)}</td></tr>'
              if test_note else "")
    body = [
        f'<div style="background:#eef2f7;padding:24px 8px;margin:0">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td align="center">',
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden">',
        f'<tr><td style="background:{NAVY};padding:30px 32px 26px">'
        f'<div style="font:700 11px/1.4 {SANS};letter-spacing:2px;color:{SKY}">THE PUBPULSE NEWSLETTER · {html.escape(issue.upper())}</div>'
        f'<div style="font:400 30px/1.2 {SERIF};color:#ffffff;margin:12px 0 6px">New from Clinical Data Science</div>'
        f'<div style="font:14px/1.5 {SANS};color:#aec7df">Maastro · Maastricht University · Maastricht UMC+</div></td></tr>' + banner,
        f'<tr><td style="padding:24px 32px 20px;font:15px/1.6 {SANS};color:#182f4b">'
        + (f'<b style="font-size:17px">{n} new paper{"s" if n != 1 else ""} since the last newsletter.</b><br>With {html.escape(person_line)}. '
           f'<span style="color:{MUTED}">Papers can take weeks to reach OpenAlex, our source, so some were published a while ago.</span>' if n else
           '<b style="font-size:17px">Nothing new since the last newsletter.</b>')
        + "</td></tr>",
        "".join(_item_html(w, names, site) for w in items),
        f'<tr><td style="padding:20px 32px 6px;border-top:1px solid {LINE}">{_button(site, "Browse all publications")}{_button(site + "digest.html", "Newsletter on the web")}</td></tr>',
    ]
    if notes:
        body.append(f'<tr><td style="padding:10px 32px 4px;font:12px/1.55 {SANS};color:{MUTED}"><b style="color:#182f4b">Behind the scenes</b>'
                    + "".join(f'<p style="margin:6px 0">{x}</p>' for x in notes) + "</td></tr>")
    body.append(
        f'<tr><td style="background:#f5f7fa;padding:18px 32px;font:12px/1.6 {SANS};color:#8090a3">'
        f'Automated overview, not manually verified: papers are matched by simple rules and mistakes are expected. '
        f'Sent by pubpulse to {html.escape(dg.get("list_name") or "the group list")} on Mondays when there is something new. Data: OpenAlex.<br>'
        f'<a href="{{{{UNSUBSCRIBE_URL}}}}" style="color:#8090a3">Unsubscribe</a> · <a href="{html.escape(site)}#subscribe" style="color:#8090a3">Subscribe someone else</a> · '
        f'<a href="{html.escape(site)}feed.xml" style="color:#8090a3">RSS</a></td></tr>'
        "</table></td></tr></table></div>"
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
    if uncounted_new:
        text_lines += ["", f"{uncounted_new} more new paper(s) not listed (outside the team window, no group affiliation recorded): {site}#when=queued&verify=uncounted"]
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


def digest_page(heading: str, status: str, body: str, archive: list[str], site: str, prefix: str = "") -> str:
    issues = "".join(
        f'<a class="issue" href="{prefix}digests/{d}.html"><span>Week {__import__("datetime").date.fromisoformat(d).isocalendar()[1]}</span>{html.escape(_long_date(d))}</a>'
        for d in archive)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(heading)} · pubpulse</title><link rel="icon" href="{prefix}favicon.ico">
<style>
:root{{--navy:#001c3d;--accent:#0e71bb;--sky:#049fd8;--muted:#607087;--line:#dfe5ec}}
*{{box-sizing:border-box}} body{{margin:0;background:#eef2f7;color:#182f4b;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
.top{{background:var(--navy);color:#fff}} .bar{{max-width:1000px;margin:0 auto;padding:16px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
.brand{{color:#fff;text-decoration:none;font-weight:700;font-size:20px;display:flex;align-items:center;gap:10px}} .brand img{{width:30px;height:30px}}
.brand span span{{font-weight:400;color:#aec7df}} .bar nav a{{color:#fff;text-decoration:none;font-size:14px;margin-left:18px}}
.hero{{background:var(--navy);color:#fff;padding:18px 16px 70px}} .hero-in{{max-width:600px;margin:0 auto}}
.eyebrow{{font-size:11px;font-weight:700;letter-spacing:2px;color:var(--sky);margin:0}}
h1{{font:400 34px/1.15 Georgia,serif;margin:10px 0 8px}} .status{{color:#aec7df;font-size:14px;margin:0}}
.status b{{color:#fff}} .actions{{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}}
.btn{{display:inline-block;padding:10px 16px;border-radius:6px;font-weight:600;font-size:13px;text-decoration:none;background:var(--sky);color:var(--navy)}}
.btn.ghost{{background:transparent;color:#fff;border:1px solid #2c4c70}}
.mail{{max-width:616px;margin:-56px auto 0;padding:0 8px}} .mail > div{{padding:0 !important;background:none !important}}
.mail table[width="600"]{{box-shadow:0 12px 40px #001c3d22}}
.past{{max-width:600px;margin:32px auto 56px;padding:0 16px}} .past h2{{font:400 22px Georgia,serif;margin:0 0 12px}}
.issues{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}}
.issue{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px;text-decoration:none;color:var(--navy);font-size:14px}}
.issue span{{display:block;font-size:11px;font-weight:700;letter-spacing:1px;color:var(--accent);text-transform:uppercase}}
.issue:hover{{border-color:var(--accent)}}
</style></head>
<body>
<header class="top"><div class="bar"><a class="brand" href="{prefix}./"><img src="{prefix}assets/cds-icon.svg" alt=""><span>pub<span>pulse</span></span></a>
<nav><a href="{prefix}./#publications">Publications</a><a href="{prefix}./#stats">Statistics</a><a href="{prefix}digest.html">Newsletter</a></nav></div></header>
<section class="hero"><div class="hero-in"><p class="eyebrow">THE PUBPULSE NEWSLETTER</p><h1>{html.escape(heading)}</h1><p class="status">{status}</p>
<div class="actions"><a class="btn" href="{prefix}./#subscribe">Get it every Monday ↗</a><a class="btn ghost" href="{prefix}./#publications">All publications</a></div></div></section>
<main class="mail">{body}</main>
{f'<section class="past"><h2>Past issues</h2><div class="issues">{issues}</div></section>' if archive else '<div style="height:48px"></div>'}
</body></html>
"""


def write_digest_pages(pubs: dict, cfg: dict, pending: list[str], dist: Path, digests_dir: Path | None = None) -> None:
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
    (dist / "digest.html").write_text(digest_page(heading, status, body.replace("{{UNSUBSCRIBE_URL}}", "#"), archive, site), encoding="utf-8")
    if archive:
        (dist / "digests").mkdir(exist_ok=True)
        for day in archive:
            page = digest_page(f"Issue of {_long_date(day)}", f"Sent {html.escape(_long_date(day))}.",
                               (folder / f"{day}.html").read_text(encoding="utf-8"), [d for d in archive if d != day], site, prefix="../")
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
    index = DIST_DIR / "index.html"
    html_text = index.read_text(encoding="utf-8") if index.exists() else ""
    for asset in ("app.js", "style.css"):
        if (DIST_DIR / asset).exists():
            digest_hex = hashlib.sha1((DIST_DIR / asset).read_bytes()).hexdigest()[:10]
            html_text = html_text.replace(f'"{asset}"', f'"{asset}?v={digest_hex}"')
    if index.exists():
        index.write_text(html_text, encoding="utf-8")
    if (DATA_DIR / "scholar_check.json").exists():
        shutil.copy(DATA_DIR / "scholar_check.json", DIST_DIR / "data" / "scholar_check.json")
    pending = load_pending() if NOTIFIED_PATH.exists() else list((pubs.get("last_run") or {}).get("new_ids") or [])
    write_digest_pages(pubs, cfg, pending, DIST_DIR)
    (DIST_DIR / ".nojekyll").write_text("")
    print(f"built dist/ ({len(pubs.get('works', []))} works), out/digest.html, out/teams.json; new this run: {digest['new_count']}")
    return digest


if __name__ == "__main__":
    run()
