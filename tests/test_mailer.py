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


def test_outgoing_message_keeps_styled_html_and_personal_unsubscribe(monkeypatch):
    from pubpulse.build import build_digest

    messages = []

    class LocalSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, *args):
            pass

        def send_message(self, message):
            messages.append(message)

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", LocalSMTP)
    digest = build_digest({"works": [], "people": [], "last_run": {"date": "2026-10-21"}}, {"site_url": "https://example.org/"})
    unsubscribe = "https://example.org/unsubscribe?token=test-token"
    result = mailer.send_all(
        [{"email": "reader@example.org", "unsubscribe": unsubscribe}],
        digest["subject"], digest["html"], digest["text"],
        "sender@example.org", "test-password", delay=0,
    )
    assert result == (1, 0) and len(messages) == 1
    message = messages[0]
    assert message.get_content_type() == "multipart/alternative"
    outgoing_html = message.get_body(preferencelist=("html",)).get_content()
    assert outgoing_html.rstrip() == mailer.personalise(digest["html"], unsubscribe).rstrip()
    assert f'href="{unsubscribe}"' in outgoing_html
    assert "{{UNSUBSCRIBE_URL}}" not in outgoing_html
    assert unsubscribe in message.get_body(preferencelist=("plain",)).get_content()
    assert message["List-Unsubscribe"] == f"<{unsubscribe}>"
