/* Social post studio: find a paper (pubpulse collection, else OpenAlex by DOI), then mount the share editor. */
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let data = { works: [], people: [] };
  let drafts = {};
  let index = [];
  let libraryReady;
  let libraryLoaded = false;
  let lookupVersion = 0;
  let looking = false;

  const normDoi = (s) => (String(s || "").match(/10\.\d{4,9}\/[^\s"<>]+/i) || [""])[0].replace(/[.,;)]+$/, "").toLowerCase();
  const nameOf = (slug) => (data.people.find((p) => p.slug === slug) || {}).name || slug;
  // Lowercase without accents, so "sóest" and "soest" match each other.
  const fold = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  function status(text, busy = false) {
    $("paper-msg").textContent = text;
    $("paper-msg").classList.toggle("is-busy", busy);
  }

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

  function buildIndex() {
    index = data.works.map((w) => {
      const members = (w.group_members || []).map(nameOf);
      return {
        w, members, doi: normDoi(w.doi), title: fold(w.title), people: fold(members.join(" ")),
        rest: fold([w.journal, w.year, w.id, ...(w.authors || [])].join(" ")),
      };
    });
  }

  // Every word must match somewhere; title, DOI and group-author hits rank above journal or co-author hits.
  function search(query) {
    const q = fold(query).trim();
    if (q.length < 2) return [];
    const doi = normDoi(query);
    const terms = q.split(/\s+/);
    const hits = [];
    for (const e of index) {
      let score = 0;
      if (doi && e.doi === doi) score = 100;
      else for (const t of terms) {
        const s = e.title.includes(t) || e.doi.includes(t) ? 3 : e.people.includes(t) ? 2 : e.rest.includes(t) ? 1 : 0;
        if (!s) { score = 0; break; }
        score += s;
      }
      if (score) hits.push({ score, e });
    }
    hits.sort((a, b) => b.score - a.score || String(b.e.w.publication_date).localeCompare(String(a.e.w.publication_date)));
    return hits.slice(0, 8).map((h) => h.e);
  }

  function mark(text, terms) {
    const s = String(text || ""), f = fold(s), hay = f.length === s.length ? f : s.toLowerCase();
    const on = new Array(s.length).fill(false);
    for (const t of terms) for (let i = hay.indexOf(t); i >= 0; i = hay.indexOf(t, i + t.length)) on.fill(true, i, i + t.length);
    let out = "";
    for (let i = 0, j; i < s.length; i = j) {
      for (j = i; j < s.length && on[j] === on[i]; j++);
      out += on[i] ? `<mark>${esc(s.slice(i, j))}</mark>` : esc(s.slice(i, j));
    }
    return out;
  }

  // Autocomplete: a combobox over the collection; anything else still goes to OpenAlex on submit.
  const input = $("paper-q");
  const list = $("paper-suggest");
  let matches = [];
  let active = -1;

  function setOpen(open) {
    list.hidden = !open;
    input.setAttribute("aria-expanded", String(open));
    if (!open) setActive(-1);
  }

  function setActive(i) {
    active = i;
    list.querySelectorAll('[role="option"]').forEach((li) => li.setAttribute("aria-selected", String(+li.dataset.i === i)));
    const li = i >= 0 ? $(`paper-opt-${i}`) : null;
    if (li) { input.setAttribute("aria-activedescendant", li.id); li.scrollIntoView({ block: "nearest" }); }
    else input.removeAttribute("aria-activedescendant");
  }

  function suggest() {
    const q = input.value.trim();
    matches = libraryLoaded ? search(q) : [];
    const terms = fold(q).split(/\s+/).filter(Boolean);
    let html = matches.map((e, i) =>
      `<li id="paper-opt-${i}" role="option" aria-selected="false" data-i="${i}">` +
      `<span class="studio-suggest-title">${mark(e.w.title, terms)}</span>` +
      `<span class="studio-suggest-meta">${drafts[e.w.id]?.post ? '<span class="badge ready">Draft</span>' : ""}` +
      `<span>${esc([e.members.join(", "), e.w.journal, e.w.year].filter(Boolean).join(" · "))}</span></span></li>`).join("");
    if (!matches.length && libraryLoaded && q.length >= 3)
      html = `<li class="studio-suggest-empty" aria-disabled="true">${normDoi(q)
        ? "Not in pubpulse. Press Enter to look this DOI up in OpenAlex."
        : "No papers in pubpulse match. Paste a DOI to find a paper outside the collection."}</li>`;
    list.innerHTML = html;
    setOpen(!!html && document.activeElement === input);
  }

  function pick(i) {
    const w = matches[i]?.w;
    if (!w) return;
    input.value = normDoi(w.doi) || w.id;
    setOpen(false);
    load(w.id);
  }

  input.addEventListener("input", suggest);
  input.addEventListener("focus", () => { if (input.value.trim()) suggest(); });
  input.addEventListener("blur", () => setOpen(false));
  input.addEventListener("keydown", (ev) => {
    const n = matches.length;
    if ((ev.key === "ArrowDown" || ev.key === "ArrowUp") && n) {
      ev.preventDefault();
      if (list.hidden) setOpen(true);
      setActive(ev.key === "ArrowDown" ? (active + 1) % n : active <= 0 ? n - 1 : active - 1);
    } else if (ev.key === "Enter" && !list.hidden && active >= 0) {
      ev.preventDefault();
      pick(active);
    } else if (ev.key === "Escape" && !list.hidden) {
      ev.preventDefault();
      setOpen(false);
    }
  });
  // Keep focus in the input while clicking an option, so blur does not close the list first.
  list.addEventListener("mousedown", (ev) => ev.preventDefault());
  list.addEventListener("click", (ev) => {
    const li = ev.target.closest('[role="option"]');
    if (li) pick(+li.dataset.i);
  });
  list.addEventListener("mousemove", (ev) => {
    const li = ev.target.closest('[role="option"]');
    if (li && +li.dataset.i !== active) setActive(+li.dataset.i);
  });

  async function find(query) {
    const q = String(query || "").trim();
    if (!q) return null;
    await libraryReady;
    const wid = (q.match(/\bW\d{4,}\b/) || [])[0];
    const doi = normDoi(q);
    const local = data.works.find((w) => (wid && w.id === wid) || (doi && normDoi(w.doi) === doi));
    if (local) return fromCollection(local);
    const key = wid || (doi ? "doi:" + doi : null);
    if (!key) {
      // Free text: take the best match from the collection, as shown first in the suggestions.
      const best = search(q)[0];
      if (best) return fromCollection(best.w);
      throw new Error("No paper in pubpulse matches that. Paste a DOI (10.xxxx/…) to find a paper outside the collection.");
    }
    const r = await fetch(`https://api.openalex.org/works/${encodeURIComponent(key)}?mailto=s.puts@maastrichtuniversity.nl`);
    if (!r.ok) throw new Error(r.status === 404 ? "OpenAlex does not know this DOI (yet). New papers can take a few days." : `OpenAlex lookup failed (${r.status}).`);
    return fromOpenAlex(await r.json());
  }

  // While a lookup runs: a placeholder card on first load, otherwise the current card is dimmed.
  function showPending() {
    const card = $("paper-card");
    if (!card.classList.contains("hidden")) { card.classList.add("is-stale"); return; }
    card.classList.remove("hidden");
    card.classList.add("is-skeleton");
    card.setAttribute("aria-hidden", "true");
    card.innerHTML = '<span class="studio-skel"></span>'.repeat(4);
  }

  function clearPending() {
    const card = $("paper-card");
    card.classList.remove("is-stale");
    if (!card.classList.contains("is-skeleton")) return;
    card.classList.remove("is-skeleton");
    card.removeAttribute("aria-hidden");
    card.classList.add("hidden");
    card.innerHTML = "";
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
    looking = true;
    status("Looking up the paper…", true);
    showPending();
    try {
      const paper = await find(query);
      if (version !== lookupVersion) return;
      clearPending();
      status("");
      if (paper) show(paper);
    } catch (e) {
      if (version !== lookupVersion) return;
      clearPending();
      status(e.message);
    } finally {
      if (version === lookupVersion) { button.disabled = false; looking = false; }
    }
  }

  $("paper-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    setOpen(false);
    load(input.value);
  });

  status("Loading the publication collection…", true);
  libraryReady = Promise.all([
    fetch("data/publications.json", { cache: "no-cache" }).then((r) => r.json()),
    fetch("data/social/index.json", { cache: "no-cache" }).then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
  ]).then(([pubs, social]) => {
    data = pubs;
    drafts = social;
    buildIndex();
    libraryLoaded = true;
    if (!looking) status("");
    if (document.activeElement === input && input.value.trim()) suggest();
  }).catch(() => { status("Could not load pubpulse data; DOIs are still looked up in OpenAlex."); });

  const params = new URLSearchParams(location.search);
  const start = params.get("id") || params.get("doi");
  if (start) { input.value = start; load(start); }
})();
