from datetime import date

from pubpulse.former import review_former
from pubpulse.staff import is_active, is_tracked, merge_people, tracked_until
from pubpulse.sync import fetch_works, normalise_work, public_people

TODAY = date(2026, 10, 21)


def people():
    return [
        {"slug": "current", "name": "Current Researcher", "section": "current", "orcid": "0000-0001-0000-0001", "openalex_ids": ["A1"]},
        {"slug": "former", "name": "Alice Marie Alumni", "section": "previous", "active_until": None},
        {"slug": "old", "name": "Old Collaborator", "section": "previous", "active_until": "2019-01-01"},
        {"slug": "none", "name": "No Evidence", "section": "previous"},
    ]


def work(wid="W1", published="2026-10-07", members=None, authors=None):
    return {"id": wid, "title": "A CDS collaboration", "publication_date": published, "group_members": ["current"] if members is None else members,
            "authors": authors or ["Alice Alumni", "Current Researcher"], "author_members": [None, "current"], "author_positions": [1, 2], "doi": "https://doi.org/10.1/example"}


def test_all_former_staff_are_reviewed_and_recent_collaborations_extend_followup():
    roster = people()
    works = [work(), work("W2", "2024-01-01", authors=["Old Collaborator", "Current Researcher"])]
    report = review_former(roster, works, TODAY)
    assert report["former_staff_reviewed"] == 3
    assert report["with_collaborations"] == 2
    assert report["with_recent_collaborations"] == 1
    person = roster[1]
    assert works[0]["author_members"][0] == "former"
    assert person["publication_name_aliases"] == ["Alice Alumni"]
    assert person["active_until"] is None
    assert not is_active(person, TODAY)
    assert is_tracked(person, TODAY, 18)
    assert tracked_until(person, 18) == date(2028, 10, 7)
    assert not is_tracked(person, date(2028, 10, 8), 18)
    assert not is_tracked(roster[2], TODAY, 18)
    assert report["people"]["none"]["status"] == "no_collaboration_found_in_collection"
    exported = public_people(roster, TODAY, 18)
    assert exported[1]["former"] and not exported[1]["active"]
    assert exported[3]["tracked_until"] is None


def test_name_matches_require_a_current_coauthor_and_unique_first_last_names():
    roster = people() + [{"slug": "namesake", "name": "Alice Other Alumni", "section": "previous"}]
    works = [work(), work("W2", members=[], authors=["Old Collaborator", "Someone Else"])]
    works[1]["author_members"] = [None, None]
    report = review_former(roster, works, TODAY)
    assert works[0]["author_members"][0] is None
    assert report["with_recent_collaborations"] == 0


def test_future_papers_do_not_extend_followup_and_cutoff_is_inclusive():
    roster = people()
    report = review_former(roster, [work("W1", "2026-11-01"), work("W2", "2024-10-21")], TODAY)
    summary = report["people"]["former"]
    assert summary["shared_papers"] == 2 and summary["recent_shared_papers"] == 1
    assert summary["last_collaboration_date"] == "2024-10-21"


def test_imported_former_staff_are_not_given_an_invented_departure_date():
    roster = [{"slug": "current", "name": "Current Researcher", "source": "staff_page", "section": "current", "active_until": None}]
    scraped = [{"slug": "current", "name": "Current Researcher", "section": "current"}, {"slug": "former", "name": "Alice Alumni", "section": "previous"}]
    merged, _ = merge_people(roster, scraped, ["current"], TODAY, min_people=1)
    person = next(p for p in merged if p["slug"] == "former")
    assert person["active_until"] is None and person["active_from"] is None
    assert person["former_observed_at"] == TODAY.isoformat()
    assert not is_active(person, TODAY) and not is_tracked(person, TODAY, 18)


def test_observed_name_aliases_are_used_by_future_work_syncs():
    roster = people()
    review_former(roster, [work()], TODAY)
    raw = {"id": "https://openalex.org/W1", "authorships": [
        {"author": {"id": "https://openalex.org/A2", "display_name": "Alice Alumni"}},
        {"author": {"id": "https://openalex.org/A1", "display_name": "Current Researcher"}},
    ]}
    assert normalise_work(raw, roster, ["maastro"])["author_members"] == ["former", "current"]


def test_new_collaborations_reopen_identifier_discovery():
    roster = people()
    roster[1]["identifier_discovery_checked_at"] = TODAY.isoformat()
    roster[1]["former_collaboration"] = {"last_collaboration_date": "2025-01-01"}
    review_former(roster, [work()], TODAY)
    assert "identifier_discovery_checked_at" not in roster[1]


def test_alumni_followup_collects_current_collaborations_beyond_departure_grace():
    roster = people()
    former = roster[1]
    former.update({"active_until": "2019-01-01", "openalex_ids": ["A2"], "former_collaboration": {"followup_until": "2028-10-07"}})
    shared = {"id": "https://openalex.org/W1", "type": "article", "authorships": [
        {"author": {"id": "https://openalex.org/A2", "display_name": "Alice Marie Alumni"}, "institutions": [{"display_name": "Another University"}]},
        {"author": {"id": "https://openalex.org/A1", "display_name": "Current Researcher"}, "institutions": [{"display_name": "Maastro"}]},
    ]}
    unrelated = {**shared, "id": "https://openalex.org/W2", "authorships": shared["authorships"][:1]}
    class Client:
        def works(self, query, **kwargs):
            if "A2" in query:
                assert "authorships.author.id:A2,authorships.author.id:A1" in query
            return [shared, unrelated] if "A2" in query else []
    works, errors = fetch_works(roster, Client(), 2024, TODAY, keywords=["maastro"], grace_months=18)
    assert not errors and set(works) == {"W1"}
    assert works["W1"]["author_members"] == ["former", "current"]
    assert works["W1"]["group_members"] == ["current"]
