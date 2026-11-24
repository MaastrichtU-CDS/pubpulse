const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const zlib = require("node:zlib");

const context = { window: {}, TextEncoder, Uint8Array, Uint32Array, DataView, ArrayBuffer };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../site/references.js"), "utf8"), context);
const { splitName, bibtex, ris, docx, documentXml, text, html } = context.window.PubpulseReferences;

const article = {
  id: "W1", doi: "https://doi.org/10.1016/s1470-2045(26)00465-1", title: "Prostate SBRT & <i>pelvic</i> nodes: 50% fewer events",
  publication_date: "2026-11-01", year: 2026, type: "article", journal: "The Lancet Oncology",
  biblio: { volume: "27", issue: "11", first_page: "1450", last_page: "1462" },
  authors: ["Johan van Soest", "Ali Al Zein", "Sander Puts"], author_members: ["johan-van-soest", null, "sander-puts"],
};
const preprint = {
  id: "W2", doi: null, landing_url: "https://medrxiv.org/x", title: "Radiomics versus semantic features?", publication_date: "2025-04-28",
  year: 2025, type: "preprint", journal: "medRxiv", authors: ["Leonard Wee"], author_members: ["leonard-wee"],
};

test("family names keep their particles", () => {
  assert.deepEqual({ ...splitName("Johan van Soest") }, { given: "Johan", family: "van Soest" });
  assert.deepEqual({ ...splitName("Maria de la Cruz") }, { given: "Maria", family: "de la Cruz" });
  assert.deepEqual({ ...splitName("Ali Al Zein") }, { given: "Ali", family: "Al Zein" });
  assert.deepEqual({ ...splitName("Umesh Kumar Baburao Sherkhane") }, { given: "Umesh Kumar Baburao", family: "Sherkhane" });
  assert.deepEqual({ ...splitName("Plato") }, { given: "", family: "Plato" });
});

