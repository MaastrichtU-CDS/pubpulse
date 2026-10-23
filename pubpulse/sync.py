"""Fetch publications from OpenAlex for every tracked person and maintain data/publications.json."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from .openalex import OpenAlex, abstract_from_inverted_index, author_affiliations, author_current_institutions, short_id
from .members import apply_members, fetch_members, in_period
from .staff import fetch_staff, is_active, is_tracked, merge_people, tracked_until

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
PEOPLE_PATH = ROOT / "people.yml"
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
PUBLICATIONS_PATH = DATA_DIR / "publications.json"
RUNS_PATH = DATA_DIR / "runs.json"
OVERRIDES_PATH = ROOT / "overrides.yml"
NOTIFIED_PATH = DATA_DIR / "pending.json"

DEFAULT_EXCLUDE_TYPES = ["supplementary-materials", "erratum", "paratext"]


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_people(path: Path = PEOPLE_PATH) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("people", []) or []


def save_people(people: list[dict], path: Path = PEOPLE_PATH) -> None:
    header = (
        "# People tracked by pubpulse. Refreshed automatically from the staff page on every run.\n"
        "# Fields you may edit by hand (never overwritten): openalex_id (forces one OpenAlex author record),\n"
        "# orcid (only if the staff page has none), exclude: true, notes.\n"
        "# To track someone who is not on the staff page, add an entry with source: manual.\n"
        "# openalex_ids is filled automatically from the ORCID and refreshed every run.\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump({"people": people}, f, sort_keys=False, allow_unicode=True, width=120)


def load_publications(path: Path = PUBLICATIONS_PATH) -> dict:
    if not path.exists():
        return {"works": [], "people": [], "last_run": None}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_pending(path: Path = NOTIFIED_PATH) -> list[str]:
    """Ids of works found by earlier runs that have not been announced yet (email/Teams failed or was skipped)."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list((json.load(f) or {}).get("pending_ids") or [])


def save_pending(ids: list[str], path: Path = NOTIFIED_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"pending_ids": ids}, f, indent=1)


def load_overrides(path: Path = OVERRIDES_PATH) -> dict:
    """Manual decisions: {'confirm': [W..], 'reject': [W..]}. Ids may be given as W123 or full OpenAlex URLs."""
    if not path.exists():
        return {"confirm": set(), "reject": set(), "approve_external": set(), "verify_affiliation": set()}
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    out = {k: {short_id(str(x)) for x in (raw.get(k) or [])} for k in ("confirm", "reject", "approve_external")}
    out["verify_affiliation"] = {str(x).strip().lower() for x in (raw.get("verify_affiliation") or [])}
    return out


def apply_overrides(works: list[dict], overrides: dict) -> list[dict]:
    kept = []
    for w in works:
        if w["id"] in overrides["reject"]:
            continue
        if w["id"] in overrides["confirm"]:
            w["verified"] = True
            w["counted"] = True
            w["manual"] = "confirmed"
        w["approved_external"] = w["id"] in overrides.get("approve_external", set())
        kept.append(w)
    return kept


def affiliation_matches(affiliations: list[str], keywords: list) -> bool:
    """A keyword entry is a string (substring match) or a list of strings that must ALL occur in the same
    affiliation string (e.g. ["maastricht", "radiation oncology"]), so a generic department name alone never counts."""
    rules = [[x.lower() for x in k] if isinstance(k, (list, tuple)) else [str(k).lower()] for k in keywords]
    for a in affiliations:
        a = (a or "").lower()
        if any(all(term in a for term in rule) for rule in rules):
            return True
    return False


def author_name_key(name: str) -> tuple[str, ...]:
    """Full given name and surname, allowing accents, punctuation and middle initials.

    A first initial alone is deliberately insufficient for a name-based identity match.
    Full middle names and surname particles remain significant.
    """
    plain = "".join(c for c in unicodedata.normalize("NFKD", name.casefold()) if not unicodedata.combining(c))
    tokens = re.findall(r"[^\W_]+", plain)
    if len(tokens) < 2 or len(tokens[0]) < 2:
        return ()
    return tuple(token for i, token in enumerate(tokens) if i == 0 or len(token) > 1)


