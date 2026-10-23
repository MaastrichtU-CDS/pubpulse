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
  const initialHash = location.hash;
  let data = null;
  let listenersBound = false;
  let state = readHash();

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    return {
      q: p.get("q") || "",
      year: p.get("year") || "",
      type: p.get("type") || "",
      journal: p.get("journal") || "",
      sort: p.get("sort") || "date",
      people: (p.get("people") || "").split(",").filter(Boolean),
      when: p.get("when") || (p.get("new") === "1" ? "week" : ""),
      verify: p.get("verify") || "",
      oa: p.get("oa") === "1",
      preprints: p.get("preprints") === "1",
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
    if (state.preprints) p.set("preprints", "1");
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
    return links.length
      ? `<span class="author-profile-links">${links.join("")}</span>`
      : "";
  }

  function fillSelect(el, values, current) {
    const first = el.options[0];
    el.innerHTML = "";
    el.appendChild(first);
    for (const [v, label] of values) {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = label;
      if (v === current) o.selected = true;
      el.appendChild(o);
    }
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
        maxItems: 1,
        maxOptions: null,
        allowEmptyOption: true,
        searchField: ["text"],
        highlight: true,
        closeAfterSelect: true,
        refreshThrottle: 0,
        placeholder: "Type to search…",
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

  function siteDefaults() {
    const site = (data && data.site) || {};
    return { verify: site.default_verified_only ? "verified" : "", preprints: !!site.default_include_preprints };
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
    data.newIds = new Set(
      data.last_run && !data.last_run.baseline ? data.last_run.new_ids : [],
    );
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
    $("total-publications").textContent =
      data.works.length.toLocaleString("en-GB");
    $("total-researchers").textContent = data.people
      .filter((person) => person.active)
      .length.toLocaleString("en-GB");
    $("total-open").textContent = data.works.length
      ? Math.round(
          (data.works.filter((w) => w.is_oa).length / data.works.length) * 100,
        ) + "%"
      : "—";
    $("coverage-start").textContent = "since " + coverageStart();
    $("publication-range").textContent =
      `${data.works.length.toLocaleString("en-GB")} publications · ${coverageStart()} onwards · OpenAlex`;
    configureDigest(data.list || {});

    const years = [
      ...new Set(data.works.map((w) => w.year).filter(Boolean)),
    ].sort((a, b) => b - a);
    fillSelect(
      els.year,
      years.map((y) => [String(y), String(y)]),
      state.year,
    );
    const types = [
      ...new Set(data.works.map((w) => w.type).filter(Boolean)),
    ].sort();
    fillSelect(
      els.type,
      types.map((t) => [t, fmtType(t)]),
      state.type,
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

    els.q.value = state.q;
    els.sort.value = state.sort;
    els.verify.value = state.verify === "all" ? "" : state.verify;
    els.when.value = state.when;
    els.onlyOa.checked = state.oa;
    els.preprints.checked = state.preprints;
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
        state.type = els.type.value;
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
      $("reset").addEventListener("click", () => {
        state = {
          q: "",
          year: "",
          type: "",
          journal: "",
          sort: "date",
          people: [],
          when: "",
          verify: siteDefaults().verify,
          oa: false,
          preprints: siteDefaults().preprints,
        };
        els.q.value = "";
        els.year.value = "";
        els.type.value = "";
        els.journal.value = "";
        els.sort.value = "date";
        els.verify.value = "";
        els.when.value = "";
        els.onlyOa.checked = false;
        els.preprints.checked = state.preprints;
        els.peopleQ.value = "";
        renderPeople();
        update();
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
        state = readHash();
        init(data);
      });
    }
    update();
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
            const description = [person.role, person.employer]
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

  const TYPE_GROUPS = [
    { key: "article", label: "Journal articles", color: "#2a78d6", types: ["article"], filter: "article" },
    { key: "review", label: "Reviews", color: "#eb6834", types: ["review"], filter: "review" },
    { key: "preprint", label: "Preprints", color: "#1baf7a", types: ["preprint"], filter: "preprint" },
    { key: "conference", label: "Conference", color: "#eda100", types: ["conference-paper", "conference-abstract"], filter: null },
    { key: "other", label: "Other", color: "#e87ba4", types: null, filter: null },
  ];

  function renderTypeBar() {
    const box = $("type-bar");
    if (!box) return;
    const pool = data.works.filter((w) => matches(w, { ignoreType: true }));
    const known = new Set(TYPE_GROUPS.flatMap((g) => g.types || []));
    const counts = TYPE_GROUPS.map((g) => ({
      ...g,
      n: pool.filter((w) => (g.types ? g.types.includes(w.type) : !known.has(w.type))).length,
    }));
    const total = counts.reduce((s, g) => s + g.n, 0);
    if (!total) { box.innerHTML = ""; return; }
    const hidden = !state.type && !state.preprints ? counts.find((g) => g.key === "preprint").n : 0;
    const seg = counts.filter((g) => g.n).map((g) => {
      const pct = (100 * g.n) / total;
      const on = g.filter && state.type === g.filter;
      const title = `${g.label}: ${g.n} (${pct.toFixed(0)}%)${g.filter ? (on ? ". Clear type filter" : ". Filter to this type") : ""}`;
      const inner = `<span class="type-seg-fill" style="background:${g.color}"></span>`;
      return g.filter
        ? `<button type="button" class="type-seg" style="flex:${g.n}" data-type="${g.filter}" aria-pressed="${on}" title="${esc(title)}" aria-label="${esc(title)}">${inner}</button>`
        : `<span class="type-seg" style="flex:${g.n}" title="${esc(title)}" aria-label="${esc(title)}">${inner}</span>`;
    }).join("");
    const legend = counts.filter((g) => g.n).map((g) =>
      `<span class="type-key"><span class="type-swatch" style="background:${g.color}"></span>${esc(g.label)} <b>${g.n}</b> <span class="meta">${((100 * g.n) / total).toFixed(0)}%</span></span>`).join("");
    box.innerHTML = `<div class="type-track" role="img" aria-label="${esc(counts.filter((g) => g.n).map((g) => `${g.label} ${g.n}`).join(", "))}">${seg}</div>` +
      `<div class="type-legend">${legend}${hidden ? `<span class="meta">· ${hidden} preprint${hidden === 1 ? "" : "s"} hidden by default</span>` : ""}</div>`;
    box.querySelectorAll("button.type-seg").forEach((b) => b.addEventListener("click", () => {
      const ty = b.dataset.type;
      state.type = state.type === ty ? "" : ty;
      if (state.type === "preprint") state.preprints = true;
      els.preprints.checked = state.preprints;
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
          els.year.value = state.year;
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
    if (state.when && state.when !== "week" && !inPeriod(w, state.when))
      return false;
    if (state.verify === "verified" && !w.verified) return false;
    if (state.verify === "unverified" && w.verified) return false;
    if (state.verify === "approved" && !w.approved_external) return false;
    if (state.oa && !w.is_oa) return false;
    if (!options.ignoreYear && state.year && String(w.year) !== state.year)
      return false;
    if (!options.ignoreType) {
      if (state.type && w.type !== state.type) return false;
      if (!state.type && !state.preprints && w.type === "preprint") return false;
    }
    if (state.journal && w.journal !== state.journal) return false;
    if (
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
    syncDropdowns();
    writeHash();
    let items = data.works.filter((w) => matches(w));
    renderYearChart();
    renderTypeBar();
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
    els.count.textContent =
      `${items.length} of ${data.works.length} publications · since ${coverageStart()}` +
      (data.newIds.size ? ` · ${data.newIds.size} new this week` : "");
    renderSelectedProfiles();
    els.list.innerHTML = items.map(render).join("");
    els.empty.classList.toggle("hidden", items.length > 0);
    els.list.querySelectorAll("[data-copy],[data-copy-short]").forEach((b) =>
      b.addEventListener("click", async () => {
        const id = b.dataset.copy || b.dataset.copyShort;
        const text = b.dataset.copy ? data.social[id].post : data.social[id].short;
        try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; setTimeout(() => (b.textContent = b.dataset.copy ? "Copy post" : "Copy short"), 1500); }
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

  function draftHtml(w, link) {
    const d = data.social && data.social[w.id];
    if (!d || !d.post) return "";
    const share = "https://www.linkedin.com/sharing/share-offsite/?url=" + encodeURIComponent(w.doi || link);
    const flags = d.flags ? ` · ${d.flags} [check] mark${d.flags === 1 ? "" : "s"} to verify` : "";
    return `<details class="social-draft"><summary>LinkedIn draft <span class="meta">(AI-written, read before posting${esc(flags)})</span></summary>
      ${d.card || (d.figure && d.figure.path) ? `<div class="draft-images">${d.figure && d.figure.path ? `<figure><img src="${esc(d.figure.path)}" alt="Figure from the paper" loading="lazy"><figcaption>${esc(d.figure.credit || "")} · <a href="${esc(d.figure.path)}" download>download</a></figcaption></figure>` : ""}${d.card ? `<figure><img src="${esc(d.card)}" alt="Card image for this paper" loading="lazy"><figcaption>Card · <a href="${esc(d.card)}" download>download</a></figcaption></figure>` : ""}</div>` : ""}
      ${d.figure_note ? `<p class="meta">${esc(d.figure_note)}</p>` : ""}
      <pre class="draft-text">${esc(d.post)}</pre>
      ${d.short ? `<p class="draft-short"><b>Short:</b> ${esc(d.short)}</p>` : ""}
      <div class="draft-actions"><button type="button" class="button button-small" data-copy="${esc(w.id)}">Copy post</button><button type="button" class="button button-small" data-copy-short="${esc(w.id)}">Copy short</button><a class="button button-small button-dark" href="${esc(share)}" target="_blank" rel="noopener">Share on LinkedIn ↗</a><span class="meta">Opens LinkedIn with the paper link; paste the copied text.</span></div>
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
        return `<strong class="cds-author" title="${esc(nameOf(slug))} · ${data.peopleBySlug[slug].active ? "CDS author" : "Former CDS staff"} · position ${position} of ${authorCount}">${esc(name)}<span class="author-position" aria-label="position ${position} of ${authorCount}">${position}/${authorCount}</span></strong>`;
      })
      .join(", ");
    const incomplete = w.authors.length < authorCount;
    const meta = [
      w.publication_date,
      fmtType(w.type),
      w.cited_by_count ? `${w.cited_by_count} citations` : null,
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    return `<li class="item">
      <div class="publication-top"><span class="journal-name">${esc(w.journal || "Research publication")}</span><span class="badges">${isNew ? '<span class="badge new">new</span>' : ""}${w.manual === "confirmed" ? '<span class="badge oa">confirmed</span>' : w.verified ? "" : '<span class="badge warn">unverified</span>'}${w.approved_external ? '<span class="badge new" title="approved for external communication">approved</span>' : ""}${w.is_oa ? '<span class="badge oa">open access</span>' : ""}</span></div>
      <h3><a href="${esc(link)}" target="_blank" rel="noopener">${esc(w.title)}</a></h3>
      <div class="meta">${meta}</div>
      <div class="authors group-authors"><span class="group-author-label">CDS authors</span><ul class="group-author-list">${members}</ul></div>
      <div class="authors authors-full"><span class="author-list-label">Authors (${authorCount}):</span> ${authors}${incomplete ? ` <span class="author-list-note">· ${w.authors.length} names available in OpenAlex</span>` : ""}</div>
      ${w.abstract ? `<details><summary>Abstract</summary><p>${esc(w.abstract)}</p></details>` : ""}
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
