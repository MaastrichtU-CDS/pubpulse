"""Rebuild the CDS logo variants and icons from site/assets/logo-cds.svg.

Run with: python scripts/build_brand_assets.py
The supplied source stays unchanged; derived SVGs use explicit fills so both
browser canvas and PyMuPDF render the same artwork.
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "site" / "assets"
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)


def svg_node(tag: str, **attrs: str) -> ET.Element:
    return ET.Element(f"{{{SVG}}}{tag}", attrs)


def write_svg(path: Path, root: ET.Element) -> bytes:
    content = ET.tostring(root, encoding="utf-8") + b"\n"
    path.write_bytes(content)
    return content


def rasterize(svg: bytes, size: int) -> Image.Image:
    with pymupdf.open(stream=svg, filetype="svg") as doc:
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(size / doc[0].rect.width, size / doc[0].rect.height), alpha=True)
        return Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)


def email_logo(name: str, width: int) -> None:
    """Opaque PNGs keep white institutional artwork visible in email clients."""
    with pymupdf.open(ASSETS / f"{name}.svg") as doc:
        page = doc[0]
        scale = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
        artwork = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    image = Image.new("RGBA", artwork.size, "#001c3d")
    image.alpha_composite(artwork)
    image.convert("RGB").save(ASSETS / f"{name}-email.png", optimize=True)


def main() -> None:
    source = ET.parse(ASSETS / "logo-cds.svg").getroot()
    # Flatten the source's class-based fill rules without changing its paths.
    styles: dict[str, dict[str, str]] = {}
    for style in source.iter(f"{{{SVG}}}style"):
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]+)\}", style.text or ""):
            declarations = dict(re.findall(r"(fill(?:-rule)?)\s*:\s*([^;]+)", body))
            for selector in selectors.split(","):
                styles.setdefault(selector.strip().removeprefix("."), {}).update(declarations)
    logo = copy.deepcopy(source)
    logo.attrib = {"viewBox": source.attrib["viewBox"], "fill": "#fff"}
    for node in logo.iter():
        for cls in node.attrib.pop("class", "").split():
            node.attrib.update(styles.get(cls, {}))
        node.attrib.pop("id", None)
        node.attrib.pop("data-name", None)
    for defs in list(logo.findall(f"{{{SVG}}}defs")):
        logo.remove(defs)
    write_svg(ASSETS / "cds.svg", logo)

    full_mask = copy.deepcopy(logo)
    for node in full_mask.iter():
        if "fill" in node.attrib:
            node.set("fill", "#000")
    write_svg(ASSETS / "logo-cds-mask.svg", full_mask)

    # The source has one direct path: the emblem, separate from the wordmark group.
    emblems = logo.findall(f"{{{SVG}}}path")
    if len(emblems) != 1:
        raise ValueError("Expected one standalone emblem path in logo-cds.svg")
    emblem = emblems[0]
    mask = svg_node("svg", viewBox="0 0 112 112")
    group = ET.SubElement(mask, f"{{{SVG}}}g", {"transform": "translate(8 8)"})
    group.append(copy.deepcopy(emblem))
    group[0].set("fill", "#000")
    write_svg(ASSETS / "cds-mask.svg", mask)

    icon = copy.deepcopy(mask)
    icon.insert(0, svg_node("rect", width="112", height="112", rx="22", fill="#001c3d"))
    icon[1][0].set("fill", "#fff")
    icon_svg = write_svg(ASSETS / "cds-icon.svg", icon)
    high_res = rasterize(icon_svg, 1024)
    high_res.resize((32, 32), Image.Resampling.LANCZOS).save(ASSETS / "cds-icon-32.png", optimize=True)
    # Touch/app icons are full bleed; the OS supplies its own corner treatment.
    icon[0].attrib.pop("rx")
    app_image = rasterize(ET.tostring(icon), 1024)
    for name, size in (
        ("apple-touch-icon-152.png", 152),
        ("apple-touch-icon-167.png", 167),
        ("apple-touch-icon.png", 180),
        ("cds-icon-192.png", 192),
        ("cds-icon-512.png", 512),
    ):
        app_image.resize((size, size), Image.Resampling.LANCZOS).save(ASSETS / name, optimize=True)
    # Keep classic bitmap ICO entries for the same compatibility as the old favicon.
    high_res.save(ROOT / "site" / "favicon.ico", format="ICO", bitmap_format="bmp", sizes=[(16, 16), (32, 32), (48, 48)])
    for name, width in (("cds", 384), ("maastricht-university", 512), ("maastro", 228), ("maastricht-umc", 408)):
        email_logo(name, width)
    print("Rebuilt CDS logo, masks, browser/app icons, and email PNG logos.")


if __name__ == "__main__":
    main()
