from datetime import date

from pubpulse.openalex import abstract_from_inverted_index
from pubpulse.sync import merge_works, normalise_work, person_filter

PEOPLE = [
    {"slug": "jvs", "name": "J", "orcid": "0000-0003-2548-0330", "openalex_id": None},
    {"slug": "sp", "name": "S", "orcid": None, "openalex_id": "A5000000001"},
]
KW = ["maastricht", "maastro"]


def _raw(wid="W1", authorships=None):
    return {
        "id": f"https://openalex.org/{wid}", "doi": "https://doi.org/10.1/x", "title": "T", "publication_date": "2026-10-09",
        "publication_year": 2026, "type": "article", "cited_by_count": 3,
        "primary_location": {"source": {"display_name": "JMIR AI"}, "landing_page_url": "https://j/x"},
        "open_access": {"is_oa": True, "oa_url": "https://oa/x"},
        "abstract_inverted_index": {"Hello": [0], "world": [1]},
        "authorships": authorships or [],
    }


def test_normalise_work_matches_members_and_verifies_affiliations():
    raw = _raw(authorships=[
        {"author": {"id": "https://openalex.org/A5034589930", "orcid": "https://orcid.org/0000-0003-2548-0330", "display_name": "Johan van Soest"},
         "institutions": [{"display_name": "Maastricht University"}], "raw_affiliation_strings": []},
        {"author": {"id": "https://openalex.org/A5000000001", "orcid": None, "display_name": "S P"},
         "institutions": [{"display_name": "Harvard University"}], "raw_affiliation_strings": ["Harvard"]},
        {"author": {"id": "https://openalex.org/A999", "orcid": None, "display_name": "Other"}, "institutions": []},
    ])
    w = normalise_work(raw, PEOPLE, KW)
    assert w["id"] == "W1" and w["group_members"] == ["jvs", "sp"] and w["author_count"] == 3
    assert w["affiliation_status"] == {"jvs": "verified", "sp": "mismatch"}
    assert w["member_affiliations"]["sp"] == ["Harvard University", "Harvard"]
    assert w["abstract"] == "Hello world" and w["journal"] == "JMIR AI" and w["is_oa"]


def test_merge_works_keeps_first_seen_and_detects_new():
    today = date(2026, 10, 21)
    existing = [{"id": "W1", "publication_date": "2026-01-01", "first_seen": "2026-01-05"}, {"id": "W0", "publication_date": "2025-01-01", "first_seen": "2025-02-01"}]
    fetched = {"W1": {"id": "W1", "publication_date": "2026-01-01"}, "W2": {"id": "W2", "publication_date": "2026-10-01"}}
    merged, new_ids = merge_works(existing, fetched, today)
    by = {w["id"]: w for w in merged}
    assert new_ids == ["W2"] and by["W2"]["first_seen"] == "2026-10-21"
    assert by["W1"]["first_seen"] == "2026-01-05"
    assert "W0" in by  # not refetched but kept
    assert [w["id"] for w in merged] == ["W2", "W1", "W0"]


def test_person_filter_precedence():
    assert person_filter(PEOPLE[0]) == "authorships.author.orcid:0000-0003-2548-0330"
    assert person_filter({**PEOPLE[0], "openalex_ids": ["A1", "A2"]}) == "authorships.author.id:A1|A2"
    assert person_filter(PEOPLE[1]) == "authorships.author.id:A5000000001"
    assert person_filter({"orcid": None, "openalex_id": None}) is None


class _FakeClient:
    def __init__(self, works_by_filter):
        self.works_by_filter = works_by_filter

    def works(self, filter_expr, **kw):
        key = filter_expr.split(",")[0]
        return iter(self.works_by_filter.get(key, []))


