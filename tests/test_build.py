import xml.etree.ElementTree as ET

from pubpulse.build import build_digest, build_feed

CFG = {"group_name": "CDS", "site_url": "https://example.org/pubpulse/", "digest": {"subject_prefix": "pubpulse", "teams_max_items": 2}}


def _pubs(n_new):
    works = [
        {"id": f"W{i}", "openalex_url": f"https://openalex.org/W{i}", "doi": f"https://doi.org/10.1/{i}", "title": f"Paper {i} <b>",
         "publication_date": f"2026-10-{10 + i:02d}", "year": 2026, "type": "article", "journal": "J", "landing_url": None,
         "is_oa": False, "oa_url": None, "authors": ["A"], "author_count": 1, "group_members": ["p1"], "verified": i % 2 == 0,
         "affiliation_status": {"p1": "verified" if i % 2 == 0 else "unknown"}, "member_affiliations": {"p1": []}, "cited_by_count": 0, "abstract": None, "first_seen": "2026-10-21"}
        for i in range(5)
    ]
    return {"generated": "2026-10-21T06:00:00+00:00", "people": [{"slug": "p1", "name": "Person One"}], "works": works,
            "last_run": {"date": "2026-10-21", "baseline": False, "new_ids": [f"W{i}" for i in range(n_new)], "needs_review": ["p2"], "errors": []}}


def test_feed_is_valid_atom():
    xml = build_feed(_pubs(2), CFG, max_items=3)
    root = ET.fromstring(xml)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    assert len(root.findall("a:entry", ns)) == 3
    assert "Paper" in root.find("a:entry/a:title", ns).text


def test_digest_zero_one_many():
    d0 = build_digest(_pubs(0), CFG)
    assert d0["new_count"] == 0 and "0 new publications" in d0["subject"] and "Nothing new" in d0["html"]
    d1 = build_digest(_pubs(1), CFG)
    assert "1 new publication this week" in d1["subject"] and "Paper 0 &lt;b&gt;" in d1["html"]
    d5 = build_digest(_pubs(5), CFG)
    assert d5["new_count"] == 5 and "Person One (5)" in d5["html"]
    assert "not verified" in d5["html"] and "not verified" in d5["text"]
    assert "p2" in d5["text"]  # needs_review mentioned
    card = d5["teams"]["attachments"][0]["content"]
    assert card["type"] == "AdaptiveCard" and any("and 3 more" in b.get("text", "") for b in card["body"])


def test_digest_baseline_sends_nothing():
    pubs = _pubs(5)
    pubs["last_run"]["baseline"] = True
    assert build_digest(pubs, CFG)["new_count"] == 0
