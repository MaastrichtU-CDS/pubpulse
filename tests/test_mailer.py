from pubpulse import mailer


def test_personalise_and_recipients(monkeypatch):
    monkeypatch.setattr(mailer, "fetch_subscribers", lambda endpoint, key: [{"email": "A@x.org", "token": "t1"}, {"email": "b@x.org", "token": "t2"}])
    recips = mailer.recipients("https://script/exec", "key", "b@x.org, c@x.org", "https://site/")
    assert [r["email"] for r in recips] == ["a@x.org", "b@x.org", "c@x.org"]
    assert recips[0]["unsubscribe"] == "https://script/exec?action=unsubscribe&token=t1"
    assert recips[2]["unsubscribe"] == "https://site/#unsubscribe"
    assert mailer.personalise("bye {{UNSUBSCRIBE_URL}}", "U") == "bye U"


def test_recipients_without_endpoint():
    assert [r["email"] for r in mailer.recipients(None, None, "x@y.org", "https://site/")] == ["x@y.org"]
    assert mailer.recipients(None, None, "", "https://site/") == []


def test_digest_contains_unsubscribe_placeholder():
    from pubpulse.build import build_digest
    pubs = {"generated": "", "people": [], "works": [], "last_run": {"date": "2026-10-21", "baseline": False, "new_ids": [], "needs_review": [], "errors": []}}
    d = build_digest(pubs, {"site_url": "https://s/", "digest": {}})
    assert "{{UNSUBSCRIBE_URL}}" in d["html"] and "{{UNSUBSCRIBE_URL}}" in d["text"]


def test_brevo_campaign_html_uses_brevo_unsubscribe_tag():
    from pubpulse.brevo import campaign_html
    assert campaign_html('<a href="{{UNSUBSCRIBE_URL}}">u</a>') == '<a href="{{ unsubscribe }}">u</a>'