def test_fetch_works_rules():
    from datetime import date
    from pubpulse.sync import fetch_works

    people = [
        {"slug": "o", "name": "O", "orcid": "0000-0001-0000-0001", "openalex_ids": ["A1"]},
        {"slug": "n", "name": "N", "orcid": None, "openalex_ids": ["A2"]},   # name-matched
    ]
    def auth(aid, insts):
        return {"author": {"id": f"https://openalex.org/{aid}", "display_name": aid}, "institutions": [{"display_name": i} for i in insts]}
    w_both = _raw("W1", [auth("A1", []), auth("A2", ["Maastro Clinic"])])
    w_n_mismatch = _raw("W2", [auth("A2", ["Harvard"])])
    w_o_unknown = _raw("W3", [auth("A1", [])])
    w_supp = _raw("W4", [auth("A1", ["Maastricht University"])]); w_supp["type"] = "supplementary-materials"
    client = _FakeClient({"authorships.author.id:A1": [w_both, w_o_unknown, w_supp], "authorships.author.id:A2": [w_both, w_n_mismatch]})
    works, errors = fetch_works(people, client, 2024, date(2026, 10, 21), keywords=KW)
    assert errors == [] and set(works) == {"W1", "W3"}          # W2 dropped (name-only, mismatch); W4 excluded type
    assert works["W1"]["group_members"] == ["o", "n"] and works["W1"]["verified"] is True
    assert works["W3"]["verified"] is False and works["W3"]["affiliation_status"] == {"o": "unknown"}
    works, _ = fetch_works(people, client, 2024, date(2026, 10, 21), keywords=KW, policy="require")
    assert set(works) == {"W1"}


def test_abstract_truncation():
    idx = {f"w{i}": [i] for i in range(600)}
    text = abstract_from_inverted_index(idx, max_chars=100)
    assert text.endswith("…") and len(text) <= 100


def test_apply_overrides():
    from pubpulse.sync import apply_overrides

    works = [{"id": "W1", "verified": False}, {"id": "W2", "verified": True}, {"id": "W3", "verified": False}]
    out = apply_overrides(works, {"confirm": {"W1"}, "reject": {"W2"}})
    assert [w["id"] for w in out] == ["W1", "W3"]
    assert out[0]["verified"] is True and out[0]["manual"] == "confirmed"


def test_merge_works_drops_stale_attributions_but_keeps_left_people():
    from datetime import date
    existing = [
        {"id": "W1", "publication_date": "2026-01-01", "first_seen": "2026-01-05", "group_members": ["active"]},
        {"id": "W9", "publication_date": "2025-01-01", "first_seen": "2025-02-01", "group_members": ["left"]},
    ]
    merged, new_ids = merge_works(existing, {}, date(2026, 10, 21), fetched_slugs={"active"})
    assert [w["id"] for w in merged] == ["W9"] and new_ids == []


def test_select_author_records_prefers_current_group_institution():
    from pubpulse.sync import select_author_records
    wrong = {"id": "https://openalex.org/A1", "last_known_institutions": [], "affiliations": [{"institution": {"display_name": "Radiation Oncology Dept, Leeds"}}]}
    right = {"id": "https://openalex.org/A2", "last_known_institutions": [{"display_name": "Maastro Clinic"}], "affiliations": []}
    strict, broad = ["maastro", "radiation oncology"], ["maastricht", "maastro"]
    assert select_author_records([wrong, right], strict, broad) == [right]
    assert select_author_records([wrong], strict, broad) == [wrong]
    neither = {"id": "https://openalex.org/A3", "last_known_institutions": [], "affiliations": []}
    assert select_author_records([wrong, neither], strict, broad) == [wrong]   # strict past affiliation beats nothing


def test_manual_openalex_id_accepts_list():
    assert person_filter({"openalex_id": ["A1", "A2"], "orcid": "x"}) == "authorships.author.id:A1|A2"
    assert person_filter({"openalex_id": "A1", "orcid": "x"}) == "authorships.author.id:A1"


def test_departed_person_counts_only_verified_papers():
    from datetime import date
    from pubpulse.sync import fetch_works

    people = [{"slug": "gone", "name": "G", "orcid": "0000-0001-0000-0001", "openalex_ids": ["A1"], "active_until": "2026-06-01"}]
    def auth(aid, insts):
        return {"author": {"id": f"https://openalex.org/{aid}", "display_name": aid}, "institutions": [{"display_name": i} for i in insts]}
    client = _FakeClient({"authorships.author.id:A1": [_raw("W1", [auth("A1", ["Maastro Clinic"])]), _raw("W2", [auth("A1", ["Elsewhere"])])]})
    works, _ = fetch_works(people, client, 2024, date(2026, 10, 21), keywords=KW, grace_months=18)
    assert set(works) == {"W1", "W2"} and works["W1"]["counted"] is True  # within the grace period: still tracked
    assert works["W2"]["counted"] is False  # listed with another institution only
    works, _ = fetch_works(people, client, 2024, date(2028, 10, 21), keywords=KW, grace_months=18)
    assert works == {}  # grace period over