def known_author_ids(person: dict) -> list[str]:
    if manual_ids(person):
        return manual_ids(person)
    canonical = (person.get("orcid") or person.get("orcid_discovered") or "").upper()
    conflicting = {
        s.get("openalex_id") for s in person.get("publication_identity_sources") or []
        if canonical and s.get("orcid") and s["orcid"].upper() != canonical
    }
    return [aid for aid in dict.fromkeys(list(person.get("openalex_ids") or []) + list(person.get("publication_author_ids") or [])) if aid not in conflicting]


def enrich_people_from_works(people: list[dict], works, keywords: list[str]) -> None:
    """Recover split author IDs and reported ORCIDs from affiliated coauthored papers.

    Keep source works for every discovery. Conflicting ORCIDs are recorded rather than promoted;
    a publication-derived ORCID remains informational and never changes collection confidence.
    """
    by_slug = {p["slug"]: p for p in people if not p.get("exclude")}
    candidates = defaultdict(list)
    for work in works:
        for slug, profile in (work.get("author_profiles") or {}).items():
            person = by_slug.get(slug)
            if not person:
                continue
            confirmed_orcid = (person.get("orcid") or person.get("orcid_discovered") or "").upper()
            same_orcid = bool(confirmed_orcid and confirmed_orcid == (profile.get("orcid") or "").upper())
            if not same_orcid and not affiliation_matches(profile.get("affiliations") or [], keywords):
                continue
            candidates[slug].append({"work": work["id"], "openalex_id": profile.get("openalex_id"), "orcid": profile.get("orcid")})
    for slug, discoveries in candidates.items():
        person = by_slug[slug]
        sources = person.setdefault("publication_identity_sources", [])
        accepted_ids = set(person.get("publication_author_ids") or [])
        canonical = (person.get("orcid") or person.get("orcid_discovered") or "").upper()
        reported = set(person.get("orcid_openalex_conflicts") or [])
        if person.get("orcid_openalex"):
            reported.add(person["orcid_openalex"].upper())
        for discovery in discoveries:
            if not any((s.get("openalex_id"), s.get("orcid")) == (discovery["openalex_id"], discovery["orcid"]) for s in sources):
                sources.append(discovery)
        for discovery in sources:
            orcid = (discovery.get("orcid") or "").upper()
            # A merged OpenAlex record can attach somebody else's ORCID to a valid coauthor.
            if canonical and orcid and orcid != canonical:
                continue
            if discovery["openalex_id"]:
                accepted_ids.add(discovery["openalex_id"])
            if orcid:
                reported.add(orcid)
        if not canonical and len(reported) > 1:
            # A shared name with conflicting identifiers needs review before extending its search.
            accepted_ids.clear()
            person["publication_author_ids"] = []
        if accepted_ids:
            person["publication_author_ids"] = sorted(accepted_ids - {
                s.get("openalex_id") for s in sources if canonical and s.get("orcid") and s["orcid"].upper() != canonical
            })
        if known_author_ids(person):
            person["needs_review"] = False
        if not canonical and len(reported) == 1:
            person["orcid_openalex"] = next(iter(reported))
        elif not canonical and len(reported) > 1:
            person["orcid_openalex"] = None
            person["orcid_openalex_conflicts"] = sorted(reported)


# ---------------------------------------------------------------------------------------------- resolve

def match_confidence(person: dict) -> str:
    """'orcid' when identity comes from an ORCID or a hand-set OpenAlex id, 'name' when matched by name only."""
    if person.get("orcid") or person.get("openalex_id"):
        return "orcid"
    return "name"


def select_author_records(records: list[dict], strict: list[str], broad: list[str]) -> list[dict]:
    """Pick the records that most plausibly belong to the group member, in tiers:
    current institution matches the broad group words > any past affiliation matches the strict words >
    any past affiliation matches the broad words > everything (no evidence either way)."""
    if len(records) <= 1:
        return records
    tiers = (
        [r for r in records if affiliation_matches(author_current_institutions(r), broad)],
        [r for r in records if affiliation_matches(author_affiliations(r), strict)],
        [r for r in records if affiliation_matches(author_affiliations(r), broad)],
    )
    for tier in tiers:
        if tier:
            return tier
    return records


def _fresh(resolved_at: str | None, today: date, max_age_days: int) -> bool:
    if not resolved_at or max_age_days <= 0:
        return False
    try:
        return (today - date.fromisoformat(str(resolved_at))).days < max_age_days
    except ValueError:
        return False


