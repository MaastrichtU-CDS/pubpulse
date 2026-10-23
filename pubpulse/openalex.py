"""Thin OpenAlex API client: polite pool, optional API key, retries, paging."""

from __future__ import annotations

import logging
import os
import time
from typing import Iterator

import requests

BASE_URL = "https://api.openalex.org"
log = logging.getLogger(__name__)

WORK_FIELDS = (
    "id,doi,title,display_name,publication_date,publication_year,type,"
    "primary_location,best_oa_location,open_access,authorships,cited_by_count,abstract_inverted_index,biblio"
)


class OpenAlex:
    """Without an API key OpenAlex shares a small daily budget per IP address and refuses cursor paging,
    so page-based paging (max 10,000 results) is used instead. With a key (free, https://openalex.org/settings/api)
    cursor paging is used. The key is read from the OPENALEX_API_KEY environment variable."""

    def __init__(self, mailto: str | None = None, api_key: str | None = None, session: requests.Session | None = None, retries: int = 4):
        self.mailto = mailto
        self.api_key = api_key if api_key is not None else os.environ.get("OPENALEX_API_KEY") or None
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = f"pubpulse (mailto:{mailto})" if mailto else "pubpulse"
        self.retries = retries
        if not self.api_key:
            log.warning("no OPENALEX_API_KEY set: using the shared per-IP budget and page-based paging")

    def get(self, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        if self.mailto:
            params["mailto"] = self.mailto
        if self.api_key:
            params["api_key"] = self.api_key
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        delay = 2.0
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=60)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"{resp.status_code} from OpenAlex", response=resp)
                resp.raise_for_status()
                return resp.json()
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
                if attempt == self.retries:
                    raise
                log.warning("OpenAlex request failed (%s), retry %d/%d in %.0fs", exc, attempt, self.retries, delay)
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")

    def works(self, filter_expr: str, select: str = WORK_FIELDS, per_page: int = 200) -> Iterator[dict]:
        """Yield every work matching an OpenAlex filter expression."""
        base = {"filter": filter_expr, "select": select, "per-page": per_page}
        if self.api_key:
            cursor = "*"
            while cursor:
                data = self.get("/works", {**base, "cursor": cursor})
                yield from data.get("results", [])
                cursor = data.get("meta", {}).get("next_cursor")
        else:
            page = 1
            while True:
                data = self.get("/works", {**base, "page": page})
                results = data.get("results", [])
                yield from results
                if len(results) < per_page or page * per_page >= 10_000:
                    break
                page += 1

    def search_authors(self, name: str, per_page: int = 10) -> list[dict]:
        return self.get("/authors", {"search": name, "per-page": per_page}).get("results", [])

    def authors_by_orcid(self, orcid: str) -> list[dict]:
        """All OpenAlex author records carrying this ORCID (there can be several when OpenAlex split or merged people)."""
        return self.get("/authors", {"filter": f"orcid:{orcid}", "per-page": 25}).get("results", [])


def short_id(openalex_url: str | None) -> str | None:
    """'https://openalex.org/W123' -> 'W123'. ORCID URLs -> bare ORCID."""
    if not openalex_url:
        return None
    return openalex_url.rstrip("/").rsplit("/", 1)[-1]


def author_affiliations(author: dict) -> list[str]:
    """All institutions ever recorded on an author record (past and current)."""
    affs = [(a.get("institution") or {}).get("display_name", "") for a in (author.get("affiliations") or [])]
    affs += [(i or {}).get("display_name", "") for i in (author.get("last_known_institutions") or [])]
    return [a for a in affs if a]


def author_current_institutions(author: dict) -> list[str]:
    return [(i or {}).get("display_name", "") for i in (author.get("last_known_institutions") or []) if i]


def abstract_from_inverted_index(index: dict | None, max_chars: int = 6000) -> str | None:
    if not index:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in index.items():
        positions.extend((i, word) for i in idxs)
    positions.sort()
    text = " ".join(word for _, word in positions)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return text