def test_resolve_keeps_state_on_api_errors_and_caches():
    from datetime import date
    from pubpulse.sync import resolve_people

    class Boom:
        def authors_by_orcid(self, o): raise RuntimeError("429")
        def search_authors(self, n): raise RuntimeError("429")

    people = [
        {"slug": "o", "name": "O", "orcid": "0000-0001-0000-0001", "openalex_ids": ["A1"], "resolved_at": "2026-01-01"},
        {"slug": "n", "name": "N", "orcid": None, "openalex_ids": ["A2"], "needs_review": False, "resolved_at": "2026-01-01"},
        {"slug": "u", "name": "U", "orcid": None, "needs_review": True},
    ]
    unresolved = resolve_people(people, Boom(), ["maastro"], date(2026, 10, 21), max_age_days=30)
    assert people[0]["openalex_ids"] == ["A1"] and people[1]["openalex_ids"] == ["A2"] and people[1]["needs_review"] is False
    assert unresolved == ["u"]

    class Count:
        calls = 0
        def authors_by_orcid(self, o): Count.calls += 1; return [{"id": "https://openalex.org/A9", "last_known_institutions": [], "affiliations": []}]
        def search_authors(self, n): Count.calls += 1; return []

    fresh = [{"slug": "o", "name": "O", "orcid": "0000-0001-0000-0001", "openalex_ids": ["A1"], "resolved_at": "2026-10-15"}]
    resolve_people(fresh, Count(), ["maastro"], date(2026, 10, 21), max_age_days=30)
    assert Count.calls == 0 and fresh[0]["openalex_ids"] == ["A1"]          # cached
    resolve_people(fresh, Count(), ["maastro"], date(2026, 12, 21), max_age_days=30)
    assert Count.calls == 1 and fresh[0]["openalex_ids"] == ["A9"]          # refreshed after 30 days


def test_normalise_work_preserves_full_author_order_and_member_identity():
    authorships = [
        {"author": {"id": f"https://openalex.org/A{10000 + i}", "display_name": f"External Author {i}"}}
        for i in range(45)
    ]
    # An unnamed record still occupies its original authorship position.
    authorships[2]["author"].pop("display_name")
    # Match by identity even when the indexed name uses initials, beyond the old 40-name cutoff.
    authorships[44]["author"] = {"id": "https://openalex.org/A5000000001", "display_name": "S. P."}
    work = normalise_work(_raw(authorships=authorships), PEOPLE, KW)
    assert work["author_count"] == 45
    assert len(work["authors"]) == 44
    assert work["authors"][-1] == "S. P."
    assert work["author_members"][-1] == "sp"
    assert work["author_positions"][-1] == 45
    assert work["author_positions"][:4] == [1, 2, 4, 5]
    assert len(work["author_members"]) == len(work["authors"]) == len(work["author_positions"])
    assert work["author_members"][:-1] == [None] * 43


def test_public_people_includes_known_author_profile_identifiers():
    from pubpulse.sync import public_people

    people = [
        {"slug": "known", "name": "Known Author", "orcid": "0000-0003-2548-0330", "scholar_id": "AbCdEfGAAAAJ"},
        {"slug": "unknown", "name": "Unknown Author"},
        {"slug": "reported", "name": "Reported Author", "orcid_openalex": "0009-0003-5286-6973"},
    ]
    public = {p["slug"]: p for p in public_people(people, date(2026, 10, 21))}
    assert public["known"]["orcid"] == "0000-0003-2548-0330"
    assert public["known"]["scholar_id"] == "AbCdEfGAAAAJ"
    assert public["unknown"]["orcid"] is None
    assert public["unknown"]["scholar_id"] is None

    assert public["reported"]["orcid"] is None
    assert public["reported"]["orcid_openalex"] == "0009-0003-5286-6973"


