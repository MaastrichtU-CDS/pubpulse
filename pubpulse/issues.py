"""Apply an 'identifiers' issue form (GitHub issue body) to people.yml."""

from __future__ import annotations

import re
import unicodedata

ORCID_RE = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", re.I)
SCHOLAR_RE = re.compile(r"user=([\w-]+)")
OPENALEX_RE = re.compile(r"\bA\d{4,}\b", re.I)

FIELDS = {
    "name": "your name",
    "orcid": "orcid",
    "scholar": "google scholar",
    "openalex": "openalex author",
    "note": "anything else",
}


def parse_issue_body(body: str) -> dict:
    """Issue forms render as '### Label\\n\\nvalue' blocks; '_No response_' means empty."""
    out: dict[str, str] = {}
    for m in re.finditer(r"^###\s+(.+?)\s*\n(.*?)(?=^###\s|\Z)", body, re.S | re.M):
        label, value = m.group(1).strip().lower(), m.group(2).strip()
        if value == "_No response_":
            value = ""
        for key, needle in FIELDS.items():
            if needle in label:
                out[key] = value
    return out


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def find_person(people: list[dict], name: str) -> list[dict]:
    n = _norm(name)
    if not n:
        return []
    exact = [p for p in people if _norm(p.get("name", "")) == n]
    if exact:
        return exact
    parts = n.split()
    return [p for p in people if all(part in _norm(p.get("name", "")).split() for part in parts)]


def apply_identifiers(people: list[dict], form: dict) -> tuple[bool, str]:
    """Update the matching person in place. Returns (changed, markdown message for the issue)."""
    matches = find_person(people, form.get("name", ""))
    if len(matches) != 1:
        who = ", ".join(p["name"] for p in matches) or "nobody"
        return False, (
            f"I could not match **{form.get('name', '')}** to exactly one person on the list (found: {who}). "
            "A maintainer will handle this by hand. If you are new, make sure you are on the staff page first."
        )
    p = matches[0]
    lines, changed = [], False

    orcid = ORCID_RE.search(form.get("orcid") or "")
    if form.get("orcid") and not orcid:
        lines.append(f"- ORCID `{form['orcid']}` does not look like an ORCID (expected 0000-0000-0000-0000); ignored.")
    elif orcid and p.get("orcid") != orcid.group(1).upper():
        p["orcid"] = orcid.group(1).upper()
        p.pop("openalex_ids", None)
        p.pop("resolved_at", None)
        p["needs_review"] = False
        lines.append(f"- ORCID set to `{p['orcid']}`.")
        changed = True

    scholar_raw = form.get("scholar") or ""
    scholar = SCHOLAR_RE.search(scholar_raw)
    sid = scholar.group(1) if scholar else (scholar_raw.strip() if re.fullmatch(r"[\w-]{8,}", scholar_raw.strip()) else None)
    if scholar_raw and not sid:
        lines.append("- Google Scholar link not understood (expected a link containing `user=`); ignored.")
    elif sid and p.get("scholar_id") != sid:
        p["scholar_id"] = sid
        lines.append(f"- Google Scholar id set to `{sid}` (informational).")
        changed = True

    ids = [i.upper() for i in OPENALEX_RE.findall(form.get("openalex") or "")]
    if form.get("openalex") and not ids:
        lines.append("- OpenAlex id not understood (expected e.g. A5012345678); ignored.")
    elif ids:
        new = ids[0] if len(ids) == 1 else ids
        if p.get("openalex_id") != new:
            p["openalex_id"] = new
            p["needs_review"] = False
            lines.append(f"- OpenAlex author id set to `{', '.join(ids)}`.")
            changed = True

    if form.get("note"):
        p["notes"] = (p.get("notes") + " | " if p.get("notes") else "") + form["note"].strip()[:300]
        lines.append("- Note saved for the maintainers.")
        changed = True

    if not lines:
        lines.append("- Nothing to change: the values you entered are already on file.")
    head = f"Applied to **{p['name']}**:" if changed else f"Checked **{p['name']}**:"
    tail = "\n\nThe next run (within a few minutes) refreshes the website with these identifiers." if changed else ""
    return changed, head + "\n" + "\n".join(lines) + tail
