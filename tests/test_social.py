from pubpulse.social import eligible, parse_output, user_message


def test_eligibility_excludes_preprints_and_unverified():
    base = {"verified": True, "type": "article", "abstract": "x"}
    assert eligible(base)
    assert not eligible({**base, "type": "preprint"})
    assert not eligible({**base, "verified": False})
    assert not eligible({**base, "abstract": None})


def test_parse_output_sections():
    text = "### POST\nLine one.\n\nPublished in J.\n\n### COMMENT\nPaper: https://doi.org/x\n\n### SHORT\nShort one. https://doi.org/x"
    out = parse_output(text)
    assert out["post"].startswith("Line one.") and out["post"].endswith("Published in J.")
    assert out["comment"] == "Paper: https://doi.org/x" and out["short"] == "Short one. https://doi.org/x"
    assert parse_output("no headings")["post"] == "no headings"


def test_user_message_contains_facts():
    w = {"id": "W1", "title": "T", "journal": "J", "publication_date": "2026-10-01", "type": "article",
         "group_members": ["a"], "authors": ["X", "Y"], "author_count": 2, "doi": "https://doi.org/1", "oa_url": None, "abstract": "ABS"}
    m = user_message(w, {"a": "Ann A"})
    assert "Ann A" in m and "https://doi.org/1" in m and "ABS" in m and "Open-access link: none" in m
