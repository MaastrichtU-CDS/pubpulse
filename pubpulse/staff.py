"""Scrape the group's staff page and keep people.yml in sync with it."""

from __future__ import annotations

import html as htmllib
import logging
import re
import time
from datetime import date
from urllib.parse import urljoin

import requests

log = logging.getLogger(__name__)

SCRAPED_FIELDS = ("name", "profile_url", "role", "employer", "orcid", "scholar_id", "cris_url")
ORCID_RE = re.compile(r"orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", re.I)
SCHOLAR_RE = re.compile(r"scholar\.google\.[a-z.]+/citations\?[^\"']*user=([\w-]+)", re.I)
CRIS_RE = re.compile(r'href="(https?://cris\.maastrichtuniversity\.nl/[^"]+)"', re.I)


def _text(fragment: str | None) -> str | None:
    if fragment is None:
        return None
    return htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip() or None


def section_key(title: str) -> str:
    t = title.lower()
    if "previous" in t or "former" in t or "alumni" in t:
        return "previous"
    if "current" in t:
        return "current"
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "other"


def parse_staff_page(html: str, base_url: str = "https://www.clinicaldatascience.nl/") -> list[dict]:
    """Return one dict per person on the staff page: section, slug, name, profile_url, role, employer."""
    people: list[dict] = []
    blocks = re.split(r'<div class="paragraph paragraph--type--people-list', html)[1:]
    for block in blocks:
        title_m = re.search(r"field--name-field-title[^>]*>([^<]*)<", block)
        section = section_key(title_m.group(1)) if title_m else "other"
        for person_html in re.findall(r'<div class="person">(.*?)</li>', block, re.S):
            href_m = re.search(r'href="([^"]+)"', person_html)
            name = _text(_group(re.search(r"field--name-title[^>]*>(.*?)</span>", person_html, re.S)))
            if not href_m or not name:
                continue
            href = href_m.group(1)
            slug = href.rstrip("/").rsplit("/", 1)[-1].lower()
            people.append(
                {
                    "section": section,
                    "slug": slug,
                    "name": name,
                    "profile_url": urljoin(base_url, href),
                    "role": _text(_group(re.search(r"field--name-field-function[^>]*>(.*?)</div>", person_html, re.S))),
                    "employer": _text(_group(re.search(r"field--name-field-location[^>]*>(.*?)</div>", person_html, re.S))),
                }
            )
    return people


def _group(m: re.Match | None) -> str | None:
    return m.group(1) if m else None


def parse_profile(html: str) -> dict:
    """Extract ORCID, Google Scholar id and CRIS link from a person's profile page."""
    orcid = ORCID_RE.search(html)
    scholar = SCHOLAR_RE.search(htmllib.unescape(html))
    cris = CRIS_RE.search(html)
    return {
        "orcid": orcid.group(1).upper() if orcid else None,
        "scholar_id": scholar.group(1) if scholar else None,
        "cris_url": cris.group(1) if cris else None,
    }


def fetch_staff(
    staff_url: str, track_sections: list[str], session: requests.Session | None = None, delay: float = 1.0,
    known: dict[str, dict] | None = None, today: date | None = None, profile_refresh_days: int = 30,
    contact: str | None = None,
) -> list[dict]:
    """Download the staff page (1 request) and the profile pages of tracked people that are new or whose profile
    was last checked more than profile_refresh_days ago. Be gentle: one request per `delay` seconds, identify
    ourselves, stop fetching profiles after the first server error."""
    session = session or requests.Session()
    ua = "pubpulse/1.0 (publication tracker for the CDS group; weekly; +https://github.com/MaastrichtU-CDS/pubpulse"
    session.headers.setdefault("User-Agent", ua + (f"; mailto:{contact})" if contact else ")"))
    resp = session.get(staff_url, timeout=60)
    resp.raise_for_status()
    people = parse_staff_page(resp.text, base_url=staff_url)
    known = known or {}
    today = today or date.today()
    fetched = 0
    for person in people:
        if person["section"] not in track_sections:
            continue
        prev = known.get(person["slug"])
        checked = (prev or {}).get("profile_checked_at")
        if prev and checked and profile_refresh_days > 0:
            try:
                if (today - date.fromisoformat(str(checked))).days < profile_refresh_days:
                    continue  # profile recently checked: no request
            except ValueError:
                pass
        time.sleep(delay)
        try:
            p = session.get(person["profile_url"], timeout=60)
            p.raise_for_status()
            person.update(parse_profile(p.text))
            person["_profile_fetched"] = True
            fetched += 1
        except requests.RequestException as exc:
            log.warning("could not fetch profile %s: %s (not fetching further profiles this run)", person["profile_url"], exc)
            break
    log.info("staff page: %d people, %d profile pages fetched", len(people), fetched)
    return people