def resolve_people(
    people: list[dict], client: OpenAlex, keywords: list[str], today: date,
    broad_keywords: list[str] | None = None, grace_months: int = 0, max_age_days: int = 30,
) -> list[str]:
    """Work out which OpenAlex author record(s) each active person corresponds to.

    - hand-set openalex_id: used as is
    - ORCID: all author records with that ORCID; if several (OpenAlex sometimes attaches one ORCID to a merged
      record of several people), the most plausible tier is kept (see select_author_records)
    - neither: search by name, accept only an exact name whose record has a group affiliation (broad words);
      papers of such people later count only with a strict, verified affiliation on the paper itself
    Results are cached in people.yml (openalex_ids + resolved_at) for max_age_days to save API budget; transient
    API errors keep the previous state instead of flipping people to needs_review.
    Returns the slugs that still need review.
    """
    unresolved = []
    broad = broad_keywords or keywords
    for p in people:
        if not is_tracked(p, today, grace_months):
            continue
        if manual_ids(p):
            p["openalex_ids"] = manual_ids(p)
            p["needs_review"] = False
            continue
        identity_orcid = p.get("orcid") or p.get("orcid_discovered")
        if identity_orcid:
            if p.get("openalex_ids") and _fresh(p.get("resolved_at"), today, max_age_days):
                p["needs_review"] = False
                continue
            try:
                records = client.authors_by_orcid(identity_orcid)
            except Exception as exc:  # noqa: BLE001
                log.warning("author lookup by ORCID failed for %s (keeping previous ids): %s", p["name"], exc)
                continue
            if len(records) > 1:
                chosen = select_author_records(records, keywords, broad)
                log.info("%s: ORCID maps to %d OpenAlex records, keeping %d (%s)", p["name"], len(records), len(chosen), ", ".join(short_id(r["id"]) for r in chosen))
                records = chosen
            ids = [short_id(r["id"]) for r in records]
            if ids:
                p["openalex_ids"] = ids
            else:
                p.pop("openalex_ids", None)  # no record: fall back to the ORCID filter
            p["resolved_at"] = today.isoformat()
            p["needs_review"] = False
            continue
        if p.get("openalex_ids") and _fresh(p.get("resolved_at"), today, max_age_days):
            p["needs_review"] = False
            continue
        try:
            candidates = client.search_authors(p["name"])
        except Exception as exc:  # noqa: BLE001
            log.warning("author search failed for %s (keeping previous state): %s", p["name"], exc)
            if p.get("needs_review", True):
                unresolved.append(p["slug"])
            continue
        match = None
        for c in candidates:
            if author_name_key(p["name"]) and author_name_key(c.get("display_name", "")) == author_name_key(p["name"]) and affiliation_matches(author_affiliations(c), broad):
                match = c
                break
        p["resolved_at"] = today.isoformat()
        if match:
            p["openalex_ids"] = [short_id(match["id"])]
            # Keep the ORCID OpenAlex knows as information only: identity still rests on a name match,
            # so papers for this person count only with a verified group affiliation.
            p["orcid_openalex"] = (short_id(match.get("orcid")) if match.get("orcid") else None) if not p.get("orcid_openalex_conflicts") else None
            p["needs_review"] = False
            log.info("resolved by name: %s -> %s", p["name"], p["openalex_ids"][0])
        else:
            p.pop("openalex_ids", None)
            p["needs_review"] = not bool(p.get("publication_author_ids"))
            if p["needs_review"]:
                unresolved.append(p["slug"])
    return unresolved


def manual_ids(person: dict) -> list[str]:
    """Hand-set openalex_id may be one id or a list (to join records OpenAlex split)."""
    v = person.get("openalex_id")
    if not v:
        return []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def person_filter(person: dict) -> str | None:
    if known_author_ids(person):
        return "authorships.author.id:" + "|".join(known_author_ids(person))
    if person.get("orcid") or person.get("orcid_discovered"):
        return f"authorships.author.orcid:{person.get('orcid') or person['orcid_discovered']}"
    return None


# ---------------------------------------------------------------------------------------------- fetch

