from datetime import date

from pubpulse.members import apply_members, in_period, parse_date, parse_members_csv, template_csv


def test_parse_dates():
    assert parse_date("2026-03-01") == "2026-03-01" and parse_date("01-03-2026") == "2026-03-01"
    assert parse_date("2026-03") == "2026-03-01" and parse_date("2026-03", end=True) == "2026-03-31"
    assert parse_date("2025", end=True) == "2025-12-31" and parse_date("") is None


def test_csv_and_apply_and_period():
    csv = "Name,Start date,End,Note\nAnn A,2025-09,,\nBob B,2024-01-15,2025-06-30,left for IKNL\nNew Person,2026-01,,external\n"
    rows = parse_members_csv(csv)
    assert rows[0]["start"] == "2025-09-01" and rows[1]["end"] == "2025-06-30"
    people = [{"slug": "ann-a", "name": "Ann A", "active_until": None, "source": "staff_page"},
              {"slug": "bob-b", "name": "Bob B", "active_until": None, "source": "staff_page"}]
    ch = apply_members(people, rows, date(2026, 10, 23))
    by = {p["slug"]: p for p in people}
    assert by["ann-a"]["member_from"] == "2025-09-01" and by["bob-b"]["active_until"] == "2025-06-30"
    assert ch["added"] == ["new-person"] and by["new-person"]["needs_review"]
    assert not in_period(by["ann-a"], "2025-03-01") and in_period(by["ann-a"], "2026-02-01")
    assert in_period(by["bob-b"], "2025-01-01") and not in_period(by["bob-b"], "2025-09-01") and in_period(by["bob-b"], "2025-09-01", grace_months=6)
    assert in_period({"slug": "x", "name": "X", "active_until": None}, "2024-05-05")          # current member, no dates
    assert not in_period({"slug": "y", "name": "Y", "status": "former"}, "2024-05-05")        # former without dates
    assert "Ann A" in template_csv(people)
