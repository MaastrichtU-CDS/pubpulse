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


def make_card(w: dict, names: dict[str, str], out_path: Path, group_label: str = "Clinical Data Science · Maastricht") -> Path:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", CARD_SIZE, NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (14, CARD_SIZE[1])], fill=ACCENT)
    x, y, width = 70, 60, CARD_SIZE[0] - 140
    d.text((x, y), group_label.upper(), font=_font(22, True), fill=ACCENT)
    y += 54
    title_font = _font(50, True)
    lines = _wrap(w["title"], title_font, width, d)
    if len(lines) > 4:
        title_font = _font(40, True)
        lines = _wrap(w["title"], title_font, width, d)[:5]
        if len(_wrap(w["title"], title_font, width, d)) > 5:
            lines[-1] = lines[-1].rstrip(".,;:") + " …"
    for line in lines:
        d.text((x, y), line, font=title_font, fill=LIGHT)
        y += int(title_font.size * 1.25)
    y += 18
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
                out.append({"image": im, "page": pno + 1, "score": score})
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
                out.append({"image": im, "page": pno + 1, "score": box.get_area() * zoom * zoom * (0.9 if pno < 7 else 0.5)})
    out.sort(key=lambda f: -f["score"])
    return out


def best_figures(pdf_bytes: bytes) -> list[dict]:
    figs = extract_figures(pdf_bytes)
    if not figs:
        figs = extract_vector_figures(pdf_bytes)
    return figs


def credit_line(w: dict) -> str:
    first = (w.get("authors") or ["the authors"])[0]
    many = (w.get("author_count") or 1) > 1
    return f"Figure from {first}{' et al.' if many else ''}, {w.get('journal') or ''} ({(w.get('publication_date') or '')[:4]}), {w.get('license', '').upper()} · {w.get('doi') or ''}"


def run(ids: list[str] | None = None, all_drafts: bool = False, force: bool = False) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
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
            make_card(w, names, card)
            cards += 1
        d["card"] = f"data/social/images/{card.name}"
        fig = IMG_DIR / f"{d['id']}-figure.png"
        if figure_allowed(w) and (force or not fig.exists()) and (w.get("pdf_url") or w.get("oa_url")):
            pdf = None
            for url in [u for u in (w.get("pdf_url"), w.get("oa_url")) if u]:
                pdf = fetch_pdf(url, session)
                if pdf:
                    break
            cands = best_figures(pdf) if pdf else []
            if cands:
                im = cands[0]["image"]
                im.thumbnail((1600, 1600))
                im.save(fig, "PNG", optimize=True)
                d["figure"] = {"path": f"data/social/images/{fig.name}", "page": cands[0]["page"], "credit": credit_line(w), "license": w.get("license")}
                figs += 1
            else:
                d["figure"] = None
        elif not figure_allowed(w):
            d["figure"] = None
            d["figure_note"] = f"licence {w.get('license') or 'unknown'}: figure reuse not allowed, card only"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    write_index()
    log.info("images: %d cards, %d figures", cards, figs)
    return 0
