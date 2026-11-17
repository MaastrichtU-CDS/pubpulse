/* Maastro divisions page: all Maastro papers per division, from data/divisions.json (pubpulse/divisions.py).
   Separate from the CDS data. A paper credited to several divisions counts in each row and once in the total. */
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const fmt = (n) => n.toLocaleString("en-GB");
  const NONE = "__none__"; // filter value for papers without an identified division
  const MAASTRO_LED = "__maastricht__", OUTSIDE = "__outside__"; // "Led by" values: last author in / outside Maastricht
  const PAGE = 100;
  const GROUPS = {
    journal: ["article", "review", "letter", "editorial"],
    conference: ["conference-abstract", "conference-paper"],
    preprint: ["preprint"],
  };
  const groupOf = (type) => Object.keys(GROUPS).find((g) => GROUPS[g].includes(type)) || "other";
  let data = null;
  let showAll = false;

  const inYear = (w) => !$("dv-year").value || String(w.year) === $("dv-year").value;
  const inDivision = (w, division) => (division === NONE ? !w.divisions.length : !division || w.divisions.includes(division));
  const inLead = (w, lead) =>
    !lead || (lead === MAASTRO_LED ? w.last_author_home : lead === OUTSIDE ? !w.last_author_home : w.led_by === lead);
  const current = () => data.works.filter((w) => inYear(w) && inDivision(w, $("dv-division").value) && inLead(w, $("dv-lead").value));

  function stats(works, division) {
    const s = { papers: works.length, led: 0, journal: 0, conference: 0, preprint: 0, other: 0, first: 0, last: 0, oa: 0, citations: 0 };
    for (const w of works) {
      s[groupOf(w.type)]++;
      if (w.last_author_home) s.led++;
      const lead = division && w.leaders[division];
      if (lead && (lead.position === "first" || lead.position === "only")) s.first++;
      if (lead && lead.position === "last") s.last++;
      if (w.is_oa) s.oa++;
      s.citations += w.cited_by_count || 0;
    }
    return s;
  }

  const cells = (s, leader = true) =>
    [s.papers, s.led, s.journal, s.conference, s.preprint, s.other].map((n) => `<td class="num">${fmt(n)}</td>`).join("") +
    (leader ? `<td class="num">${fmt(s.first)}</td><td class="num">${fmt(s.last)}</td>` : '<td class="num">–</td><td class="num">–</td>') +
    `<td class="num">${s.papers ? Math.round((100 * s.oa) / s.papers) + "%" : "–"}</td><td class="num">${fmt(s.citations)}</td>`;

  function renderTable() {
    const year = data.works.filter(inYear);
    const chosen = $("dv-division").value;
    const row = (value, label, leader, works, leaderCols) =>
      `<tr${value === chosen ? ' class="is-selected"' : ""}><th scope="row"><button type="button" class="link" data-division="${esc(value)}">${label}</button></th>` +
      `<td>${esc(leader)}</td>${cells(stats(works, value), leaderCols)}</tr>`;
    $("dv-rows").innerHTML =
      data.divisions.map((d) => row(d.division, esc(d.division), d.leader, year.filter((w) => w.divisions.includes(d.division)), true)).join("") +
      row(NONE, "<i>Division not identified</i>", "", year.filter((w) => !w.divisions.length), false);
    const shared = year.filter((w) => w.divisions.length > 1).length;
    $("dv-total").innerHTML =
      `<tr><th scope="row" colspan="2"><button type="button" class="link" data-division="">All Maastro, distinct papers</button>` +
      `${shared ? ` <span class="dv-hint">(${fmt(shared)} credited to more than one division, counted once)</span>` : ""}</th>${cells(stats(year), false)}</tr>`;
  }

  function renderList() {
    const works = current();
    const chosen = $("dv-division").value;
    const label = chosen === NONE ? "division not identified" : chosen || "all Maastro";
    const leadValue = $("dv-lead").value;
    const lead = leadValue === MAASTRO_LED ? "Maastricht-led" : leadValue === OUTSIDE ? "led from outside Maastricht" : leadValue ? "led by " + leadValue : "";
    $("dv-list-heading").textContent = `Papers: ${[label, lead, $("dv-year").value].filter(Boolean).join(", ")} (${fmt(works.length)})`;
    const shown = showAll ? works : works.slice(0, PAGE);
    $("dv-papers").innerHTML = shown.length
      ? shown.map((w) => {
          const tags = (w.divisions.length ? w.divisions.map((d) => `<span class="dv-tag">${esc(d)}</span>`).join("") : '<span class="dv-tag is-none">Division not identified</span>') +
            (w.led_by ? `<span class="dv-tag is-lead">Led by ${esc(w.led_by)}${w.led_by_division ? " (division leader)" : ""}</span>`
              : w.last_author_home ? "" : '<span class="dv-tag is-outside">Led from outside Maastricht</span>');
          const lead = chosen && chosen !== NONE && w.leaders[chosen] ? ` · leader ${esc(w.leaders[chosen].position)} author` : "";
          const authors = [w.first_author, w.last_author].filter(Boolean).map(esc).join(" … ");
          return `<li><a href="${esc(w.doi || "https://openalex.org/" + w.id)}" target="_blank" rel="noopener">${esc(w.title)}</a>` +
            `<span class="meta">${esc(w.journal || "No journal")} · ${esc(w.publication_date || "")} · ${esc((w.type || "").replace(/-/g, " "))}${lead}</span>` +
            `<span class="meta">${authors}${w.maastro ? "" : " · leader's Maastricht affiliation, no Maastro"}</span><span class="dv-tags">${tags}</span></li>`;
        }).join("")
      : "<li>No papers for this selection.</li>";
    $("dv-more").hidden = showAll || works.length <= PAGE;
    $("dv-more").textContent = `Show all ${fmt(works.length)}`;
  }

  function renderFrequent() {
    $("dv-freq-rows").innerHTML = (data.frequent_leaders || []).map((f) =>
      `<tr><th scope="row"><button type="button" class="link" data-lead="${esc(f.name)}">${esc(f.name)}</button></th>` +
      `<td class="num">${fmt(f.papers)}</td><td class="num">${fmt(f.unidentified)}</td>` +
      `<td>${Object.entries(f.divisions).map(([d, n]) => `${esc(d)} (${fmt(n)})`).join(", ") || '<span class="dv-hint">none</span>'}</td></tr>`).join("");
    $("dv-freq").hidden = !(data.frequent_leaders || []).length;
  }

  function render() {
    renderTable();
    renderList();
    const url = new URL(location.href);
    for (const [key, id] of [["division", "dv-division"], ["lead", "dv-lead"], ["year", "dv-year"]]) {
      if ($(id).value) url.searchParams.set(key, $(id).value);
      else url.searchParams.delete(key);
    }
    history.replaceState(null, "", url);
  }

  function csv() {
    const head = ["openalex_id", "doi", "title", "journal", "publication_date", "type", "divisions", "led_by", "maastricht_led", "first_author", "last_author", "maastro_affiliation", "open_access", "cited_by_count"];
    const quote = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = [head.join(",")];
    for (const w of current())
      lines.push([w.id, w.doi, w.title, w.journal, w.publication_date, w.type, w.divisions.join("; ") || "not identified", w.led_by, w.last_author_home ? "yes" : "no", w.first_author, w.last_author, w.maastro ? "yes" : "no", w.is_oa ? "yes" : "no", w.cited_by_count].map(quote).join(","));
    const name = ["maastro", $("dv-division").value === NONE ? "not-identified" : $("dv-division").value, $("dv-year").value].filter(Boolean).join("-");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv" }));
    link.download = name.toLowerCase().replace(/[^a-z0-9]+/g, "-") + ".csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 2000);
  }

  fetch("data/divisions.json", { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
    .then((json) => {
      data = json;
      const options = data.divisions.map((d) => `<option value="${esc(d.division)}">${esc(d.division)} (${esc(d.leader)})</option>`);
      $("dv-division").insertAdjacentHTML("beforeend", options.join("") + `<option value="${NONE}">Division not identified</option>`);
      const leaders = data.divisions.map((d) => `<option value="${esc(d.leader)}">${esc(d.leader)} (${esc(d.division)})</option>`).join("");
      const frequent = (data.frequent_leaders || []).map((f) => `<option value="${esc(f.name)}">${esc(f.name)} (${fmt(f.papers)})</option>`).join("");
      $("dv-lead").insertAdjacentHTML("beforeend",
        `<option value="${MAASTRO_LED}">Anyone in Maastricht</option><option value="${OUTSIDE}">Led from outside Maastricht</option>` +
        `<optgroup label="Division leaders">${leaders}</optgroup>` + (frequent ? `<optgroup label="Frequent Maastricht leaders">${frequent}</optgroup>` : ""));
      $("dv-min").textContent = data.frequent_leader_min_papers || 2;
      const years = [...new Set(data.works.map((w) => w.year).filter(Boolean))].sort((a, b) => b - a);
      $("dv-year").insertAdjacentHTML("beforeend", years.map((y) => `<option>${y}</option>`).join(""));
      const params = new URLSearchParams(location.search);
      for (const [key, id] of [["division", "dv-division"], ["lead", "dv-lead"], ["year", "dv-year"]]) {
        const value = params.get(key);
        if (value && [...$(id).options].some((o) => o.value === value)) $(id).value = value;
      }
      $("dv-keywords").textContent = (data.keywords || []).join(", ");
      $("dv-updated").textContent = `Data since ${data.since_year}, updated ${new Date(data.generated).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}.`;
      $("dv-msg").textContent = "";
      $("dv-table").hidden = false;
      $("dv-csv").disabled = false;
      renderFrequent();
      render();
    })
    .catch(() => { $("dv-msg").textContent = "The division data could not be loaded. It is refreshed with the weekly sync."; });

  $("dv-division").addEventListener("change", () => { showAll = false; render(); });
  $("dv-year").addEventListener("change", () => { showAll = false; render(); });
  $("dv-lead").addEventListener("change", () => { showAll = false; render(); });
  $("dv-freq").addEventListener("click", (event) => {
    const button = event.target.closest("[data-lead]");
    if (!button) return;
    $("dv-lead").value = button.dataset.lead;
    $("dv-division").value = "";
    showAll = false;
    render();
    $("dv-list-heading").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  });
  $("dv-csv").addEventListener("click", csv);
  $("dv-more").addEventListener("click", () => { showAll = true; renderList(); });
  $("dv-table").addEventListener("click", (event) => {
    const button = event.target.closest("[data-division]");
    if (!button) return;
    $("dv-division").value = button.dataset.division;
    showAll = false;
    render();
    $("dv-list-heading").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  });
})();
