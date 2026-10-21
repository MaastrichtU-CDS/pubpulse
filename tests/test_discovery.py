from copy import deepcopy
from datetime import date
import json

import pytest

from pubpulse.discovery import BudgetExhausted, DiscoveryClient, assess_scholar, contexts, discover, read_orcid, same_name, scholar_id, valid_orcid

TODAY = date(2026, 10, 21)
ORCID = "0000-0003-2548-0330"
TITLE = "A sufficiently specific publication shared by the clinical research team"
PEOPLE = [
    {"slug": "alice", "name": "Alice Researcher", "employer": "Maastricht University"},
    {"slug": "bob", "name": "Bob Colleague", "orcid": ORCID, "scholar_id": "BobAAAAAAA AJ".replace(" ", "")},
]
WORKS = [{"id": "W1", "title": TITLE, "doi": "https://doi.org/10.1/example", "group_members": ["bob"], "author_members": ["alice", "bob"]}]


def orcid_record(name="Alice", family="Researcher", title=TITLE):
    return {"person": {"name": {"given-names": {"value": name}, "family-name": {"value": family}}},
            "activities-summary": {"works": {"group": [{"work-summary": [{"title": {"title": {"value": title}}}]}]}}}


class FakeClient:
    def __init__(self, *, profiles=None, candidates=None, records=None):
        self.profiles = profiles or {}
        self.candidates = candidates or []
        self.records = records or {}
        self.calls = []

    def scholar_profile(self, identifier):
        self.calls.append(("profile", identifier))
        return self.profiles.get(identifier, {})

    def scholar_search(self, name, context=None):
        self.calls.append(("scholar_search", name))
        return self.candidates

    def orcid_search(self, name, context=None):
        self.calls.append(("orcid_search", name))
        return list(self.records)

    def orcid_record(self, identifier):
        return self.records[identifier]


def test_generic_discovery_uses_shared_publications_and_preserves_evidence():
    people = deepcopy(PEOPLE)
    client = FakeClient(candidates=[{"name": "Alice Researcher", "author_id": "AliceAAAAAAJ"}, {"name": "Alice Researcher", "author_id": "WrongAAAAAAJ"}],
                        profiles={"AliceAAAAAAJ": {"author": {"name": "Alice Researcher"}, "articles": [{"title": TITLE}]},
                                  "WrongAAAAAAJ": {"author": {"name": "Alice Researcher", "affiliations": "Maastricht University"}, "articles": [{"title": "An unrelated publication"}]}},
                        records={ORCID: orcid_record()})
    report = discover(people, WORKS, client, TODAY)
    assert people[0]["scholar_id"] == "AliceAAAAAAJ"
    assert people[0]["orcid_discovered"] == ORCID
    assert not people[0].get("orcid")  # inferred identifiers stay distinct from supplied ones
    evidence = people[0]["identifier_evidence"]
    assert evidence["scholar"]["shared_works"][0]["work"] == "W1"
    assert evidence["orcid"]["shared_works"][0]["coauthors"] == ["alice", "bob"]
    assert report["accepted_orcids"] == report["accepted_scholar"] == 1
    assert people[1] == PEOPLE[1]


def test_name_and_affiliation_alone_never_accept_a_scholar_namesake():
    person = PEOPLE[0]
    candidate = {"id": "WrongAAAAAAJ", "author": {"name": person["name"], "affiliations": "Maastricht University"}}
    result = assess_scholar(person, candidate, contexts(PEOPLE, WORKS)["alice"], PEOPLE, [])
    assert result["name_match"] and result["institution_match"]
    assert not result["accepted"]
    candidate["author"]["name"] = "Alice Other"
    candidate["articles"] = [{"title": TITLE}]
    assert not assess_scholar(person, candidate, contexts(PEOPLE, WORKS)["alice"], PEOPLE, ["bob"])["accepted"]


def test_coauthor_network_discovers_people_without_an_existing_paper():
    people = deepcopy(PEOPLE)
    people[0]["orcid"] = ORCID
    client = FakeClient(profiles={
        PEOPLE[1]["scholar_id"]: {"co_authors": [{"name": "Alice Researcher", "author_id": "AliceAAAAAAJ"}]},
        "AliceAAAAAAJ": {"author": {"name": "Alice Researcher", "affiliations": "Maastricht University"}},
    })
    report = discover(people, [], client, TODAY)
    assert people[0]["scholar_id"] == "AliceAAAAAAJ"
    assert report["people"]["alice"]["scholar_candidates"][0]["known_coauthors"] == ["bob"]


