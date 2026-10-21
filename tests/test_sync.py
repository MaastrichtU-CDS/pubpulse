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
