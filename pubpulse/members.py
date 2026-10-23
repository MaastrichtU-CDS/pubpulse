"""Membership periods from a Google Sheet (or a local CSV): start and end date per member.

The sheet is shared "anyone with the link can view" and read through its CSV export URL; no API, no key.
Columns (header names are flexible): name, slug (optional), start, end, note. Dates: YYYY-MM-DD, YYYY-MM or YYYY."""

from __future__ import annotations

import csv
import io
import logging
import re
import unicodedata
from datetime import date
from pathlib import Path

import requests

log = logging.getLogger(__name__)
HEADER_ALIASES = {
    "name": ("name", "naam", "member", "person"),
    "slug": ("slug", "id"),
    "start": ("start", "start_date", "startdate", "from", "member_from", "begin", "joined"),
    "end": ("end", "end_date", "enddate", "until", "member_until", "to", "left", "departure"),
    "note": ("note", "notes", "remark", "opmerking", "comment"),
}


def parse_date(value: str | None, end: bool = False) -> str | None:
    """Accept 2026-03-01, 01-03-2026, 2026-03, 2026, or empty. End-of-period dates round up (2026 -> 2026-12-31)."""
    v = (value or "").strip()
    if not v:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", v)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", v)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", v)
    if m:
        y, mo = int(m[1]), int(m[2])
        if not end:
            return date(y, mo, 1).isoformat()
        nxt = date(y + (mo == 12), (mo % 12) + 1, 1)
        return (nxt.toordinal() - 1 and date.fromordinal(nxt.toordinal() - 1)).isoformat()
    m = re.fullmatch(r"\d{4}", v)
    if m:
        return f"{v}-12-31" if end else f"{v}-01-01"
    raise ValueError(f"unrecognised date: {value!r}")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(name)).strip("-")


def parse_members_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not reader.fieldnames:
        return []
    colmap = {}
    for field in reader.fieldnames:
        key = re.sub(r"[\s-]+", "_", (field or "").strip().lower())
        for canon, aliases in HEADER_ALIASES.items():
            if key in aliases and canon not in colmap:
                colmap[canon] = field
    if "name" not in colmap:
        raise ValueError(f"members sheet needs a 'name' column; found {reader.fieldnames}")
    rows = []
    for raw in reader:
        name = (raw.get(colmap["name"]) or "").strip()
        if not name:
            continue
        rows.append({
            "name": name,
            "slug": (raw.get(colmap["slug"]) or "").strip().lower() if "slug" in colmap else "",
            "start": parse_date(raw.get(colmap["start"]) if "start" in colmap else None),
            "end": parse_date(raw.get(colmap["end"]) if "end" in colmap else None, end=True),
            "note": (raw.get(colmap["note"]) or "").strip() if "note" in colmap else "",
        })
    return rows


def fetch_members(cfg: dict, root: Path) -> list[dict] | None:
    """Rows from the sheet URL, else from members.csv in the repo, else None (keep what people.yml has)."""
    import os
    url = (os.environ.get("MEMBERS_SHEET_CSV_URL") or cfg.get("members_sheet_csv_url") or "").strip()
    if url:
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "pubpulse/1.0"})
            r.raise_for_status()
            if "<html" in r.text[:500].lower():
                raise ValueError("got an HTML page instead of CSV: is the sheet shared with 'anyone with the link'?")
            rows = parse_members_csv(r.text)
            log.info("members sheet: %d rows", len(rows))
            return rows
        except Exception as exc:  # noqa: BLE001
            log.error("members sheet could not be read (%s); keeping existing periods", exc)
            return None
    local = root / (cfg.get("members_csv") or "members.csv")
    if local.exists():
        rows = parse_members_csv(local.read_text(encoding="utf-8"))
        log.info("members.csv: %d rows", len(rows))
        return rows
    return None


def apply_members(people: list[dict], rows: list[dict], today: date) -> dict:
    """Write member_from / member_until onto people (matched by slug, else by name). Unknown names are added as
    manual entries (needs_review until an ORCID is known). An end date in the past makes the person inactive."""
    by_slug = {p["slug"]: p for p in people}
    by_name = {}
    for p in people:
        by_name.setdefault(_norm(p["name"]), []).append(p)
        for alias in (p.get("publication_name_aliases") or []) + (p.get("aliases") or []):
            by_name.setdefault(_norm(alias), []).append(p)
    changes = {"updated": [], "added": [], "ambiguous": []}
    for r in rows:
        p = by_slug.get(r["slug"]) if r["slug"] else None
        if p is None:
            cands = by_name.get(_norm(r["name"]), [])
            if len(cands) > 1:
                changes["ambiguous"].append(r["name"])
                continue
            p = cands[0] if cands else None
        if p is None:
            p = {"slug": slugify(r["name"]), "name": r["name"], "source": "manual", "orcid": None, "openalex_id": None,
                 "needs_review": True, "active_from": r["start"], "active_until": None}
            people.append(p)
            by_slug[p["slug"]] = p
            changes["added"].append(p["slug"])
        new = {"member_from": r["start"], "member_until": r["end"], "member_note": r["note"] or None, "membership_source": "sheet"}
        if any(p.get(k) != v for k, v in new.items()):
            p.update(new)
            changes["updated"].append(p["slug"])
        if r["end"] and date.fromisoformat(r["end"]) < today and not p.get("active_until"):
            p["active_until"] = r["end"]
        if r["end"] and date.fromisoformat(r["end"]) >= today and p.get("active_until") and p.get("membership_source") == "sheet":
            p["active_until"] = None  # sheet says still a member
    return changes


def in_period(person: dict, date_s: str | None, grace_months: int = 0) -> bool:
    """Does a publication date fall inside the member's period (plus grace after the end)?
    Without dates: current members count the whole window, former staff only through verified affiliation."""
    from .staff import add_months, is_active

    if not date_s:
        return False
    start, end = person.get("member_from"), person.get("member_until") or person.get("active_until")
    if not start and not end:
        return is_active(person) and person.get("status") != "former"
    if start and date_s < start:
        return False
    if end:
        last = add_months(date.fromisoformat(end), grace_months).isoformat() if grace_months else end
        if date_s > last:
            return False
    return True


def template_csv(people: list[dict]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["name", "slug", "role", "employer", "start", "end", "note"])
    for p in sorted(people, key=lambda p: ((p.get("status") == "former" or bool(p.get("active_until"))), (p.get("name") or "").lower())):
        if p.get("exclude"):
            continue
        w.writerow([p["name"], p["slug"], p.get("role") or "", p.get("employer") or "", p.get("member_from") or "", p.get("member_until") or p.get("active_until") or "", p.get("member_note") or ("former staff" if p.get("status") == "former" else "")])
    return out.getvalue()
