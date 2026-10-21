"""Discover missing researcher identifiers using shared publications and coauthor networks.

ORCID's public registry supplies candidate records; SerpAPI supplies Scholar profile search,
articles and coauthor lists. A name or institutional match alone never accepts a profile.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from .scholar import SERPAPI_URL, api_key
from .staff import is_active, is_tracked
from .sync import DATA_DIR, OUT_DIR, author_name_key, load_config, load_people, load_publications, public_people, save_people, today_utc

log = logging.getLogger(__name__)
REPORT_PATH = DATA_DIR / "identifier_discovery.json"
CACHE_PATH = OUT_DIR / "identifier-cache.json"


class BudgetExhausted(RuntimeError):
    pass


def profile_name(name: str) -> tuple[str, ...]:
    name = re.sub(r"^(?:(?:prof(?:essor)?|dr|ir|mr|ms)\.?\s+)+", "", name.strip(), flags=re.I)
    return author_name_key(name)


def same_name(left: str, right: str) -> bool:
    a, b = profile_name(left), profile_name(right)
    # Full first and last names may be accompanied by different middle names/initials.
    # This only admits a candidate: shared work or coauthor evidence is still required.
    return bool(a and b and a[0] == b[0] and a[-1] == b[-1])


def title_key(title: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", title.casefold()))


def scholar_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname not in {"scholar.google.com", "scholar.google.nl"} or parsed.path != "/citations":
        return None
    value = parse_qs(parsed.query).get("user", [""])[0]
    return value if re.fullmatch(r"[A-Za-z0-9_-]{6,64}", value) else None


def valid_orcid(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", value):
        return False
    digits = value.replace("-", "")
    total = 0
    for digit in digits[:-1]:
        total = (total + int(digit)) * 2
    check = (12 - total % 11) % 11
    return digits[-1] == ("X" if check == 10 else str(check))


def person_works(person: dict, works: list[dict]) -> list[dict]:
    return [w for w in works if person["slug"] in set(w.get("group_members", []) + (w.get("author_members") or []))]


def contexts(people: list[dict], works: list[dict]) -> dict[str, dict]:
    by_slug = {p["slug"]: p for p in people}
    result = {}
    for person in people:
        own = person_works(person, works)
        counts = Counter()
        for work in own:
            counts.update(set(work.get("group_members", []) + (work.get("author_members") or [])) - {None, person["slug"]})
        result[person["slug"]] = {"works": own, "coauthors": [by_slug[s] for s, _ in counts.most_common() if s in by_slug]}
    return result


class DiscoveryClient:
    """Bound paid searches, cache public results and never put API credentials in logs/reports."""
    def __init__(self, key: str | None, budget: int, today: date, cache_path: Path = CACHE_PATH, session=None):
        self.key, self.budget, self.today = key, max(0, budget), today
        self.used = 0
        self.cache_path = cache_path
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "pubpulse author identifier discovery"})
        try:
            self.cache = json.loads(cache_path.read_text())
        except (FileNotFoundError, ValueError):
            self.cache = {}
        self.serp_available = bool(key)

    def save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False))

    def _get(self, url: str, params=None, *, paid=False):
        params = dict(params or {})
        cache_key = hashlib.sha256(json.dumps([url, params], sort_keys=True).encode()).hexdigest()
        hit = self.cache.get(cache_key)
        if hit and (self.today - date.fromisoformat(hit["date"])).days < 30:
            return hit["data"]
        if paid:
            if not self.serp_available or self.used >= self.budget:
                raise BudgetExhausted("Scholar search unavailable or search budget reached")
            self.used += 1  # count attempted requests, including provider errors
            params["api_key"] = self.key
        try:
            response = self.session.get(url, params=params, headers={"Accept": "application/json"}, timeout=20)
        except requests.RequestException:
            raise RuntimeError("Profile provider request failed") from None
        if not response.ok:
            if paid and response.status_code in (401, 402, 403, 429):
                self.serp_available = False
            raise RuntimeError(f"Profile provider returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError("Profile provider returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError("Profile provider returned an unexpected response")
        if payload.get("error"):
            if paid and params.get("engine") == "google" and "hasn't returned any results" in str(payload["error"]).lower():
                payload = {"organic_results": []}
            else:
                raise RuntimeError("Profile provider returned a search error")
        if paid:
            # Only public profile fields, not provider metadata or credential-bearing URLs.
            payload = {k: payload[k] for k in ("profiles", "author", "articles", "co_authors", "organic_results") if k in payload}
            payload = self._public_fields(payload)
        self.cache[cache_key] = {"date": self.today.isoformat(), "data": payload}
        self.save_cache()
        return payload

    @staticmethod
    def _public_fields(value):
        if isinstance(value, dict):
            return {k: DiscoveryClient._public_fields(v) for k, v in value.items() if k not in {"serpapi_link", "thumbnail", "email"}}
        if isinstance(value, list):
            return [DiscoveryClient._public_fields(v) for v in value]
        return value

    def reserve_quota(self, reserve: int = 60):
        if not self.key:
            return
        try:
            r = self.session.get("https://serpapi.com/account.json", params={"api_key": self.key}, timeout=20)
            if r.ok:
                left = r.json().get("total_searches_left")
                if isinstance(left, int):
                    self.budget = min(self.budget, max(0, left - reserve))
        except requests.RequestException:
            pass

    def orcid_search(self, name: str, context=None):
        key = profile_name(name)
        if not key:
            return []
        query = f'given-names:"{key[0]}" AND family-name:"{key[-1]}"'
        data = self._get("https://pub.orcid.org/v3.0/expanded-search/", {"q": query, "rows": 20})
        if data.get("num-found", 0) > 5 and context:
            dois = [(w.get("doi") or "").removeprefix("https://doi.org/") for w in context["works"]]
            dois = [doi.replace('"', '\\"') for doi in dois if doi][:8]
            if dois:
                # Resolve common names by the papers shared with known group coauthors.
                linked = " OR ".join(f'digital-object-ids:"{doi}"' for doi in dois)
                data = self._get("https://pub.orcid.org/v3.0/expanded-search/", {"q": f"({query}) AND ({linked})", "rows": 20})
        return [x["orcid-id"] for x in data.get("expanded-result") or [] if valid_orcid(x.get("orcid-id", "")) and any(
            same_name(n, name) for n in [" ".join([x.get("given-names") or "", x.get("family-names") or ""]), x.get("credit-name") or "", *(x.get("other-name") or [])]
        )]

    def orcid_record(self, identifier: str):
        return self._get(f"https://pub.orcid.org/v3.0/{identifier}/record")

    def scholar_search(self, name: str, context=None):
        # The legacy google_scholar_profiles engine is discontinued. Discover actual
        # profile URLs through web search, then verify names on the author profile itself.
        data = self._get(SERPAPI_URL, {"engine": "google", "q": f'site:scholar.google.com/citations "{name}"', "num": 10, "hl": "en"}, paid=True)
        identifiers = list(dict.fromkeys(scholar_id(r.get("link") or "") for r in data.get("organic_results") or []))
        if not any(identifiers) and context and context["coauthors"]:
            key = profile_name(name)
            hints = " OR ".join('"' + p["name"].replace('"', '') + '"' for p in context["coauthors"][:2])
            query = f'site:scholar.google.com/citations "{key[0]}" "{key[-1]}" ({hints})'
            data = self._get(SERPAPI_URL, {"engine": "google", "q": query, "num": 10, "hl": "en"}, paid=True)
            identifiers = list(dict.fromkeys(scholar_id(r.get("link") or "") for r in data.get("organic_results") or []))
        return [{"name": name, "author_id": identifier} for identifier in identifiers if identifier]

    def scholar_profile(self, identifier: str):
        return self._get(SERPAPI_URL, {"engine": "google_scholar_author", "author_id": identifier, "num": 100, "hl": "en"}, paid=True)

    def scholar_coauthors(self, identifier: str):
        return self._get(SERPAPI_URL, {"engine": "google_scholar_author", "author_id": identifier, "view_op": "list_colleagues", "hl": "en"}, paid=True).get("co_authors") or []


def read_orcid(record: dict, identifier: str) -> dict:
    person = record.get("person") or {}
    name = person.get("name") or {}
    full_name = " ".join((name.get(k) or {}).get("value") or "" for k in ("given-names", "family-name")).strip()
    names = [full_name, (name.get("credit-name") or {}).get("value", "")]
    names += [n.get("content", "") for n in (person.get("other-names") or {}).get("other-name") or []]
    urls = [((r.get("url") or {}).get("value") or "") for r in (person.get("researcher-urls") or {}).get("researcher-url") or []]
    works, affiliations = [], []
    def visit(obj):
        if isinstance(obj, dict):
            if "organization" in obj:
                affiliations.append((obj["organization"] or {}).get("name", ""))
            for key, value in obj.items():
                if key == "work-summary":
                    for work in value or []:
                        ids = (work.get("external-ids") or {}).get("external-id") or []
                        works.append({"title": ((work.get("title") or {}).get("title") or {}).get("value", ""), "dois": [(i.get("external-id-value") or "").lower().removeprefix("https://doi.org/") for i in ids if i.get("external-id-type") == "doi"]})
                else:
                    visit(value)
        elif isinstance(obj, list):
            for value in obj:
                visit(value)
    visit(record.get("activities-summary") or {})
    return {"id": identifier, "name": full_name, "names": names, "affiliations": affiliations, "urls": urls, "works": works}


def institution_match(person: dict, affiliations: list[str]) -> bool:
    values = " ".join(a or "" for a in affiliations).casefold()
    if any(k in values for k in ("maastricht", "maastro", "mumc", "medical data works")):
        return True
    employer = person.get("employer") or ""
    # External group members can have an institution outside Maastricht.
    return len(employer) >= 12 and employer.casefold() in values


def shared_works(candidate_works: list[dict], context: dict) -> list[dict]:
    matches = {}
    for candidate in candidate_works:
        title = title_key(candidate.get("title") or "")
        dois = set(candidate.get("dois") or [])
        for known in context["works"]:
            known_title = title_key(known.get("title") or "")
            doi = (known.get("doi") or "").lower().removeprefix("https://doi.org/")
            # Titles must be substantial and exact; no substring/fuzzy identity inference.
            if (doi and doi in dois) or (len(title) >= 30 and title == known_title):
                coauthors = set(known.get("group_members", []) + (known.get("author_members") or [])) - {None}
                if len(coauthors) >= 2:
                    matches[known["id"]] = {"work": known["id"], "title": known["title"], "url": known.get("doi") or known.get("openalex_url"), "coauthors": sorted(coauthors)}
    return list(matches.values())


def assess_scholar(person: dict, candidate: dict, context: dict, people: list[dict], linked_from: list[str]) -> dict:
    author = candidate.get("author") or {}
    identifier = candidate["id"]
    name_matches = same_name(author.get("name", ""), person["name"])
    shared = shared_works(candidate.get("articles") or [], context)
    known_ids = {p["scholar_id"]: p["slug"] for p in people if p.get("scholar_id") and p["slug"] != person["slug"]}
    coauthors = set(linked_from)
    for other in candidate.get("co_authors") or []:
        slug = known_ids.get(other.get("author_id") or scholar_id(other.get("link", "")))
        if slug:
            coauthors.add(slug)
    affiliated = institution_match(person, [author.get("affiliations") or ""])
    accepted = name_matches and (bool(shared) or len(coauthors) >= 2 or (bool(coauthors) and affiliated))
    sources = [{"slug": p["slug"], "url": "https://scholar.google.com/citations?user=" + p["scholar_id"]} for p in people if p["slug"] in coauthors and p.get("scholar_id")]
    return {"id": identifier, "url": "https://scholar.google.com/citations?user=" + identifier, "name": author.get("name"), "affiliations": author.get("affiliations"), "name_match": name_matches, "shared_works": shared, "known_coauthors": sorted(coauthors), "coauthor_profiles": sources, "institution_match": affiliated, "accepted": accepted}


def assess_orcid(person: dict, candidate: dict, context: dict, accepted_scholar: dict | None) -> dict:
    name_matches = any(same_name(n, person["name"]) for n in candidate["names"] if n)
    shared = shared_works(candidate["works"], context)
    linked_scholar = bool(accepted_scholar and any(scholar_id(url) == accepted_scholar["id"] for url in candidate["urls"]))
    affiliated = institution_match(person, candidate["affiliations"])
    return {"id": candidate["id"], "url": "https://orcid.org/" + candidate["id"], "name": candidate["name"], "affiliations": candidate["affiliations"], "name_match": name_matches, "shared_works": shared, "linked_verified_scholar": linked_scholar, "institution_match": affiliated, "accepted": name_matches and (bool(shared) or linked_scholar)}


def discover(people: list[dict], works: list[dict], client, today: date, *, force=False, only=None, refresh_days=30, target_slugs=None, max_network_profiles=12) -> dict:
    graph = contexts(people, works)
    report = {"checked_at": today.isoformat(), "people": {}, "accepted_orcids": 0, "accepted_scholar": 0}
    by_name = defaultdict(list)
    for person in people:
        key = profile_name(person["name"])
        by_name[(key[0], key[-1]) if key else ()].append(person["slug"])
    targets = [p for p in people if not p.get("exclude") and (target_slugs is None or p["slug"] in target_slugs) and (not only or p["slug"] == only) and (not (p.get("orcid") or p.get("orcid_discovered")) or not p.get("scholar_id"))]
    targets.sort(key=lambda p: (p.get("identifier_discovery_checked_at") or "", -len(graph[p["slug"]]["works"]), p["name"]))
    due = []
    for person in targets:
        checked = person.get("identifier_discovery_checked_at")
        if not force and checked and (today - date.fromisoformat(checked)).days < refresh_days:
            continue
        due.append(person)
    if not due:
        return report

    # Walk already known Scholar profiles once: their named coauthor links seed candidates.
    seeds = defaultdict(lambda: defaultdict(set))
    anchors = [p for p in people if p.get("scholar_id") and not p.get("exclude")]
    anchors.sort(key=lambda p: (not is_active(p, today), -len(graph[p["slug"]]["works"]), p["name"]))
    for anchor in anchors[:max_network_profiles]:
        try:
            profile = client.scholar_profile(anchor["scholar_id"])
            coauthors = profile.get("co_authors") or []
            if len(coauthors) >= 20:
                try:
                    coauthors = client.scholar_coauthors(anchor["scholar_id"]) or coauthors
                except (BudgetExhausted, RuntimeError):
                    pass
            for coauthor in coauthors:
                name = profile_name(coauthor.get("name") or "")
                key = (name[0], name[-1]) if name else ()
                identifier = coauthor.get("author_id") or scholar_id(coauthor.get("link") or "")
                if key and len(by_name[key]) == 1 and identifier:
                    seeds[by_name[key][0]][identifier].add(anchor["slug"])
        except (BudgetExhausted, RuntimeError):
            continue

    for person in due:
        slug = person["slug"]
        had_orcid = bool(person.get("orcid") or person.get("orcid_discovered"))
        had_scholar = bool(person.get("scholar_id"))
        item = {"name": person["name"], "checked_at": today.isoformat(), "known_coauthors": [p["slug"] for p in graph[slug]["coauthors"]], "orcid_candidates": [], "scholar_candidates": [], "errors": [], "complete": True}
        report["people"][slug] = item
        key = profile_name(person["name"])
        if not key or len(by_name[(key[0], key[-1])]) != 1:
            item["status"] = "ambiguous_roster_name"
            continue
        orcids = []
        orcid_complete, scholar_complete = True, True
        if not (person.get("orcid") or person.get("orcid_discovered")):
            try:
                identifiers = list(dict.fromkeys(([person["orcid_openalex"]] if person.get("orcid_openalex") else []) + client.orcid_search(person["name"], graph[slug])))
                if len(identifiers) > 5:
                    orcid_complete = False
                    item["errors"].append("More than five matching ORCID records require review")
                    item["complete"] = False
                for identifier in identifiers[:5]:
                    try:
                        candidate = read_orcid(client.orcid_record(identifier), identifier)
                        if any(same_name(n, person["name"]) for n in candidate["names"] if n):
                            orcids.append(candidate)
                    except RuntimeError:
                        item["errors"].append("An ORCID candidate could not be read")
                        item["complete"] = False
                        orcid_complete = False
            except RuntimeError:
                item["errors"].append("ORCID registry search unavailable")
                item["complete"] = False
                orcid_complete = False

        accepted_scholar = None
        if not person.get("scholar_id"):
            identifiers = dict(seeds[slug])
            for record in orcids:
                for url in record["urls"]:
                    identifier = scholar_id(url)
                    if identifier:
                        identifiers.setdefault(identifier, set())
            try:
                for candidate in client.scholar_search(person["name"], graph[slug]):
                    if same_name(candidate.get("name") or "", person["name"]):
                        identifier = candidate.get("author_id") or scholar_id(candidate.get("link") or "")
                        if identifier:
                            identifiers.setdefault(identifier, set())
                if len(identifiers) > 5:
                    item["errors"].append("More than five matching Scholar profiles require review")
                    item["complete"] = False
                    scholar_complete = False
                for identifier, anchors in list(identifiers.items())[:5]:
                    candidate = {**client.scholar_profile(identifier), "id": identifier}
                    item["scholar_candidates"].append(assess_scholar(person, candidate, graph[slug], people, list(anchors)))
            except BudgetExhausted:
                item["errors"].append("Scholar search deferred: search budget reached or no search key configured")
                item["complete"] = False
                scholar_complete = False
            except RuntimeError as exc:
                item["errors"].append(f"Scholar search deferred: {exc}")
                item["complete"] = False
                scholar_complete = False
            accepted = [c for c in item["scholar_candidates"] if c["accepted"]]
            if len(accepted) == 1 and scholar_complete:
                accepted_scholar = accepted[0]
                person["scholar_id"] = accepted_scholar["id"]
                person.setdefault("identifier_evidence", {})["scholar"] = {"checked_at": today.isoformat(), **accepted_scholar}
                report["accepted_scholar"] += 1
        else:
            accepted_scholar = {"id": person["scholar_id"]}

        item["orcid_candidates"] = [assess_orcid(person, candidate, graph[slug], accepted_scholar) for candidate in orcids]
        accepted = [c for c in item["orcid_candidates"] if c["accepted"]]
        if len(accepted) == 1 and orcid_complete:
            candidate = accepted[0]
            person["orcid_discovered"] = candidate["id"]
            person.setdefault("identifier_evidence", {})["orcid"] = {"checked_at": today.isoformat(), **candidate}
            report["accepted_orcids"] += 1
        for kind, was_known, now_known, complete in [
            ("orcid", had_orcid, bool(person.get("orcid_discovered")), orcid_complete),
            ("scholar", had_scholar, bool(person.get("scholar_id")), scholar_complete),
        ]:
            candidates = item[kind + "_candidates"]
            supported = sum(c["accepted"] for c in candidates)
            item[kind + "_decision"] = "known" if was_known else "accepted" if now_known else "ambiguous" if supported > 1 else "deferred" if not complete else "insufficient_evidence" if candidates else "not_found"
        item["status"] = "matched" if "accepted" in (item["orcid_decision"], item["scholar_decision"]) else "no_new_confirmed_profile"
        item["identifiers"] = {"orcid": person.get("orcid") or person.get("orcid_discovered"), "scholar_id": person.get("scholar_id")}
        item["verified_evidence"] = dict(person.get("identifier_evidence") or {})
        if item["complete"]:
            person["identifier_discovery_checked_at"] = today.isoformat()
        log.info("%-32s ORCID candidates %d, Scholar candidates %d, %s", person["name"], len(item["orcid_candidates"]), len(item["scholar_candidates"]), item["status"])
    return report


def run(max_searches=None, only=None, force=False, dry_run=False, former=False, recent_former=False, reserve_searches=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config, today = load_config(), today_utc()
    settings = config.get("identifier_discovery") or {}
    budget = int(max_searches if max_searches is not None else settings.get("max_searches_per_run", 30))
    client = DiscoveryClient(api_key(), budget, today)
    client.reserve_quota(int(settings.get("reserve_searches", 60)) if reserve_searches is None else max(0, reserve_searches))
    people, publications = load_people(), load_publications()
    tracked = [p for p in people if former or recent_former or is_tracked(p, today, int(config.get("departed_grace_months", 0)))]
    target_slugs = {p["slug"] for p in people if p.get("section") == "previous" or p.get("active_until")} if former or recent_former else None
    if recent_former:
        target_slugs = {p["slug"] for p in people if target_slugs and p["slug"] in target_slugs and (p.get("former_collaboration") or {}).get("recent_shared_papers")}
    report = discover(tracked, publications.get("works", []), client, today, force=force, only=only, refresh_days=int(settings.get("refresh_days", 30)), target_slugs=target_slugs, max_network_profiles=int(settings.get("max_network_profiles", 12)))
    report.update({"searches_used": client.used, "search_budget": client.budget, "coverage": {
        "tracked_people": len(tracked),
        "verified_orcid_profiles": sum(bool(p.get("orcid") or p.get("orcid_discovered")) for p in tracked),
        "scholar_profiles": sum(bool(p.get("scholar_id")) for p in tracked),
        "discovered_orcids": sum(bool(p.get("orcid_discovered")) for p in tracked),
        "discovered_scholar_profiles": sum(bool((p.get("identifier_evidence") or {}).get("scholar")) for p in tracked),
    }})
    try:
        previous = json.loads(REPORT_PATH.read_text())
    except (FileNotFoundError, ValueError):
        previous = {"people": {}}
    report["people"] = {**previous.get("people", {}), **report["people"]}
    for person in tracked:
        if person["slug"] in report["people"]:
            entry = report["people"][person["slug"]]
            entry["identifiers"] = {"orcid": person.get("orcid") or person.get("orcid_discovered"), "scholar_id": person.get("scholar_id")}
            entry["verified_evidence"] = dict(person.get("identifier_evidence") or {})
    target = OUT_DIR / "identifier_discovery.json" if dry_run else REPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    save_people(people, OUT_DIR / "people.yml" if dry_run else Path(__file__).resolve().parent.parent / "people.yml")
    if not dry_run:
        publications["people"] = public_people(people, today, int(config.get("departed_grace_months", 0)))
        (DATA_DIR / "publications.json").write_text(json.dumps(publications, ensure_ascii=False, indent=1) + "\n")
    log.info("Discovery complete: %d ORCIDs, %d Scholar profiles accepted; %d/%d paid searches used", report["accepted_orcids"], report["accepted_scholar"], client.used, client.budget)
    return 0
