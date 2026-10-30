from datetime import date
from pathlib import Path

from pubpulse.staff import is_active, merge_people, parse_profile, parse_staff_page

FIX = Path(__file__).parent / "fixtures"


def test_parse_staff_page_sections_and_fields():
    people = parse_staff_page((FIX / "staff.html").read_text(encoding="utf-8"))
    current = [p for p in people if p["section"] == "current"]
    previous = [p for p in people if p["section"] == "previous"]
    assert len(current) == 61
    assert len(previous) == 88
    sp = next(p for p in current if p["slug"] == "sander-puts")
    assert sp["name"] == "Sander Puts" and sp["role"] == "Researcher" and sp["employer"] == "Maastro"
    assert sp["profile_url"] == "https://www.clinicaldatascience.nl/sander-puts"
    jvs = next(p for p in current if p["slug"] == "johan-van-soest")
    assert jvs["profile_url"].endswith("/Staff/johan-van-soest")


def test_parse_profile_extracts_ids():
    prof = parse_profile((FIX / "profile-johan-van-soest.html").read_text(encoding="utf-8"))
    assert prof["orcid"] == "0000-0003-2548-0330"
    assert prof["scholar_id"] == "zemi8wYAAAAJ"
    assert prof["cris_url"].startswith("https://cris.maastrichtuniversity.nl/")


def _scraped(slug, section="current", **kw):
    d = {"section": section, "slug": slug, "name": slug.replace("-", " ").title(), "profile_url": f"https://x/{slug}",
         "role": "PhD student", "employer": "UM", "orcid": None, "scholar_id": None, "cris_url": None}
    d.update(kw)
    return d


def test_merge_adds_deactivates_reactivates_and_keeps_manual_fields():
    today = date(2026, 10, 21)
    existing = [
        {"slug": "a", "name": "A", "orcid": "0000-0001-0000-0001", "openalex_id": "A1", "source": "staff_page", "active_from": "2026-01-01", "active_until": None},
        {"slug": "b", "name": "B", "orcid": None, "openalex_id": "A2", "source": "staff_page", "active_from": "2026-01-01", "active_until": None},
        {"slug": "c", "name": "C", "orcid": None, "openalex_id": None, "source": "staff_page", "active_from": "2025-01-01", "active_until": "2026-01-01"},
        {"slug": "m", "name": "Manual", "orcid": "0000-0001-0000-0009", "source": "manual", "active_from": "2026-01-01", "active_until": None},
    ]
    scraped = [_scraped("a", orcid="0000-0001-0000-0001"), _scraped("c"), _scraped("d", orcid="0000-0001-0000-0004"), _scraped("b", section="previous")]
    people, changes = merge_people(existing, scraped, ["current"], today)
    by = {p["slug"]: p for p in people}
    assert changes["added"] == ["d"] and by["d"]["orcid"] == "0000-0001-0000-0004" and by["d"]["active_from"] == "2026-10-21"
    assert changes["deactivated"] == ["b"] and by["b"]["active_until"] == "2026-10-21" and by["b"]["section"] == "previous"
    assert by["b"]["openalex_id"] == "A2"  # manual field preserved
    assert changes["reactivated"] == ["c"] and by["c"]["active_until"] is None
    assert by["m"]["active_until"] is None  # manual entries never deactivated
    assert by["a"]["openalex_id"] == "A1" and by["a"]["role"] == "PhD student"
    assert is_active(by["d"], today) and not is_active(by["b"], today)


def test_merge_refuses_tiny_scrape():
    existing = [{"slug": "a", "name": "A", "source": "staff_page", "active_until": None}]
    people, changes = merge_people(existing, [_scraped("z")], ["current"], date(2026, 10, 21), min_people=3)
    assert changes["skipped"] is True and people[0]["active_until"] is None


def test_grace_period_tracking():
    from pubpulse.staff import add_months, is_tracked, tracked_until
    left = {"slug": "x", "name": "X", "active_until": "2026-01-31"}
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert tracked_until(left, 18) == date(2027, 7, 31)
    assert is_tracked(left, date(2027, 7, 31), 18) and not is_tracked(left, date(2027, 8, 1), 18)
    assert not is_active(left, date(2026, 6, 1))
    assert is_tracked({"slug": "a", "name": "A", "active_until": None}, date(2030, 1, 1), 0)


def test_fetch_staff_skips_recently_checked_profiles(monkeypatch):
    import pubpulse.staff as st
    from pathlib import Path
    html = (Path(__file__).parent / "fixtures" / "staff.html").read_text(encoding="utf-8")
    prof = (Path(__file__).parent / "fixtures" / "profile-johan-van-soest.html").read_text(encoding="utf-8")
    calls = []

    class R:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass

    class S:
        headers = {}
        def get(self, url, timeout=0):
            calls.append(url)
            return R(html if url.endswith("/staff") else prof)

    monkeypatch.setattr(st.time, "sleep", lambda s: None)
    known = {"sander-puts": {"profile_checked_at": "2026-10-15"}, "johan-van-soest": {"profile_checked_at": "2026-01-01"}}
    people = st.fetch_staff("https://www.clinicaldatascience.nl/staff", ["current"], session=S(), known=known, today=date(2026, 10, 21), profile_refresh_days=30)
    assert calls[0].endswith("/staff")
    assert not any(u.endswith("/sander-puts") for u in calls)          # checked 6 days ago: skipped
    assert any(u.endswith("/Staff/johan-van-soest") for u in calls)     # stale: fetched
    jvs = next(p for p in people if p["slug"] == "johan-van-soest")
    assert jvs["orcid"] == "0000-0003-2548-0330" and jvs["_profile_fetched"]
    assert len(calls) == 1 + 60  # 61 current minus the one skipped



def test_in_period_follows_the_staff_page():
    from pubpulse.staff import in_period
    assert in_period({"slug": "x", "name": "X", "active_until": None}, "2024-05-05")          # current member
    assert not in_period({"slug": "y", "name": "Y", "status": "former"}, "2024-05-05")        # former, never seen leaving
    left = {"slug": "b", "name": "B", "active_until": "2025-06-30"}
    assert in_period(left, "2025-01-01") and not in_period(left, "2025-09-01") and in_period(left, "2025-09-01", grace_months=6)