def test_author_name_key_keeps_full_names_and_allows_middle_initials():
    from pubpulse.sync import author_name_key

    assert author_name_key("Rutger F. R. van Mierlo") == author_name_key("Rutger van Mierlo")
    assert author_name_key("Daniël Slob") == author_name_key("Daniel Slob")
    assert author_name_key("Anne-Lore Bynens") == author_name_key("Anne Lore Bynens")
    assert author_name_key("R. van Mierlo") == ()
    assert author_name_key("Rutger Frank van Mierlo") != author_name_key("Rutger van Mierlo")
    assert author_name_key("Wenjia Liang") != author_name_key("Wenjie Liang")


def test_middle_name_match_needs_a_single_current_group_record():
    from pubpulse.sync import middle_name_match

    strict = ["maastro"]
    thijs = {"display_name": "Thijs Maria Anne Ackermans", "last_known_institutions": [{"display_name": "Maastro Clinic"}]}
    leuven = {"display_name": "Thijs Pieter Ackermans", "last_known_institutions": [{"display_name": "KU Leuven"}]}
    assert middle_name_match("Thijs Ackermans", [leuven, thijs], strict) is thijs
    assert middle_name_match("Thijs Ackermans", [leuven], strict) is None
    twin = {**thijs, "display_name": "Thijs Johan Ackermans"}
    assert middle_name_match("Thijs Ackermans", [thijs, twin], strict) is None
    assert middle_name_match("Thijs Ackermans", [{**thijs, "display_name": "Thijs Ackermans-Smit"}], strict) is None


def test_normalise_recovers_coauthors_without_relaxing_name_ambiguity():
    people = [
        {"slug": "known", "name": "Known Researcher", "openalex_ids": ["A1"]},
        {"slug": "wenjie", "name": "Wenjie Liang", "openalex_ids": ["A2"]},
        {"slug": "rutger", "name": "Rutger van Mierlo"},
        {"slug": "anne", "name": "Anne-Lore Bynens", "openalex_ids": ["A3"]},
        {"slug": "dup1", "name": "Same Name"},
        {"slug": "dup2", "name": "Same Name"},
        {"slug": "excluded", "name": "Excluded Person", "exclude": True},
    ]
    def auth(aid, name, institution):
        return {"author": {"id": "https://openalex.org/" + aid, "display_name": name}, "institutions": [{"display_name": institution}]}
    raw = _raw(authorships=[
        auth("A9", "Wenjie Liang", "Maastro"),
        auth("A10", "Rutger F. R. van Mierlo", "Maastro"),
        auth("A3", "Anne-Lore Bynens", "Maastricht University Medical Centre"),
        auth("A1", "K. Researcher", "Maastro"),
        auth("A11", "Same Name", "Maastro"),
        auth("A12", "R. van Mierlo", "Maastro"),
        auth("A13", "Excluded Person", "Maastro"),
    ])
    work = normalise_work(raw, people, ["maastro"])
    assert work["author_members"] == ["wenjie", "rutger", "anne", "known", None, None, None]
    assert work["author_profiles"]["rutger"]["match"] == "name"
    assert work["author_profiles"]["rutger"]["openalex_id"] == "A10"
    assert work["affiliation_status"]["anne"] == "unspecific"  # a bare MUMC is no other affiliation
    # A matching name without a CDS affiliation or confirmed coauthor is not enough.
    unrelated = normalise_work(_raw(authorships=[auth("A9", "Wenjie Liang", "Elsewhere")]), people, ["maastro"])
    assert unrelated["author_members"] == [None]


