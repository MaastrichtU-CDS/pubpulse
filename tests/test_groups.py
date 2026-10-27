from pubpulse.groups import load_groups, parse_groups_csv, resolve_groups, template_csv

PEOPLE = [
    {"slug": "andre-dekker", "name": "Andre Dekker", "role": "Professor"},
    {"slug": "joshi-hogenboom", "name": "Joshi Hogenboom", "role": "PhD student"},
    {"slug": "leonard-wee", "name": "Leonard Wee", "role": "Assistant Professor"},
]


def test_parse_and_resolve_groups():
    text = "﻿Name,Senior,Group\nAndré Dekker,yes,FAIR data; Federated learning\nJoshi Hogenboom,,Federated learning\nNo Body,x,Ghost\n"
    rows = parse_groups_csv(text)
    assert rows[0] == {"name": "André Dekker", "slug": "", "groups": ["FAIR data", "Federated learning"], "senior": True}
    out = resolve_groups(rows, PEOPLE)
    assert out["seniors"] == ["andre-dekker"] and out["unmatched"] == ["No Body"]
    fed = next(g for g in out["groups"] if g["name"] == "Federated learning")
    assert fed["members"] == ["andre-dekker", "joshi-hogenboom"] and fed["seniors"] == ["andre-dekker"]


def test_load_groups_prefers_csv_then_cache(tmp_path):
    cache = tmp_path / "data" / "groups.json"
    empty = load_groups({}, PEOPLE, tmp_path, cache)
    assert empty["groups"] == [] and empty["source"] is None
    (tmp_path / "groups.csv").write_text("name,group\nLeonard Wee,Imaging\n")
    out = load_groups({"groups": {"edit_url": "https://docs.google.com/x"}}, PEOPLE, tmp_path, cache)
    assert out["source"] == "csv" and out["groups"][0]["members"] == ["leonard-wee"] and out["edit_url"].startswith("https://")
    (tmp_path / "groups.csv").unlink()
    assert load_groups({}, PEOPLE, tmp_path, cache)["groups"][0]["name"] == "Imaging"  # last good copy


def test_template_marks_professors_as_senior():
    lines = template_csv(PEOPLE).splitlines()
    assert lines[0] == "name,slug,role,senior,group"
    assert lines[1].startswith("Andre Dekker,andre-dekker,Professor,yes,Andre Dekker")
    assert "Joshi Hogenboom,joshi-hogenboom,PhD student,," in lines[-1]
