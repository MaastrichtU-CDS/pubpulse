"""Groups for the authorship statistics, from each person's role on the CDS staff page (no list to maintain).

Senior vs non-senior follows each person's role on the staff page: professors, researchers and postdocs are senior,
everyone else (PhD students, interns, support staff) is not. It needs no upkeep. Everyone who left is grouped as
former staff (their last role still shows).
"""

from __future__ import annotations

import re

SENIOR_ROLES = re.compile(r"\bprofessor\b|\bresearcher\b|\bpostdoc", re.I)
SENIOR, NON_SENIOR, FORMER = "Senior staff", "Non-senior staff", "Former staff"
SPELLING = {"assistent": "assistant", "phd": "PhD", "ph.d.": "PhD"}


def role_title(role: str | None) -> str:
    """Clean staff-page role: "Former PhD Student" -> "PhD student", "Management Assistent" -> "Management assistant",
    "Postdoc – AI & … (OPERAI" -> "Postdoc", "Visiting researcher from Fudan University" -> "Visiting researcher"."""
    r = re.sub(r"^\s*former\s+", "", role or "", flags=re.I)
    r = re.split(r"\s+[–—-]\s+|\s+from\s+|\s*\(", r, maxsplit=1)[0]
    r = re.sub(r"\s*-\s+", " ", r)  # "Student- assistant"
    words = [SPELLING.get(w.lower(), w.lower()) for w in r.split()]
    if not words:
        return ""
    t = " ".join(words)
    return t[0].upper() + t[1:]


def role_group(role: str | None) -> str | None:
    """Senior or non-senior staff from the staff-page role; None when the role is unknown."""
    r = re.sub(r"^\s*former\s+", "", role or "", flags=re.I).strip()
    if not r:
        return None
    return SENIOR if SENIOR_ROLES.search(r) else NON_SENIOR


def role_groups(people: list[dict]) -> dict:
    """Current staff split into senior / non-senior; everyone who left is one former-staff group.
    "seniors" lists every senior by role, current or former (for the badge in the people table)."""
    groups: dict[str, list[str]] = {SENIOR: [], NON_SENIOR: [], FORMER: []}
    seniors = []
    for p in people:
        g = role_group(p.get("role"))
        if p.get("exclude") or (not g and p.get("active", True)):
            continue
        if g == SENIOR:
            seniors.append(p["slug"])
        groups[g if p.get("active", True) else FORMER].append(p["slug"])
    return {
        "groups": [{"name": g, "members": m, "seniors": [s for s in m if s in seniors], "kind": "role"} for g, m in groups.items() if m],
        "seniors": seniors,
    }
