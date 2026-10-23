"""LinkedIn drafts for verified journal papers, written by Claude. Human in the loop by design: this only writes
drafts into data/social/; a person reads, edits and posts. Needs ANTHROPIC_API_KEY (or an `ant auth login` profile
locally)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .sync import DATA_DIR, load_config, load_publications

log = logging.getLogger(__name__)
SOCIAL_DIR = DATA_DIR / "social"
INDEX_PATH = SOCIAL_DIR / "index.json"
DEFAULT_MODEL = "claude-opus-5-5"
ELIGIBLE_TYPES = {"article", "review"}

SYSTEM_PROMPT = """You write LinkedIn posts for the Clinical Data Science group (Maastro / Maastricht University / Maastricht UMC+).
Audience: clinicians, health-data scientists, hospital managers. Tone: plain, concrete, no hype, no emojis, no
hashtags in the body (at most 3 at the very end), no phrases like "excited to share" or "thrilled".

Write two things from the paper you are given:

### POST
A LinkedIn post of 120 to 180 words:
- first line: the main finding as a plain sentence a clinician would repeat (no question hooks)
- what was done, in one or two sentences (data, size, method)
- why it matters for practice or research, in one or two sentences
- one honest limitation taken from the abstract
- last lines: "Paper: <DOI link>" and, if an open-access link is given, "Full text: open access"
- name the group authors by name; do not tag anyone

### SHORT
A two-sentence version of at most 280 characters including the DOI link.

Rules: use only facts that are in the abstract; if the abstract gives no numbers, do not invent any; never say
"first", "novel" or "breakthrough" unless the abstract does; mark any claim you are unsure about with [check].
Output exactly the two sections, each starting with its "### POST" / "### SHORT" heading line, nothing else."""


def eligible(w: dict) -> bool:
    return bool(w.get("counted", w.get("verified"))) and w.get("type") in ELIGIBLE_TYPES and bool(w.get("abstract"))


def user_message(w: dict, names: dict[str, str]) -> str:
    members = ", ".join(names.get(s, s) for s in w.get("group_members", []))
    lines = [
        f"Title: {w['title']}",
        f"Journal: {w.get('journal') or 'unknown'}",
        f"Published: {w.get('publication_date') or 'unknown'} ({w.get('type')})",
        f"Group authors: {members or 'none listed'}",
        f"First authors: {', '.join(w.get('authors', [])[:3])} (total {w.get('author_count')})",
        f"DOI link: {w.get('doi') or w.get('landing_url') or w.get('openalex_url')}",
        f"Open-access link: {w.get('oa_url') or 'none'}",
        "",
        "Abstract:",
        w.get("abstract") or "(no abstract)",
    ]
    return "\n".join(lines)


def parse_output(text: str) -> dict:
    post = re.search(r"###\s*POST\s*\n(.*?)(?=\n###\s*SHORT|\Z)", text, re.S)
    short = re.search(r"###\s*SHORT\s*\n(.*)", text, re.S)
    return {"post": (post.group(1) if post else text).strip(), "short": (short.group(1) if short else "").strip()}


def draft_one(client, w: dict, names: dict[str, str], model: str) -> dict:
    import anthropic  # local import: optional dependency outside the workflow

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": user_message(w, names)}],
        )
    except anthropic.RateLimitError as exc:
        raise RuntimeError(f"rate limited: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"API error {exc.status_code}: {exc.message}") from exc
    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined this paper")
    text = "".join(b.text for b in response.content if b.type == "text")
    out = parse_output(text)
    out.update({
        "id": w["id"], "title": w["title"], "doi": w.get("doi"), "model": response.model,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "flags": len(re.findall(r"\[check[^\]]*\]", text)),
    })
    return out


def load_index() -> dict:
    if not INDEX_PATH.exists():
        return {}
    with open(INDEX_PATH, encoding="utf-8") as f:
        return json.load(f)


def write_index() -> dict:
    index = {}
    for p in sorted(SOCIAL_DIR.glob("W*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        index[d["id"]] = {k: d.get(k) for k in ("post", "short", "model", "generated_at", "flags", "card", "figure", "figure_note")}
    SOCIAL_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return index


def run(ids: list[str] | None = None, since: str | None = None, limit: int | None = None, dry_run: bool = False, force: bool = False) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config()
    sc = cfg.get("social") or {}
    model = sc.get("model") or DEFAULT_MODEL
    pubs = load_publications()
    names = {p["slug"]: p["name"] for p in pubs.get("people", [])}
    works = [w for w in pubs.get("works", []) if eligible(w)]
    if ids:
        wanted = set(ids)
        works = [w for w in works if w["id"] in wanted]
    elif since:
        works = [w for w in works if (w.get("publication_date") or "") >= since]
    else:
        new = set((pubs.get("last_run") or {}).get("new_ids") or [])
        works = [w for w in works if w["id"] in new]
    SOCIAL_DIR.mkdir(parents=True, exist_ok=True)
    if not force:
        works = [w for w in works if not (SOCIAL_DIR / f"{w['id']}.json").exists()]
    works.sort(key=lambda w: w.get("publication_date") or "", reverse=True)
    if limit:
        works = works[:limit]
    if not works:
        log.info("no papers to draft")
        write_index()
        return 0
    if dry_run:
        for w in works:
            log.info("would draft %s %s", w["id"], w["title"][:70])
        return 0
    try:
        import anthropic
    except ImportError:
        raise SystemExit("pip install anthropic")
    client = anthropic.Anthropic()
    done = failed = 0
    for w in works:
        try:
            d = draft_one(client, w, names, model)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log.error("draft failed for %s: %s", w["id"], exc)
            continue
        (SOCIAL_DIR / f"{w['id']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        done += 1
        log.info("drafted %s (%d [check] marks) %s", w["id"], d["flags"], w["title"][:60])
    write_index()
    log.info("social drafts: %d written, %d failed", done, failed)
    return 1 if failed and not done else 0
