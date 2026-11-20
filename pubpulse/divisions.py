"""Maastro publications per research division (divisions.html).

Separate from the CDS tracking on purpose: nothing here feeds the CDS counts, statistics or newsletter.

Scope: every paper since since_year where any author lists Maastro (the OpenAlex institution record, or "maastro" in
the affiliation text: OpenAlex links only about half of them to the institution), plus papers where a division leader
lists a Maastro / GROW affiliation (division_keywords; hospital departments do not count). Division credit: Clinical Data Science when a
person tracked by pubpulse is on the paper; any division whose leader is on it. Papers with neither are listed as
"division not identified" with their first and last author, so they can be traced.

Deduplication: works are keyed by OpenAlex id across all queries; a preprint whose published version is also there is
dropped; a paper credited to several divisions counts once in the Maastro total on the page.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .openalex import OpenAlex, short_id
from .sync import (CONFIG_PATH, DATA_DIR, PUBLICATIONS_PATH, affiliation_matches, author_name_key,
                   conference_abstract_type, load_config)

DIVISIONS_PATH = DATA_DIR / "divisions.json"
DEFAULT_KEYWORDS = ["maastro", "grow", ["maastricht", "radiation oncology"]]
MAASTRO_INSTITUTION = "I4210161616"  # Maastro Clinic, ror.org/059wkzj26
FIELDS = "id,doi,title,display_name,publication_date,publication_year,type,primary_location,open_access,authorships,cited_by_count"
log = logging.getLogger(__name__)


def title_key(title: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())[:150]


def _affiliations(a: dict) -> list[str]:
    return [x for x in [i.get("display_name") for i in (a.get("institutions") or [])] + list(a.get("raw_affiliation_strings") or []) if x]


def lists_maastro(a: dict, institution: str = MAASTRO_INSTITUTION) -> bool:
    return any(short_id(i.get("id")) == institution for i in (a.get("institutions") or [])) \
        or any("maastro" in s.lower() for s in _affiliations(a))


def normalise(raw: dict, leaders: dict[str, set[str]], keywords: list, cds_ids: set[str],
              cds_division: str | None, institution: str = MAASTRO_INSTITUTION) -> dict | None:
    """The work as the page needs it, or None when it is out of scope (no Maastro author, no Maastricht leader)."""
    authorships = raw.get("authorships") or []
    n = len(authorships)
    maastro = any(lists_maastro(a, institution) for a in authorships)
    found = {}
    for i, a in enumerate(authorships):
        aid = short_id((a.get("author") or {}).get("id"))
        for division, ids in leaders.items():
            if aid in ids and division not in found:
                found[division] = {"position": "only" if n == 1 else "first" if i == 0 else "last" if i == n - 1 else "middle",
                                   "maastricht": affiliation_matches(_affiliations(a), keywords)}
    if not maastro and not any(v["maastricht"] for v in found.values()):
        return None
    wid = short_id(raw["id"])
    divisions = [d for d in leaders if d in found]
    if cds_division and wid in cds_ids and cds_division not in divisions:
        divisions.insert(0, cds_division)
    name = lambda a: (a.get("author") or {}).get("display_name") or ""
    source = ((raw.get("primary_location") or {}).get("source") or {})
    w = {
        "id": wid,
        "doi": raw.get("doi"),
        "title": raw.get("title") or raw.get("display_name") or "(untitled)",
        "publication_date": raw.get("publication_date"),
        "year": raw.get("publication_year"),
        "type": raw.get("type"),
        "journal": source.get("display_name"),
        "cited_by_count": raw.get("cited_by_count") or 0,
        "is_oa": bool((raw.get("open_access") or {}).get("is_oa")),
        "author_count": n,
        "first_author": name(authorships[0]) if authorships else "",
        "last_author": name(authorships[-1]) if n > 1 else "",
        # The last author leads the paper; it is led from Maastricht when they list Maastro or a division keyword
        # (GROW or Maastricht radiation oncology; Maastricht UMC+ departments such as radiology are the hospital, not Maastro).
        "last_author_home": bool(authorships) and (lists_maastro(authorships[-1], institution)
                                                   or affiliation_matches(_affiliations(authorships[-1]), keywords)),
        "maastro": maastro,
        "divisions": divisions,
        "leaders": found,
    }
    w["type"] = conference_abstract_type(w) or w["type"]
    return w


def lead_key(name: str) -> tuple[str, ...]:
    """First name and surname: "Liesbeth J. Boersma" and "Liesbeth Jorinne Boersma" are one person."""
    tokens = author_name_key(name or "")
    return (tokens[0], tokens[-1]) if tokens else ()


def label_leads(works: list[dict], divisions: list[dict], minimum: int) -> list[dict]:
    """Set w["led_by"] (+ "led_by_division" for a division leader) on every paper whose last author is a division
    leader, or someone who is last author listed in Maastricht on at least `minimum` papers. Returns those frequent
    leaders (division leaders excluded), most papers first, with how many of their papers have no division."""
    leaders = {lead_key(d["leader"]): d for d in divisions}
    counts, names = {}, {}
    for w in works:
        key = lead_key(w["last_author"])
        if key and w.get("last_author_home") and key not in leaders:
            counts[key] = counts.get(key, 0) + 1
            names.setdefault(key, {}).setdefault(w["last_author"], 0)
            names[key][w["last_author"]] += 1
    frequent = {k for k, c in counts.items() if c >= minimum}
    for w in works:
        key = lead_key(w["last_author"])
        w.pop("led_by", None)
        w.pop("led_by_division", None)
        if key in leaders and leaders[key]["division"] in w["divisions"]:
            w["led_by"], w["led_by_division"] = leaders[key]["leader"], leaders[key]["division"]
        elif key in frequent and w.get("last_author_home"):
            w["led_by"] = max(names[key], key=names[key].get)  # the spelling OpenAlex uses most
    out = []
    for key in frequent:
        name = max(names[key], key=names[key].get)
        mine = [w for w in works if w.get("led_by") == name]
        divisions_seen = {}
        for w in mine:
            for d in w["divisions"]:
                divisions_seen[d] = divisions_seen.get(d, 0) + 1
        out.append({"name": name, "papers": len(mine), "unidentified": sum(1 for w in mine if not w["divisions"]),
                    "divisions": dict(sorted(divisions_seen.items(), key=lambda kv: -kv[1]))})
    return sorted(out, key=lambda f: (-f["papers"], f["name"]))


def drop_superseded_preprints(works: list[dict]) -> list[dict]:
    """A preprint whose title also appears as a non-preprint is the same paper: keep the published version."""
    published = {title_key(w["title"]) for w in works if w["type"] != "preprint"}
    return [w for w in works if w["type"] != "preprint" or title_key(w["title"]) not in published]


def cds_work_ids(path: Path = PUBLICATIONS_PATH) -> set[str]:
    """Works with a person tracked by pubpulse (the CDS group) on them."""
    if not path.exists():
        return set()
    return {w["id"] for w in json.loads(path.read_text(encoding="utf-8")).get("works", []) if w.get("group_members")}


def collect(client: OpenAlex, divisions: list[dict], since_year: int, keywords: list, excluded: set,
            cds_ids: set[str], institution: str = MAASTRO_INSTITUTION) -> tuple[dict[str, list[str]], list[dict]]:
    leaders = {}
    for d in divisions:
        ids = sorted({short_id(a["id"]) for a in client.authors_by_orcid(d["orcid"])})
        if not ids:
            raise LookupError(f"no OpenAlex author record carries ORCID {d['orcid']} ({d['leader']})")
        leaders[d["division"]] = ids
    cds_division = next((d["division"] for d in divisions if d.get("cds")), None)
    since = f"from_publication_date:{since_year}-01-01"
    queries = [f"authorships.institutions.id:{institution},{since}", f"raw_affiliation_strings.search:maastro,{since}"]
    queries += [f"authorships.author.id:{'|'.join(ids)},{since}" for ids in leaders.values()]
    sets = {k: set(v) for k, v in leaders.items()}
    works = {}
    for q in queries:
        for raw in client.works(q, select=FIELDS):
            if raw.get("type") in excluded or short_id(raw["id"]) in works:
                continue
            w = normalise(raw, sets, keywords, cds_ids, cds_division, institution)
            if w:
                works[w["id"]] = w
    kept = drop_superseded_preprints(list(works.values()))
    return leaders, sorted(kept, key=lambda w: w.get("publication_date") or "", reverse=True)


def run(config_path: Path = CONFIG_PATH, out_path: Path = DIVISIONS_PATH, client: OpenAlex | None = None,
        publications_path: Path = PUBLICATIONS_PATH) -> int:
    cfg = load_config(config_path)
    divisions = cfg.get("maastro_divisions") or []
    if not divisions:
        print("no maastro_divisions in config.yml: nothing to do")
        return 0
    keywords = cfg.get("division_keywords") or DEFAULT_KEYWORDS
    since_year = int(cfg.get("since_year", 2024))
    # No contact address: these requests need nothing beyond the API key.
    client = client or OpenAlex()
    try:
        leaders, works = collect(client, divisions, since_year, keywords, set(cfg.get("exclude_types") or []),
                                 cds_work_ids(publications_path), str(cfg.get("maastro_institution") or MAASTRO_INSTITUTION))
    except Exception as exc:  # an incomplete set would undercount: keep last week's file as it is
        log.error("divisions: OpenAlex failed (%s); data/divisions.json left unchanged", exc)
        return 1
    frequent = label_leads(works, divisions, int(cfg.get("frequent_leader_min_papers", 2)))
    data = {
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "since_year": since_year,
        "keywords": [k if isinstance(k, str) else " + ".join(k) if isinstance(k, list) else k.get("school") for k in keywords],
        "divisions": [{"division": d["division"], "leader": d["leader"], "orcid": d["orcid"], "cds": bool(d.get("cds")),
                       "openalex_ids": leaders[d["division"]]} for d in divisions],
        "frequent_leaders": frequent,
        "frequent_leader_min_papers": int(cfg.get("frequent_leader_min_papers", 2)),
        "works": works,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    unassigned = sum(1 for w in works if not w["divisions"])
    print(f"divisions: {len(works)} Maastro papers, {unassigned} without an identified division")
    return 0