def normalise_work(raw: dict, people: list[dict], keywords: list[str] | None = None) -> dict:
    """Flatten an OpenAlex work and attribute it to group members.

    Per member an affiliation_status is recorded: 'verified' (a group institution is on this authorship),
    'mismatch' (affiliations present, none from the group) or 'unknown' (OpenAlex has no affiliation for it).
    """
    people = [p for p in people if not p.get("exclude")]
    by_orcid = {(p.get("orcid") or p["orcid_discovered"]).upper(): p["slug"] for p in people if p.get("orcid") or p.get("orcid_discovered")}
    by_name = defaultdict(list)
    by_id: dict[str, str] = {}
    for p in people:
        for name in [p["name"], *(p.get("publication_name_aliases") or []), *(p.get("aliases") or [])]:
            key = author_name_key(name)
            if key and p["slug"] not in by_name[key]:
                by_name[key].append(p["slug"])
        for aid in known_author_ids(p):
            by_id[aid] = p["slug"]
    authorships = raw.get("authorships", []) or []
    def affiliations(a):
        return [x for x in ([i.get("display_name") for i in (a.get("institutions") or [])] + list(a.get("raw_affiliation_strings") or [])) if x]
    # Names are useful beside an identified CDS coauthor, not as a global first/last-name search.
    group_context = any(
        ((short_id((a.get("author") or {}).get("id")) in by_id) or
         (short_id((a.get("author") or {}).get("orcid")) or "").upper() in by_orcid)
        for a in authorships
    )
    authors, author_members, author_positions = [], [], []
    members, member_affiliations, status = [], {}, {}
    profiles = {}
    for position, a in enumerate(authorships, start=1):
        author = a.get("author") or {}
        name = author.get("display_name")
        orcid = short_id(author.get("orcid"))
        aid = short_id(author.get("id"))
        slug = (aid and by_id.get(aid)) or (orcid and by_orcid.get(orcid.upper()))
        method = "openalex" if aid and by_id.get(aid) else "orcid"
        affs = affiliations(a)
        if not slug and (group_context or affiliation_matches(affs, keywords or [])):
            matches = set()
            for variant in [name or "", a.get("raw_author_name") or ""]:
                matched = by_name.get(author_name_key(variant), [])
                if len(matched) == 1:
                    matches.add(matched[0])
            if len(matches) == 1:
                slug = next(iter(matches))
                method = "name"
        if name:
            authors.append(name)
            author_members.append(slug or None)
            author_positions.append(position)
        if slug and slug not in members:
            members.append(slug)
            member_affiliations[slug] = affs
            status[slug] = "unknown" if not affs else ("verified" if affiliation_matches(affs, keywords or []) else "mismatch")
            profiles[slug] = {"openalex_id": aid or None, "orcid": orcid or None, "match": method, "affiliations": affs}
    loc = raw.get("primary_location") or {}
    source = loc.get("source") or {}
    oa = raw.get("open_access") or {}
    return {
        "id": short_id(raw["id"]),
        "openalex_url": raw["id"],
        "doi": raw.get("doi"),
        "title": raw.get("title") or raw.get("display_name") or "(untitled)",
        "publication_date": raw.get("publication_date"),
        "year": raw.get("publication_year"),
        "type": raw.get("type"),
        "journal": source.get("display_name"),
        "landing_url": loc.get("landing_page_url"),
        "is_oa": bool(oa.get("is_oa")),
        "oa_url": oa.get("oa_url"),
        "license": loc.get("license") or (raw.get("best_oa_location") or {}).get("license"),
        "pdf_url": (raw.get("best_oa_location") or {}).get("pdf_url") or loc.get("pdf_url"),
        "authors": authors,
        "author_members": author_members,
        "author_profiles": profiles,
        "author_positions": author_positions,
        "author_count": len(raw.get("authorships") or []),
        "group_members": members,
        "member_affiliations": member_affiliations,
        "affiliation_status": status,
        "cited_by_count": raw.get("cited_by_count", 0),
        "abstract": abstract_from_inverted_index(raw.get("abstract_inverted_index")),
    }