def merge_people(existing: list[dict], scraped: list[dict], track_sections: list[str], today: date, min_people: int = 3) -> tuple[list[dict], dict]:
    """Merge scraped staff into the existing people list.

    - new person in a tracked section -> added
    - person no longer in a tracked section -> active_until = today (kept, never deleted)
    - person reappearing -> active_until cleared
    - scraped fields refresh existing ones only when the scraped value is non-empty
    - manual fields (openalex_id, aliases, exclude, notes, ...) are never touched
    - source: manual entries are never deactivated by the scrape
    """
    today_s = today.isoformat()
    changes = {"added": [], "deactivated": [], "reactivated": [], "updated": [], "skipped": False}
    tracked = [p for p in scraped if p["section"] in track_sections]
    if len(tracked) < min_people:
        log.warning("staff page returned only %d tracked people (< %d); keeping people.yml unchanged", len(tracked), min_people)
        changes["skipped"] = True
        return existing, changes

    by_slug = {p["slug"]: p for p in existing}
    scraped_by_slug = {p["slug"]: p for p in scraped}
    tracked_slugs = {p["slug"] for p in tracked}

    for s in tracked:
        p = by_slug.get(s["slug"])
        if p is None:
            p = {
                "slug": s["slug"],
                "name": s["name"],
                "profile_url": s.get("profile_url"),
                "role": s.get("role"),
                "employer": s.get("employer"),
                "section": s["section"],
                "orcid": s.get("orcid"),
                "scholar_id": s.get("scholar_id"),
                "cris_url": s.get("cris_url"),
                "openalex_id": None,
                "source": "staff_page",
                "profile_checked_at": today_s if s.get("_profile_fetched") else None,
                "active_from": today_s,
                "active_until": None,
                "needs_review": False,
            }
            existing.append(p)
            by_slug[s["slug"]] = p
            changes["added"].append(s["slug"])
            continue
        updated = False
        if s.get("_profile_fetched"):
            p["profile_checked_at"] = today_s
        for field in SCRAPED_FIELDS:
            val = s.get(field)
            if val and p.get(field) != val:
                p[field] = val
                updated = True
        if p.get("section") != s["section"]:
            p["section"] = s["section"]
            updated = True
        if p.get("active_until"):
            p["active_until"] = None
            changes["reactivated"].append(p["slug"])
        elif updated:
            changes["updated"].append(p["slug"])

    for p in existing:
        if p.get("source", "staff_page") != "staff_page" or p.get("active_until"):
            continue
        if p["slug"] not in tracked_slugs:
            p["active_until"] = today_s
            if p["slug"] in scraped_by_slug:
                p["section"] = scraped_by_slug[p["slug"]]["section"]
            changes["deactivated"].append(p["slug"])

    existing.sort(key=lambda p: (p.get("active_until") is not None, (p.get("name") or "").lower()))
    return existing, changes


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    last = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(d.day, last))


def is_active(person: dict, today: date | None = None) -> bool:
    """Currently in the group (on the staff page, or a manual entry without an end date)."""
    if person.get("exclude"):
        return False
    until = person.get("active_until")
    if not until:
        return True
    today = today or date.today()
    return date.fromisoformat(str(until)) > today


def tracked_until(person: dict, grace_months: int) -> date | None:
    """Last day on which papers are still collected for a person who left; None while active."""
    until = person.get("active_until")
    if not until:
        return None
    return add_months(date.fromisoformat(str(until)), grace_months)


def is_tracked(person: dict, today: date, grace_months: int) -> bool:
    """Active, or left less than grace_months ago (papers in the pipeline still count, with a verified affiliation)."""
    if person.get("exclude"):
        return False
    if is_active(person, today):
        return True
    return tracked_until(person, grace_months) >= today
