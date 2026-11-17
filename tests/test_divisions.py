import json

from pubpulse import divisions
from pubpulse.divisions import drop_superseded_preprints, normalise

KEYWORDS = ["maastro", "grow", ["maastricht", "radiation oncology"]]
LEADERS = {"Physics": {"A1"}, "Imaging": {"A2"}}


def authorship(author_id, *affiliations, institution=None):
    return {"author": {"id": f"https://openalex.org/{author_id}", "display_name": author_id},
            "institutions": [{"id": f"https://openalex.org/{institution}", "display_name": "Inst"}] if institution else [],
            "raw_affiliation_strings": list(affiliations)}


def raw_work(work_id, authorships, title="A paper", type_="article"):
    return {"id": f"https://openalex.org/{work_id}", "doi": None, "title": title, "publication_date": "2025-03-01",
            "publication_year": 2025, "type": type_, "primary_location": {"source": {"display_name": "Journal"}},
            "open_access": {"is_oa": True}, "authorships": authorships, "cited_by_count": 4}


def norm(raw, cds_ids=frozenset()):
    return normalise(raw, LEADERS, KEYWORDS, set(cds_ids), "CDS")


def test_any_maastro_author_brings_a_paper_in_scope_without_a_division():
    w = norm(raw_work("W1", [authorship("A8", "Elsewhere"), authorship("A9", "Dept of Radiotherapy (MAASTRO), Maastricht")]))
    assert (w["maastro"], w["divisions"], w["first_author"], w["last_author"]) == (True, [], "A8", "A9")
    # Linked only through OpenAlex's institution record, with no "Maastro" in the text.
    assert norm(raw_work("W2", [authorship("A9", institution="I4210161616")]))["maastro"] is True


def test_division_credit_by_leader_and_cds_membership():
    w = norm(raw_work("W1", [authorship("A2", "GROW, Maastricht University"), authorship("A1", "Maastro")]), cds_ids={"W1"})
    assert w["divisions"] == ["CDS", "Physics", "Imaging"]
    assert w["leaders"] == {"Imaging": {"position": "first", "maastricht": True}, "Physics": {"position": "last", "maastricht": True}}


def test_leader_papers_need_a_maastricht_affiliation_when_no_one_lists_maastro():
    assert norm(raw_work("W1", [authorship("A2", "The Netherlands Cancer Institute")])) is None
    w = norm(raw_work("W2", [authorship("A2", "Radiology, GROW, Maastricht University")]))
    assert (w["maastro"], w["divisions"]) == (False, ["Imaging"])
    assert norm(raw_work("W3", [authorship("A9", "Elsewhere")])) is None


def test_normalise_applies_the_conference_abstract_rule():
    assert norm(raw_work("W1", [authorship("A1", "Maastro")], title="4666 The interplay"))["type"] == "conference-abstract"


def test_preprint_is_dropped_when_its_published_version_is_present():
    works = [{"id": "W1", "title": "Federated learning, at scale", "type": "article"},
             {"id": "W2", "title": "Federated Learning at Scale", "type": "preprint"},
             {"id": "W3", "title": "Only a preprint", "type": "preprint"}]
    assert [w["id"] for w in drop_superseded_preprints(works)] == ["W1", "W3"]


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.queries = []

    def authors_by_orcid(self, orcid):
        return [{"id": "https://openalex.org/A1"}, {"id": "https://openalex.org/A3"}]

    def works(self, filter_expr, select=None):
        if self.fail:
            raise ConnectionError("OpenAlex down")
        self.queries.append(filter_expr)
        # The same work comes back from every query; it must be stored once.
        yield raw_work("W1", [authorship("A1", "Maastro")])
        yield raw_work("W2", [authorship("A9", "Maastro")], type_="erratum")


def write_config(tmp_path):
    config = tmp_path / "config.yml"
    config.write_text("since_year: 2024\nexclude_types: [erratum]\nmaastro_divisions:\n"
                      "  - {division: Physics, leader: P, orcid: 0000-0000-0000-0001}\n", encoding="utf-8")
    return config


def test_run_deduplicates_across_queries(tmp_path):
    out, client = tmp_path / "divisions.json", FakeClient()
    assert divisions.run(write_config(tmp_path), out, client, tmp_path / "none.json") == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [w["id"] for w in data["works"]] == ["W1"]  # once, erratum excluded
    assert data["divisions"][0]["openalex_ids"] == ["A1", "A3"]
    assert any("raw_affiliation_strings.search:maastro" in q for q in client.queries)
    assert any("authorships.author.id:A1|A3" in q for q in client.queries)


def test_run_keeps_last_weeks_file_when_openalex_fails(tmp_path):
    out = tmp_path / "divisions.json"
    out.write_text('{"works": ["old"]}', encoding="utf-8")
    assert divisions.run(write_config(tmp_path), out, FakeClient(fail=True), tmp_path / "none.json") == 1
    assert json.loads(out.read_text(encoding="utf-8")) == {"works": ["old"]}


def test_leads_are_labelled_for_division_leaders_and_frequent_maastro_last_authors():
    from pubpulse.divisions import label_leads
    divs = [{"division": "Physics", "leader": "Frank Verhaegen"}]
    def work(i, last, maastro=True, division=()):
        return {"id": f"W{i}", "last_author": last, "last_author_home": maastro, "divisions": list(division)}
    works = [work(1, "Liesbeth J. Boersma"), work(2, "Liesbeth Jorinne Boersma"), work(3, "Liesbeth J. Boersma", division=["Physics"]),
             work(4, "Frank Verhaegen", division=["Physics"]), work(5, "Once Only"), work(6, "Away Author", maastro=False),
             work(7, "Away Author", maastro=False)]
    frequent = label_leads(works, divs, minimum=2)
    assert [f["name"] for f in frequent] == ["Liesbeth J. Boersma"]  # one person under two spellings
    assert frequent[0] | {} == {"name": "Liesbeth J. Boersma", "papers": 3, "unidentified": 2, "divisions": {"Physics": 1}}
    assert [w.get("led_by") for w in works] == ["Liesbeth J. Boersma"] * 3 + ["Frank Verhaegen", None, None, None]
    assert works[3]["led_by_division"] == "Physics"