def fetch_works(
    people: list[dict], client: OpenAlex, since_year: int, today: date,
    keywords: list[str] | None = None, policy: str = "flag", exclude_types: list[str] | None = None,
    grace_months: int = 0, affiliation_required: set[str] | None = None,
) -> tuple[dict[str, dict], list[str]]:
    """Return {work_id: normalised work} for all tracked people, plus a list of per-person errors.

    Rules:
    - a member matched by name only (no ORCID) is attributed a paper only when that authorship is 'verified'
    - a member who left the group (within the grace period) is attributed a paper only when it is 'verified'
    - policy 'flag' keeps every paper and marks whether any group member has a verified affiliation;
      policy 'require' drops papers without one
    - types in exclude_types are skipped
    """
    works: dict[str, dict] = {}
    errors: list[str] = []
    keywords = keywords or []
    excluded = set(exclude_types if exclude_types is not None else DEFAULT_EXCLUDE_TYPES)
    confidence = {p["slug"]: match_confidence(p) for p in people}
    current_slugs = {p["slug"] for p in people if is_active(p, today)}
    current_ids = sorted({aid for p in people if p["slug"] in current_slugs for aid in known_author_ids(p)})
    strict_only = {p["slug"] for p in people if confidence[p["slug"]] == "name" or not is_active(p, today)}
    by_slug_all = {p["slug"]: p for p in people}
    for p in people:
        if not is_tracked(p, today, grace_months):
            continue
        flt = person_filter(p)
        if not flt:
            continue
        until = p.get("active_until")
        in_grace = bool(until and tracked_until({"active_until": until}, grace_months) >= today)
        requires_collaboration = not is_active(p, today) and not in_grace
        if requires_collaboration and current_ids:
            # Repeating the author filter means former-author AND (any current-author).
            # This avoids downloading a former researcher's whole subsequent career.
            flt += ",authorships.author.id:" + "|".join(current_ids)
        n = 0
        try:
            for raw in client.works(f"{flt},from_publication_date:{since_year}-01-01"):
                if raw.get("type") in excluded:
                    continue
                w = normalise_work(raw, people, keywords)
                if not is_active(p, today) and not current_slugs.intersection(w["group_members"]):
                    # Ongoing alumni follow-up covers CDS collaborations, not their entire
                    # later career. A known departure date still permits the original pipeline grace.
                    if not in_grace:
                        continue
                n += 1
                if p["slug"] not in w["group_members"]:
                    # Filter matched but the authorship carried neither the id nor the ORCID: attribute, status unknown.
                    w["group_members"].append(p["slug"])
                    w["affiliation_status"][p["slug"]] = "unknown"
                    w["member_affiliations"][p["slug"]] = []
                existing = works.get(w["id"])
                if existing:
                    for m in w["group_members"]:
                        if m not in existing["group_members"]:
                            existing["group_members"].append(m)
                    existing["member_affiliations"].update(w["member_affiliations"])
                    existing["affiliation_status"].update(w["affiliation_status"])
                else:
                    works[w["id"]] = w
        except Exception as exc:  # noqa: BLE001
            log.error("fetching works for %s failed: %s", p["name"], exc)
            errors.append(f"{p['name']}: {exc}")
            continue
        log.info("%-40s %4d works since %d", p["name"], n, since_year)

    dropped_name, dropped_policy = 0, 0
    for wid in list(works):
        w = works[wid]
        keep = [
            m for m in w["group_members"]
            if w["affiliation_status"].get(m) == "verified"
            or (confidence.get(m) == "orcid" and (m not in strict_only or in_period(by_slug_all.get(m, {}), w.get("publication_date"), grace_months)))
        ]
        if len(keep) != len(w["group_members"]):
            for m in set(w["group_members"]) - set(keep):
                w["member_affiliations"].pop(m, None)
                w["affiliation_status"].pop(m, None)
            w["group_members"] = keep
        if not keep:
            works.pop(wid)
            dropped_name += 1
            continue
        w["verified"] = any(s == "verified" for s in w["affiliation_status"].values())
        # Counted for the group: team members count without any affiliation check while they are in the team
        # (current staff, or inside the start/end period from the members sheet). Outside the team, and for
        # people matched by name only, a verified group affiliation is required.
        w["counted_members"] = [
            m for m in w["group_members"]
            if w["affiliation_status"].get(m) == "verified"
            or (confidence.get(m) == "orcid" and m not in (affiliation_required or set())
                and in_period(by_slug_all.get(m, {}), w.get("publication_date"), grace_months))
        ]
        w["counted"] = bool(w["counted_members"])
        if policy == "require" and not w["verified"]:
            works.pop(wid)
            dropped_policy += 1
    if dropped_name:
        log.info("dropped %d works attributed only to name-matched or departed people without a verified affiliation", dropped_name)
    if dropped_policy:
        log.info("affiliation policy 'require': dropped %d unverified works", dropped_policy)
    return works, errors