test("BibTeX escapes LaTeX characters, strips markup and fills the journal fields", () => {
  const bib = bibtex([article, preprint]);
  assert.match(bib, /^@article\{vansoest2026prostate,$/m);
  assert.match(bib, /author = \{van Soest, Johan and Al Zein, Ali and Puts, Sander\}/);
  assert.match(bib, /title = \{\{Prostate SBRT \\& pelvic nodes: 50\\% fewer events\}\}/);
  assert.match(bib, /journal = \{The Lancet Oncology\}/);
  assert.match(bib, /volume = \{27\},\n  number = \{11\},\n  pages = \{1450--1462\},\n  doi = \{10.1016\/s1470-2045\(26\)00465-1\}/);
  assert.match(bib, /@misc\{wee2025radiomics,[\s\S]*howpublished = \{medRxiv\}[\s\S]*url = \{https:\/\/medrxiv.org\/x\}[\s\S]*note = \{Preprint\}/);
});

test("BibTeX keys stay unique", () => {
  const keys = [...bibtex([article, { ...article, id: "W3" }]).matchAll(/^@\w+\{([^,]+),/gm)].map((m) => m[1]);
  assert.deepEqual(keys, ["vansoest2026prostatea", "vansoest2026prostateb"]);
});

test("RIS has one record per work with family-first authors", () => {
  const text = ris([article, preprint]);
  assert.equal(text.match(/^TY {2}- /gm).length, 2);
  assert.equal(text.match(/^ER {2}- /gm).length, 2);
  assert.match(text, /TY {2}- JOUR\r\nAU {2}- van Soest, Johan\r\nAU {2}- Al Zein, Ali\r\nAU {2}- Puts, Sander\r\n/);
  assert.match(text, /SP {2}- 1450\r\nEP {2}- 1462\r\nDO {2}- 10.1016\/s1470-2045\(26\)00465-1\r\n/);
  assert.match(text, /TY {2}- UNPB[\s\S]*N1 {2}- Preprint/);
});

test("Word list: Vancouver references, highlighted researcher in bold", () => {
  const doc = documentXml([article, preprint], { title: "Publications of Sander Puts", highlight: ["sander-puts"] });
  assert.match(doc, /<w:t xml:space="preserve">Puts S<\/w:t>/);
  assert.match(doc, /<w:r><w:rPr><w:b\/><\/w:rPr><w:t xml:space="preserve">Puts S<\/w:t><\/w:r>/);
  assert.match(doc, /van Soest J/);
  assert.match(doc, /Prostate SBRT &amp; pelvic nodes: 50% fewer events\. /);
  assert.match(doc, /2026;27\(11\):1450-1462\. /);
  assert.match(doc, /<w:i\/><\/w:rPr><w:t xml:space="preserve">The Lancet Oncology<\/w:t>/);
});

const review = { ...article, id: "W4", type: "review", title: "A review", publication_date: "2026-12-01" };
const abstract = { ...article, id: "W5", type: "conference-abstract", title: "An abstract", publication_date: "2026-12-02" };

test("publication list is grouped by type and numbered straight through", () => {
  const list = text([abstract, review, preprint, article], { title: "Publications of Sander Puts", highlight: ["sander-puts"] });
  assert.equal(list, [
    "Publications of Sander Puts",
    "",
    "Journal articles",
    "1. van Soest J, Al Zein A, Puts S. Prostate SBRT & pelvic nodes: 50% fewer events. The Lancet Oncology. 2026;27(11):1450-1462. doi:10.1016/s1470-2045(26)00465-1",
    "",
    "Reviews",
    "2. van Soest J, Al Zein A, Puts S. A review. The Lancet Oncology. 2026;27(11):1450-1462. doi:10.1016/s1470-2045(26)00465-1",
    "",
    "Conference papers and abstracts",
    "3. van Soest J, Al Zein A, Puts S. An abstract. The Lancet Oncology. 2026;27(11):1450-1462. doi:10.1016/s1470-2045(26)00465-1",
    "",
    "Preprints",
    "4. Wee L. Radiomics versus semantic features? medRxiv. 2025. https://medrxiv.org/x",
    "",
  ].join("\n"));
  const doc = documentXml([preprint, article], {});
  assert.ok(doc.indexOf(">Journal articles<") < doc.indexOf(">Preprints<"));
});

test("clipboard HTML keeps headings, bold names and italic journals, escaped", () => {
  const out = html([article], { title: "T & co", note: "n", highlight: ["sander-puts"] });
  assert.match(out, /^<h1>T &amp; co<\/h1><p><i>n<\/i><\/p><h2>Journal articles<\/h2><p>1\. van Soest J, Al Zein A, <b>Puts S<\/b>\. /);
  assert.match(out, /Prostate SBRT &amp; pelvic nodes: 50% fewer events\. <i>The Lancet Oncology<\/i>\. /);
});

test("long author lists keep the highlighted researcher", () => {
  const authors = Array.from({ length: 40 }, (_, i) => `Author Number${i}`);
  const members = authors.map((_, i) => (i === 30 ? "me" : null));
  const doc = documentXml([{ ...article, authors, author_members: members }], { highlight: ["me"] });
  assert.match(doc, /Number9 A<\/w:t>[\s\S]*, … [\s\S]*<w:b\/><\/w:rPr><w:t xml:space="preserve">Number30 A<\/w:t>[\s\S]*, et al/);
  assert.doesNotMatch(doc, /Number10 A/);
});

test(".docx is a valid zip with the Word parts", () => {
  const bytes = Buffer.from(docx([article], { title: "T", highlight: [] }));
  assert.equal(bytes.readUInt32LE(0), 0x04034b50);
  const end = bytes.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const entries = bytes.readUInt16LE(end + 10);
  let at = bytes.readUInt32LE(end + 16);
  const names = [];
  for (let i = 0; i < entries; i++) {
    const size = bytes.readUInt32LE(at + 24);
    const nameLength = bytes.readUInt16LE(at + 28);
    const offset = bytes.readUInt32LE(at + 42);
    const name = bytes.subarray(at + 46, at + 46 + nameLength).toString();
    const data = bytes.subarray(offset + 30 + nameLength, offset + 30 + nameLength + size);
    assert.equal(bytes.readUInt32LE(at + 16), zlib.crc32(data), name);
    names.push(name);
    at += 46 + nameLength;
  }
  assert.deepEqual(names, ["[Content_Types].xml", "_rels/.rels", "word/_rels/document.xml.rels", "word/styles.xml", "word/document.xml"]);
});
