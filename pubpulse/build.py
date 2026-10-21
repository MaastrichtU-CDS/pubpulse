"""Build the static site bundle (dist/), the Atom feed and the weekly digest (email + Teams card)."""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from .sync import DATA_DIR, OUT_DIR, ROOT, load_config, load_publications

SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"


def work_link(w: dict) -> str:
    return w.get("doi") or w.get("landing_url") or w.get("openalex_url")


def new_works(pubs: dict) -> list[dict]:
    last = pubs.get("last_run") or {}
    if last.get("baseline"):
        return []
    ids = set(last.get("new_ids") or [])
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

def _item_html(w: dict, names: dict[str, str]) -> str:
    members = ", ".join(html.escape(names.get(s, s)) for s in w.get("group_members", []))
    meta = " · ".join(x for x in (w.get("journal"), w.get("publication_date"), (w.get("type") or "").replace("-", " ")) if x)
    flag = "" if w.get("verified", True) else ' <span style="color:#8a5a00;font-size:12px">⚠ group affiliation not verified</span>'
    return (
        f'<li style="margin:0 0 14px 0">'
        f'<a href="{html.escape(work_link(w))}" style="font-weight:600;color:#1a4b8c;text-decoration:none">{html.escape(w["title"])}</a>'
        f'<div style="color:#555;font-size:13px">{html.escape(meta)}</div>'
        f'<div style="font-size:13px">Group authors: <b>{members}</b>{flag}</div>'
        f"</li>"
    )


def build_digest(pubs: dict, cfg: dict) -> dict:
    """Return subject, html, text, teams payload (dict) for this run's new works."""
    names = people_names(pubs)
    items = sorted(new_works(pubs), key=lambda w: w.get("publication_date") or "", reverse=True)
    last = pubs.get("last_run") or {}
    site = cfg.get("site_url", "")
    group = cfg.get("group_name", "the group")
    prefix = (cfg.get("digest") or {}).get("subject_prefix", "pubpulse")
    n = len(items)
    subject = f"{prefix}: {n} new publication{'s' if n != 1 else ''} this week ({last.get('date', '')})"

    per_person: dict[str, int] = {}
    for w in items:
        for s in w.get("group_members", []):
            per_person[s] = per_person.get(s, 0) + 1
    person_line = ", ".join(f"{names.get(s, s)} ({c})" for s, c in sorted(per_person.items(), key=lambda x: -x[1]))

    review = [names.get(s, s) for s in last.get("needs_review", [])]
    errors = last.get("errors") or []

    body = [
        '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:680px;margin:auto;color:#222">',
        f'<h2 style="margin-bottom:4px">{html.escape(group)}</h2>',
        f'<p style="margin-top:0;color:#555">{n} new publication{"s" if n != 1 else ""} found this week'
        + (f" · {html.escape(person_line)}" if person_line else "")
        + "</p>",
        "<ol>" + "".join(_item_html(w, names) for w in items) + "</ol>" if items else "<p>Nothing new this week.</p>",
        f'<p><a href="{html.escape(site)}">Browse and filter all publications</a> · <a href="{html.escape(site)}feed.xml">RSS feed</a></p>',
    ]
    unverified_new = sum(1 for w in items if not w.get("verified", True))
    if unverified_new:
        body.append(
            f'<p style="font-size:13px;color:#8a5a00;border-left:3px solid #e0a800;padding-left:8px">{unverified_new} of these have no '
            f'group affiliation recorded by OpenAlex. <a href="{html.escape(site)}#when=week&amp;verify=unverified">Check them</a> and confirm or '
            "reject them in overrides.yml.</p>"
        )
    if review:
        body.append(
            '<p style="font-size:13px;color:#8a5a00;border-left:3px solid #e0a800;padding-left:8px">Needs attention: no ORCID or '
            "OpenAlex match for " + html.escape(", ".join(review)) + ". Add an ORCID to their staff profile, or an openalex_id in people.yml.</p>"
        )
    if errors:
        body.append('<p style="font-size:13px;color:#a00">Errors during this run: ' + html.escape("; ".join(errors)) + "</p>")
    body.append('<p style="font-size:12px;color:#999">Sent automatically by pubpulse. Data: OpenAlex.</p></div>')
    html_body = "\n".join(body)

    text_lines = [f"{group}: {n} new publication(s) this week", ""]
    for i, w in enumerate(items, 1):
        members = ", ".join(names.get(s, s) for s in w.get("group_members", []))
        flag = "" if w.get("verified", True) else "  [group affiliation not verified]"
        text_lines += [f"{i}. {w['title']}", f"   {w.get('journal') or ''} · {w.get('publication_date') or ''}", f"   Group authors: {members}{flag}", f"   {work_link(w)}", ""]
    text_lines += [f"All publications: {site}", f"Feed: {site}feed.xml"]
    if unverified_new:
        text_lines += ["", f"{unverified_new} of these have no group affiliation recorded: {site}#when=week&verify=unverified"]
    if review:
        text_lines += ["", "Needs attention (no ORCID/OpenAlex match): " + ", ".join(review)]

    teams_max = int((cfg.get("digest") or {}).get("teams_max_items", 10))
    card_body = [
        {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": f"📚 {n} new publication{'s' if n != 1 else ''} this week", "wrap": True},
        {"type": "TextBlock", "text": html.escape(group), "isSubtle": True, "wrap": True},
    ]
    for w in items[:teams_max]:
        members = ", ".join(names.get(s, s) for s in w.get("group_members", []))
        card_body.append(
            {"type": "TextBlock", "wrap": True, "spacing": "Medium",
             "text": f"**[{w['title']}]({work_link(w)})**  \n{w.get('journal') or ''} · {w.get('publication_date') or ''}  \n_{members}_"
                     + ("" if w.get("verified", True) else "  ⚠ affiliation not verified")}
        )
    if n > teams_max:
        card_body.append({"type": "TextBlock", "text": f"… and {n - teams_max} more on the website.", "isSubtle": True, "wrap": True})
    if review:
        card_body.append({"type": "TextBlock", "text": "⚠️ Needs attention (no ORCID/OpenAlex match): " + ", ".join(review), "wrap": True, "isSubtle": True})
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
                "actions": [{"type": "Action.OpenUrl", "title": "Open pubpulse", "url": site}],
            },
        }],
    }
    return {"subject": subject, "html": html_body, "text": "\n".join(text_lines), "teams": teams, "new_count": n}


