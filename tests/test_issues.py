from pubpulse.issues import apply_identifiers, parse_issue_body

BODY = """### Your name, exactly as on the staff page

Sander  Puts

### ORCID

https://orcid.org/0000-0003-4148-1755

### Google Scholar profile link

https://scholar.google.com/citations?user=NxRF8PIAAAAJ&hl=en

### OpenAlex author id(s)

A5089485363, a5112986579

### Anything else

_No response_
"""


def test_parse_and_apply():
    form = parse_issue_body(BODY)
    assert form["name"] == "Sander  Puts" and form["note"] == ""
    people = [{"slug": "sander-puts", "name": "Sander Puts", "orcid": None, "openalex_ids": ["A1"], "needs_review": True},
              {"slug": "sander-x", "name": "Sander Xander", "orcid": None}]
    changed, msg = apply_identifiers(people, form)
    p = people[0]
    assert changed and p["orcid"] == "0000-0003-4148-1755" and p["scholar_id"] == "NxRF8PIAAAAJ"
    assert p["openalex_id"] == ["A5089485363", "A5112986579"] and "openalex_ids" not in p and p["needs_review"] is False
    assert "Applied to **Sander Puts**" in msg


def test_ambiguous_or_unknown_name():
    people = [{"slug": "a", "name": "Ali Zaila"}, {"slug": "b", "name": "Ali Al Zein"}]
    changed, msg = apply_identifiers(people, {"name": "Ali", "orcid": "0000-0001-0000-0001"})
    assert not changed and "could not match" in msg
    changed, msg = apply_identifiers(people, {"name": "Nobody Here", "orcid": "0000-0001-0000-0001"})
    assert not changed


def test_bad_values_are_reported_not_applied():
    people = [{"slug": "a", "name": "Ali Zaila"}]
    changed, msg = apply_identifiers(people, {"name": "ali zaila", "orcid": "12345", "scholar": "nonsense!"})
    assert not changed and "does not look like an ORCID" in msg and "not understood" in msg