def test_multiple_supported_profiles_are_left_for_review():
    people = deepcopy(PEOPLE)
    candidates = [{"name": "Alice Researcher", "author_id": identifier} for identifier in ["Alice1AAAAAJ", "Alice2AAAAAJ"]]
    client = FakeClient(candidates=candidates, profiles={c["author_id"]: {"author": {"name": "Alice Researcher"}, "articles": [{"title": TITLE}]} for c in candidates})
    report = discover(people, WORKS, client, TODAY)
    assert not people[0].get("scholar_id")
    assert len([c for c in report["people"]["alice"]["scholar_candidates"] if c["accepted"]]) == 2


def test_ambiguous_roster_names_are_not_assigned_identifiers():
    people = deepcopy(PEOPLE) + [{"slug": "other-alice", "name": "Alice Researcher"}]
    report = discover(people, WORKS, FakeClient(), TODAY)
    assert report["people"]["alice"]["status"] == "ambiguous_roster_name"
    assert not people[0].get("scholar_id")


def test_negative_results_are_cached_but_provider_failures_are_retried():
    people = deepcopy(PEOPLE)
    discover(people, WORKS, FakeClient(), TODAY)
    assert people[0]["identifier_discovery_checked_at"] == TODAY.isoformat()
    client = FakeClient()
    assert not discover(people, WORKS, client, TODAY)["people"]
    assert client.calls == []

    class NoScholar(FakeClient):
        def scholar_search(self, name, context=None): raise BudgetExhausted()
    people = deepcopy(PEOPLE)
    report = discover(people, WORKS, NoScholar(records={ORCID: orcid_record()}), TODAY)
    assert people[0]["orcid_discovered"] == ORCID
    assert "identifier_discovery_checked_at" not in people[0]
    assert report["people"]["alice"]["complete"] is False


def test_orcid_failure_does_not_block_a_verified_scholar_profile():
    class NoOrcid(FakeClient):
        def orcid_search(self, name, context=None): raise RuntimeError("Unavailable")
    people = deepcopy(PEOPLE)
    client = NoOrcid(candidates=[{"name": "Alice Researcher", "author_id": "AliceAAAAAAJ"}], profiles={"AliceAAAAAAJ": {"author": {"name": "Alice Researcher"}, "articles": [{"title": TITLE}]}})
    discover(people, WORKS, client, TODAY)
    assert people[0]["scholar_id"] == "AliceAAAAAAJ"


def test_budget_is_strict_and_cached_responses_do_not_consume_quota_or_store_keys(tmp_path):
    class Response:
        ok = True
        def json(self):
            return {"organic_results": [{"title": "Alice Researcher - Google Scholar", "link": "https://scholar.google.com/citations?user=AliceAAAAAAJ"}], "search_parameters": {"api_key": "TOPSECRET"}}
    class Session:
        headers = {}
        calls = 0
        def get(self, *args, **kwargs): self.calls += 1; return Response()
    session = Session()
    cache = tmp_path / "cache.json"
    client = DiscoveryClient("TOPSECRET", 1, TODAY, cache_path=cache, session=session)
    assert client.scholar_search("Alice Researcher") == [{"name": "Alice Researcher", "author_id": "AliceAAAAAAJ"}]
    assert client.scholar_search("Alice Researcher") == [{"name": "Alice Researcher", "author_id": "AliceAAAAAAJ"}]
    assert session.calls == client.used == 1
    with pytest.raises(BudgetExhausted): client.scholar_search("Another Researcher")
    assert "TOPSECRET" not in cache.read_text()
    assert "api_key" not in cache.read_text()
    assert json.loads(cache.read_text())


def test_identifier_validation_and_orcid_record_extraction():
    assert valid_orcid(ORCID)
    assert not valid_orcid("0000-0003-2548-0331")
    assert scholar_id("https://scholar.google.com/citations?user=AliceAAAAAAJ&hl=en") == "AliceAAAAAAJ"
    assert scholar_id("https://example.org/citations?user=AliceAAAAAAJ") is None
    assert scholar_id("https://scholar.google.com/citations?mauthors=Alice") is None
    assert read_orcid(orcid_record(), ORCID)["works"][0]["title"] == TITLE


