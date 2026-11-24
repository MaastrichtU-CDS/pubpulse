/* Reference exports of a publication list: BibTeX (LaTeX), RIS (EndNote, Zotero, Mendeley), and a publication list for
   a thesis or CV, grouped by type, as Word (.docx) or as text/HTML for the clipboard. Pure functions without dependencies: the .docx is written with a small zip writer. */
(() => {
  // Name particles that belong to the family name: "Johan van Soest" → van Soest, Johan; "Ali Al Zein" → Al Zein, Ali.
  const PARTICLES = new Set(["van", "von", "der", "den", "de", "del", "della", "di", "da", "du", "dos", "das", "le", "la",
    "ten", "ter", "te", "op", "het", "'t", "al", "el", "bin", "ibn"]);

  function splitName(name) {
    const tokens = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (tokens.length < 2) return { given: "", family: tokens[0] || "" };
    let i = tokens.length - 1;
    while (i > 1 && PARTICLES.has(tokens[i - 1].toLowerCase())) i--;
    return { given: tokens.slice(0, i).join(" "), family: tokens.slice(i).join(" ") };
  }

  const initials = (given) =>
    given.split(/[\s.\-]+/).filter(Boolean).map((part) => part[0].toUpperCase()).join("");

  const fold = (s) => String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const plainTitle = (w) => String(w.title || "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
  const doiOf = (w) => String(w.doi || "").replace(/^https?:\/\/(dx\.)?doi\.org\//i, "");
  const urlOf = (w) => (w.doi ? "https://doi.org/" + doiOf(w) : w.landing_url || w.openalex_url || "");
  const biblio = (w) => w.biblio || {};
  const yearOf = (w) => w.year || String(w.publication_date || "").slice(0, 4);
  const pageRange = (w, dash = "-") => {
    const b = biblio(w);
    if (!b.first_page) return "";
    return b.last_page && b.last_page !== b.first_page ? `${b.first_page}${dash}${b.last_page}` : b.first_page;
  };

  // OpenAlex work type → kind of reference.
  const KIND = {
    article: "article", review: "article", letter: "article", editorial: "article", erratum: "article",
    preprint: "preprint", "conference-abstract": "abstract", "conference-paper": "conference",
    "book-chapter": "chapter", book: "book", dataset: "dataset", software: "software", dissertation: "thesis",
  };
  const kindOf = (w) => KIND[w.type] || "other";
  const LABEL = { preprint: "Preprint", abstract: "Conference abstract", dataset: "Dataset", software: "Software" };

  // ------------------------------------------------------------------------------------------------ BibTeX

  const bibEscape = (s) =>
    String(s ?? "")
      .replace(/\\/g, "\\textbackslash{}")
      .replace(/([&%$#_{}])/g, "\\$1")
      .replace(/~/g, "\\textasciitilde{}")
      .replace(/\^/g, "\\textasciicircum{}");

  function bibKeys(works) {
    const counts = new Map();
    const base = works.map((w) => {
      const family = fold(splitName((w.authors || [])[0]).family).replace(/[^a-z]/g, "") || "anon";
      const word = fold(plainTitle(w)).split(/[^a-z0-9]+/).find((t) => t.length > 3 && !["with", "from", "that", "this", "using", "into"].includes(t)) || "";
      const key = family + yearOf(w) + word;
      counts.set(key, (counts.get(key) || 0) + 1);
      return key;
    });
    const seen = new Map();
    return base.map((key) => {
      if (counts.get(key) === 1) return key;
      const n = seen.get(key) || 0;
      seen.set(key, n + 1);
      return key + String.fromCharCode(97 + (n % 26)) + (n >= 26 ? Math.floor(n / 26) : "");
    });
  }

  function bibtex(works) {
    const keys = bibKeys(works);
    return works.map((w, i) => {
      const kind = kindOf(w);
      const type = { article: "article", conference: "inproceedings", abstract: "inproceedings", chapter: "incollection",
        book: "book", thesis: "phdthesis" }[kind] || "misc";
      const container = { article: "journal", conference: "booktitle", abstract: "booktitle", chapter: "booktitle" }[kind] || "howpublished";
      const b = biblio(w);
      const fields = [
        ["author", (w.authors || []).map((name) => {
          const n = splitName(name);
          return n.given ? `${bibEscape(n.family)}, ${bibEscape(n.given)}` : `{${bibEscape(n.family)}}`;
        }).join(" and ")],
        ["title", `{${bibEscape(plainTitle(w))}}`],
        [container, w.journal ? bibEscape(w.journal) : ""],
        ["year", yearOf(w)],
        ["date", w.publication_date || ""],
        ["volume", b.volume ? bibEscape(b.volume) : ""],
        ["number", b.issue ? bibEscape(b.issue) : ""],
        ["pages", bibEscape(pageRange(w, "--"))],
        ["doi", bibEscape(doiOf(w))],
        ["url", w.doi ? "" : urlOf(w)],
        ["note", LABEL[kind] || ""],
      ].filter(([, v]) => v);
      return `@${type}{${keys[i]},\n` + fields.map(([k, v]) => `  ${k} = {${v}}`).join(",\n") + "\n}\n";
    }).join("\n");
  }

  // ------------------------------------------------------------------------------------------------ RIS

  function ris(works) {
    const line = (tag, value) => (value ? `${tag}  - ${String(value).replace(/\s*[\r\n]+\s*/g, " ")}\r\n` : "");
    return works.map((w) => {
      const kind = kindOf(w);
      const type = { article: "JOUR", preprint: "UNPB", conference: "CPAPER", abstract: "ABST", chapter: "CHAP", book: "BOOK",
        dataset: "DATA", software: "COMP", thesis: "THES" }[kind] || "GEN";
      const b = biblio(w);
      const date = String(w.publication_date || "");
      return line("TY", type) +
        (w.authors || []).map((name) => {
          const n = splitName(name);
          return line("AU", n.given ? `${n.family}, ${n.given}` : n.family);
        }).join("") +
        line("TI", plainTitle(w)) +
        line("T2", w.journal) +
        line("PY", yearOf(w)) +
        line("DA", date.replace(/-/g, "/")) +
        line("VL", b.volume) +
        line("IS", b.issue) +
        line("SP", b.first_page) +
        line("EP", b.last_page) +
        line("DO", doiOf(w)) +
        line("UR", urlOf(w)) +
        line("N1", LABEL[kind]) +
        "ER  - \r\n";
    }).join("\r\n");
  }

  // ------------------------------------------------------------------------------------------------ publication list

  // Sections of a publication list, in this order; papers keep the list order (newest first) within a section.
  const SECTIONS = [
    ["Journal articles", ["article"], (w) => w.type !== "review"],
    ["Reviews", ["article"], (w) => w.type === "review"],
    ["Conference papers and abstracts", ["conference", "abstract"]],
    ["Books and book chapters", ["book", "chapter"]],
    ["Theses", ["thesis"]],
    ["Preprints", ["preprint"]],
    ["Datasets and software", ["dataset", "software"]],
    ["Other", ["other"]],
  ];

  function sections(works) {
    return SECTIONS.map(([title, kinds, test]) => ({
      title,
      works: works.filter((w) => kinds.includes(kindOf(w)) && (!test || test(w))),
    })).filter((s) => s.works.length);
  }

  const sentence = (s) => (/[.?!]$/.test(s) ? s : s + ".");

  // One reference as text segments {t, b (bold), i (italic)}: Vancouver style. Long author lists show the first ten
  // authors and every highlighted one, then "et al.".
  function segments(w, highlight) {
    const names = w.authors || [];
    const members = w.author_members || [];
    const shown = names.length <= 20
      ? names.map((_, i) => i)
      : names.map((_, i) => i).filter((i) => i < 10 || highlight.has(members[i]));
    const out = [];
    shown.forEach((i, k) => {
      const n = splitName(names[i]);
      if (k > 0) out.push({ t: shown[k - 1] === i - 1 ? ", " : ", … " });
      out.push({ t: n.given ? `${n.family} ${initials(n.given)}` : n.family, b: highlight.has(members[i]) });
    });
    if (shown.length && shown[shown.length - 1] < names.length - 1) out.push({ t: ", et al" });
    if (out.length) out.push({ t: ". " });
    const b = biblio(w);
    let source = String(yearOf(w) || "");
    if (b.volume) source += `;${b.volume}`;
    if (b.issue) source += `(${b.issue})`;
    if (pageRange(w)) source += `:${pageRange(w)}`;
    out.push({ t: sentence(plainTitle(w)) + " " });
    if (w.journal) out.push({ t: w.journal, i: true }, { t: ". " });
    if (source) out.push({ t: sentence(source) + " " });
    out.push({ t: w.doi ? `doi:${doiOf(w)}` : urlOf(w) });
    return out.filter((x) => x.t);
  }

  // The list as {title, note, sections: [{title, items: [{number, segments}]}]}, numbered straight through.
  function publicationList(works, { title = "Publications", note = "", highlight = [] } = {}) {
    const marked = new Set(highlight);
    let number = 0;
    return {
      title,
      note,
      sections: sections(works).map((s) => ({
        title: s.title,
        items: s.works.map((w) => ({ number: ++number, segments: segments(w, marked) })),
      })),
    };
  }

  function text(works, options = {}) {
    const list = publicationList(works, options);
    const plain = (segs) => segs.map((x) => x.t).join("");
    return [list.title, list.note, ...list.sections.flatMap((s) => ["", s.title, ...s.items.map((it) => `${it.number}. ${plain(it.segments)}`)])]
      .filter((line, i) => i !== 1 || line).join("\n") + "\n";
  }

  const htmlEscape = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  // HTML for the clipboard: pasting into Word, Outlook or Google Docs keeps the headings, bold and italics.
  function html(works, options = {}) {
    const list = publicationList(works, options);
    const seg = (x) => (x.b ? `<b>${htmlEscape(x.t)}</b>` : x.i ? `<i>${htmlEscape(x.t)}</i>` : htmlEscape(x.t));
    return `<h1>${htmlEscape(list.title)}</h1>` + (list.note ? `<p><i>${htmlEscape(list.note)}</i></p>` : "") +
      list.sections.map((s) => `<h2>${htmlEscape(s.title)}</h2>` +
        s.items.map((it) => `<p>${it.number}. ${it.segments.map(seg).join("")}</p>`).join("")).join("");
  }

  // ------------------------------------------------------------------------------------------------ Word

  const xml = (s) =>
    String(s ?? "")
      .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const run = (t, props = "") =>
    t ? `<w:r>${props ? `<w:rPr>${props}</w:rPr>` : ""}<w:t xml:space="preserve">${xml(t)}</w:t></w:r>` : "";
  const para = (runs, props = "") => `<w:p>${props ? `<w:pPr>${props}</w:pPr>` : ""}${runs}</w:p>`;

  function documentXml(works, options = {}) {
    const list = publicationList(works, options);
    let body = para(run(list.title), '<w:pStyle w:val="Heading1"/>');
    if (list.note) body += para(run(list.note, '<w:i/><w:color w:val="555555"/><w:sz w:val="18"/>'));
    for (const s of list.sections) {
      body += para(run(s.title), '<w:pStyle w:val="Heading2"/>');
      for (const it of s.items) {
        const runs = it.segments.map((x) => run(x.t, x.b ? "<w:b/>" : x.i ? "<w:i/>" : "")).join("");
        body += para(run(`${it.number}.\t`) + runs, '<w:ind w:left="567" w:hanging="567"/>');
      }
    }
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body +
      '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>' +
      "</w:body></w:document>";
  }

  const STYLES = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' +
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" w:cs="Calibri"/>' +
    '<w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="en-GB"/></w:rPr></w:rPrDefault>' +
    '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>' +
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>' +
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>' +
    '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>' +
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>' +
    '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:style>' +
    "</w:styles>";

  const CONTENT_TYPES = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
    '<Default Extension="xml" ContentType="application/xml"/>' +
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' +
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>' +
    "</Types>";
  const ROOT_RELS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>' +
    "</Relationships>";
  const DOC_RELS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' +
    "</Relationships>";

  // Minimal zip writer (stored entries, no compression): enough for a .docx.
  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[n] = c >>> 0;
    }
    return table;
  })();
  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }
  function zip(files) {
    const encoder = new TextEncoder();
    const parts = [];
    const central = [];
    let offset = 0;
    const DOS_DATE = 0x21; // 1980-01-01: a fixed date keeps the output reproducible
    for (const file of files) {
      const name = encoder.encode(file.name);
      const data = typeof file.data === "string" ? encoder.encode(file.data) : file.data;
      const crc = crc32(data);
      const local = new DataView(new ArrayBuffer(30));
      local.setUint32(0, 0x04034b50, true);
      local.setUint16(4, 20, true);
      local.setUint16(6, 0x0800, true); // UTF-8 names
      local.setUint16(12, DOS_DATE, true);
      local.setUint32(14, crc, true);
      local.setUint32(18, data.length, true);
      local.setUint32(22, data.length, true);
      local.setUint16(26, name.length, true);
      parts.push(new Uint8Array(local.buffer), name, data);
      const entry = new DataView(new ArrayBuffer(46));
      entry.setUint32(0, 0x02014b50, true);
      entry.setUint16(4, 20, true);
      entry.setUint16(6, 20, true);
      entry.setUint16(8, 0x0800, true);
      entry.setUint16(14, DOS_DATE, true);
      entry.setUint32(16, crc, true);
      entry.setUint32(20, data.length, true);
      entry.setUint32(24, data.length, true);
      entry.setUint16(28, name.length, true);
      entry.setUint32(42, offset, true);
      central.push(new Uint8Array(entry.buffer), name);
      offset += 30 + name.length + data.length;
    }
    const centralSize = central.reduce((n, a) => n + a.length, 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true);
    end.setUint16(8, files.length, true);
    end.setUint16(10, files.length, true);
    end.setUint32(12, centralSize, true);
    end.setUint32(16, offset, true);
    const chunks = [...parts, ...central, new Uint8Array(end.buffer)];
    const out = new Uint8Array(chunks.reduce((n, a) => n + a.length, 0));
    let at = 0;
    for (const chunk of chunks) {
      out.set(chunk, at);
      at += chunk.length;
    }
    return out;
  }

  function docx(works, options = {}) {
    return zip([
      { name: "[Content_Types].xml", data: CONTENT_TYPES },
      { name: "_rels/.rels", data: ROOT_RELS },
      { name: "word/_rels/document.xml.rels", data: DOC_RELS },
      { name: "word/styles.xml", data: STYLES },
      { name: "word/document.xml", data: documentXml(works, options) },
    ]);
  }

  const DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  window.PubpulseReferences = { splitName, bibtex, ris, docx, documentXml, text, html, DOCX_TYPE };
})();
