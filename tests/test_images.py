import io

from pubpulse.images import credit_line, extract_figures, figure_allowed, make_card


def test_card_is_linkedin_sized(tmp_path):
    from PIL import Image
    w = {"title": "A fairly long title that needs wrapping across several lines to test the layout of the card properly",
         "journal": "npj Breast Cancer", "publication_date": "2026-10-12", "group_members": ["a", "b"], "doi": "https://doi.org/10.1/x"}
    out = make_card(w, {"a": "Ann A", "b": "Bob B"}, tmp_path / "c.png")
    assert Image.open(out).size == (1200, 627)


def test_figure_licences():
    assert figure_allowed({"license": "cc-by"}) and figure_allowed({"license": "cc-by-nc-sa"}) and figure_allowed({"license": "CC-BY-4.0".lower()})
    assert not figure_allowed({"license": "cc-by-nd"}) and not figure_allowed({"license": None}) and not figure_allowed({"license": "publisher-specific-oa"})


def test_extract_figures_from_synthetic_pdf():
    import pymupdf
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (900, 600), "white")
    ImageDraw.Draw(img).rectangle([50, 50, 850, 550], fill=(30, 90, 200))
    ImageDraw.Draw(img).ellipse([200, 150, 700, 450], fill=(240, 180, 20))
    buf = io.BytesIO(); img.save(buf, "PNG")
    tiny = Image.new("RGB", (80, 80), "red"); tbuf = io.BytesIO(); tiny.save(tbuf, "PNG")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(50, 50, 500, 350), stream=buf.getvalue())
    page.insert_image(pymupdf.Rect(50, 400, 100, 450), stream=tbuf.getvalue())
    pdf = doc.tobytes()
    figs = extract_figures(pdf)
    assert len(figs) == 1 and figs[0]["page"] == 1 and figs[0]["image"].size == (900, 600)
    assert "et al." in credit_line({"authors": ["X", "Y"], "author_count": 2, "journal": "J", "publication_date": "2026-01-01", "license": "cc-by", "doi": "d"})


def test_main_finding_and_card_with_finding(tmp_path):
    from PIL import Image
    from pubpulse.images import main_finding, make_card
    d = {"post": "Two privacy techniques kept hazard ratios almost unchanged while hiding individual time-to-event data.\n\nMore text."}
    f = main_finding(d)
    assert f and f.startswith("Two privacy techniques")
    out = make_card({"title": "T", "journal": "J", "publication_date": "2026-01-01", "group_members": [], "doi": "https://doi.org/x"}, {}, tmp_path / "c.png", finding=f)
    assert Image.open(out).size == (1200, 627)
    assert main_finding({"post": "short"}) is None