def merge_works(existing: list[dict], fetched: dict[str, dict], today: date, fetched_slugs: set[str] | None = None) -> tuple[list[dict], list[str]]:
    """Keep first_seen from existing records; anything unknown is new.

    Existing works that were not returned this run are dropped when any of their group members was (re)fetched this
    run (the attribution no longer holds), and kept otherwise (e.g. papers of people who have left the group).
    """
    today_s = today.isoformat()
    fetched_slugs = fetched_slugs or set()
    merged: dict[str, dict] = {
        w["id"]: w for w in existing
        if w["id"] in fetched or not any(m in fetched_slugs for m in w.get("group_members", []))
    }
    new_ids: list[str] = []
    for wid, w in fetched.items():
        old = merged.get(wid)
        if old:
            w["first_seen"] = old.get("first_seen", today_s)
        else:
            w["first_seen"] = today_s
            new_ids.append(wid)
        merged[wid] = w
    ordered = sorted(merged.values(), key=lambda w: (w.get("publication_date") or "", w["id"]), reverse=True)
    return ordered, new_ids


def public_people(people: list[dict], today: date, grace_months: int = 0) -> list[dict]:
    return [
        {
            "slug": p["slug"],
            "name": p["name"],
            "profile_url": p.get("profile_url"),
            "role": p.get("role"),
            "employer": p.get("employer"),
            "orcid": p.get("orcid"),
            "orcid_discovered": p.get("orcid_discovered"),
            "orcid_openalex": p.get("orcid_openalex"),
            "scholar_id": p.get("scholar_id"),
            "openalex_ids": known_author_ids(p),
            "match": match_confidence(p),
            "active": is_active(p, today),
            "former": not is_active(p, today),
            "former_collaboration": p.get("former_collaboration"),
            "tracked": is_tracked(p, today, grace_months),
            "tracked_until": tracked_until(p, grace_months).isoformat() if not is_active(p, today) and tracked_until(p, grace_months) else None,
            "needs_review": bool(p.get("needs_review")) and is_tracked(p, today, grace_months),
        }
        for p in people
        if not p.get("exclude")
    ]


# ---------------------------------------------------------------------------------------------- run