# ---------------------------------------------------------------------------------------------- run

def run(config_path: Path | None = None) -> dict:
    cfg = load_config(config_path) if config_path else load_config()
    pubs = load_publications()
    OUT_DIR.mkdir(exist_ok=True)

    feed = build_feed(pubs, cfg, max_items=int((cfg.get("feed") or {}).get("max_items", 50)))
    (DATA_DIR / "feed.xml").write_text(feed, encoding="utf-8")

    digest = build_digest(pubs, cfg)
    (OUT_DIR / "digest.html").write_text(digest["html"], encoding="utf-8")
    (OUT_DIR / "digest.txt").write_text(digest["text"], encoding="utf-8")
    (OUT_DIR / "subject.txt").write_text(digest["subject"], encoding="utf-8")
    (OUT_DIR / "teams.json").write_text(json.dumps(digest["teams"], ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "new_count.txt").write_text(str(digest["new_count"]), encoding="utf-8")

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    shutil.copytree(SITE_DIR, DIST_DIR)
    (DIST_DIR / "data").mkdir()
    shutil.copy(DATA_DIR / "publications.json", DIST_DIR / "data" / "publications.json")
    shutil.copy(DATA_DIR / "feed.xml", DIST_DIR / "feed.xml")
    (DIST_DIR / ".nojekyll").write_text("")
    print(f"built dist/ ({len(pubs.get('works', []))} works), out/digest.html, out/teams.json; new this run: {digest['new_count']}")
    return digest


if __name__ == "__main__":
    run()
