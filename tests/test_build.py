import xml.etree.ElementTree as ET
from html import escape

from pubpulse.build import build_digest, build_feed

CFG = {"group_name": "CDS", "site_url": "https://example.org/pubpulse/", "digest": {"subject_prefix": "pubpulse", "teams_max_items": 2}}


def _pubs(n_new):
    works = [
        {"id": f"W{i}", "openalex_url": f"https://openalex.org/W{i}", "doi": f"https://doi.org/10.1/{i}", "title": f"Paper {i} <b>",
         "publication_date": f"2026-10-{10 + i:02d}", "year": 2026, "type": "article", "journal": "J", "landing_url": None,
         "is_oa": False, "oa_url": None, "authors": ["A"], "author_count": 1, "group_members": ["p1"], "verified": i % 2 == 0, "counted": i < 4,
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
    assert d0["new_count"] == 0 and "0 new publications" in d0["subject"] and "Nothing new since the last newsletter" in d0["html"]
    d1 = build_digest(_pubs(1), CFG)
    assert "1 new publication ·" in d1["subject"] and "published 10 October 2026" in d1["html"] and "Paper 0 &lt;b&gt;" in d1["html"]
    d5 = build_digest(_pubs(5), CFG)
    # team-window rule: the uncounted W4 is not listed, only mentioned in one note
    assert d5["new_count"] == 4 and "Person One (4)" in d5["html"] and "Paper 4" not in d5["html"]
    pubs = _pubs(2)
    pubs["works"][0]["type"] = "dataset"  # data deposits stay on the website only
    assert build_digest(pubs, CFG)["new_count"] == 1
    assert "1 staff profile" in d5["text"] and "#coverage-notes" in d5["html"]  # needs_review as a count, no name list
    card = d5["teams"]["attachments"][0]["content"]
    assert card["type"] == "AdaptiveCard" and any("and 2 more" in b.get("text", "") for b in card["body"])


def test_digest_baseline_sends_nothing():
    pubs = _pubs(5)
    pubs["last_run"]["baseline"] = True
    assert build_digest(pubs, CFG)["new_count"] == 0


def test_site_build_uses_current_mailing_list_settings(tmp_path, monkeypatch):
    import json
    from pubpulse import build

    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<!doctype html><title>pubpulse</title>")
    assets = site / "assets"
    assets.mkdir()
    (assets / "pubpulse.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    data = tmp_path / "data"
    data.mkdir()
    pubs = _pubs(0)
    pubs["list"] = {"subscribe_url": "https://example.org/old-list"}
    monkeypatch.setattr(build, "SITE_DIR", site)
    monkeypatch.setattr(build, "DATA_DIR", data)
    monkeypatch.setattr(build, "DIST_DIR", tmp_path / "dist")
    monkeypatch.setattr(build, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(build, "load_publications", lambda: pubs)

    # A config-only change must work without fetching publications again.
    for digest in [
        {"subscribe_endpoint": "", "subscribe_form_url": "https://example.org/join", "list_name": "CDS digest"},
        {},
    ]:
        monkeypatch.setattr(build, "load_config", lambda: {**CFG, "digest": digest})
        build.run()
        result = json.loads((build.DIST_DIR / "data" / "publications.json").read_text())
        assert result["list"] == {key: digest.get(key, "") for key in ("subscribe_endpoint", "subscribe_form_url", "list_name")}
        assert result["works"] == pubs["works"]
        assert (build.DIST_DIR / "assets" / "pubpulse.svg").exists()
    assert pubs["list"]["subscribe_url"] == "https://example.org/old-list"


def test_new_works_includes_pending_from_earlier_runs():
    from pubpulse.build import new_works
    pubs = _pubs(1)
    assert [w["id"] for w in new_works(pubs)] == ["W0"]
    assert sorted(w["id"] for w in new_works(pubs, ["W3", "W4", "W999"])) == ["W0", "W3", "W4"]


def test_site_build_cache_busts_assets(tmp_path, monkeypatch):
    import json
    import shutil
    from pubpulse import build
    site = tmp_path / "site"; shutil.copytree(build.SITE_DIR, site)
    data = tmp_path / "data"; data.mkdir()
    (data / "publications.json").write_text(json.dumps({"works": [], "people": [], "last_run": None}))
    monkeypatch.setattr(build, "SITE_DIR", site); monkeypatch.setattr(build, "DATA_DIR", data)
    monkeypatch.setattr(build, "DIST_DIR", tmp_path / "dist"); monkeypatch.setattr(build, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(build, "load_publications", lambda: {"works": [], "people": [], "last_run": None})
    monkeypatch.setattr(build, "load_config", lambda: CFG)
    build.run()
    html = (build.DIST_DIR / "index.html").read_text()
    assert 'src="app.js?v=' in html and 'href="style.css?v=' in html


def test_digest_separates_news_from_backfill():
    from pubpulse.build import build_digest, split_recent
    pubs = _pubs(5)
    for i, w in enumerate(pubs["works"]):
        w["publication_date"] = "2026-10-20" if i < 2 else "2025-03-12"
    recent, older = split_recent(pubs["works"], 120, "2026-10-21")
    assert [w["id"] for w in recent] == ["W0", "W1"] and len(older) == 3
    d = build_digest(pubs, {**CFG, "digest": {"recent_days": 120}})
    assert d["new_count"] == 2 and "2 new publications" in d["subject"]
    # older papers that only now got linked are not news: not listed, not even counted
    assert "older" not in d["html"] and not any(escape(w["title"]) in d["html"] or w["title"] in d["text"] for w in older)
    assert all(escape(w["title"]) in d["html"] for w in recent)


def test_digest_lists_last_week_first_then_earlier_papers_in_their_own_section():
    from pubpulse.build import build_digest
    pubs = _pubs(4)
    for w, day in zip(pubs["works"], ["2026-10-01", "2026-10-18", "2026-08-01", "2026-10-15"]):
        w["publication_date"] = day
    d = build_digest(pubs, {**CFG, "digest": {"recent_days": 30}})
    assert d["new_count"] == 3  # W2 (August) is older than 30 days: left out
    html_body = d["html"]
    week, earlier = html_body.index("Published last week"), html_body.index("Published earlier, only now listed")
    assert week < html_body.index("Paper 1", week) < html_body.index("Paper 3", week) < earlier < html_body.index("Paper 0", week)
    assert "Paper 2" not in html_body and "2 published last week, 1 published earlier" in html_body
    assert d["text"].index("PUBLISHED LAST WEEK") < d["text"].index("PUBLISHED EARLIER") < d["text"].index("Paper 0")
    titles = [b["text"] for b in d["teams"]["attachments"][0]["content"]["body"]]
    assert titles.index("Published last week") < titles.index("Published earlier, only now listed")


def test_digest_lists_papers_with_another_institution_in_their_own_section():
    from pubpulse.build import build_digest
    pubs = _pubs(3)
    for w in pubs["works"][:3]:
        w["publication_date"] = "2026-10-18"
    pubs["works"][0].update(counted=False, listed_elsewhere=True, affiliation_status={"p1": "mismatch"},
                            member_affiliations={"p1": ["Other Institute", "Dept X, Other Institute"]})
    d = build_digest(pubs, {**CFG, "digest": {"recent_days": 30}})
    body = d["html"]
    week, other = body.index("Published last week"), body.index("Also by team members, with another group or affiliation")
    assert week < body.index("Paper 1", week) < body.index("Paper 2", week) < other < body.index("Paper 0", week)
    assert "Person One (Other Institute)" in body and "Person One (Other Institute)" in d["text"]
    assert "2 published last week, 1 with another group or affiliation" in body and d["new_count"] == 3
    assert "Paper 0" not in d["subject"]


def test_digest_preview_uses_the_issue_day_like_the_monday_send():
    from pubpulse.build import build_digest
    pubs = _pubs(2)
    pubs["works"][0]["publication_date"] = "2026-10-15"  # last week seen from the 21st, not from Monday the 26th
    pubs["works"][1]["publication_date"] = "2026-09-23"  # within 30 days of the 21st, not of the 26th
    preview = build_digest(pubs, {**CFG, "digest": {"recent_days": 30}}, issue_date="2026-10-26")
    monday = build_digest({**pubs, "last_run": {**pubs["last_run"], "date": "2026-10-26"}}, {**CFG, "digest": {"recent_days": 30}})
    assert preview["html"] == monday["html"] and preview["new_count"] == monday["new_count"] == 1
    assert "Published earlier, only now listed" in preview["html"] and "Published last week" not in preview["html"]


def test_digest_page_previews_queue_and_lists_sent_digests(tmp_path):
    from pubpulse.build import archive_digest, write_digest_pages
    digests = tmp_path / "digests"
    archive_digest("<div>sent mail <a href='{{UNSUBSCRIBE_URL}}'>x</a></div>", "2026-10-19", digests)
    dist = tmp_path / "dist"; dist.mkdir()
    pubs = _pubs(3)  # last_run.new_ids are ignored: the preview shows the queue only
    write_digest_pages(pubs, CFG, ["W1"], dist, digests)
    page = (dist / "digest.html").read_text()
    assert "Preview of the issue" in page and "Monday 26 October 2026" in page
    assert "Paper 1 &lt;b&gt;" in page and "Paper 0" not in page
    assert 'href="digests/2026-10-19.html"' in page and "{{UNSUBSCRIBE_URL}}" not in page
    assert "sent mail" in (dist / "digests" / "2026-10-19.html").read_text()
    write_digest_pages(pubs, CFG, [], dist, digests)
    page = (dist / "digest.html").read_text()  # nothing queued: the last sent issue is the current one
    assert "Sent <b>Monday 19 October 2026</b>" in page and "sent mail" in page


def test_digest_is_a_standalone_email_with_absolute_png_images(monkeypatch):
    from html.parser import HTMLParser
    from pubpulse import build

    monkeypatch.setattr(build, "_draft_for", lambda w: {
        "headline": "A clearer research headline", "short": "A summary & its implications.",
        "card": "data/social/images/W0-card.png", "post": "Ready to share",
    })
    digest = build.build_digest(_pubs(1), CFG)

    class Images(HTMLParser):
        def __init__(self):
            super().__init__()
            self.sources = []

        def handle_starttag(self, tag, attrs):
            if tag == "img":
                self.sources.append(dict(attrs)["src"])

    images = Images()
    images.feed(digest["html"])
    assert digest["html"].lower().startswith("<!doctype html>")
    assert '<html lang="en">' in digest["html"] and '<meta name="viewport"' in digest["html"]
    assert len(images.sources) == 5  # CDS, paper graphic, and three partner logos
    assert all(src.startswith(CFG["site_url"]) and src.endswith(".png") for src in images.sources)
    assert f'{CFG["site_url"]}social.html?id=W0' in digest["html"]
    assert "A summary &amp; its implications." in digest["html"]
    assert "{{UNSUBSCRIBE_URL}}" in digest["html"]


def test_full_email_archives_embed_without_nested_documents(tmp_path):
    from pubpulse.build import archive_digest, write_digest_pages

    pubs = _pubs(1)
    digest = build_digest(pubs, CFG)
    digests = tmp_path / "digests"
    archive_digest(digest["html"], "2026-10-19", digests)
    dist = tmp_path / "dist"
    dist.mkdir()
    write_digest_pages(pubs, CFG, [], dist, digests)
    for filename, prefix in (("digest.html", "./"), ("digests/2026-10-19.html", "../")):
        page = (dist / filename).read_text()
        assert page.count("<!doctype html>") == 1 and page.count('<html lang="en">') == 1
        assert page.count("<body") == 1 and page.count("</body>") == 1
        assert f'src="{prefix}assets/cds-email.png"' in page
        assert f'href="{prefix}#unsubscribe"' in page
        assert 'href="https://doi.org/10.1/0"' in page
        assert "{{UNSUBSCRIBE_URL}}" not in page
        assert 'digest.css?v=' in page
        assert "@media only screen" in page  # preserve the email's responsive styling
