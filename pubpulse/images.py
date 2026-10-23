"""Images for social posts: a branded card for every drafted paper, plus a figure from the paper itself when its
licence allows reuse (CC BY family, not ND). Figures are raster images embedded in the open-access PDF; vector
figures are not extracted."""

from __future__ import annotations

import io
import json
import logging
import textwrap
from pathlib import Path

import requests

from .social import SOCIAL_DIR, write_index
from .sync import load_publications

log = logging.getLogger(__name__)
IMG_DIR = SOCIAL_DIR / "images"
CARD_SIZE = (1200, 627)
NAVY, LIGHT, ACCENT, MUTED = (0, 28, 61), (245, 247, 250), (4, 159, 216), (160, 176, 196)
FONT_CANDIDATES = {
    "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"],
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"],
}
REUSABLE_LICENCES = ("cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nc-sa", "cc0", "public-domain")


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    for path in FONT_CANDIDATES["bold" if bold else "regular"]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _wrap(text: str, font, max_width: int, draw) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_card(w: dict, names: dict[str, str], out_path: Path, group_label: str = "Clinical Data Science · Maastricht", finding: str | None = None) -> Path:
    """Branded 1200x627 card. With `finding` (the main point, usually the first line of the draft post) the finding is the
    headline and the title goes underneath; without it the title is the headline."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", CARD_SIZE, NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (14, CARD_SIZE[1])], fill=ACCENT)
    x, y, width = 70, 60, CARD_SIZE[0] - 140
    d.text((x, y), group_label.upper(), font=_font(22, True), fill=ACCENT)
    y += 54
    headline = (finding or w["title"]).strip()
    size = 50 if len(headline) < 120 else 42 if len(headline) < 200 else 36
    head_font = _font(size, True)
    lines = _wrap(headline, head_font, width, d)
    while len(lines) > 5 and size > 30:
        size -= 4
        head_font = _font(size, True)
        lines = _wrap(headline, head_font, width, d)
    if len(lines) > 5:
        lines = lines[:5]
        lines[-1] = lines[-1].rstrip(".,;:") + " …"
    for line in lines:
        d.text((x, y), line, font=head_font, fill=LIGHT)
        y += int(head_font.size * 1.25)
    y += 14
    if finding:
        tf = _font(24)
        for line in _wrap(w["title"], tf, width, d)[:2]:
            d.text((x, y), line, font=tf, fill=(205, 215, 230))
            y += 32
        y += 8
    meta = " · ".join(x for x in (w.get("journal"), (w.get("publication_date") or "")[:4]) if x)
    d.text((x, y), meta, font=_font(28), fill=ACCENT)
    y += 46
    members = ", ".join(names.get(s, s) for s in w.get("group_members", []))
    if members:
        for line in _wrap("With " + members, _font(26), width, d)[:2]:
            d.text((x, y), line, font=_font(26), fill=MUTED)
            y += 36
    foot = _font(24)
    d.text((x, CARD_SIZE[1] - 70), (w.get("doi") or "").replace("https://", ""), font=foot, fill=MUTED)
    d.text((CARD_SIZE[0] - 70 - d.textlength("pubpulse", font=_font(24, True)), CARD_SIZE[1] - 70), "pubpulse", font=_font(24, True), fill=ACCENT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def figure_allowed(w: dict) -> bool:
    lic = (w.get("license") or "").lower().replace("_", "-")
    return any(lic == x or lic.startswith(x + "-") for x in REUSABLE_LICENCES) and "nd" not in lic.split("-")


def fetch_pdf(url: str, session: requests.Session | None = None) -> bytes | None:
    session = session or requests.Session()
    try:
        r = session.get(url, timeout=90, headers={"User-Agent": "pubpulse/1.0 (figure extraction for the paper's own group; +https://github.com/MaastrichtU-CDS/pubpulse)", "Accept": "application/pdf,*/*"}, allow_redirects=True)
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            log.info("no PDF at %s (status %s)", url, r.status_code)
            return None
        return r.content
    except requests.RequestException as exc:
        log.info("PDF fetch failed for %s: %s", url, exc)
        return None


def extract_figures(pdf_bytes: bytes, max_pages: int = 14, min_w: int = 480, min_h: int = 300) -> list[dict]:
    """Raster images from the first pages, scored by size and position. Returns [{image, page, score}] best first."""
    import pymupdf
    from PIL import Image, ImageStat

    out = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for pno, page in enumerate(doc):
            if pno >= max_pages:
                break
            for info in page.get_images(full=True):
                try:
                    raw = doc.extract_image(info[0])
                    im = Image.open(io.BytesIO(raw["image"])).convert("RGB")
                except Exception:  # noqa: BLE001
                    continue
                wdt, hgt = im.size
                if wdt < min_w or hgt < min_h or not 0.45 <= wdt / hgt <= 3.2:
                    continue
                stat = ImageStat.Stat(im.convert("L"))
                if stat.stddev[0] < 12:  # blank or near-uniform
                    continue
                score = wdt * hgt * (1.0 if pno < 7 else 0.6) * (1.1 if 1.1 <= wdt / hgt <= 2.0 else 1.0)
                caption = ""
                try:
                    bbox = pymupdf.Rect(page.get_image_bbox(info))
                    caps = [b for b in page.get_text("blocks") if b[4].strip().lower().startswith(("fig.", "figure", "fig "))]
                    below = sorted((b for b in caps if b[1] >= bbox.y1 - 5), key=lambda b: b[1] - bbox.y1)
                    above = sorted((b for b in caps if b[3] <= bbox.y0 + 5), key=lambda b: bbox.y0 - b[3])
                    caption = " ".join((below or above)[0][4].split()) if (below or above) else ""
                except Exception:  # noqa: BLE001
                    pass
                out.append({"image": im, "page": pno + 1, "score": score, "caption": caption})
    out.sort(key=lambda f: -f["score"])
    return out


def extract_vector_figures(pdf_bytes: bytes, max_pages: int = 14, zoom: float = 2.5) -> list[dict]:
    """Vector figures: for every caption starting with 'Fig', take the drawings above it in the same column and
    render that region. Tables (captions 'Table') are ignored by construction."""
    import pymupdf
    from PIL import Image

    out = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for pno, page in enumerate(doc):
            if pno >= max_pages:
                break
            captions = [b for b in page.get_text("blocks") if b[4].strip().lower().startswith(("fig.", "figure", "fig "))]
            if not captions:
                continue
            rects = [d["rect"] for d in page.get_drawings() if d["rect"].width > 2 and d["rect"].height > 2]
            images = [pymupdf.Rect(page.get_image_bbox(i)) for i in page.get_images(full=True)]
            for cap in captions:
                cx0, cy0, cx1, cy1 = cap[:4]
                # Captions sit below the figure, above it, or beside it in a margin column: use vertical windows only.
                win = page.rect.height * 0.75
                above = [r for r in rects + images if r.y1 <= cy0 + 2 and r.y0 >= cy0 - win]
                below = [r for r in rects + images if r.y0 >= cy0 - 8 and r.y1 <= cy1 + win]
                parts = above if len(above) >= 3 and len(above) >= len(below) else below
                if len(parts) < 3:
                    continue
                box = pymupdf.Rect(min(r.x0 for r in parts), min(r.y0 for r in parts), max(r.x1 for r in parts), max(r.y1 for r in parts))
                box = box & page.rect
                if box.height < 120 or box.width < 160 or box.get_area() < page.rect.get_area() * 0.08:
                    continue
                pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=box, alpha=False)
                im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                out.append({"image": im, "page": pno + 1, "score": box.get_area() * zoom * zoom * (0.9 if pno < 7 else 0.5), "caption": " ".join(cap[4].split())})
    out.sort(key=lambda f: -f["score"])
    return out


def best_figures(pdf_bytes: bytes) -> list[dict]:
    figs = extract_figures(pdf_bytes)
    if not figs:
        figs = extract_vector_figures(pdf_bytes)
    return figs


def describe_with_claude(w: dict, draft: dict, cands: list[dict], model: str) -> dict | None:
    """Ask Claude to pick the candidate that shows the main finding (or none) and to describe it. Returns
    {"choice": index|None, "description": str, "alt": str} or None when no API key / on failure."""
    import base64
    import io
    import os
    import re

    try:
        import anthropic
    except ImportError:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return None
    content = [{"type": "text", "text": (
        "You help a research group pick ONE figure for a LinkedIn post about their paper. The figure must show the MAIN "
        "FINDING of the paper, not the methods (flow diagrams, pipelines, PRISMA charts, study designs do not qualify unless "
        "the paper is about the method itself). If no candidate shows the main finding, answer NONE.\n\n"
        f"Title: {w['title']}\nAbstract: {w.get('abstract') or ''}\n\nDraft post (first line is the main finding):\n{draft.get('post', '')}\n\n"
        "Answer with exactly:\n### CHOICE\n<candidate number or NONE>\n### DESCRIPTION\n<a caption for LinkedIn readers outside the field, "
        "at most 2 short sentences (about 40 words): say in everyday words what the picture shows and the one takeaway, the main point of the paper. "
        "No method names, no statistics or abbreviations unless the reader needs them, no hype; only what is visible and in the abstract>"
        "\n### ALT\n<one-sentence alt text describing the image for screen readers>"
    )}]
    for i, c in enumerate(cands, 1):
        im = c["image"].copy()
        im.thumbnail((1200, 1200))
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        content.append({"type": "text", "text": f"Candidate {i} (page {c['page']}). Caption: {c.get('caption') or 'none found'}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(buf.getvalue()).decode()}})
    try:
        resp = anthropic.Anthropic().messages.create(model=model, max_tokens=2000, output_config={"effort": "medium"}, messages=[{"role": "user", "content": content}])
    except anthropic.APIError as exc:
        log.warning("figure selection failed: %s", exc)
        return None
    if resp.stop_reason == "refusal":
        return None
    text = "".join(b.text for b in resp.content if b.type == "text")
    ch = re.search(r"###\s*CHOICE\s*\n\s*(\S+)", text)
    de = re.search(r"###\s*DESCRIPTION\s*\n(.*?)(?=\n###|\Z)", text, re.S)
    al = re.search(r"###\s*ALT\s*\n(.*?)(?=\n###|\Z)", text, re.S)
    choice = None
    if ch and ch.group(1).strip().upper() != "NONE":
        try:
            choice = int(re.sub(r"\D", "", ch.group(1))) - 1
        except ValueError:
            choice = None
    if choice is not None and not 0 <= choice < len(cands):
        choice = None
    return {"choice": choice, "description": (de.group(1).strip() if de else ""), "alt": (al.group(1).strip() if al else ""), "model": resp.model}


def credit_line(w: dict) -> str:
    first = (w.get("authors") or ["the authors"])[0]
    many = (w.get("author_count") or 1) > 1
    return f"Figure from {first}{' et al.' if many else ''}, {w.get('journal') or ''} ({(w.get('publication_date') or '')[:4]}), {w.get('license', '').upper()} · {w.get('doi') or ''}"


def main_finding(draft: dict) -> str | None:
    """First sentence/line of the post: the plain statement of the finding."""
    post = (draft.get("post") or "").strip()
    if not post:
        return None
    first = post.split("\n")[0].strip()
    return first if 20 <= len(first) <= 260 else None


def run(ids: list[str] | None = None, all_drafts: bool = False, force: bool = False) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from .sync import load_config
    model = ((load_config().get("social") or {}).get("model")) or "claude-opus-5-5"
    pubs = load_publications()
    names = {p["slug"]: p["name"] for p in pubs.get("people", [])}
    byid = {w["id"]: w for w in pubs.get("works", [])}
    drafts = sorted(SOCIAL_DIR.glob("W*.json"))
    if ids:
        drafts = [p for p in drafts if p.stem in set(ids)]
    elif not all_drafts:
        new = set((pubs.get("last_run") or {}).get("new_ids") or [])
        drafts = [p for p in drafts if p.stem in new or not (IMG_DIR / f"{p.stem}-card.png").exists()]
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    cards = figs = 0
    for p in drafts:
        d = json.loads(p.read_text(encoding="utf-8"))
        w = byid.get(d["id"])
        if not w:
            continue
        card = IMG_DIR / f"{d['id']}-card.png"
        if force or not card.exists():
            make_card(w, names, card, finding=main_finding(d))
            cards += 1
        d["card"] = f"data/social/images/{card.name}"
        fig = IMG_DIR / f"{d['id']}-figure.png"
        if figure_allowed(w) and (force or not fig.exists()) and (w.get("pdf_url") or w.get("oa_url")):
            pdf = None
            for url in [u for u in (w.get("pdf_url"), w.get("oa_url")) if u]:
                pdf = fetch_pdf(url, session)
                if pdf:
                    break
            cands = (best_figures(pdf) if pdf else [])[:4]
            picked = describe_with_claude(w, d, cands, model) if cands else None
            if cands and (picked is None or picked["choice"] is not None):
                c = cands[picked["choice"]] if picked else cands[0]
                im = c["image"]
                im.thumbnail((1600, 1600))
                im.save(fig, "PNG", optimize=True)
                d["figure"] = {
                    "path": f"data/social/images/{fig.name}", "page": c["page"], "caption": c.get("caption") or "",
                    "credit": credit_line(w), "license": w.get("license"),
                    "description": picked["description"] if picked else f"[check] {c.get('caption') or 'Figure from the paper'}",
                    "alt": picked["alt"] if picked else (c.get("caption") or "Figure from the paper"),
                    "chosen_by": "claude" if picked else "largest figure (no API key); description unverified",
                }
                figs += 1
            elif cands and picked and picked["choice"] is None:
                d["figure"] = None
                d["figure_note"] = "no figure shows the main finding (judged by Claude); card only"
                if fig.exists():
                    fig.unlink()
            else:
                d["figure"] = None
        elif not figure_allowed(w):
            d["figure"] = None
            d["figure_note"] = f"licence {w.get('license') or 'unknown'}: figure reuse not allowed, card only"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    write_index()
    log.info("images: %d cards, %d figures", cards, figs)
    return 0
