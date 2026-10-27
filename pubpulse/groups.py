"""Research groups and seniors from a Google Sheet (or a local groups.csv), for the authorship statistics.

The sheet is edited by invited people only (Google login). pubpulse reads its "Publish to web" CSV link, so the
sheet itself can stay restricted. Columns (header names are flexible): name, slug (optional), group, senior.
- group: one or more group names separated by ";" (usually the senior's name or the research line)
- senior: yes / no (also y, x, 1, true, ja)
Unknown names are reported, never added to people.yml. Group composition is published with the site."""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
from pathlib import Path

import requests

from .members import _norm

log = logging.getLogger(__name__)
HEADER_ALIASES = {
    "name": ("name", "naam", "member", "person"),
    "slug": ("slug", "id"),
    "group": ("group", "groups", "groep", "research_group", "team", "line", "research_line"),
    "senior": ("senior", "is_senior", "pi", "lead"),
}
YES = {"yes", "y", "x", "1", "true", "ja", "j"}
SENIOR_ROLES = re.compile(r"\bprofessor\b|\bsenior researcher\b|\bprincipal investigator\b|\bgroup lead", re.I)


def parse_groups_csv(text: str) -> list[dict]:
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
        raise ValueError(f"groups sheet needs a 'name' column; found {reader.fieldnames}")
    rows = []
    for raw in reader:
        name = (raw.get(colmap["name"]) or "").strip()
        if not name:
            continue
        cell = lambda k: (raw.get(colmap[k]) or "").strip() if k in colmap else ""  # noqa: E731
        rows.append({
            "name": name,
            "slug": cell("slug").lower(),
            "groups": [g.strip() for g in cell("group").split(";") if g.strip()],
            "senior": cell("senior").lower() in YES,
        })
    return rows


def resolve_groups(rows: list[dict], people: list[dict]) -> dict:
    """Match rows to people (slug, else name or alias) and collect {group: members}, seniors and unmatched names."""
    by_slug = {p["slug"]: p for p in people}
    by_name: dict[str, list[str]] = {}
    for p in people:
        for n in [p["name"]] + list(p.get("publication_name_aliases") or []) + list(p.get("aliases") or []):
            by_name.setdefault(_norm(n), []).append(p["slug"])
    groups: dict[str, list[str]] = {}
    seniors, unmatched = [], []
    for r in rows:
        slug = r["slug"] if r["slug"] in by_slug else None
        if not slug:
            cands = list(dict.fromkeys(by_name.get(_norm(r["name"]), [])))
            slug = cands[0] if len(cands) == 1 else None
        if not slug:
            unmatched.append(r["name"])
            continue
        if r["senior"] and slug not in seniors:
            seniors.append(slug)
        for g in r["groups"]:
            members = groups.setdefault(g, [])
            if slug not in members:
                members.append(slug)
    return {
        "groups": [{"name": g, "members": m, "seniors": [s for s in m if s in seniors]} for g, m in sorted(groups.items(), key=lambda x: x[0].lower())],
        "seniors": seniors,
        "unmatched": unmatched,
    }


def load_groups(cfg: dict, people: list[dict], root: Path, cache: Path) -> dict:
    """Sheet (GROUPS_SHEET_CSV_URL or groups.sheet_csv_url) > local groups.csv > last cached data/groups.json."""
    gc = cfg.get("groups") or {}
    url = (os.environ.get("GROUPS_SHEET_CSV_URL") or gc.get("sheet_csv_url") or "").strip()
    rows, source = None, None
    if url:
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "pubpulse/1.0"})
            r.raise_for_status()
            if "<html" in r.text[:500].lower():
                raise ValueError("got an HTML page instead of CSV: use the 'Publish to web' CSV link")
            rows, source = parse_groups_csv(r.text), "sheet"
        except Exception as exc:  # noqa: BLE001
            log.error("groups sheet could not be read (%s); using the last cached copy", exc)
    if rows is None:
        local = root / (gc.get("csv") or "groups.csv")
        if local.exists():
            rows, source = parse_groups_csv(local.read_text(encoding="utf-8")), "csv"
    if rows is None:
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        return {"groups": [], "seniors": [], "unmatched": [], "source": None, "edit_url": gc.get("edit_url") or ""}
    out = {**resolve_groups(rows, people), "source": source, "edit_url": gc.get("edit_url") or ""}
    if out["unmatched"]:
        log.warning("groups sheet: names not found in people.yml: %s", ", ".join(out["unmatched"]))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def template_csv(people: list[dict]) -> str:
    """Current staff, seniors pre-marked from the staff-page role (check them), group left empty."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["name", "slug", "role", "senior", "group"])
    current = [p for p in people if not p.get("exclude") and p.get("section", "current") == "current" and not p.get("active_until")]
    for p in sorted(current, key=lambda p: (not SENIOR_ROLES.search(p.get("role") or ""), (p.get("name") or "").lower())):
        senior = bool(SENIOR_ROLES.search(p.get("role") or ""))
        w.writerow([p["name"], p["slug"], p.get("role") or "", "yes" if senior else "", p["name"] if senior else ""])
    return out.getvalue()