def test_publication_identity_discovery_keeps_sources_and_conflicts_separate():
    from pubpulse.sync import enrich_people_from_works, known_author_ids, resolve_people

    person = {"slug": "r", "name": "Rutger van Mierlo", "needs_review": True}
    def work(wid, aid, orcid, affs):
        return {"id": wid, "author_profiles": {"r": {"openalex_id": aid, "orcid": orcid, "affiliations": affs}}}
    affiliated = work("W1", "A1", "0009-0009-4156-5669", ["Maastro"])
    enrich_people_from_works([person], [affiliated, work("W2", "A9", "0000-0000-0000-0000", ["Unrelated University"])], ["maastro"])
    assert known_author_ids(person) == ["A1"]
    assert person["orcid_openalex"] == "0009-0009-4156-5669" and not person.get("orcid")
    assert person["publication_identity_sources"] == [{"work": "W1", "openalex_id": "A1", "orcid": "0009-0009-4156-5669"}]
    enrich_people_from_works([person], [affiliated], ["maastro"])
    assert len(person["publication_identity_sources"]) == 1

    class EmptySearch:
        def search_authors(self, name): return []
    assert resolve_people([person], EmptySearch(), ["maastro"], date(2026, 10, 21), max_age_days=0) == []
    assert known_author_ids(person) == ["A1"] and person["needs_review"] is False

    enrich_people_from_works([person], [work("W3", "A2", "0000-0000-0000-0000", ["Maastro"])], ["maastro"])
    assert person["orcid_openalex"] is None  # conflicting reported IDs are never guessed
    person["orcid"] = "0009-0009-4156-5669"
    enrich_people_from_works([person], [work("W4", "A3", "0000-0000-0000-0000", ["Maastro"])], ["maastro"])
    assert person["orcid"] == "0009-0009-4156-5669" and "A3" not in known_author_ids(person)
    assert "A2" not in known_author_ids(person)
    person["openalex_id"] = "Amanual"
    assert known_author_ids(person) == ["Amanual"]


def test_known_coauthor_metadata_survives_strict_collection_rules():
    from pubpulse.sync import fetch_works

    people = [
        {"slug": "anchor", "name": "CDS Anchor", "orcid": "0000-0001-0000-0001", "openalex_ids": ["A1"]},
        {"slug": "anne", "name": "Anne-Lore Bynens", "openalex_ids": ["A2"]},
    ]
    raw = _raw(authorships=[
        {"author": {"id": "https://openalex.org/A2", "display_name": "Anne-Lore Bynens"}, "institutions": [{"display_name": "Maastricht University Medical Centre"}]},
        {"author": {"id": "https://openalex.org/A1", "display_name": "CDS Anchor"}, "institutions": [{"display_name": "Maastro"}]},
    ])
    client = _FakeClient({"authorships.author.id:A1": [raw], "authorships.author.id:A2": [raw]})
    works, errors = fetch_works(people, client, 2024, date(2026, 10, 21), keywords=["maastro"])
    assert not errors
    assert works["W1"]["group_members"] == ["anchor"]
    assert works["W1"]["author_members"] == ["anne", "anchor"]
    assert works["W1"]["author_profiles"]["anne"]["affiliations"] == ["Maastricht University Medical Centre"]
    assert works["W1"]["verified"] is True


def test_discovered_orcid_resolves_without_relaxing_collection_confidence():
    from pubpulse.sync import match_confidence, public_people, resolve_people

    person = {"slug": "discovered", "name": "Discovered Author", "orcid_discovered": "0000-0003-2548-0330"}
    class Client:
        def authors_by_orcid(self, identifier):
            assert identifier == person["orcid_discovered"]
            return [{"id": "https://openalex.org/A42"}]
    assert person_filter(person) == "authorships.author.orcid:0000-0003-2548-0330"
    assert resolve_people([person], Client(), KW, date(2026, 10, 21)) == []
    assert person_filter(person) == "authorships.author.id:A42"
    assert match_confidence(person) == "name"
    assert public_people([person], date(2026, 10, 21))[0]["orcid_discovered"] == person["orcid_discovered"]


def test_affiliation_rules_require_cooccurrence():
    from pubpulse.sync import affiliation_matches
    rules = ["maastro", ["maastricht", "radiation oncology"]]
    assert affiliation_matches(["Department of Radiation Oncology (Maastro), GROW, Maastricht University Medical Centre+"], rules)
    assert affiliation_matches(["Maastro Clinic"], rules)
    assert not affiliation_matches(["Department of Radiation Oncology, Christian Medical College, Vellore"], rules)
    assert not affiliation_matches(["Maastricht University"], rules)
    assert affiliation_matches(["Dept. of Radiation Oncology, Maastricht University Medical Centre"], rules)


