/* pubpulse front-end: loads data/publications.json and filters it client-side. State lives in the URL hash. */
(() => {
  const $ = (id) => document.getElementById(id);
  const els = {
    q: $("q"), when: $("when"), verify: $("verify"), onlyOa: $("only-oa"), year: $("year"),
    type: $("type"), journal: $("journal"), sort: $("sort"), people: $("people"), peopleQ: $("people-q"),
    list: $("list"), count: $("count"), empty: $("empty"), chips: $("active-chips"), attention: $("attention"),
  };
  let data = null;
  let state = readHash();

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    return {
      q: p.get("q") || "", year: p.get("year") || "", type: p.get("type") || "", journal: p.get("journal") || "",
      sort: p.get("sort") || "date", people: (p.get("people") || "").split(",").filter(Boolean),
      when: p.get("when") || (p.get("new") === "1" ? "week" : ""), verify: p.get("verify") || "", oa: p.get("oa") === "1",
    };
  }
  function writeHash() {
    const p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.year) p.set("year", state.year);
    if (state.type) p.set("type", state.type);
    if (state.journal) p.set("journal", state.journal);
    if (state.sort !== "date") p.set("sort", state.sort);
    if (state.people.length) p.set("people", state.people.join(","));
    if (state.when) p.set("when", state.when);
    if (state.verify) p.set("verify", state.verify);
    if (state.oa) p.set("oa", "1");
    history.replaceState(null, "", p.toString() ? "#" + p.toString() : location.pathname);
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const nameOf = (slug) => (data.peopleBySlug[slug] || {}).name || slug;
  const fmtType = (t) => (t || "").replace(/-/g, " ");

  function fillSelect(el, values, current) {
    const first = el.options[0];
    el.innerHTML = "";
    el.appendChild(first);
    for (const [v, label] of values) {
      const o = document.createElement("option");
      o.value = v; o.textContent = label; if (v === current) o.selected = true;
      el.appendChild(o);
    }
  }

  function init(json) {
    data = json;
    data.peopleBySlug = Object.fromEntries(data.people.map((p) => [p.slug, p]));
    data.newIds = new Set(data.last_run && !data.last_run.baseline ? data.last_run.new_ids : []);
    $("group-name").textContent = data.group_name || "";
    $("updated").textContent = "Updated " + (data.generated || "").slice(0, 10);
    $("repo-link").href = data.repo_url || "#";
    const list = data.list || {};
    $("list-links").innerHTML = (list.subscribe_url ? `<a href="${esc(list.subscribe_url)}" target="_blank" rel="noopener"><b>Get the weekly email</b></a> · ` : "") +
      (list.unsubscribe_url ? `<a href="${esc(list.unsubscribe_url)}" target="_blank" rel="noopener">unsubscribe</a> · ` : "");

    const years = [...new Set(data.works.map((w) => w.year).filter(Boolean))].sort((a, b) => b - a);
    fillSelect(els.year, years.map((y) => [String(y), String(y)]), state.year);
    const types = [...new Set(data.works.map((w) => w.type).filter(Boolean))].sort();
    fillSelect(els.type, types.map((t) => [t, fmtType(t)]), state.type);
    const jc = {};
    for (const w of data.works) if (w.journal) jc[w.journal] = (jc[w.journal] || 0) + 1;
    const journals = Object.entries(jc).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    fillSelect(els.journal, journals.map(([j, n]) => [j, `${j} (${n})`]), state.journal);

    els.q.value = state.q; els.sort.value = state.sort; els.verify.value = state.verify; els.when.value = state.when;
    els.onlyOa.checked = state.oa;
    renderPeople();

    const review = data.people.filter((p) => p.needs_review);
    if (review.length) {
      els.attention.classList.remove("hidden");
      els.attention.innerHTML = `<details><summary><b>${review.length} ${review.length === 1 ? "person" : "people"} not matched yet</b></summary>` +
        "No ORCID on the staff profile and no OpenAlex author with a group affiliation: " +
        review.map((p) => esc(p.name)).join(", ") + ". Their papers are not tracked until an ORCID is added to the staff profile.</details>";
    }

    els.q.addEventListener("input", () => { state.q = els.q.value; update(); });
    els.year.addEventListener("change", () => { state.year = els.year.value; update(); });
    els.type.addEventListener("change", () => { state.type = els.type.value; update(); });
    els.journal.addEventListener("change", () => { state.journal = els.journal.value; update(); });
    els.sort.addEventListener("change", () => { state.sort = els.sort.value; update(); });
    els.when.addEventListener("change", () => { state.when = els.when.value; update(); });
    els.verify.addEventListener("change", () => { state.verify = els.verify.value; update(); });
    els.onlyOa.addEventListener("change", () => { state.oa = els.onlyOa.checked; update(); });
    els.peopleQ.addEventListener("input", renderPeople);
    $("clear-people").addEventListener("click", () => { state.people = []; renderPeople(); update(); });
    $("reset").addEventListener("click", () => {
      state = { q: "", year: "", type: "", journal: "", sort: "date", people: [], when: "", verify: "", oa: false };
      els.q.value = ""; els.year.value = ""; els.type.value = ""; els.journal.value = ""; els.sort.value = "date"; els.verify.value = ""; els.when.value = "";
      els.onlyOa.checked = false;
      renderPeople(); update();
    });
    window.addEventListener("hashchange", () => { state = readHash(); init(data); });
    update();
  }

  function renderPeople() {
    const counts = {};
    for (const w of data.works) for (const s of w.group_members) counts[s] = (counts[s] || 0) + 1;
    const q = els.peopleQ.value.trim().toLowerCase();
    const people = data.people
      .filter((p) => !q || p.name.toLowerCase().includes(q))
      .sort((a, b) => (b.active - a.active) || (counts[b.slug] || 0) - (counts[a.slug] || 0) || a.name.localeCompare(b.name));
    els.people.innerHTML = people.map((p) => `
      <label class="${p.active ? "" : "inactive"}" title="${p.active ? "" : p.tracked ? "left the group; papers with a group affiliation still counted until " + p.tracked_until : "no longer in the group"}">
        <input type="checkbox" value="${esc(p.slug)}" ${state.people.includes(p.slug) ? "checked" : ""}>
        ${esc(p.name)} <span class="n">${counts[p.slug] || 0}</span>
      </label>`).join("");
    els.people.querySelectorAll("input").forEach((cb) => cb.addEventListener("change", () => {
      state.people = cb.checked ? [...state.people, cb.value] : state.people.filter((s) => s !== cb.value);
      update();
    }));
  }

  function inPeriod(w, when) {
    if (!w.publication_date) return false;
    const d = new Date(w.publication_date + "T00:00:00Z");
    const now = new Date();
    if (when === "year") return d.getUTCFullYear() === now.getUTCFullYear();
    const days = { "30d": 30, "90d": 90, "12m": 365 }[when];
    return days ? (now - d) / 86400000 <= days : true;
  }

  function matches(w) {
    if (state.when === "week" && !data.newIds.has(w.id)) return false;
    if (state.when && state.when !== "week" && !inPeriod(w, state.when)) return false;
    if (state.verify === "verified" && !w.verified) return false;
    if (state.verify === "unverified" && w.verified) return false;
    if (state.oa && !w.is_oa) return false;
    if (state.year && String(w.year) !== state.year) return false;
    if (state.type && w.type !== state.type) return false;
    if (state.journal && w.journal !== state.journal) return false;
    if (state.people.length && !state.people.some((s) => w.group_members.includes(s))) return false;
    if (state.q) {
      const hay = (w.title + " " + w.authors.join(" ") + " " + (w.journal || "") + " " + w.group_members.map(nameOf).join(" ")).toLowerCase();
      if (!state.q.toLowerCase().split(/\s+/).every((t) => hay.includes(t))) return false;
    }
    return true;
  }

  function update() {
    writeHash();
    let items = data.works.filter(matches);
    if (state.sort === "cited") items.sort((a, b) => (b.cited_by_count || 0) - (a.cited_by_count || 0));
    else if (state.sort === "added") items.sort((a, b) => (b.first_seen || "").localeCompare(a.first_seen || "") || (b.publication_date || "").localeCompare(a.publication_date || ""));
    else items.sort((a, b) => (b.publication_date || "").localeCompare(a.publication_date || ""));
    els.count.textContent = `${items.length} of ${data.works.length} publications` + (data.newIds.size ? ` · ${data.newIds.size} new this week` : "");
    els.chips.innerHTML = state.people.map((s) => `<button class="chip" data-slug="${esc(s)}" title="remove">${esc(nameOf(s))} ✕</button>`).join("");
    els.chips.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
      state.people = state.people.filter((s) => s !== c.dataset.slug); renderPeople(); update();
    }));
    els.list.innerHTML = items.map(render).join("");
    els.empty.classList.toggle("hidden", items.length > 0);
    els.list.querySelectorAll("[data-person]").forEach((b) => b.addEventListener("click", () => {
      const s = b.dataset.person;
      if (!state.people.includes(s)) state.people = [...state.people, s];
      renderPeople(); update(); window.scrollTo({ top: 0, behavior: "smooth" });
    }));
  }

  function render(w) {
    const link = w.doi || w.landing_url || w.openalex_url;
    const isNew = data.newIds.has(w.id);
    const members = w.group_members.map((s) => {
      const st = (w.affiliation_status || {})[s] || "unknown";
      const affs = (w.member_affiliations && w.member_affiliations[s] || []).join("; ");
      const mark = st === "verified" ? "" : st === "mismatch" ? " <span class='badge warn' title='other affiliation on this paper'>other affil.</span>" : " <span class='badge warn' title='no affiliation recorded by OpenAlex'>no affil.</span>";
      return `<button class="link" data-person="${esc(s)}" title="${esc(affs || "no affiliation recorded by OpenAlex")}"><b>${esc(nameOf(s))}</b>${mark}</button>`;
    }).join(", ");
    const others = w.authors.length > 12 ? w.authors.slice(0, 12).join(", ") + ` … (${w.author_count} authors)` : w.authors.join(", ");
    const meta = [w.journal, w.publication_date, fmtType(w.type), w.cited_by_count ? `${w.cited_by_count} citations` : null].filter(Boolean).map(esc).join(" · ");
    return `<li class="item">
      <h3><a href="${esc(link)}" target="_blank" rel="noopener">${esc(w.title)}</a>
        <span class="badges">${isNew ? '<span class="badge new">new</span>' : ""}${w.manual === "confirmed" ? '<span class="badge oa">confirmed</span>' : w.verified ? "" : '<span class="badge warn">unverified</span>'}${w.is_oa ? '<span class="badge oa">open access</span>' : ""}</span></h3>
      <div class="meta">${meta}</div>
      <div class="authors">Group: ${members}</div>
      <div class="authors">${esc(others)}</div>
      ${w.abstract ? `<details><summary>Abstract</summary><p>${esc(w.abstract)}</p></details>` : ""}
      <div class="links">${w.doi ? `<a href="${esc(w.doi)}" target="_blank" rel="noopener">DOI</a>` : ""}${w.oa_url ? `<a href="${esc(w.oa_url)}" target="_blank" rel="noopener">Full text</a>` : ""}<a href="${esc(w.openalex_url)}" target="_blank" rel="noopener">OpenAlex</a><span class="meta" title="use this id in overrides.yml">${esc(w.id)}</span></div>
    </li>`;
  }

  fetch("data/publications.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(init)
    .catch((e) => { els.count.textContent = "Could not load data/publications.json (" + e.message + ")."; });
})();
