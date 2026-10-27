/* Social post studio: find a paper (pubpulse collection, else OpenAlex by DOI), then mount the share editor. */
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let data = { works: [], people: [] };
  let drafts = {};
  let libraryReady;
  let lookupVersion = 0;

  const normDoi = (s) => (String(s || "").match(/10\.\d{4,9}\/[^\s"<>]+/i) || [""])[0].replace(/[.,;)]+$/, "").toLowerCase();
  const nameOf = (slug) => (data.people.find((p) => p.slug === slug) || {}).name || slug;

  function fromCollection(w) {
    return {
      id: w.id, title: w.title, journal: w.journal, publication_date: w.publication_date, type: w.type,
      link: w.doi || w.landing_url || w.openalex_url, oa_url: w.oa_url, authors: w.authors, author_count: w.author_count,
      group_authors: (w.group_members || []).map(nameOf), abstract: w.abstract, source: "pubpulse",
    };
  }

  function abstractFromIndex(index) {
    if (!index) return "";
    const words = [];
    for (const [word, positions] of Object.entries(index)) for (const i of positions) words[i] = word;
    return words.filter(Boolean).join(" ");
  }

  // A paper outside the collection: group authors are recognised by their OpenAlex id or ORCID.
  function fromOpenAlex(raw) {
    const byId = new Map(), byOrcid = new Map();
    for (const p of data.people) {
      for (const id of p.openalex_ids || []) byId.set(id, p.name);
      for (const o of [p.orcid, p.orcid_discovered]) if (o) byOrcid.set(String(o).toUpperCase(), p.name);
    }
    const short = (u) => String(u || "").split("/").pop();
    const authorships = raw.authorships || [];
    const group = [...new Set(authorships.map((a) => byId.get(short(a.author?.id)) || byOrcid.get(short(a.author?.orcid).toUpperCase())).filter(Boolean))];
    return {
      id: short(raw.id), title: raw.title || raw.display_name, journal: raw.primary_location?.source?.display_name,
      publication_date: raw.publication_date, type: raw.type, link: raw.doi || raw.id, oa_url: raw.open_access?.oa_url,
      authors: authorships.map((a) => a.author?.display_name).filter(Boolean), author_count: authorships.length,
      group_authors: group, abstract: abstractFromIndex(raw.abstract_inverted_index), source: "OpenAlex",
    };
  }

  async function find(query) {
    const q = String(query || "").trim();
    if (!q) return null;
    await libraryReady;
    const wid = (q.match(/\bW\d{4,}\b/) || [])[0];
    const doi = normDoi(q);
    const local = data.works.find((w) => (wid && w.id === wid) || (doi && normDoi(w.doi) === doi));
    if (local) return fromCollection(local);
    const key = wid || (doi ? "doi:" + doi : null);
    if (!key) throw new Error("That does not look like a DOI (10.xxxx/…) or an OpenAlex id (W…).");
    const r = await fetch(`https://api.openalex.org/works/${encodeURIComponent(key)}?mailto=s.puts@maastrichtuniversity.nl`);
    if (!r.ok) throw new Error(r.status === 404 ? "OpenAlex does not know this DOI (yet). New papers can take a few days." : `OpenAlex lookup failed (${r.status}).`);
    return fromOpenAlex(await r.json());
  }

  function show(paper) {
    const draft = drafts[paper.id] || null;
    const warn = paper.type === "preprint" ? '<p class="studio-warn">This is a preprint. Preprints are not posted externally.</p>' : "";
    $("paper-card").classList.remove("hidden");
    $("paper-card").innerHTML =
      `<div class="studio-paper-top"><p class="meta">${esc(paper.journal || "Publication")} · ${esc(paper.publication_date || "")}</p>` +
      ` ${draft?.post ? '<span class="badge ready">Draft available</span>' : '<span class="badge">Ready to draft</span>'}</div>` +
      `<h3><a href="${esc(paper.link)}" target="_blank" rel="noopener">${esc(paper.title)}</a></h3>` +
      `<p class="studio-paper-authors">CDS authors: ${esc(paper.group_authors.join(", ") || "none identified in this record")}</p>` +
      (paper.abstract ? `<details class="studio-paper-context"><summary>Abstract &amp; source details</summary><p>${esc(paper.abstract)}</p><p class="meta">${esc(paper.source)} · ${esc((paper.type || "publication").replace(/-/g, " "))}</p></details>` : '<p class="studio-warn">No abstract was found. Add the abstract in your AI chat before asking it to write the post.</p>') + warn;
    window.PubpulseSocial.mount($("studio-editor"), paper, { draft, prompt: data.social_prompt });
    const url = new URL(location.href);
    url.search = "";
    url.searchParams.set(paper.source === "pubpulse" ? "id" : "doi", paper.source === "pubpulse" ? paper.id : normDoi(paper.link) || paper.id);
    history.replaceState(null, "", url);
  }

  async function load(query) {
    const version = ++lookupVersion;
    const button = $("paper-form").querySelector("button");
    button.disabled = true;
    $("paper-msg").textContent = "Looking up the paper…";
    try {
      const paper = await find(query);
      if (version !== lookupVersion) return;
      if (!paper) { $("paper-msg").textContent = ""; return; }
      $("paper-msg").textContent = "";
      show(paper);
    } catch (e) {
      if (version === lookupVersion) $("paper-msg").textContent = e.message;
    } finally {
      if (version === lookupVersion) button.disabled = false;
    }
  }

  $("paper-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    load($("paper-q").value);
  });

  libraryReady = Promise.all([
    fetch("data/publications.json", { cache: "no-cache" }).then((r) => r.json()),
    fetch("data/social/index.json", { cache: "no-cache" }).then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
  ]).then(([pubs, social]) => {
    data = pubs;
    drafts = social;
    const params = new URLSearchParams(location.search);
    const start = params.get("id") || params.get("doi");
    if (start) { $("paper-q").value = start; load(start); }
  }).catch(() => { $("paper-msg").textContent = "Could not load pubpulse data; DOIs are still looked up in OpenAlex."; });
})();
