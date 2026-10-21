from pubpulse.scholar import compare, norm


def test_compare_matches_fuzzy_and_flags_attribution():
    works = [
        {"id": "W1", "title": "Developing an ICD-10 Coding Assistant: Pilot Study Using RoBERTa and GPT-4", "group_members": ["sp"]},
        {"id": "W2", "title": "Natural language processing in oncology", "group_members": ["other"]},
    ]
    articles = [
        {"title": "Developing an ICD-10 coding assistant: pilot study using RoBERTa and GPT-4 for term extraction", "year": 2025, "link": "l", "venue": "JMIR"},
        {"title": "Natural Language Processing in Oncology", "year": 2024, "link": None, "venue": None},
        {"title": "Pushing the boundaries: a Danish semantic tagger", "year": 2025, "link": None, "venue": "CL2025"},
        {"title": "Old paper", "year": 2019, "link": None, "venue": None},
        {"title": "rectalcancerpatients", "year": None, "link": None, "venue": None},
    ]
    r = compare(articles, works, "sp", since_year=2024)
    assert r["checked"] == 3 and r["matched"] == 1
    assert [x["pubpulse_id"] for x in r["not_attributed"]] == ["W2"]
    assert [x["title"] for x in r["missing"]] == ["Pushing the boundaries: a Danish semantic tagger"]
    assert norm("A, B: c!") == "a b c"


def test_compare_prefix_match():
    works = [{"id": "W1", "title": "Harmonized steps", "group_members": ["sp"]}]
    articles = [{"title": "Harmonized steps: Orchestrating healthcare transformation with natural language processing", "year": 2024, "link": None, "venue": None}]
    r = compare(articles, works, "sp", since_year=2024)
    assert r["matched"] == 1 and not r["missing"]  # 16-char prefix: accepted
    works[0]["title"] = "Radiomics"
    r = compare(articles, works, "sp", since_year=2024)
    assert r["matched"] == 0 and len(r["missing"]) == 1  # too short to be a safe prefix
    works[0]["title"] = "Developing an ICD-10 coding assistant"
    articles[0]["title"] = "Developing an ICD-10 coding assistant: pilot study using RoBERTa and GPT-4"
    r = compare(articles, works, "sp", since_year=2024)
    assert r["matched"] == 1 and not r["missing"]


def test_compare_recognises_identified_coauthors_outside_strict_attribution():
    works = [{"id": "W1", "title": "A clinical collaboration", "group_members": ["other"], "author_members": ["sp", "other"]}]
    articles = [{"title": "A clinical collaboration", "year": 2026, "link": None, "venue": None}]
    result = compare(articles, works, "sp", since_year=2024)
    assert result["matched"] == 1 and not result["not_attributed"]