def test_counted_for_team_members_without_another_affiliation():
    from datetime import date
    from pubpulse.sync import fetch_works

    people = [{"slug": "m", "name": "M", "orcid": "0000-0001-0000-0001", "openalex_ids": ["A1"], "active_until": None}]
    def auth(aid, insts):
        return {"author": {"id": f"https://openalex.org/{aid}", "display_name": aid}, "institutions": [{"display_name": i} for i in insts]}
    w_in_unknown = _raw("W2", [auth("A1", [])]); w_in_unknown["publication_date"] = "2025-06-01"
    w_in_mismatch = _raw("W3", [auth("A1", ["Elsewhere"])]); w_in_mismatch["publication_date"] = "2025-06-01"
    client = _FakeClient({"authorships.author.id:A1": [w_in_unknown, w_in_mismatch]})
    works, _ = fetch_works(people, client, 2024, date(2026, 10, 23), keywords=KW)
    # in team: no affiliation listed counts; listed with another institution only does not
    assert works["W2"]["counted"] is True and works["W3"]["counted"] is False


def test_bare_maastricht_affiliation_is_not_another_affiliation_and_grow_alone_verifies():
    from datetime import date
    from pubpulse.sync import fetch_works

    people = [{"slug": "m", "name": "M", "orcid": "0000-0001-0000-0001", "openalex_ids": ["A1"], "active_until": None}]
    def auth(aid, insts):
        return {"author": {"id": f"https://openalex.org/{aid}", "display_name": aid}, "institutions": [{"display_name": i} for i in insts]}
    client = _FakeClient({"authorships.author.id:A1": [
        _raw("W1", [auth("A1", ["Maastricht University", "Maastricht University, P.O. Box 616, 6200MD Maastricht, The Netherlands"])]),
        _raw("W2", [auth("A1", ["KU Leuven"])]),
        _raw("W3", [auth("A1", ["5GROW School for Oncology and Reproduction"])]),
        _raw("W11", [auth("A1", ["Department of Radiation Oncology, GROW Research Institute for Oncology and Reproduction, "
                                  "Maastricht University Medical Centre+, Maastricht, The Netherlands"])]),
        _raw("W12", [auth("A1", ["Department of Radiotherapy, Res. Inst. for Oncology and Reproduction (GROW), Maastricht University"])]),
        _raw("W4", [auth("A1", ["Dept of Growth and Reproduction"])]),
        _raw("W5", [auth("A1", ["Department of Radiation Oncology"])]),
        _raw("W6", [auth("A1", ["Maastricht University Medical Centre", "Department of Surgery, Maastricht University Medical Centre+"])]),
        _raw("W7", [auth("A1", ["Department of Radiation Oncology, Stanford University"])]),
        _raw("W8", [auth("A1", ["The D-Lab, Department of Precision Medicine, GROW - Research Institute for Oncology and Reproduction"])]),
        _raw("W9", [auth("A1", ["Radiology and Nuclear Medicine, GROW & CARIM, Maastricht University"])]),
        _raw("W10", [auth("A1", ["Departments of Radiation Oncology and Radiology, Harvard Medical School, Boston; "
                                  "Department of Radiology and Nuclear Medicine, Maastricht University Medical Center"])])]})
    works, _ = fetch_works(people, client, 2024, date(2026, 10, 30),
                           keywords=["maastro", {"school": "grow"}, ["maastricht", "radiation oncology"]])
    for wid in ("W1", "W5"):  # names no department or institution beyond Maastricht University / Radiation Oncology
        assert works[wid]["affiliation_status"]["m"] == "unspecific"
        assert works[wid]["counted"] is True and works[wid]["listed_elsewhere"] is False
    for wid in ("W2", "W4", "W6", "W7", "W8", "W9", "W10"):  # another institution or department; "growth" is not GROW
        assert works[wid]["affiliation_status"]["m"] == "mismatch"
        assert works[wid]["counted"] is False and works[wid]["listed_elsewhere"] is True
    for wid in ("W3", "W11", "W12"):  # GROW without another department, or with our own (the official affiliation)
        assert works[wid]["affiliation_status"]["m"] == "verified" and works[wid]["counted"] is True


