"""Fetch publications from OpenAlex for every tracked person and maintain data/publications.json."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from .openalex import OpenAlex, abstract_from_inverted_index, author_affiliations, author_current_institutions, short_id
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
        return {"confirm": set(), "reject": set()}
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return {k: {short_id(str(x)) for x in (raw.get(k) or [])} for k in ("confirm", "reject")}


def apply_overrides(works: list[dict], overrides: dict) -> list[dict]:
    kept = []
    for w in works:
        if w["id"] in overrides["reject"]:
            continue
        if w["id"] in overrides["confirm"]:
            w["verified"] = True
            w["manual"] = "confirmed"
        kept.append(w)
    return kept


def affiliation_matches(affiliations: list[str], keywords: list[str]) -> bool:
    kws = [k.lower() for k in keywords]
    return any(any(k in (a or "").lower() for k in kws) for a in affiliations)


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
        if p.get("orcid"):
            if p.get("openalex_ids") and _fresh(p.get("resolved_at"), today, max_age_days):
                p["needs_review"] = False
                continue
            try:
                records = client.authors_by_orcid(p["orcid"])
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
            if c.get("display_name", "").lower() == p["name"].lower() and affiliation_matches(author_affiliations(c), broad):
                match = c
                break
        p["resolved_at"] = today.isoformat()
        if match:
            p["openalex_ids"] = [short_id(match["id"])]
            # Keep the ORCID OpenAlex knows as information only: identity still rests on a name match,
            # so papers for this person count only with a verified group affiliation.
            p["orcid_openalex"] = short_id(match.get("orcid")) if match.get("orcid") else None
            p["needs_review"] = False
            log.info("resolved by name: %s -> %s", p["name"], p["openalex_ids"][0])
        else:
            p.pop("openalex_ids", None)
            p["needs_review"] = True
            unresolved.append(p["slug"])
    return unresolved


def manual_ids(person: dict) -> list[str]:
    """Hand-set openalex_id may be one id or a list (to join records OpenAlex split)."""
    v = person.get("openalex_id")
    if not v:
        return []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def person_filter(person: dict) -> str | None:
    if manual_ids(person):
        return "authorships.author.id:" + "|".join(manual_ids(person))
    if person.get("openalex_ids"):
        return "authorships.author.id:" + "|".join(person["openalex_ids"])
    if person.get("orcid"):
        return f"authorships.author.orcid:{person['orcid']}"
    return None


# ---------------------------------------------------------------------------------------------- fetch

def normalise_work(raw: dict, people: list[dict], keywords: list[str] | None = None) -> dict:
    """Flatten an OpenAlex work and attribute it to group members.

    Per member an affiliation_status is recorded: 'verified' (a group institution is on this authorship),
    'mismatch' (affiliations present, none from the group) or 'unknown' (OpenAlex has no affiliation for it).
    """
    by_orcid = {p["orcid"].upper(): p["slug"] for p in people if p.get("orcid")}
    by_id: dict[str, str] = {}
    for p in people:
        for aid in manual_ids(p) + list(p.get("openalex_ids") or []):
            by_id[aid] = p["slug"]
    authors, members, member_affiliations, status = [], [], {}, {}
    for a in raw.get("authorships", []) or []:
        author = a.get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(name)
        orcid = short_id(author.get("orcid"))
        aid = short_id(author.get("id"))
        slug = (aid and by_id.get(aid)) or (orcid and by_orcid.get(orcid.upper()))
        if slug and slug not in members:
            members.append(slug)
            affs = [i.get("display_name") for i in (a.get("institutions") or [])]
            affs += list(a.get("raw_affiliation_strings") or [])
            affs = [x for x in affs if x]
            member_affiliations[slug] = affs
            status[slug] = "unknown" if not affs else ("verified" if affiliation_matches(affs, keywords or []) else "mismatch")
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
        "authors": authors[:40],
        "author_count": len(authors),
        "group_members": members,
        "member_affiliations": member_affiliations,
        "affiliation_status": status,
        "cited_by_count": raw.get("cited_by_count", 0),
        "abstract": abstract_from_inverted_index(raw.get("abstract_inverted_index")),
    }


def fetch_works(
    people: list[dict], client: OpenAlex, since_year: int, today: date,
    keywords: list[str] | None = None, policy: str = "flag", exclude_types: list[str] | None = None,
    grace_months: int = 0,
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
    strict_only = {p["slug"] for p in people if confidence[p["slug"]] == "name" or not is_active(p, today)}
    for p in people:
        if not is_tracked(p, today, grace_months):
            continue
        flt = person_filter(p)
        if not flt:
            continue
        n = 0
        try:
            for raw in client.works(f"{flt},from_publication_date:{since_year}-01-01"):
                if raw.get("type") in excluded:
                    continue
                w = normalise_work(raw, people, keywords)
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
        keep = [m for m in w["group_members"] if m not in strict_only or w["affiliation_status"].get(m) == "verified"]
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
            "openalex_ids": manual_ids(p) or list(p.get("openalex_ids") or []),
            "match": match_confidence(p),
            "active": is_active(p, today),
            "tracked": is_tracked(p, today, grace_months),
            "tracked_until": tracked_until(p, grace_months).isoformat() if not is_active(p, today) else None,
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

    client = OpenAlex(mailto=cfg.get("openalex_mailto"))
    unresolved = resolve_people(
        people, client, keywords, today, broad_keywords=cfg.get("author_match_keywords") or keywords,
        grace_months=grace, max_age_days=int(cfg.get("resolve_cache_days", 30)),
    )
    fetched, errors = fetch_works(
        people, client, int(cfg.get("since_year", 2024)), today,
        keywords=keywords, policy=cfg.get("affiliation_policy", "flag"), exclude_types=cfg.get("exclude_types"),
        grace_months=grace,
    )

    previous = load_publications()
    baseline = not previous.get("works")
    overrides = load_overrides()
    failed_names = {e.split(":")[0] for e in errors}
    fetched_slugs = {p["slug"] for p in people if is_tracked(p, today, grace) and person_filter(p) and p["name"] not in failed_names}
    works, new_ids = merge_works(previous.get("works", []), fetched, today, fetched_slugs)
    works = apply_overrides(works, overrides)
    new_ids = [i for i in new_ids if i not in overrides["reject"]]

    run_record = {
        "date": today.isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseline": baseline,
        "people_active": sum(1 for p in people if is_active(p, today)),
        "people_tracked": sum(1 for p in people if is_tracked(p, today, grace) and person_filter(p)),
        "works_total": len(works),
        "unverified_total": sum(1 for w in works if not w.get("verified")),
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
    runs = []
    if RUNS_PATH.exists():
        with open(RUNS_PATH, encoding="utf-8") as f:
            runs = json.load(f)
    runs.append(run_record)
    with open(out_dir / "runs.json", "w", encoding="utf-8") as f:
        json.dump(runs, f, ensure_ascii=False, indent=1)
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
