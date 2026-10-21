"""Monthly cross-check against Google Scholar profiles via SerpAPI.

Scholar is NOT a data source (no DOIs, no affiliations, no API of its own). This module only answers one question per
person with a Scholar id: which papers are on their Scholar profile but absent from pubpulse? Those are listed as
"possibly missing" for a human to look at. Budget: 1 SerpAPI search per 100 papers per profile; the free plan has
250 searches a month. The key is read from SERPAPI_KEY (or SHERP_API_KEY)."""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
from datetime import date

import requests

from .staff import is_tracked
from .sync import DATA_DIR, load_config, load_people, load_publications, save_people, today_utc

log = logging.getLogger(__name__)
CHECK_PATH = DATA_DIR / "scholar_check.json"
SERPAPI_URL = "https://serpapi.com/search.json"


def api_key() -> str | None:
    return os.environ.get("SERPAPI_KEY") or os.environ.get("SHERP_API_KEY") or None


def norm(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (title or "").lower()).strip()


def fetch_profile_articles(scholar_id: str, key: str, max_pages: int = 3, session: requests.Session | None = None) -> tuple[list[dict], int]:
    """All articles on a Scholar profile (100 per search). Returns (articles, searches_used)."""
    session = session or requests.Session()
    articles: list[dict] = []
    start, used = 0, 0
    for _ in range(max_pages):
        resp = session.get(SERPAPI_URL, params={"engine": "google_scholar_author", "author_id": scholar_id, "num": 100, "start": start, "api_key": key}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        used += 1
        if data.get("error"):
            raise RuntimeError(data["error"])
        page = data.get("articles") or []
        for a in page:
            year = a.get("year")
            try:
                year = int(year) if year else None
            except ValueError:
                year = None
            articles.append({"title": a.get("title") or "", "year": year, "link": a.get("link"), "venue": a.get("publication"), "cited_by": (a.get("cited_by") or {}).get("value")})
        if len(page) < 100 or not (data.get("serpapi_pagination") or {}).get("next"):
            break
        start += 100
    return articles, used


def compare(articles: list[dict], works: list[dict], slug: str, since_year: int, cutoff: float = 0.85) -> dict:
    """Split a profile's articles (from since_year on) into: matched & attributed, matched but not attributed to
    this person, and missing from pubpulse."""
    by_norm = {norm(w["title"]): w for w in works}
    keys = list(by_norm)
    result = {"checked": 0, "matched": 0, "not_attributed": [], "missing": []}
    for a in articles:
        if not a["year"] or a["year"] < since_year or not a["title"]:
            continue  # undated Scholar entries are nearly always fragments or old items
        result["checked"] += 1
        n = norm(a["title"])
        hit = by_norm.get(n)
        if not hit:
            close = difflib.get_close_matches(n, keys, n=1, cutoff=cutoff)
            hit = by_norm[close[0]] if close else None
        if not hit:
            for k in keys:  # one title is a prefix of the other (subtitle dropped on one side)
                short, long_ = (k, n) if len(k) < len(n) else (n, k)
                if len(short) >= 15 and long_.startswith(short):
                    hit = by_norm[k]
                    break
        item = {"title": a["title"], "year": a["year"], "venue": a["venue"], "link": a["link"]}
        if hit is None:
            result["missing"].append(item)
        elif slug not in hit.get("group_members", []):
            result["not_attributed"].append({**item, "pubpulse_id": hit["id"]})
        else:
            result["matched"] += 1
    return result


def run(max_searches: int | None = None, only: str | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    key = api_key()
    if not key:
        log.warning("no SERPAPI_KEY: Scholar check skipped")
        return 0
    cfg = load_config()
    today = today_utc()
    since_year = int(cfg.get("since_year", 2024))
    budget = int(max_searches if max_searches is not None else (cfg.get("scholar") or {}).get("max_searches_per_run", 60))
    people = load_people()
    pubs = load_publications()
    works = pubs.get("works", [])
    previous = json.load(open(CHECK_PATH, encoding="utf-8")) if CHECK_PATH.exists() else {"people": {}}
    report = {"checked_at": today.isoformat(), "since_year": since_year, "people": dict(previous.get("people", {}))}

    candidates = [p for p in people if p.get("scholar_id") and is_tracked(p, today, int(cfg.get("departed_grace_months", 0))) and (not only or p["slug"] == only)]
    candidates.sort(key=lambda p: p.get("scholar_checked_at") or "")  # stalest first
    used = 0
    for p in candidates:
        if used >= budget:
            log.info("search budget (%d) reached; %s and later wait for the next run", budget, p["name"])
            break
        try:
            articles, n = fetch_profile_articles(p["scholar_id"], key)
        except Exception as exc:  # noqa: BLE001
            log.error("Scholar fetch failed for %s: %s", p["name"], exc)
            continue
        used += n
        res = compare(articles, works, p["slug"], since_year)
        res.update({"name": p["name"], "scholar_id": p["scholar_id"], "profile_total": len(articles), "checked_at": today.isoformat(),
                    "articles": [a for a in articles if a["year"] and a["year"] >= since_year]})
        report["people"][p["slug"]] = res
        p["scholar_checked_at"] = today.isoformat()
        log.info("%-32s profile %3d | since %d: %2d checked, %2d matched, %2d not attributed, %2d missing", p["name"], len(articles), since_year, res["checked"], res["matched"], len(res["not_attributed"]), len(res["missing"]))
    report["searches_used"] = used
    report["total_missing"] = sum(len(v.get("missing", [])) for v in report["people"].values())
    report["total_not_attributed"] = sum(len(v.get("not_attributed", [])) for v in report["people"].values())
    DATA_DIR.mkdir(exist_ok=True)
    with open(CHECK_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    save_people(people)
    log.info("Scholar check done: %d searches used, %d possibly missing, %d not attributed", used, report["total_missing"], report["total_not_attributed"])
    return 0
