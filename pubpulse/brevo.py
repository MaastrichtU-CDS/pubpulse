"""Send the weekly digest as a Brevo email campaign to the subscriber list.

Why a campaign and not SMTP: Brevo manages the list (sign-up form with double opt-in, unsubscribe link in every
mail, bounces) so no backend of our own is needed. Needs: BREVO_API_KEY (Settings → SMTP & API → API keys) and a
contact list (created automatically on first run, id stored in data/brevo_list.json)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from .sync import DATA_DIR, OUT_DIR, load_config

log = logging.getLogger(__name__)
API = "https://api.brevo.com/v3"
LIST_STATE = DATA_DIR / "brevo_list.json"
LIST_NAME = "pubpulse weekly"


class Brevo:
    def __init__(self, api_key: str):
        self.s = requests.Session()
        self.s.headers.update({"api-key": api_key, "accept": "application/json", "content-type": "application/json"})

    def _req(self, method: str, path: str, **kw) -> dict:
        r = self.s.request(method, f"{API}{path}", timeout=60, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"Brevo {method} {path}: {r.status_code} {r.text[:300]}")
        return r.json() if r.text else {}

    def account(self) -> dict:
        return self._req("GET", "/account")

    def find_list(self, name: str) -> dict | None:
        offset = 0
        while True:
            data = self._req("GET", "/contacts/lists", params={"limit": 50, "offset": offset})
            for lst in data.get("lists", []):
                if lst["name"].lower() == name.lower():
                    return lst
            offset += 50
            if offset >= data.get("count", 0):
                return None

    def create_list(self, name: str) -> dict:
        folders = self._req("GET", "/contacts/folders", params={"limit": 1}).get("folders") or []
        folder_id = folders[0]["id"] if folders else self._req("POST", "/contacts/folders", json={"name": "pubpulse"})["id"]
        return self._req("POST", "/contacts/lists", json={"name": name, "folderId": folder_id})

    def list_info(self, list_id: int) -> dict:
        return self._req("GET", f"/contacts/lists/{list_id}")

    def send_campaign(self, list_id: int, subject: str, html: str, sender_email: str, sender_name: str, reply_to: str | None = None) -> dict:
        name = f"pubpulse {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        body = {
            "name": name, "subject": subject, "type": "classic",
            "sender": {"name": sender_name, "email": sender_email},
            "replyTo": reply_to or sender_email,
            "htmlContent": html,
            "recipients": {"listIds": [list_id]},
        }
        camp = self._req("POST", "/emailCampaigns", json=body)
        self._req("POST", f"/emailCampaigns/{camp['id']}/sendNow")
        return camp


def api_key() -> str | None:
    return os.environ.get("BREVO_API_KEY") or None


def ensure_list(client: Brevo, name: str = LIST_NAME) -> int:
    if LIST_STATE.exists():
        state = json.loads(LIST_STATE.read_text(encoding="utf-8"))
        if state.get("id"):
            return int(state["id"])
    lst = client.find_list(name) or client.create_list(name)
    LIST_STATE.parent.mkdir(exist_ok=True)
    LIST_STATE.write_text(json.dumps({"id": lst["id"], "name": name}), encoding="utf-8")
    log.info("Brevo list '%s' id %s", name, lst["id"])
    return int(lst["id"])


def campaign_html(html: str) -> str:
    """Brevo requires an unsubscribe link in campaigns: replace our placeholder with Brevo's tag."""
    return html.replace("{{UNSUBSCRIBE_URL}}", "{{ unsubscribe }}")


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    key = api_key()
    if not key:
        log.warning("BREVO_API_KEY not set: campaign skipped")
        return 0
    cfg = load_config()
    dg = cfg.get("digest") or {}
    client = Brevo(key)
    list_id = ensure_list(client, dg.get("brevo_list_name") or LIST_NAME)
    info = client.list_info(list_id)
    n = int(info.get("uniqueSubscribers") or 0)
    if n == 0:
        log.info("Brevo list %s has no subscribers yet: nothing sent", list_id)
        return 0
    subject = (OUT_DIR / "subject.txt").read_text(encoding="utf-8").strip()
    html = campaign_html((OUT_DIR / "digest.html").read_text(encoding="utf-8"))
    sender_email = os.environ.get("SMTP_FROM") or os.environ.get("BREVO_SENDER") or dg.get("sender_email")
    if not sender_email:
        raise SystemExit("no sender address: set SMTP_FROM (a sender verified in Brevo)")
    camp = client.send_campaign(list_id, subject, html, sender_email, dg.get("from_name") or "pubpulse", reply_to=dg.get("reply_to"))
    log.info("Brevo campaign %s sent to list %s (%d subscribers)", camp.get("id"), list_id, n)
    (OUT_DIR / "sent.txt").write_text(f"campaign {camp.get('id')} to {n} subscribers\n", encoding="utf-8")
    return 0