def test_paper_led_by_another_maastricht_group_does_not_count():
    from pubpulse.sync import apply_overrides
    people = [{"slug": "m", "name": "M Member", "role": "PhD student"}, {"slug": "ib", "name": "Inigo Bermejo Delgado"},
              {"slug": "lead", "name": "Lead", "role": "Professor"}, {"slug": "ap", "name": "A P", "role": "Assistant Professor"}]
    def work(wid, authors, members, senior_affs=()):
        return {"id": wid, "authors": authors, "author_members": members, "group_members": ["m"], "verified": True,
                "counted": True, "counted_members": ["m"], "listed_elsewhere": False, "senior_affiliations": list(senior_affs)}
    grow = ["Radiology and Nuclear Medicine, GROW, Maastricht University"]
    works = [
        work("W1", ["A", "M Member", "Frank Verhaegen"], [None, "m", None]),          # no affiliation here, Maastro on W8
        work("W2", ["A", "M Member", "C van der Leij"], [None, "m", None], grow),    # non-CDS senior listed with GROW
        work("W3", ["M Member", "B", "C van der Leij"], ["m", None, None], grow),     # CDS first author: CDS-led
        work("W4", ["A", "M Member", "Iñigo Bermejo"], [None, "m", None], grow),     # senior is (former) CDS
        work("W5", ["A", "M Member", "D Smith"], [None, "m", None], ["Leiden University"]),  # external collaborator
        work("W6", ["A", "M Member", "C van der Leij"], [None, "m", None], grow),    # confirmed by hand
        work("W7", ["A", "Lead", "M Member", "C van der Leij"], [None, "lead", "m", None], grow),  # a CDS professor is on it
        work("W8", ["A", "M Member", "Frank Verhaegen"], [None, "m", None], ["Maastro Clinic"]),
        work("W9", ["A", "A P", "M Member", "C van der Leij"], [None, "ap", "m", None], grow),  # assistant professor only
        work("W10", ["A", "M Member", "E Jones"], [None, "m", None]),                   # never listed with Maastro / GROW
    ]
    works[6]["group_members"] = ["lead", "m"]
    works[8]["group_members"] = ["ap", "m"]
    ov = {"confirm": {"W6"}, "reject": set()}
    out = {w["id"]: w for w in apply_overrides(works, ov, people=people, senior_keywords=["maastro", "grow"])}
    for wid in ("W1", "W2", "W8", "W9"):
        assert not out[wid]["counted"] and not out[wid]["verified"] and out[wid]["listed_elsewhere"]
    assert out["W2"]["other_group"] == "C van der Leij"
    for wid in ("W3", "W4", "W5", "W6", "W7", "W10"):
        assert out[wid]["counted"] and "other_group" not in out[wid]


def test_merge_review_decisions_respects_overrides():
    from pubpulse.sync import merge_review_decisions
    ov = {"confirm": {"W1"}, "reject": {"W2"}, "approve_external": set()}
    out = merge_review_decisions(ov, {"W1": {"cds": "no"}, "W2": {"cds": "yes"}, "W3": {"cds": "yes"}, "W4": {"cds": "no"}, "W5": {"cds": ""}})
    assert out["confirm"] == {"W1", "W3"} and out["reject"] == {"W2", "W4"}


def test_journal_metrics_are_cached_and_survive_api_errors(tmp_path):
    from datetime import date
    from pubpulse.sync import add_journal_metrics

    class Client:
        calls = 0
        def sources(self, ids):
            Client.calls += 1
            return [{"id": f"https://openalex.org/{i}", "display_name": "J", "type": "journal" if i == "S1" else "repository",
                     "summary_stats": {"2yr_mean_citedness": 16.7734, "h_index": 132}} for i in ids]

    path = tmp_path / "sources.json"
    works = [{"id": "W1", "source_id": "S1"}, {"id": "W2", "source_id": None}, {"id": "W3", "source_id": "S2"}]
    add_journal_metrics(works, Client(), date(2026, 10, 27), path=path)
    assert works[0]["journal_impact"] == 16.8 and works[0]["journal_h_index"] == 132 and works[1]["journal_impact"] is None
    assert works[2]["journal_impact"] is None  # a repository (Zenodo, medRxiv) has no journal impact
    add_journal_metrics(works, Client(), date(2026, 11, 2), path=path)  # fresh cache: no new lookup
    assert Client.calls == 1

    class Broken:
        def sources(self, ids): raise RuntimeError("429")
    add_journal_metrics(works, Broken(), date(2027, 1, 1), path=path)  # stale but the API fails: keep cached values
    assert works[0]["journal_impact"] == 16.8
