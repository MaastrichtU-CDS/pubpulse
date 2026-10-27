/* pubpulse front-end: loads data/publications.json and filters it client-side. State lives in the URL hash. */
(() => {
  const $ = (id) => document.getElementById(id);
  const els = {
    q: $("q"),
    when: $("when"),
    verify: $("verify"),
    onlyOa: $("only-oa"),
    preprints: $("include-preprints"),
    year: $("year"),
    type: $("type"),
    journal: $("journal"),
    sort: $("sort"),
    people: $("people"),
    peopleQ: $("people-q"),
    list: $("list"),
    count: $("count"),
    empty: $("empty"),
    profiles: $("selected-profiles"),
    attention: $("attention"),
    active: $("active-filters"),
  };
  const dialog = $("digest-dialog");
  document.querySelectorAll("[data-open-digest]").forEach((button) => {
    button.addEventListener("click", () => dialog.showModal());
  });
  $("close-digest").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    )
      dialog.close();
  });
  $("toggle-filters").addEventListener("click", () => {
    const expanded =
      $("toggle-filters").getAttribute("aria-expanded") !== "true";
    $("toggle-filters").setAttribute("aria-expanded", String(expanded));
    $("filter-toggle-label").textContent = expanded ? "Hide" : "Show";
    $("filters").classList.toggle("is-open", expanded);
  });
  const TYPE_GROUPS = [
    { key: "article", label: "Journal articles", color: "#2a78d6", types: ["article"], filter: "article" },
    { key: "review", label: "Reviews", color: "#eb6834", types: ["review"], filter: "review" },
    { key: "preprint", label: "Preprints", color: "#1baf7a", types: ["preprint"], filter: "preprint" },
    { key: "conference", label: "Conference", color: "#eda100", types: ["conference-paper", "conference-abstract"], filter: null },
    { key: "other", label: "Other", color: "#e87ba4", types: null, filter: null },
  ];

  // Old links used raw OpenAlex types (type=conference-paper); map them onto the groups the bar and dropdown use.
  const toTypeGroup = (t) => (TYPE_GROUPS.some((g) => g.key === t) ? t : typeGroupKey(t));

  function typeGroupKey(type) {
    const g = TYPE_GROUPS.find((g) => g.types && g.types.includes(type));
    return g ? g.key : "other";
  }

  let initialHash = location.hash;
  let data = null;
  let listenersBound = false;
  let state = readHash();

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    return {
      q: p.get("q") || "",
      year: p.get("year") || "",
      types: [...new Set((p.get("type") || "").split(",").filter(Boolean).map(toTypeGroup))],
      journal: p.get("journal") || "",
      sort: p.get("sort") || "date",
      people: (p.get("people") || "").split(",").filter(Boolean),
      when: p.get("when") || (p.get("new") === "1" ? "week" : ""),
      verify: p.get("verify") || "",
      oa: p.get("oa") === "1",
      preprints: p.get("preprints") === "1",
      view: p.get("view") === "stats" || location.hash === "#stats" ? "stats" : "list",
    };
  }
  function writeHash() {
    const p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.year) p.set("year", state.year);
    if (state.types.length) p.set("type", state.types.join(","));
    if (state.journal) p.set("journal", state.journal);
    if (state.sort !== "date") p.set("sort", state.sort);
    if (state.people.length) p.set("people", state.people.join(","));
    if (state.when) p.set("when", state.when);
    if (state.verify) p.set("verify", state.verify);
    if (state.oa) p.set("oa", "1");
    if (state.preprints) p.set("preprints", "1");
    if (state.view === "stats") p.set("view", "stats");
    if (
      !p.toString() &&
      ["#publications", "#coverage-notes"].includes(location.hash)
    )
      return;
    history.replaceState(
      null,
      "",
      p.toString() ? "#" + p.toString() : location.pathname + location.search,
    );
  }

  const esc = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const nameOf = (slug) => (data.peopleBySlug[slug] || {}).name || slug;
  const fmtType = (t) => (t || "").replace(/-/g, " ");

  function workMembers(work) {
    // Collection eligibility uses verified affiliations; author display also includes
    // known CDS coauthors whose publication lists a different department or no affiliation.
    return [
      ...new Set([
        ...(work.group_members || []),
        ...(work.author_members || []),
      ]),
    ].filter((slug) => slug && data.peopleBySlug[slug]);
  }

  function authorProfileLinks(person) {
    if (!person) return "";
    const links = [];
    const orcid = String(
      person.orcid ||
        person.orcid_discovered ||
        (!person.needs_review && person.orcid_openalex) ||
        "",
    )
      .trim()
      .replace(/^https?:\/\/(?:www\.)?orcid\.org\//i, "")
      .replace(/\/$/, "")
      .toUpperCase();
    const scholar = String(person.scholar_id || "").trim();
    const icons = {
      ORCID:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#a6ce39"/><circle cx="6.6" cy="6.1" r="1.15" fill="#fff"/><path fill="#fff" d="M5.6 8.5h2v10h-2zM10 5.5h4.2a6.5 6.5 0 0 1 0 13H10zm2 2v9h2.2a4.5 4.5 0 0 0 0-9z"/></svg>',
      OpenAlex:
        '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#0e71bb" stroke-width="1.8"><circle cx="6" cy="7" r="2.6"/><circle cx="18" cy="6" r="2.6"/><circle cx="12" cy="18" r="2.6"/><path d="M8.4 7.8 15.6 6.6M7.3 9.3l3.5 6.4M16.8 8.4l-3.6 7.3"/></svg>',
      "Google Scholar":
        '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="m12 2-12 8 4 2.7V19h2v-5l6 4 10-6.7V19h2v-9zm0 13.6L3.6 10 12 4.4l8.4 5.6z"/><path d="M7 16.2V20c3 2.7 7 2.7 10 0v-3.8l-5 3.3z"/></svg>',
    };
    const profileLink = (provider, id, url, note = "") =>
      `<a class="profile-icon" href="${esc(url)}" target="_blank" rel="noopener" aria-label="${esc(person.name)} on ${provider}: ${esc(id)}${note ? " (" + esc(note) + ")" : ""}" title="${provider}: ${esc(id)}${note ? " · " + esc(note) : ""}">${icons[provider]}</a>`;
    if (/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(orcid))
      links.push(
        profileLink(
          "ORCID",
          orcid,
          "https://orcid.org/" + orcid,
          person.orcid
            ? ""
            : person.orcid_discovered
              ? "verified using shared publications or coauthors"
              : "reported by OpenAlex",
        ),
      );
    if (/^[A-Za-z0-9_-]{6,64}$/.test(scholar))
      links.push(
        profileLink(
          "Google Scholar",
          scholar,
          "https://scholar.google.com/citations?user=" +
            encodeURIComponent(scholar),
        ),
      );
    for (const id of person.openalex_ids || [])
      if (/^A\d+$/.test(id))
        links.push(profileLink("OpenAlex", id, "https://openalex.org/" + id, (person.openalex_ids || []).length > 1 ? "one of several OpenAlex records" : ""));
    return links.length
      ? `<span class="author-profile-links">${links.join("")}</span>`
      : "";
  }

  function fillSelect(el, values, current) {
    const first = el.multiple ? null : el.options[0];
    el.innerHTML = "";
    if (first) el.appendChild(first);
    for (const [v, label] of values) {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = label;
      if (Array.isArray(current) ? current.includes(v) : v === current) o.selected = true;
      el.appendChild(o);
    }
  }

  function setMulti(el, values) {
    for (const o of el.options) o.selected = values.includes(o.value);
  }

  // Controls follow the state, so chips, bars and dropdowns can all change a filter.
  function reflectState() {
    if (els.q.value !== state.q) els.q.value = state.q;
    els.year.value = state.year;
    setMulti(els.type, state.types);
    els.journal.value = state.journal;
    els.sort.value = state.sort;
    els.verify.value = state.verify === "all" ? "" : state.verify;
    els.when.value = state.when;
    els.onlyOa.checked = state.oa;
    els.preprints.checked = state.preprints;
  }

  function enhanceDropdowns() {
    // Keep native selects as a fallback if the optional enhancement cannot load.
    if (typeof TomSelect !== "function") return;
    document.querySelectorAll("select").forEach((select) => {
      if (select.tomselect) {
        select.tomselect.sync();
        return;
      }
      new TomSelect(select, {
        create: false,
        maxItems: select.multiple ? null : 1,
        maxOptions: null,
        allowEmptyOption: true,
        searchField: ["text"],
        highlight: true,
        closeAfterSelect: !select.multiple,
        refreshThrottle: 0,
        placeholder: select.dataset.placeholder || "Type to search…",
        // Option labels carry counts "(12)"; the chosen value reads cleaner without them.
        render: { item: (d, escape) => `<div>${escape(String(d.text).replace(/\s*\(\d+\)$/, ""))}</div>` },
        controlInput:
          '<input type="text" autocomplete="off" autocapitalize="none" spellcheck="false" aria-autocomplete="list">',
      });
    });
  }

  function syncDropdowns() {
    document
      .querySelectorAll("select")
      .forEach((select) => select.tomselect?.sync());
  }

  const isCounted = (w) => (w.counted === undefined ? !!w.verified : !!w.counted);

  // The default view (config.yml site.default_view): what the headline numbers, statistics and list start from.
  const VIEWS = {
    verified: {
      label: "verified-affiliation",
      plain: "papers with a verified group affiliation",
      rule: "Counted when at least one group author has a verified Maastro, Radiation Oncology (Maastricht), GROW or Medical Data Works affiliation on the paper, or the paper was confirmed by hand",
      test: (w) => !!w.verified,
    },
    counted: {
      label: "team-window",
      plain: "counted papers (team-window rule)",
      rule: "Counted under the team-window rule: papers by current group members, and by others only with a verified group affiliation",
      test: (w) => isCounted(w),
    },
  };
  const inView = (w, view) => !VIEWS[view] || VIEWS[view].test(w);

  function headlineWorks() {
    const d = siteDefaults();
    return data.works.filter((w) => inView(w, d.verify) && (d.preprints || w.type !== "preprint"));
  }
  function headlineDescription() {
    const d = siteDefaults();
    return [VIEWS[d.verify]?.label || "", d.preprints ? "" : "non-preprint"].filter(Boolean).join(", ") || "all";
  }

  function siteDefaults() {
    const site = (data && data.site) || {};
    const view = site.default_view ?? (site.default_verified_only ? "counted" : "");
    return { verify: view === "all" ? "" : view, preprints: !!site.default_include_preprints };
  }

  function init(json) {
    data = json;
    {
      const hp = new URLSearchParams(location.hash.slice(1));
      const d = siteDefaults();
      if (!hp.has("verify")) state.verify = d.verify;
      if (!hp.has("preprints")) state.preprints = d.preprints;
    }
    data.peopleBySlug = Object.fromEntries(data.people.map((p) => [p.slug, p]));
    // "New" = first found in the 7 days before this update; "queued" = waiting for the next Monday digest.
    // Like the digest: the first (baseline) import is not new, and older papers linked late are not news.
    const daysBefore = (n) => new Date(new Date(data.generated).getTime() - n * 86400000).toISOString().slice(0, 10);
    const baseline = data.works.reduce((m, w) => (w.first_seen && w.first_seen < m ? w.first_seen : m), "9999");
    data.newIds = new Set(
      data.works
        .filter((w) => (w.first_seen || "") > daysBefore(7) && w.first_seen > baseline)
        .filter((w) => (w.publication_date || "") >= daysBefore(data.recent_days || 120))
        .map((w) => w.id),
    );
    data.queuedIds = new Set(data.pending_ids || []);
    $("group-name").textContent = data.group_name || "";
    const generated = new Date(data.generated);
    $("updated").textContent = Number.isNaN(generated.getTime())
      ? "Updated weekly"
      : "Updated " +
        generated.toLocaleDateString("en-GB", {
          day: "numeric",
          month: "short",
          year: "numeric",
        });
    $("repo-link").href =
      data.repo_url || "https://github.com/MaastrichtU-CDS/pubpulse";
    // Headline numbers follow the site defaults: verified group affiliation, no preprints.
    const headline = headlineWorks();
    const headlineLabel = headlineDescription();
    const thisYear = new Date(data.generated).getUTCFullYear() || new Date().getFullYear();
    const headlineYear = headline.filter((w) => Number(w.year) === thisYear);
    $("total-publications").textContent =
      headlineYear.length.toLocaleString("en-GB");
    $("total-researchers").textContent = data.people
      .filter((person) => person.active)
      .length.toLocaleString("en-GB");
    $("total-open").textContent = headlineYear.length
      ? Math.round(
          (headlineYear.filter((w) => w.is_oa).length / headlineYear.length) * 100,
        ) + "%"
      : "—";
    $("coverage-start").innerHTML = `in ${thisYear}<a href="#metric-footnote" class="footnote-mark" aria-label="how this is counted">*</a>`;
    $("metric-footnote").textContent =
      `* Year to date. ${VIEWS[siteDefaults().verify]?.rule || "All papers found for group members"}; ` +
      `preprints not included. Open access share refers to the same set. Since ${coverageStart()}: ${headline.length} publications. ` +
      `Automated and not manually verified; mistakes are expected.`;
    $("publication-range").textContent =
      `${headline.length.toLocaleString("en-GB")} ${headlineLabel} publications · ${coverageStart()} onwards · OpenAlex` +
      (data.works.length > headline.length ? ` · ${data.works.length - headline.length} more incl. preprints and unverified` : "");
    configureDigest(data.list || {});
    for (const o of els.verify.options) {
      o.dataset.label ||= o.textContent;
      o.textContent = o.dataset.label + (o.value === siteDefaults().verify ? " (default)" : "");
    }

    const years = [
      ...new Set(data.works.map((w) => w.year).filter(Boolean)),
    ].sort((a, b) => b - a);
    fillSelect(
      els.year,
      years.map((y) => [String(y), String(y)]),
      state.year,
    );
    fillSelect(
      els.type,
      TYPE_GROUPS.map((g) => [g, data.works.filter((w) => typeGroupKey(w.type) === g.key).length])
        .filter(([, n]) => n)
        .map(([g, n]) => [g.key, `${g.label} (${n})`]),
      state.types,
    );
    const jc = {};
    for (const w of data.works)
      if (w.journal) jc[w.journal] = (jc[w.journal] || 0) + 1;
    const journals = Object.entries(jc).sort(
      (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
    );
    fillSelect(
      els.journal,
      journals.map(([j, n]) => [j, `${j} (${n})`]),
      state.journal,
    );

    reflectState();
    enhanceDropdowns();
    renderPeople();

    const review = data.people.filter((p) => p.needs_review);
    els.attention.classList.toggle("hidden", !review.length);
    els.attention.innerHTML = review.length
      ? `<details><summary><span class="coverage-label">Author coverage</span><span class="coverage-status">${review.length} staff ${review.length === 1 ? "profile" : "profiles"} without a confirmed match</span></summary>` +
        `<p>An OpenAlex author record could not be confirmed for ${review.length} staff ${review.length === 1 ? "profile" : "profiles"}. Publications by these researchers may therefore be absent from this collection.</p>` +
        "<p>Author matching uses ORCID identifiers and institutional affiliations to distinguish researchers with similar names.</p>" +
        `<p class="coverage-detail"><strong>Profiles without a confirmed match:</strong> ${review.map((p) => esc(p.name)).join(", ")}.</p></details>`
      : "";
    updateCoverageVisibility();

    loadScholarCheck();

    if (!listenersBound) {
      listenersBound = true;
      els.q.addEventListener("input", () => {
        state.q = els.q.value;
        update();
      });
      els.year.addEventListener("change", () => {
        state.year = els.year.value;
        update();
      });
      els.type.addEventListener("change", () => {
        state.types = [...els.type.selectedOptions].map((o) => o.value);
        update();
      });
      els.journal.addEventListener("change", () => {
        state.journal = els.journal.value;
        update();
      });
      els.sort.addEventListener("change", () => {
        state.sort = els.sort.value || "date";
        els.sort.value = state.sort;
        update();
      });
      els.when.addEventListener("change", () => {
        state.when = els.when.value;
        update();
      });
      els.verify.addEventListener("change", () => {
        state.verify = els.verify.value || (siteDefaults().verify ? "all" : "");
        update();
      });
      els.preprints.addEventListener("change", () => {
        state.preprints = els.preprints.checked;
        update();
      });
      els.onlyOa.addEventListener("change", () => {
        state.oa = els.onlyOa.checked;
        update();
      });
      els.peopleQ.addEventListener("input", renderPeople);
      $("clear-people").addEventListener("click", () => {
        state.people = [];
        renderPeople();
        update();
      });
      $("reset").addEventListener("click", resetAll);
      const tabs = [["list", $("tab-list")], ["stats", $("tab-stats")]];
      tabs.forEach(([view, tab], i) => {
        tab.addEventListener("click", () => {
          state.view = view;
          update();
        });
        tab.addEventListener("keydown", (ev) => {
          if (!["ArrowLeft", "ArrowRight"].includes(ev.key)) return;
          const next = tabs[(i + (ev.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
          state.view = next[0];
          update();
          next[1].focus();
        });
      });
      window.addEventListener("hashchange", () => {
        if (
          [
            "#publications",
            "#subscribe",
            "#subscribed",
            "#unsubscribe",
            "#scholar",
            "#coverage-notes",
          ].includes(location.hash)
        )
          return;
        const toStats = location.hash === "#stats";
        state = readHash();
        init(data);
        if (toStats) showTabs();
      });
    }
    update();
  }

  function showTabs() {
    $("tab-list").parentElement.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }

  function renderTabs(count) {
    for (const [view, tab, panel] of [["list", $("tab-list"), $("panel-list")], ["stats", $("tab-stats"), $("panel-stats")]]) {
      const on = state.view === view;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      panel.hidden = !on;
    }
    $("tab-list-count").textContent = count;
  }

  function resetAll() {
    state = {
      q: "",
      year: "",
      types: [],
      journal: "",
      sort: state.sort,
      people: [],
      when: "",
      verify: siteDefaults().verify,
      oa: false,
      preprints: siteDefaults().preprints,
      view: state.view,
    };
    els.peopleQ.value = "";
    renderPeople();
    update();
    if (initialHash === "#stats") {
      initialHash = "";
      showTabs();
    }
  }

  function updateCoverageVisibility() {
    const notes = $("coverage-notes");
    const hidden = [...notes.querySelectorAll(".coverage-note")].every((note) =>
      note.classList.contains("hidden"),
    );
    notes.classList.toggle("hidden", hidden);
    $("coverage-link").classList.toggle("hidden", hidden);
  }

  function loadScholarCheck() {
    fetch("data/scholar_check.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : null))
      .then((sc) => {
        if (!sc || !sc.people) return;
        const box = $("scholar");
        const entries = Object.values(sc.people).filter(
          (p) => (p.missing || []).length || (p.not_attributed || []).length,
        );
        box.classList.toggle("hidden", !entries.length);
        if (!entries.length) {
          box.innerHTML = "";
          updateCoverageVisibility();
          return;
        }
        // Entries are counted per profile; a paper can appear on more than one profile.
        const outside = entries.reduce(
          (n, p) => n + (p.missing || []).length,
          0,
        );
        const attribution = entries.reduce(
          (n, p) => n + (p.not_attributed || []).length,
          0,
        );
        const total = outside + attribution;
        const date = new Date(sc.checked_at);
        const checked = Number.isNaN(date.getTime())
          ? "Comparison date unavailable"
          : "Compared " +
            date.toLocaleDateString("en-GB", {
              day: "numeric",
              month: "long",
              year: "numeric",
              timeZone: "UTC",
            });
        const overview =
          [
            outside
              ? `${outside} profile ${outside === 1 ? "entry is" : "entries are"} not represented in this collection`
              : "",
            attribution
              ? `${attribution} ${attribution === 1 ? "entry has" : "entries have"} a different author attribution`
              : "",
          ]
            .filter(Boolean)
            .join("; ") + ".";
        box.innerHTML =
          `<details${initialHash === "#scholar" ? " open" : ""}><summary><span class="coverage-label">Google Scholar comparison</span><span class="coverage-status">${total} profile ${total === 1 ? "difference" : "differences"}</span></summary>` +
          `<p class="coverage-date">${esc(checked)}${sc.since_year ? " · Publications since " + esc(sc.since_year) : ""}</p>` +
          `<p>${esc(overview)} Counts are per researcher profile, so the same paper may appear more than once.</p>` +
          "<p>Differences can reflect indexing coverage, update delays or author attribution. They do not necessarily indicate missing group publications. This comparison is informational and does not change the library’s publication count.</p>" +
          entries
            .map((p) => {
              const differenceCount =
                (p.missing || []).length + (p.not_attributed || []).length;
              const item = (paper, label) => {
                const link = safeLink(paper.link);
                return `<li><span class="coverage-tag">${label}</span> ${esc(paper.title)}${paper.year ? " (" + esc(paper.year) + ")" : ""}${paper.venue ? " · " + esc(paper.venue) : ""}${link ? ` <a href="${esc(link)}" target="_blank" rel="noopener">View record ↗</a>` : ""}</li>`;
              };
              return (
                `<details class="coverage-person"><summary>${esc(p.name)}<span>${differenceCount} ${differenceCount === 1 ? "difference" : "differences"}</span></summary><p>${esc(p.matched)} of ${esc(p.checked)} profile entries matched${sc.since_year ? " since " + esc(sc.since_year) : ""}.</p><ul>` +
                (p.missing || [])
                  .map((paper) => item(paper, "Not in collection"))
                  .join("") +
                (p.not_attributed || [])
                  .map((paper) => item(paper, "Author attribution differs"))
                  .join("") +
                "</ul></details>"
              );
            })
            .join("") +
          "</details>";
        updateCoverageVisibility();
      })
      .catch(() => {});
  }

  function safeLink(value) {
    try {
      const url = new URL(value);
      return ["https:", "http:", "mailto:"].includes(url.protocol)
        ? url.href
        : "";
    } catch {
      return "";
    }
  }

  function configureDigest(list) {
    const endpoint = safeLink(list.subscribe_endpoint);
    const formUrl = safeLink(list.subscribe_form_url);
    const unsubLink = $("unsubscribe-link");
    const form = $("digest-form");
    if (formUrl) {
      // Hosted sign-up form (Brevo): double opt-in and the unsubscribe link in every mail are handled there.
      $("join-steps").classList.add("hidden");
      $("join-action").classList.add("hidden");
      form.classList.add("hidden");
      unsubLink.classList.add("hidden");
      $("digest-note").textContent =
        "Enter your email, confirm the link we send you, done.";
      $("join-note").textContent =
        "Every digest has an unsubscribe link at the bottom. Your address is stored privately and only used for this digest.";
      const frame = document.createElement("iframe");
      frame.className = "signup-frame";
      frame.src = formUrl;
      frame.title = "Subscribe to the weekly digest";
      frame.loading = "lazy";
      frame.setAttribute("allowfullscreen", "");
      $("join-note").before(frame);
      const fallback = document.createElement("p");
      fallback.className = "join-note";
      fallback.innerHTML = `Form not showing? <a href="${esc(formUrl)}" target="_blank" rel="noopener">Open it in a new tab ↗</a>`;
      $("join-note").before(fallback);
      if (["#subscribe", "#subscribed"].includes(initialHash) && !dialog.open) {
        if (initialHash === "#subscribed") {
          $("join-title").innerHTML = "You're on the list.";
          $("join-description").textContent =
            "The next digest arrives on a Monday when there is something new.";
          frame.remove();
          fallback.remove();
        }
        dialog.showModal();
      }
      return;
    }
    if (!endpoint) {
      unsubLink.classList.add("hidden");
      form.classList.add("hidden");
      return;
    }
    let mode = "subscribe";
    const msg = $("digest-msg");
    const renderMode = () => {
      $("digest-form-label").textContent =
        mode === "subscribe" ? "Your email address" : "Email address to remove";
      $("digest-submit").textContent =
        mode === "subscribe" ? "Subscribe" : "Send me an unsubscribe link";
      $("digest-toggle").textContent =
        mode === "subscribe"
          ? "I want to unsubscribe instead"
          : "Back to subscribing";
      $("join-title").innerHTML =
        mode === "subscribe"
          ? "Your next good read<br />starts here."
          : "Leaving the list?";
      msg.textContent = "";
      msg.className = "digest-form-msg";
    };
    $("join-steps").classList.add("hidden");
    $("join-action").classList.add("hidden");
    form.classList.remove("hidden");
    $("digest-note").textContent =
      "Enter your email, confirm the link we send you, done. Unsubscribe whenever you like.";
    $("join-note").textContent =
      "We send a confirmation link first. Your address is stored privately and only used for this digest.";
    unsubLink.classList.remove("hidden");
    unsubLink.removeAttribute("target");
    unsubLink.href = "#unsubscribe";
    unsubLink.addEventListener("click", (ev) => {
      ev.preventDefault();
      mode = "unsubscribe";
      renderMode();
      dialog.showModal();
    });
    $("digest-toggle").addEventListener("click", () => {
      mode = mode === "subscribe" ? "unsubscribe" : "subscribe";
      renderMode();
    });
    document.querySelectorAll("[data-open-digest]").forEach((b) =>
      b.addEventListener("click", () => {
        mode = "subscribe";
        renderMode();
      }),
    );
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const email = $("digest-email").value.trim();
      $("digest-submit").disabled = true;
      msg.className = "digest-form-msg";
      msg.textContent = "One moment…";
      try {
        const r = await fetch(endpoint, {
          method: "POST",
          redirect: "follow",
          headers: { "Content-Type": "text/plain;charset=utf-8" },
          body: JSON.stringify({ action: mode, email }),
        });
        const j = await r.json();
        msg.className = "digest-form-msg " + (j.ok ? "ok" : "err");
        msg.textContent = j.ok ? j.message : j.error || "Something went wrong.";
        if (j.ok) $("digest-email").value = "";
      } catch {
        msg.className = "digest-form-msg err";
        msg.textContent =
          "Could not reach the subscription service. Please try again later.";
      }
      $("digest-submit").disabled = false;
    });
    renderMode();
    const hash = location.hash.replace("#", "");
    if (hash === "unsubscribe" || hash === "subscribe") {
      mode = hash;
      renderMode();
      if (!dialog.open) dialog.showModal();
    }
  }

  function renderPeople() {
    const counts = {};
    for (const w of data.works)
      for (const s of workMembers(w)) counts[s] = (counts[s] || 0) + 1;
    const q = els.peopleQ.value.trim().toLowerCase();
    const people = data.people
      .filter((p) => p.active || counts[p.slug] || q)
      .filter((p) => !q || p.name.toLowerCase().includes(q))
      .sort(
        (a, b) =>
          b.active - a.active ||
          (counts[b.slug] || 0) - (counts[a.slug] || 0) ||
          a.name.localeCompare(b.name),
      );
    els.people.innerHTML = people
      .map(
        (p) => `
      <div class="person-row"><label class="${p.active ? "" : "inactive"}" title="${p.active ? "" : p.former_collaboration?.recent_shared_papers ? "Former staff · recent publications with current CDS coauthors" : "Former staff"}">
        <input type="checkbox" value="${esc(p.slug)}" ${state.people.includes(p.slug) ? "checked" : ""}>
        <span>${esc(p.name)}${p.active ? "" : '<small class="former-label">Former</small>'}</span> <span class="n">${counts[p.slug] || 0}</span>
      </label></div>`,
      )
      .join("");
    els.people.querySelectorAll("input").forEach((cb) =>
      cb.addEventListener("change", () => {
        state.people = cb.checked
          ? [...state.people, cb.value]
          : state.people.filter((s) => s !== cb.value);
        update();
      }),
    );
  }

  function renderSelectedProfiles() {
    const people = state.people
      .map((slug) => data.peopleBySlug[slug])
      .filter(Boolean);
    els.profiles.classList.toggle("hidden", !people.length);
    els.profiles.innerHTML = people.length
      ? `<h3 class="profiles-heading">Selected ${people.length === 1 ? "researcher" : "researchers"}</h3><div class="profiles-grid">${people
          .map((person) => {
            const count = data.works.filter((work) =>
              workMembers(work).includes(person.slug),
            ).length;
            const description = [person.role_title || person.role, person.employer]
              .filter(Boolean)
              .join(" · ");
            const collaboration = person.former_collaboration;
            const status = person.active
              ? ""
              : `<p class="profile-status">Former staff${collaboration?.recent_shared_papers ? " · recent CDS collaborator" : ""}</p>`;
            const recent = collaboration?.last_collaboration_date
              ? `<p class="profile-collaboration">${collaboration.recent_shared_papers} shared ${collaboration.recent_shared_papers === 1 ? "paper" : "papers"} with current CDS members in the last ${collaboration.recent_months || 24} months · latest ${esc(new Date(collaboration.last_collaboration_date + "T12:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }))}</p>`
              : "";
            return `<article class="researcher-profile"><div class="profile-heading"><h4>${esc(person.name)}</h4><button class="profile-remove" type="button" data-slug="${esc(person.slug)}" aria-label="Remove ${esc(person.name)} from the author filter" title="Remove author filter">×</button></div>${status}${description ? `<p class="profile-description">${esc(description)}</p>` : ""}${recent}<div class="profile-footer"><p>${count} ${count === 1 ? "publication" : "publications"} in this collection</p>${authorProfileLinks(person)}</div></article>`;
          })
          .join("")}</div>`
      : "";
    els.profiles.querySelectorAll("[data-slug]").forEach((button) =>
      button.addEventListener("click", () => {
        state.people = state.people.filter(
          (slug) => slug !== button.dataset.slug,
        );
        renderPeople();
        update();
      }),
    );
  }

  function coverageStart() {
    const configured = Number(data.since_year);
    if (
      Number.isInteger(configured) &&
      configured >= 1800 &&
      configured <= 2200
    )
      return configured;
    const years = data.works
      .map((w) => Number(w.year))
      .filter((year) => Number.isInteger(year) && year >= 1800 && year <= 2200);
    return years.length ? Math.min(...years) : new Date().getFullYear();
  }

  function renderTypeBar() {
    const box = $("type-bar");
    if (!box) return;
    const pool = data.works.filter((w) => matches(w, { ignoreType: true }));
    const counts = TYPE_GROUPS.map((g) => {
      const works = pool.filter((w) => typeGroupKey(w.type) === g.key);
      const kinds = [...new Set(works.map((w) => fmtType(w.type) || "unknown"))].sort();
      return { ...g, n: works.length, kinds };
    }).filter((g) => g.n);
    const total = counts.reduce((s, g) => s + g.n, 0);
    if (!total) { box.innerHTML = ""; return; }
    const any = state.types.length > 0;
    const hidden = !any && !state.preprints ? (counts.find((g) => g.key === "preprint") || { n: 0 }).n : 0;
    const label = (g) => {
      const on = state.types.includes(g.key);
      const pct = ((100 * g.n) / total).toFixed(0);
      return `${g.label}: ${g.n} (${pct}%)${g.key === "other" ? " · " + g.kinds.join(", ") : ""}. ${on ? "Click to remove this type" : "Click to show only this type"}`;
    };
    const seg = counts.map((g) => {
      const on = state.types.includes(g.key);
      return `<button type="button" class="type-seg${any && !on ? " is-dim" : ""}" style="flex:${g.n}" data-type="${g.key}" aria-pressed="${on}" title="${esc(label(g))}" aria-label="${esc(label(g))}"><span class="type-seg-fill" style="background:${g.color}"></span></button>`;
    }).join("");
    const legend = counts.map((g) => {
      const on = state.types.includes(g.key);
      return `<button type="button" class="type-key${any && !on ? " is-dim" : ""}" data-type="${g.key}" aria-pressed="${on}" title="${esc(label(g))}"><span class="type-swatch" style="background:${g.color}"></span>${on ? "✓ " : ""}${esc(g.label)} <b>${g.n}</b> <span class="meta">${((100 * g.n) / total).toFixed(0)}%</span></button>`;
    }).join("");
    const status = any
      ? `<span class="type-status">Showing only: <b>${esc(state.types.map((k) => TYPE_GROUPS.find((g) => g.key === k)?.label || k).join(", "))}</b> <button type="button" class="link" data-clear-types>Show all types</button></span>`
      : hidden ? `<span class="type-status meta">${hidden} preprint${hidden === 1 ? "" : "s"} hidden by default (switch on under What → Include preprints)</span>` : "";
    box.innerHTML = `<div class="type-track">${seg}</div><div class="type-legend">${legend}</div>${status}`;
    box.querySelectorAll("[data-type]").forEach((b) => b.addEventListener("click", () => {
      const ty = b.dataset.type;
      state.types = state.types.includes(ty) ? state.types.filter((t) => t !== ty) : [...state.types, ty];
      update();
    }));
    box.querySelector("[data-clear-types]")?.addEventListener("click", () => {
      state.types = [];
      update();
    });
  }

  // One row of removable chips for everything that differs from the default view.
  function renderActiveFilters() {
    const box = els.active;
    const d = siteDefaults();
    const optionText = (el, v) => [...el.options].find((o) => o.value === v)?.textContent.replace(/\s*\(\d+\)$/, "") || v;
    const chips = [];
    const chip = (label, clear) => chips.push({ label, clear });
    if (state.q) chip(`Search: “${state.q}”`, () => (state.q = ""));
    if (state.when) chip(optionText(els.when, state.when), () => (state.when = ""));
    if (state.year) chip(`Year: ${state.year}`, () => (state.year = ""));
    for (const t of state.types)
      chip(`Type: ${TYPE_GROUPS.find((g) => g.key === t)?.label || t}`, () => (state.types = state.types.filter((x) => x !== t)));
    if (state.journal) chip(`Source: ${state.journal}`, () => (state.journal = ""));
    if ((state.verify || "") !== d.verify && !(state.verify === "all" && !d.verify))
      chip(`Group affiliation: ${optionText(els.verify, state.verify === "all" ? "" : state.verify)}`, () => (state.verify = d.verify));
    if (state.oa) chip("Open access only", () => (state.oa = false));
    if (state.preprints !== d.preprints && !state.types.length)
      chip(state.preprints ? "Preprints included" : "Preprints hidden", () => (state.preprints = d.preprints));
    for (const slug of state.people)
      chip(nameOf(slug), () => {
        state.people = state.people.filter((s) => s !== slug);
        renderPeople();
      });
    const defaults = [VIEWS[d.verify]?.plain || "papers", d.preprints ? "" : "no preprints"].filter(Boolean).join(", ");
    box.innerHTML = chips.length
      ? `<span class="active-label">Filters:</span>${chips.map((c, i) => `<button type="button" class="filter-chip" data-chip="${i}" title="Remove this filter">${esc(c.label)} <span aria-hidden="true">×</span><span class="visually-hidden">remove</span></button>`).join("")}<button type="button" class="link reset-chip" data-reset>Reset all</button>`
      : `<span class="active-label meta">No filters: showing all ${esc(defaults)}. Click a bar, a type colour or an author name to narrow the list.</span>`;
    box.querySelectorAll("[data-chip]").forEach((b) => b.addEventListener("click", () => {
      chips[Number(b.dataset.chip)].clear();
      update();
    }));
    box.querySelector("[data-reset]")?.addEventListener("click", resetAll);
  }

  // Authorship positions per person and per group, over the current filters (except the author filter).
  // Consortium papers (CONSORTIUM+ authors) are counted but left out of the position percentages: a middle position
  // there says little. "Senior author" = last or second-to-last, where supervisors usually sit.
  const CONSORTIUM = 20;
  const pct = (n, of) => (of ? Math.round((100 * n) / of) + "%" : "—");
  let statsSort = { table: "people", key: "papers", dir: -1 };
  function renderStats() {
    const pool = data.works.filter((w) => matches(w, { ignorePeople: true }));
    const groupsCfg = data.groups || { groups: [], seniors: [] };
    const nAuthors = (w) => w.author_count || (w.authors || []).length;
    const isConsortium = (w) => nAuthors(w) >= CONSORTIUM;
    const positionOf = (w, slug) => (w.author_positions || [])[(w.author_members || []).indexOf(slug)] || null;
    const place = (w, slug) => {
      const pos = positionOf(w, slug), n = nAuthors(w);
      return !pos ? "other" : pos === 1 ? "first" : pos >= n - 1 ? "senior" : "other";
    };
    const per = {};
    const row = (slug) => (per[slug] ||= { slug, papers: 0, consortium: 0, ranked: 0, first: 0, senior: 0, other: 0 });
    for (const w of pool)
      for (const slug of workMembers(w)) {
        const r = row(slug);
        r.papers += 1;
        if (isConsortium(w)) r.consortium += 1;
        else { r.ranked += 1; r[place(w, slug)] += 1; }
      }
    const isKnown = (s) => s && data.peopleBySlug[s];
    const groupRow = (name, members, note) => {
      const set = new Set(members);
      const works = pool.filter((w) => workMembers(w).some((s) => set.has(s)));
      const ranked = works.filter((w) => !isConsortium(w));
      const has = (w, where) => [...set].some((s) => workMembers(w).includes(s) && place(w, s) === where);
      return {
        name, note, members: members.length, papers: works.length, consortium: works.length - ranked.length, ranked: ranked.length,
        first: ranked.filter((w) => has(w, "first")).length,
        senior: ranked.filter((w) => has(w, "senior")).length,
      };
    };
    const everyone = data.people.map((p) => p.slug);
    const groups = [{ ...groupRow("All CDS", everyone, "everyone in this collection"), members: data.people.filter((p) => p.active).length }];
    const notes = { "Senior staff": "current professors, researchers, postdocs", "Non-senior staff": "current PhD students, interns, support staff", "Former staff": "everyone who left; last role in the people table" };
    for (const g of groupsCfg.groups || []) groups.push(groupRow(g.name, g.members, `${notes[g.name] || ""} · ${g.members.length}`));
    let people = Object.values(per).filter((r) => isKnown(r.slug));
    if (state.people.length) people = people.filter((r) => state.people.includes(r.slug));
    const sortBy = (rows, table) => {
      if (statsSort.table !== table) return rows.sort((a, b) => b.papers - a.papers);
      const k = statsSort.key;
      const val = (r) => (k === "name" ? (r.name || nameOf(r.slug)).toLowerCase() : k === "role" ? (data.peopleBySlug[r.slug]?.role_title || "").toLowerCase() : k.endsWith("Pct") ? (r.ranked ? r[k.slice(0, -3)] / r.ranked : -1) : r[k]);
      return rows.sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * statsSort.dir || b.papers - a.papers);
    };
    const th = (table, key, label, title = "") =>
      `<th scope="col"><button type="button" class="link sort-th${statsSort.table === table && statsSort.key === key ? " is-sorted" : ""}" data-table="${table}" data-key="${key}" title="${esc(title || "Sort by " + label)}">${label}${statsSort.table === table && statsSort.key === key ? (statsSort.dir < 0 ? " ↓" : " ↑") : ""}</button></th>`;
    const cell = (n, of) => `<td>${n} <span class="meta">${pct(n, of)}</span></td>`;
    const total = pool.length;
    const big = pool.filter(isConsortium).length;
    $("stats-summary").textContent = `${total} publications in the current selection · ${people.length} ${people.length === 1 ? "person" : "people"} · ${groups.length} groups`;
    const seniorTitle = "last or second-to-last author, where supervisors usually sit";
    const groupTable =
      `<table class="stats-table"><thead><tr>${th("groups", "name", "Group")}${th("groups", "papers", "Papers", "papers with at least one member of the group")}${th("groups", "firstPct", "Member first author")}${th("groups", "seniorPct", "Member senior author", seniorTitle)}${th("groups", "consortium", `${CONSORTIUM}+ authors`, "consortium papers, left out of the position percentages")}<th scope="col">Share of CDS</th></tr></thead><tbody>` +
      sortBy(groups, "groups").map((g) => `<tr><th scope="row">${esc(g.name)}${g.note ? `<span class="meta stats-note">${esc(g.note)}</span>` : ""}</th><td>${g.papers}</td>${cell(g.first, g.ranked)}${cell(g.senior, g.ranked)}<td>${g.consortium}</td><td>${pct(g.papers, total)}</td></tr>`).join("") +
      "</tbody></table>";
    const peopleTable = people.length
      ? `<table class="stats-table"><thead><tr>${th("people", "name", "Person")}${th("people", "role", "Role")}${th("people", "papers", "Papers")}${th("people", "firstPct", "First author")}${th("people", "seniorPct", "Senior author", seniorTitle)}${th("people", "otherPct", "Other position")}${th("people", "consortium", `${CONSORTIUM}+ authors`, "consortium papers, left out of the position percentages")}<th scope="col">Share of CDS</th></tr></thead><tbody>` +
        sortBy(people, "people").map((r) => {
          const p = data.peopleBySlug[r.slug];
          const senior = (groupsCfg.seniors || []).includes(r.slug);
          return `<tr><th scope="row"><button type="button" class="link" data-person="${esc(r.slug)}">${esc(p.name)}</button>${senior ? ' <span class="badge">senior</span>' : ""}${p.active ? "" : ' <small class="former-label">Former</small>'}</th><td class="stats-role">${esc(p.role_title || "")}</td><td>${r.papers}</td>${cell(r.first, r.ranked)}${cell(r.senior, r.ranked)}${cell(r.other, r.ranked)}<td>${r.consortium}</td><td>${pct(r.papers, total)}</td></tr>`;
        }).join("") + "</tbody></table>"
      : '<p class="meta">No group authors in the current selection.</p>';
    $("stats-body").innerHTML =
      `<p class="stats-intro">Counts follow the filters above (period, year, type, affiliation); the author filter only narrows the people table. ` +
      `<b>Senior author</b> = last or second-to-last author. Position percentages leave out the ${big} consortium paper${big === 1 ? "" : "s"} with ${CONSORTIUM} or more authors; "share of CDS" is of all ${total} papers in the selection.</p>` +
      `<h4>Groups</h4><div class="table-scroll">${groupTable}</div><p class="meta">Senior staff = current professors, researchers and postdocs by their role on the CDS staff page; non-senior = current PhD students, interns and support staff; former staff = everyone who left. A paper counts once per group, however many members are on it.</p>` +
      `<h4>People</h4><div class="table-scroll">${peopleTable}</div>` +
      `<p class="meta">Author positions come from the author order in OpenAlex. Shared first or last authorship (equal contribution) is not recorded there, so a co-first author listed second counts as "other position". Single-author papers count as first author. Automated, not manually verified.</p>`;
    $("stats-body").querySelectorAll(".sort-th").forEach((b) => b.addEventListener("click", () => {
      const { table, key } = b.dataset;
      statsSort = statsSort.table === table && statsSort.key === key ? { table, key, dir: -statsSort.dir } : { table, key, dir: ["name", "role"].includes(key) ? 1 : -1 };
      renderStats();
    }));
    $("stats-body").querySelectorAll("[data-person]").forEach((b) => b.addEventListener("click", () => {
      if (!state.people.includes(b.dataset.person)) state.people = [...state.people, b.dataset.person];
      renderPeople();
      update();
    }));
  }

  function renderYearChart() {
    const generatedYear =
      new Date(data.generated).getUTCFullYear() || new Date().getFullYear();
    const dated = data.works.filter((w) => Number.isInteger(w.year));
    const lastYear = Math.max(
      generatedYear,
      coverageStart(),
      ...dated.map((w) => w.year),
    );
    const years = Array.from(
      { length: lastYear - coverageStart() + 1 },
      (_, i) => coverageStart() + i,
    );
    const counts = new Map(years.map((year) => [year, 0]));
    for (const work of dated.filter((w) => matches(w, { ignoreYear: true }))) {
      counts.set(work.year, (counts.get(work.year) || 0) + 1);
    }
    const peak = Math.max(1, ...counts.values());
    const step = Math.max(1, Math.pow(10, Math.floor(Math.log10(peak))) / 5);
    const top = Math.max(2, Math.ceil(peak / step) * step);
    $("chart-axis").innerHTML =
      `<span>${top}</span><span>${top / 2}</span><span>0</span>`;
    $("chart-note").textContent = `${generatedYear} is year to date`;
    $("year-bars").style.setProperty("--year-count", years.length);
    $("year-bars").classList.toggle("has-selection", !!state.year);
    $("year-bars").innerHTML = years
      .map((year) => {
        const count = counts.get(year) || 0;
        const selected = state.year === String(year);
        const label = `${year}: ${count} publication${count === 1 ? "" : "s"}${year === generatedYear ? ", year to date" : ""}. ${selected ? "Clear year filter" : "Filter to this year"}.`;
        return `<button type="button" class="year-column" data-year="${year}" aria-pressed="${selected}" aria-label="${esc(label)}"><span class="year-bar-space"><span class="year-bar" style="height:${(count / top) * 100}%"><span class="year-value">${count}</span></span></span><span class="year-label">${year}${year === generatedYear ? "<small>year to date</small>" : ""}</span></button>`;
      })
      .join("");
    $("year-bars")
      .querySelectorAll("[data-year]")
      .forEach((button) =>
        button.addEventListener("click", () => {
          state.year =
            state.year === button.dataset.year ? "" : button.dataset.year;
          const year = button.dataset.year;
          update();
          $("year-bars")
            .querySelector(`[data-year="${year}"]`)
            .focus({ preventScroll: true });
        }),
      );
  }

  function inPeriod(w, when) {
    if (!w.publication_date) return false;
    const d = new Date(w.publication_date + "T00:00:00Z");
    const now = new Date();
    if (when === "year") return d.getUTCFullYear() === now.getUTCFullYear();
    const days = { "30d": 30, "90d": 90, "12m": 365 }[when];
    return days ? (now - d) / 86400000 <= days : true;
  }

  function matches(w, options = {}) {
    if (state.when === "week" && !data.newIds.has(w.id)) return false;
    if (state.when === "queued" && !data.queuedIds.has(w.id)) return false;
    if (state.when && !["week", "queued"].includes(state.when) && !inPeriod(w, state.when))
      return false;
    if (state.verify === "counted" && !isCounted(w)) return false;
    if (state.verify === "uncounted" && isCounted(w)) return false;
    if (state.verify === "verified" && !w.verified) return false;
    if (state.verify === "unverified" && w.verified) return false;
    if (state.verify === "approved" && !w.approved_external) return false;
    if (state.oa && !w.is_oa) return false;
    if (!options.ignoreYear && state.year && String(w.year) !== state.year)
      return false;
    if (!options.ignoreType) {
      if (state.types.length) {
        if (!state.types.includes(typeGroupKey(w.type))) return false;
      } else if (!state.preprints && w.type === "preprint") return false;
    }
    if (state.journal && w.journal !== state.journal) return false;
    if (
      !options.ignorePeople &&
      state.people.length &&
      !state.people.some((s) => workMembers(w).includes(s))
    )
      return false;
    if (state.q) {
      const hay = (
        w.title +
        " " +
        w.id +
        " " +
        w.authors.join(" ") +
        " " +
        (w.journal || "") +
        " " +
        workMembers(w).map(nameOf).join(" ")
      ).toLowerCase();
      if (
        !state.q
          .toLowerCase()
          .split(/\s+/)
          .every((t) => hay.includes(t))
      )
        return false;
    }
    return true;
  }

  function update() {
    reflectState();
    syncDropdowns();
    writeHash();
    let items = data.works.filter((w) => matches(w));
    renderActiveFilters();
    renderYearChart();
    renderTypeBar();
    renderTabs(items.length);
    if (state.view === "stats") renderStats();
    if (state.sort === "cited")
      items.sort((a, b) => (b.cited_by_count || 0) - (a.cited_by_count || 0));
    else if (state.sort === "added")
      items.sort(
        (a, b) =>
          (b.first_seen || "").localeCompare(a.first_seen || "") ||
          (b.publication_date || "").localeCompare(a.publication_date || ""),
      );
    else
      items.sort((a, b) =>
        (b.publication_date || "").localeCompare(a.publication_date || ""),
      );
    const base = state.verify === siteDefaults().verify && !state.preprints && !state.types.length ? headlineWorks().length : data.works.length;
    els.count.textContent =
      `${items.length} of ${base} publications · since ${coverageStart()}` +
      (data.newIds.size ? ` · ${data.newIds.size} new in the last 7 days` : "");
    renderSelectedProfiles();
    els.list.innerHTML = items.map(render).join("");
    els.empty.classList.toggle("hidden", items.length > 0);
    els.list.querySelectorAll("[data-copy],[data-copy-short],[data-copy-comment]").forEach((b) =>
      b.addEventListener("click", async () => {
        const id = b.dataset.copy || b.dataset.copyShort || b.dataset.copyComment;
        const text = b.dataset.copy ? linkedinText(data.social[id].post) : b.dataset.copyComment ? data.social[id].comment : data.social[id].short;
        const label = b.textContent;
        try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; setTimeout(() => (b.textContent = label), 1500); }
        catch { window.prompt("Copy the text:", text); }
      }),
    );
    els.list.querySelectorAll("[data-person]").forEach((b) =>
      b.addEventListener("click", () => {
        const s = b.dataset.person;
        if (!state.people.includes(s)) state.people = [...state.people, s];
        renderPeople();
        update();
        els.profiles.scrollIntoView({
          behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "instant"
            : "smooth",
        });
      }),
    );
  }

  // LinkedIn has no text formatting; "bold" is done with Unicode sans-serif bold letters. Used for the first line only.
  function boldUnicode(s) {
    const map = (c) => {
      const code = c.codePointAt(0);
      if (code >= 65 && code <= 90) return String.fromCodePoint(0x1d5d4 + code - 65);
      if (code >= 97 && code <= 122) return String.fromCodePoint(0x1d5ee + code - 97);
      if (code >= 48 && code <= 57) return String.fromCodePoint(0x1d7ec + code - 48);
      return c;
    };
    return Array.from(s).map(map).join("");
  }
  function linkedinText(post) {
    const paras = post.trim().split(/\n\s*\n/);
    if (!paras.length) return post;
    paras[0] = boldUnicode(paras[0]);
    return paras.join("\n\n");
  }
  const FOLD = 210; // characters LinkedIn shows before "…see more" on desktop

  // Structured abstracts arrive from OpenAlex as one run of text; restore the section labels as bold paragraphs.
  const ABSTRACT_LABELS = ["Background", "Objectives?", "Aims?", "Purpose", "Introduction", "Materials and methods", "Methods?",
    "Design", "Setting", "Participants", "Interventions?", "Main outcome measures?", "Results", "Findings", "Conclusions?",
    "Interpretation", "Funding", "Discussion", "Significance", "Trial registration", "Keywords?"];
  const ABSTRACT_RE = new RegExp("(?:^|\\s)(" + ABSTRACT_LABELS.join("|") + ")\\s*:?\\s+(?=[A-Z0-9])", "g");
  function formatAbstract(text) {
    let s = String(text || "").replace(/^\s*Abstract[:.]?\s+/i, "").trim();
    const parts = [];
    let last = 0, m, count = 0;
    ABSTRACT_RE.lastIndex = 0;
    while ((m = ABSTRACT_RE.exec(s))) {
      const body = s.slice(last, m.index).trim();
      if (parts.length || body) parts.push({ label: parts.length ? parts[parts.length - 1].pending : "", body });
      if (parts.length) parts[parts.length - 1].pending = undefined;
      parts.push({ label: m[1], body: "", pending: m[1] });
      last = ABSTRACT_RE.lastIndex;
      count += 1;
    }
    if (count < 2) return `<p>${esc(s)}</p>`;
    // rebuild: each label owns the text up to the next label
    const out = [];
    let idx = 0;
    const labels = [];
    ABSTRACT_RE.lastIndex = 0;
    while ((m = ABSTRACT_RE.exec(s))) labels.push({ label: m[1], start: m.index, end: ABSTRACT_RE.lastIndex });
    if (labels[0].start > 0) out.push(`<p>${esc(s.slice(0, labels[0].start).trim())}</p>`);
    labels.forEach((l, i) => {
      const body = s.slice(l.end, i + 1 < labels.length ? labels[i + 1].start : s.length).trim();
      out.push(`<p><b class="abs-label">${esc(l.label)}</b> ${esc(body)}</p>`);
    });
    return out.join("");
  }

  function draftHtml(w, link) {
    const d = data.social && data.social[w.id];
    if (!d || !d.post) return "";
    const formatted = linkedinText(d.post);
    const prefill = "https://www.linkedin.com/feed/?shareActive=true&text=" + encodeURIComponent(formatted);
    const flags = d.flags ? ` · ${d.flags} point${d.flags === 1 ? "" : "s"} marked [check]` : "";
    const fig = d.figure && d.figure.path;
    const paras = d.post.trim().split(/\n\s*\n/);
    let seen = 0;
    const previewParas = paras.map((p, i) => {
      const cls = i === 0 ? "li-hook" : seen > FOLD ? "li-fold" : "";
      seen += p.length + 2;
      return `<p class="${cls}">${esc(p)}</p>`;
    }).join("");
    const images = (fig || d.card) ? `<div class="draft-images">${fig ? `<figure><img src="${esc(d.figure.path)}" alt="${esc(d.figure.alt || "Figure from the paper")}" loading="lazy"><figcaption>${d.figure.description ? `<span class="fig-desc">${esc(d.figure.description)}</span><br>` : ""}${esc(d.figure.credit || "")} · <a href="${esc(d.figure.path)}" download>download</a>${d.figure.chosen_by && !/claude/i.test(d.figure.chosen_by) ? ` · <span class="badge warn">unchecked pick</span>` : ""}</figcaption></figure>` : ""}${d.card ? `<figure><img src="${esc(d.card)}" alt="Card image for this paper" loading="lazy"><figcaption>Card${fig ? " (second image)" : ""} · <a href="${esc(d.card)}" download>download</a></figcaption></figure>` : ""}</div>` : "";
    return `<details class="social-draft"><summary>Share on LinkedIn <span class="meta">· draft, read before posting${esc(flags)}</span></summary>
      <div class="li-preview" aria-label="LinkedIn preview">
        <div class="li-head"><span class="li-avatar" aria-hidden="true"></span><div><b>Clinical Data Science · Maastricht University</b><br><span class="meta">Just now</span></div></div>
        <div class="li-body">${previewParas}<span class="li-more">…see more</span></div>
        ${images}
      </div>
      ${d.comment ? `<p class="draft-comment"><b>First comment</b> (paste right after posting):<br><span>${esc(d.comment)}</span></p>` : ""}
      ${d.figure_note ? `<p class="meta">${esc(d.figure_note)}</p>` : ""}
      <div class="draft-actions"><button type="button" class="button button-small button-dark" data-copy="${esc(w.id)}">Copy post (LinkedIn format)</button>${d.comment ? `<button type="button" class="button button-small" data-copy-comment="${esc(w.id)}">Copy first comment</button>` : ""}<a class="button button-small" href="${esc(prefill)}" target="_blank" rel="noopener">Open LinkedIn with this text ↗</a>${d.short ? `<button type="button" class="button button-small" data-copy-short="${esc(w.id)}">Copy short version</button>` : ""}</div>
      <p class="meta">Dimmed text falls below LinkedIn's "see more" fold; the first line is copied in bold. Add the image${fig ? "s" : ""} (figure first) and tag the co-authors before posting.</p>
    </details>`;
  }

  function render(w) {
    const link = w.doi || w.landing_url || w.openalex_url;
    const isNew = data.newIds.has(w.id);
    const members = workMembers(w)
      .map((s) => {
        const st = (w.affiliation_status || {})[s] || "unknown";
        const affs = (
          (w.member_affiliations && w.member_affiliations[s]) ||
          w.author_profiles?.[s]?.affiliations ||
          []
        ).join("; ");
        const mark =
          st === "verified" || !w.group_members.includes(s)
            ? ""
            : st === "mismatch"
              ? " <span class='badge warn' title='other affiliation on this paper'>other affil.</span>"
              : " <span class='badge warn' title='no affiliation recorded by OpenAlex'>no affil.</span>";
        return `<li><button class="link" data-person="${esc(s)}" title="${esc(affs || "no affiliation recorded by OpenAlex")}"><b>${esc(nameOf(s))}</b>${mark}</button></li>`;
      })
      .join("");
    const authorCount = w.author_count || w.authors.length;
    const normalizeName = (name) =>
      String(name)
        .normalize("NFKD")
        .replace(/\p{M}/gu, "")
        .toLowerCase()
        .replace(/[^\p{L}\p{N}]/gu, "");
    const groupNames = new Map();
    for (const slug of workMembers(w)) {
      const name = normalizeName(nameOf(slug));
      if (groupNames.has(name)) groupNames.set(name, null);
      else groupNames.set(name, slug);
    }
    const authors = w.authors
      .map((name, index) => {
        const slug = Array.isArray(w.author_members)
          ? w.author_members[index]
          : groupNames.get(normalizeName(name));
        const position = w.author_positions?.[index] || index + 1;
        if (!slug || !data.peopleBySlug[slug]) return esc(name);
        const st = (w.affiliation_status || {})[slug];
        const affs = ((w.member_affiliations && w.member_affiliations[slug]) || []).join("; ");
        const tip = `${nameOf(slug)} · ${data.peopleBySlug[slug].active ? "CDS member" : "former CDS staff"} · author ${position} of ${authorCount}` +
          (st ? ` · affiliation ${st}${affs ? ": " + affs : ""}` : "") + " · click to filter";
        return `<button type="button" class="link cds-author" data-person="${esc(slug)}" title="${esc(tip)}">${esc(name)}</button>`;
      })
      .join(", ");
    const incomplete = w.authors.length < authorCount;
    const meta = [
      w.publication_date,
      w.cited_by_count ? `${w.cited_by_count} citations` : null,
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    return `<li class="item">
      <div class="publication-top"><span class="journal-name">${esc(w.journal || "Research publication")}</span><span class="badges"><span class="badge pill-${esc(typeGroupKey(w.type))}" title="publication type (OpenAlex)">${esc(fmtType(w.type) || "publication")}</span>${isNew ? '<span class="badge new">new</span>' : ""}${w.manual === "confirmed" ? '<span class="badge manual" title="confirmed by hand in overrides.yml">confirmed</span>' : !isCounted(w) ? '<span class="badge warn" title="not counted: outside the team window, or this author needs a verified group affiliation (overrides.yml) and none was recorded">not counted</span>' : ""}${w.approved_external ? '<span class="badge approved" title="approved for external communication">approved</span>' : ""}${w.is_oa ? '<span class="badge oa" title="open access">open access</span>' : ""}</span></div>
      <h3><a href="${esc(link)}" target="_blank" rel="noopener">${esc(w.title)}</a></h3>
      <div class="meta">${meta}</div>
      <div class="authors authors-full"><span class="author-list-label">Authors (${authorCount}):</span> ${authors}${incomplete ? ` <span class="author-list-note">· ${w.authors.length} names available in OpenAlex</span>` : ""}</div>
      ${w.abstract ? `<details class="abstract"><summary>Abstract</summary>${formatAbstract(w.abstract)}</details>` : ""}
      ${draftHtml(w, link)}
      <div class="links">${w.doi ? `<a href="${esc(w.doi)}" target="_blank" rel="noopener">DOI ↗</a>` : ""}${w.oa_url ? `<a href="${esc(w.oa_url)}" target="_blank" rel="noopener">Full text ↗</a>` : ""}<a href="${esc(w.openalex_url)}" target="_blank" rel="noopener">OpenAlex ↗</a><span class="meta work-id" title="use this id in overrides.yml">${esc(w.id)}</span></div>
    </li>`;
  }

  fetch("data/publications.json", { cache: "no-cache" })
    .then((r) => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then((json) =>
      fetch("data/social/index.json", { cache: "no-cache" })
        .then((r) => (r.ok ? r.json() : {}))
        .catch(() => ({}))
        .then((social) => Object.assign(json, { social })),
    )
    .then(init)
    .catch(() => {
      els.count.textContent =
        "Publications could not be loaded. Please refresh to try again.";
      $("updated").textContent = "Update unavailable";
    });
})();
