"""Send the weekly digest to the subscriber list (Apps Script endpoint) over Gmail SMTP, one mail per subscriber."""

from __future__ import annotations

import logging
import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

import requests

from .sync import OUT_DIR, load_config

log = logging.getLogger(__name__)
UNSUB_PLACEHOLDER = "{{UNSUBSCRIBE_URL}}"


def fetch_subscribers(endpoint: str, key: str, timeout: int = 60) -> list[dict]:
    """GET <endpoint>?action=list&key=... from the Apps Script web app. Returns [{email, token}, ...]."""
    resp = requests.get(endpoint, params={"action": "list", "key": key}, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"subscriber endpoint refused: {data.get('error')}")
    return [s for s in data.get("subscribers", []) if s.get("email")]


def recipients(endpoint: str | None, key: str | None, static_to: str | None, site_url: str) -> list[dict]:
    """Subscribers from the list plus optional fixed addresses (DIGEST_TO), each with its unsubscribe url."""
    out: list[dict] = []
    seen: set[str] = set()
    if endpoint and key:
        for s in fetch_subscribers(endpoint, key):
            e = s["email"].lower()
            if e not in seen:
                seen.add(e)
                out.append({"email": e, "unsubscribe": f"{endpoint}?action=unsubscribe&token={s['token']}"})
    for e in [x.strip().lower() for x in (static_to or "").split(",") if x.strip()]:
        if e not in seen:
            seen.add(e)
            out.append({"email": e, "unsubscribe": f"{site_url}#unsubscribe"})
    return out


def personalise(template: str, unsubscribe_url: str) -> str:
    return template.replace(UNSUB_PLACEHOLDER, unsubscribe_url)


def smtp_settings() -> dict:
    """SMTP from the environment. Default is Gmail (GMAIL_USER + app password); any other relay works with
    SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM (e.g. Brevo: smtp-relay.brevo.com:587)."""
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PASSWORD") or os.environ.get("GMAIL_PASSWORD")
    host = os.environ.get("SMTP_HOST")
    if host:
        port = int(os.environ.get("SMTP_PORT") or 587)
        return {"host": host, "port": port, "ssl": port == 465, "user": os.environ.get("SMTP_USER") or gmail_user,
                "password": os.environ.get("SMTP_PASSWORD") or gmail_pw, "from": os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or gmail_user}
    return {"host": "smtp.gmail.com", "port": 465, "ssl": True, "user": gmail_user, "password": gmail_pw, "from": gmail_user}


def send_all(recips: list[dict], subject: str, html: str, text: str, user: str, password: str, from_name: str = "pubpulse",
             delay: float = 0.5, host: str = "smtp.gmail.com", port: int = 465, use_ssl: bool = True, from_addr: str | None = None) -> tuple[int, int]:
    sent = failed = 0
    user, password = user.strip(), "".join(password.split())  # app passwords are often pasted as 'xxxx xxxx xxxx xxxx'
    from_addr = from_addr or user
    smtp = smtplib.SMTP_SSL(host, port, timeout=60) if use_ssl else smtplib.SMTP(host, port, timeout=60)
    with smtp:
        if not use_ssl:
            smtp.starttls()
        try:
            smtp.login(user, password)
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as exc:
            hint = (" For Gmail: GMAIL_USER must be the full address and GMAIL_APP_PASSWORD a 16-letter app password "
                    "(https://myaccount.google.com/apppasswords, needs 2-step verification); account passwords are refused."
                    if "gmail" in host else "")
            raise SystemExit(f"{host} refused the login for {user!r}: {exc}.{hint}") from exc
        for r in recips:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"{from_name} <{from_addr}>"
            msg["To"] = r["email"]
            msg["List-Unsubscribe"] = f"<{r['unsubscribe']}>"
            msg.set_content(personalise(text, r["unsubscribe"]))
            msg.add_alternative(personalise(html, r["unsubscribe"]), subtype="html")
            try:
                smtp.send_message(msg)
                sent += 1
            except smtplib.SMTPException as exc:
                failed += 1
                log.error("sending to %s failed: %s", r["email"], exc)
            time.sleep(delay)
    return sent, failed


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config()
    dg = cfg.get("digest") or {}
    smtp = smtp_settings()
    user, password = smtp["user"], smtp["password"]
    if not user or not password:
        log.warning("no SMTP credentials (GMAIL_USER/GMAIL_APP_PASSWORD or SMTP_*): skipping email")
        return 0
    endpoint, key = dg.get("subscribe_endpoint") or None, os.environ.get("SUBSCRIBERS_KEY") or None
    if endpoint and not key:
        log.warning("subscribe_endpoint configured but SUBSCRIBERS_KEY secret missing: list not fetched")
    recips = recipients(endpoint, key, os.environ.get("DIGEST_TO"), cfg.get("site_url", ""))
    if not recips:
        log.info("no recipients (no subscribers, no DIGEST_TO): nothing sent")
        return 0
    subject = (OUT_DIR / "subject.txt").read_text(encoding="utf-8").strip()
    html = (OUT_DIR / "digest.html").read_text(encoding="utf-8")
    text = (OUT_DIR / "digest.txt").read_text(encoding="utf-8")
    sent, failed = send_all(recips, subject, html, text, user, password, from_name=dg.get("from_name") or "pubpulse",
                            host=smtp["host"], port=smtp["port"], use_ssl=smtp["ssl"], from_addr=smtp["from"])
    log.info("digest sent to %d recipient(s), %d failed", sent, failed)
    Path(OUT_DIR / "sent.txt").write_text(f"{sent} sent, {failed} failed\n", encoding="utf-8")
    return 1 if (failed and not sent) else 0