def test_names_admit_full_first_last_variants_but_not_initials():
    assert same_name("Alice Marie Researcher", "Alice Researcher")
    assert same_name("Dr. Alice M. Researcher", "Alice Researcher")
    assert not same_name("A. Researcher", "Alice Researcher")
    assert not same_name("Alicia Researcher", "Alice Researcher")


def test_complete_coauthor_lists_are_used_for_discovery():
    class CompleteNetwork(FakeClient):
        def scholar_coauthors(self, identifier):
            self.calls.append(("all_coauthors", identifier))
            return [{"name": "Alice Researcher", "author_id": "AliceAAAAAAJ"}]
    people = deepcopy(PEOPLE)
    people[0]["orcid"] = ORCID
    client = CompleteNetwork(profiles={PEOPLE[1]["scholar_id"]: {"co_authors": [{"name": "Unrelated Person", "author_id": "OtherAAAAAAJ"}] * 20},
                                      "AliceAAAAAAJ": {"author": {"name": "Alice Researcher", "affiliations": "Maastricht University"}}})
    discover(people, [], client, TODAY)
    assert people[0]["scholar_id"] == "AliceAAAAAAJ"
    assert ("all_coauthors", PEOPLE[1]["scholar_id"]) in client.calls


def test_common_orcid_names_are_refined_using_shared_dois(tmp_path):
    class Response:
        ok = True
        def __init__(self, payload): self.payload = payload
        def json(self): return self.payload
    class Session:
        headers = {}
        queries = []
        def get(self, url, params, **kwargs):
            self.queries.append(params["q"])
            if len(self.queries) == 1:
                return Response({"num-found": 30, "expanded-result": []})
            return Response({"num-found": 1, "expanded-result": [{"orcid-id": ORCID, "given-names": "Alice", "family-names": "Researcher"}]})
    session = Session()
    client = DiscoveryClient(None, 0, TODAY, cache_path=tmp_path / "cache.json", session=session)
    assert client.orcid_search("Alice Researcher", contexts(PEOPLE, WORKS)["alice"]) == [ORCID]
    assert 'digital-object-ids:"10.1/example"' in session.queries[1]
    assert client.used == 0


def test_web_search_fallback_uses_known_coauthors(tmp_path):
    class Response:
        ok = True
        def __init__(self, payload): self.payload = payload
        def json(self): return self.payload
    class Session:
        headers = {}
        queries = []
        def get(self, url, params, **kwargs):
            self.queries.append(params["q"])
            return Response({"organic_results": [] if len(self.queries) == 1 else [{"link": "https://scholar.google.com/citations?user=AliceAAAAAAJ"}]})
    session = Session()
    client = DiscoveryClient("SECRET", 2, TODAY, cache_path=tmp_path / "cache.json", session=session)
    assert client.scholar_search("Alice Researcher", contexts(PEOPLE, WORKS)["alice"])[0]["author_id"] == "AliceAAAAAAJ"
    assert '"Bob Colleague"' in session.queries[1]


def test_two_known_coauthors_support_a_profile_without_a_current_institution():
    candidate = {"id": "AliceAAAAAAJ", "author": {"name": "Alice Researcher"}}
    result = assess_scholar(PEOPLE[0], candidate, {"works": []}, PEOPLE, ["bob", "carol"])
    assert result["accepted"]


def test_a_registry_link_to_a_verified_scholar_profile_supports_private_orcid_works():
    people = deepcopy(PEOPLE)
    record = orcid_record(title="An unrelated publication")
    record["person"]["researcher-urls"] = {"researcher-url": [{"url": {"value": "https://scholar.google.com/citations?user=AliceAAAAAAJ"}}]}
    client = FakeClient(records={ORCID: record}, candidates=[{"name": "Alice Researcher", "author_id": "AliceAAAAAAJ"}],
                        profiles={"AliceAAAAAAJ": {"author": {"name": "Alice Researcher"}, "articles": [{"title": TITLE}]}})
    discover(people, WORKS, client, TODAY)
    assert people[0]["orcid_discovered"] == ORCID
    assert people[0]["identifier_evidence"]["orcid"]["linked_verified_scholar"]
