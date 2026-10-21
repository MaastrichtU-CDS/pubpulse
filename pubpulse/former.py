"""Review the entire former-staff roster against recent collaborations with current CDS staff."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from .discovery import profile_name
from .staff import add_months, is_active, merge_people, parse_staff_page
from .sync import DATA_DIR, author_name_key, load_config, load_people, load_publications, public_people, save_people, today_utc

REPORT_PATH = DATA_DIR / "former_staff_review.json"


def review_former(people: list[dict], works: list[dict], today: date, recent_months: int = 24) -> dict:
    """Link unique full first/last-name variants only on papers with an identified current CDS coauthor.

    This changes author display metadata, not publication eligibility. No departure dates are inferred.
    Alumni with a recent collaboration remain eligible for coauthored-paper follow-up beyond the grace period.
    """
    current = {p["slug"] for p in people if is_active(p, today)}
    former = {p["slug"]: p for p in people if not is_active(p, today) and not p.get("exclude")}
    by_name = defaultdict(list)
    for person in people:
        key = profile_name(person["name"])
        if key:
            by_name[(key[0], key[-1])].append(person["slug"])
    cutoff = add_months(today, -recent_months)
    evidence = defaultdict(list)
    for work in works:
        known = set(work.get("group_members") or []) | set(work.get("author_members") or [])
        collaborators = sorted(current & known)
        if not collaborators:
            continue
        authors = work.get("authors") or []
        members = list(work.get("author_members") or [None] * len(authors))
        for index, name in enumerate(authors):
            if index >= len(members):
                members.append(None)
            slug = members[index]
            if not slug:
                key = profile_name(name)
                matches = by_name.get((key[0], key[-1]), []) if key else []
                if len(matches) == 1 and matches[0] in former:
                    slug = matches[0]
                    members[index] = slug
            if slug not in former:
                continue
            person = former[slug]
            if author_name_key(name) != author_name_key(person["name"]):
                aliases = person.setdefault("publication_name_aliases", [])
                if name not in aliases:
                    aliases.append(name)
            date_string = work.get("publication_date")
            try:
                published = date.fromisoformat(date_string or "")
            except ValueError:
                published = None
            evidence[slug].append({"work": work["id"], "title": work["title"], "date": date_string,
                                   "url": work.get("doi") or work.get("openalex_url"), "current_coauthors": collaborators,
                                   "author_name": name, "author_position": (work.get("author_positions") or list(range(1, len(authors) + 1)))[index],
                                   "recent": bool(published and cutoff <= published <= today)})
        work["author_members"] = members
    report = {"checked_at": today.isoformat(), "window_start": cutoff.isoformat(), "recent_months": recent_months,
              "roster_source": "https://www.clinicaldatascience.nl/staff", "publication_scope": "Coauthored papers in the pubpulse collection; absence is not proof of no recent publications", "people": {}}
    for slug, person in former.items():
        papers = list({item["work"]: item for item in evidence[slug]}.values())
        recent = [item for item in papers if item["recent"]]
        latest = max((item["date"] for item in recent), default=None)
        coauthors = sorted({s for item in recent for s in item["current_coauthors"]})
        summary = {"checked_at": today.isoformat(), "window_start": cutoff.isoformat(), "recent_months": recent_months, "shared_papers": len(papers),
                   "recent_shared_papers": len(recent), "last_collaboration_date": latest,
                   "followup_until": add_months(date.fromisoformat(latest), recent_months).isoformat() if latest else None,
                   "current_coauthors": coauthors}
        previous = person.get("former_collaboration") or {}
        if latest and latest != previous.get("last_collaboration_date"):
            person.pop("identifier_discovery_checked_at", None)
        person["former_collaboration"] = summary
        report["people"][slug] = {"name": person["name"], "profile_url": person.get("profile_url"), **summary,
                                   "status": "recent_collaboration" if recent else "historical_collaboration" if papers else "no_collaboration_found_in_collection",
                                   "orcid": person.get("orcid") or person.get("orcid_discovered") or person.get("orcid_openalex"),
                                   "orcid_verified": bool(person.get("orcid") or person.get("orcid_discovered")),
                                   "scholar_id": person.get("scholar_id"),
                                   "identifier_evidence": {kind: {"checked_at": value.get("checked_at"), "url": value.get("url"), "shared_works": [w["work"] for w in value.get("shared_works", [])], "known_coauthors": value.get("known_coauthors", [])} for kind, value in (person.get("identifier_evidence") or {}).items()},
                                   "evidence": papers}
    report.update({"former_staff_reviewed": len(former), "with_collaborations": sum(bool(x["shared_papers"]) for x in report["people"].values()),
                   "with_recent_collaborations": sum(bool(x["recent_shared_papers"]) for x in report["people"].values())})
    return report


def run(staff_snapshot: str | None = None) -> int:
    config, today = load_config(), today_utc()
    people, publications = load_people(), load_publications()
    if staff_snapshot:
        scraped = parse_staff_page(Path(staff_snapshot).read_text())
        people, _ = merge_people(people, scraped, config.get("track_sections") or ["current"], today)
    months = int((config.get("former_staff") or {}).get("recent_collaboration_months", 24))
    report = review_former(people, publications.get("works", []), today, months)
    save_people(people)
    publications["people"] = public_people(people, today, int(config.get("departed_grace_months", 0)))
    (DATA_DIR / "publications.json").write_text(json.dumps(publications, ensure_ascii=False, indent=1) + "\n")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    print(f"Reviewed {report['former_staff_reviewed']} former staff: {report['with_collaborations']} with coauthored papers, {report['with_recent_collaborations']} with collaborations since {report['window_start']}.")
    return 0