def run(dry_run: bool = False, skip_people: bool = False, config_path: Path = CONFIG_PATH) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config(config_path)
    today = today_utc()
    people = load_people()
    track_sections = cfg.get("track_sections") or ["current"]
    keywords = cfg.get("institution_keywords", [])
    grace = int(cfg.get("departed_grace_months", 0))

    people_changes: dict = {}
    if not skip_people:
        try:
            scraped = fetch_staff(
                cfg["staff_url"], track_sections, known={p["slug"]: p for p in people}, today=today,
                delay=float(cfg.get("scrape_delay_seconds", 1.0)), profile_refresh_days=int(cfg.get("profile_refresh_days", 30)),
                contact=cfg.get("openalex_mailto"),
            )
            people, people_changes = merge_people(
                people, scraped, track_sections, today, min_people=int(cfg.get("min_people_on_staff_page", 3))
            )
            log.info("people sync: %s", {k: v for k, v in people_changes.items() if v})
        except Exception as exc:  # noqa: BLE001
            log.error("staff page sync failed, keeping people.yml unchanged: %s", exc)
            people_changes = {"error": str(exc)}

    # Membership periods are applied in memory only: they are personal data and never written to people.yml,
    # the published data or the site. Only the resulting per-paper "counted" flag is public.
    rows = fetch_members(cfg, ROOT)
    sheet_active_until = {p["slug"]: p.get("active_until") for p in people}
    if rows:
        mchanges = apply_members(people, rows, today)
        log.info("membership periods applied for %d people (%d unknown names added)", len(mchanges["updated"]), len(mchanges["added"]))

    client = OpenAlex(mailto=cfg.get("openalex_mailto"))
    previous = load_publications()
    from .former import review_former
    review_months = int((cfg.get("former_staff") or {}).get("recent_collaboration_months", 24))
    review_former(people, previous.get("works", []), today, review_months)
    enrich_people_from_works(people, previous.get("works", []), cfg.get("author_match_keywords") or keywords)
    unresolved = resolve_people(
        people, client, keywords, today, broad_keywords=cfg.get("author_match_keywords") or keywords,
        grace_months=grace, max_age_days=int(cfg.get("resolve_cache_days", 30)),
    )
    overrides = load_overrides()
    fetched, errors = fetch_works(
        people, client, int(cfg.get("since_year", 2024)), today,
        keywords=keywords, policy=cfg.get("affiliation_policy", "flag"), exclude_types=cfg.get("exclude_types"),
        grace_months=grace, affiliation_required=overrides["verify_affiliation"],
    )

    enrich_people_from_works(people, fetched.values(), cfg.get("author_match_keywords") or keywords)
    unresolved = [p["slug"] for p in people if p.get("needs_review") and is_tracked(p, today, grace)]
    baseline = not previous.get("works")
    failed_names = {e.split(":")[0] for e in errors}
    fetched_slugs = {p["slug"] for p in people if is_tracked(p, today, grace) and person_filter(p) and p["name"] not in failed_names}
    works, new_ids = merge_works(previous.get("works", []), fetched, today, fetched_slugs)
    works = apply_overrides(works, overrides)
    former_report = review_former(people, works, today, review_months)
    new_ids = [i for i in new_ids if i not in overrides["reject"]]

    run_record = {
        "date": today.isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseline": baseline,
        "people_active": sum(1 for p in people if is_active(p, today)),
        "people_tracked": sum(1 for p in people if is_tracked(p, today, grace) and person_filter(p)),
        "works_total": len(works),
        "unverified_total": sum(1 for w in works if not w.get("verified")),
        "counted_total": sum(1 for w in works if w.get("counted")),
        "new_count": 0 if baseline else len(new_ids),
        "new_ids": [] if baseline else new_ids,
        "needs_review": unresolved,
        "people_changes": people_changes,
        "errors": errors,
    }
    publications = {
        "generated": run_record["timestamp"],
        "group_name": cfg.get("group_name"),
        "site_url": cfg.get("site_url"),
        "repo_url": cfg.get("repo_url"),
        "staff_url": cfg.get("staff_url"),
        "since_year": int(cfg.get("since_year", 2024)),
        "list": {k: (cfg.get("digest") or {}).get(k) or "" for k in ("subscribe_endpoint", "subscribe_form_url", "list_name")},
        "last_run": {k: run_record[k] for k in ("date", "baseline", "new_count", "new_ids", "needs_review", "errors")},
        "people": public_people(people, today, grace),
        "works": works,
    }

    # A partial result must never become the baseline or be committed: with fetch errors, write to out/ only and fail.
    failed = bool(errors) and not dry_run
    out_dir = OUT_DIR if (dry_run or failed) else DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "publications.json", "w", encoding="utf-8") as f:
        json.dump(publications, f, ensure_ascii=False, indent=1)
    with open(out_dir / "former_staff_review.json", "w", encoding="utf-8") as f:
        json.dump(former_report, f, ensure_ascii=False, indent=1)
    runs = []
    if RUNS_PATH.exists():
        with open(RUNS_PATH, encoding="utf-8") as f:
            runs = json.load(f)
    runs.append(run_record)
    with open(out_dir / "runs.json", "w", encoding="utf-8") as f:
        json.dump(runs, f, ensure_ascii=False, indent=1)
    for p in people:
        for k in ("member_from", "member_until", "member_note", "membership_source"):
            p.pop(k, None)
        if p["slug"] in sheet_active_until:
            p["active_until"] = sheet_active_until[p["slug"]]
    people = [p for p in people if not (p.get("source") == "manual" and p.get("needs_review") and p["slug"] not in sheet_active_until)]
    save_people(people, OUT_DIR / "people.yml" if (dry_run or failed) else PEOPLE_PATH)
    if not (dry_run or failed):
        # Carry unannounced ids over until a notification succeeds (workflow clears the file afterwards).
        known = {w["id"] for w in works}
        pending = [i for i in load_pending() if i in known and i not in overrides["reject"]]
        if not baseline:
            pending += [i for i in new_ids if i not in pending]
        save_pending(pending)

    log.info(
        "run done: %d people active, %d tracked, %d works (%d unverified), %d new%s, %d need review, %d errors",
        run_record["people_active"], run_record["people_tracked"], len(works), run_record["unverified_total"],
        run_record["new_count"], " (baseline run, no notifications)" if baseline else "", len(unresolved), len(errors),
    )
    if failed:
        log.error("run aborted: %d people could not be fetched; nothing written to data/ or people.yml (see out/)", len(errors))
        raise SystemExit(1)
    return run_record
