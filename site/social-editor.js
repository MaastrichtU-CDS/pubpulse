/* pubpulse share editor: LinkedIn post text, first comment and card image, edited in the browser. Nothing is stored.
   Used by the social post studio (social.html). A "paper" is a plain object:
   { id, title, journal, publication_date, type, link, oa_url, authors, author_count, group_authors, abstract }. */
(() => {
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const FOLD = 210; // characters LinkedIn shows before "…see more" on desktop

  // LinkedIn has no text formatting; "bold" is done with Unicode sans-serif bold letters. Used for the first paragraph.
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

  function previewParas(post) {
    let seen = 0;
    return post.trim().split(/\n\s*\n/).map((p, i) => {
      const cls = i === 0 ? "li-hook" : seen > FOLD ? "li-fold" : "";
      seen += p.length + 2;
      return `<p class="${cls}">${esc(p)}</p>`;
    }).join("");
  }

  // The paper as the pipeline sends it to Claude (pubpulse/social.py user_message), for pasting into any AI chat.
  function paperMessage(p) {
    return [
      `Title: ${p.title}`,
      `Journal: ${p.journal || "unknown"}`,
      `Published: ${p.publication_date || "unknown"} (${p.type || "article"})`,
      `Group authors: ${(p.group_authors || []).join(", ") || "none listed"}`,
      `First authors: ${(p.authors || []).slice(0, 3).join(", ")} (total ${p.author_count || (p.authors || []).length})`,
      `DOI link: ${p.link}`,
      `Open-access link: ${p.oa_url || "none"}`,
      "",
      "Abstract:",
      p.abstract || "(no abstract)",
    ].join("\n");
  }

  // Accepts the JSON the prompt asks for (also inside ``` fences or with raw line breaks), or the ### sections format.
  function parseAnswer(text) {
    const t = text.trim().replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/, "");
    const start = t.indexOf("{"), end = t.lastIndexOf("}");
    if (start >= 0 && end > start) {
      const raw = t.slice(start, end + 1);
      for (const candidate of [raw, raw.replace(/\r?\n/g, "\\n")]) {
        try {
          const o = JSON.parse(candidate);
          if (o && typeof o.post === "string") return o;
        } catch { /* try the next form */ }
      }
    }
    const sec = (name) => (t.match(new RegExp("###\\s*" + name + "\\s*\\n([\\s\\S]*?)(?=\\n###|$)", "i")) || [])[1]?.trim();
    const o = { headline: sec("HEADLINE"), post: sec("POST"), comment: sec("COMMENT"), short: sec("SHORT") };
    return o.post ? o : null;
  }

  const list = (xs) => (xs.length > 1 ? xs.slice(0, -1).join(", ") + " and " + xs[xs.length - 1] : xs[0] || "");

  function seedFor(p, draft) {
    const names = p.group_authors || [];
    return {
      post: draft?.post ||
        ["[The main finding in one plain sentence]", `Work by ${names.length ? list(names) : "[group authors]"} with colleagues.`,
          "[What was done, and why it matters, in two or three sentences.]", `Published in ${p.journal || "[journal]"}.`,
          "#ClinicalDataScience #MaastrichtUniversity"].join("\n\n"),
      comment: draft?.comment || [p.title, `Paper: ${p.link}`, p.oa_url ? `Full text: ${p.oa_url}` : ""].filter(Boolean).join("\n"),
      headline: draft?.headline || p.title,
      proof: `Published in ${p.journal || "a peer-reviewed journal"} · ${(p.publication_date || "").slice(0, 4)}`.replace(/ · $/, ""),
      byline: names.length ? "With " + list(names) : "",
    };
  }

  // opts: { draft (pipeline draft or null), prompt (chat instructions) }
  function mount(box, paper, opts = {}) {
    const draft = opts.draft || null;
    const seed = seedFor(paper, draft);
    const fig = draft?.figure?.path ? draft.figure : null;
    box.innerHTML = `
      <section class="se-step se-ai">
        <h2 class="se-step-title"><span>2</span> ${draft?.post ? "Want another version? Write it with an AI chat" : "Write it with an AI chat"}</h2>
        <ol class="se-ai-steps">
          <li><button type="button" class="button button-small button-dark" data-act="copy-prompt">Copy prompt</button>
            and paste it into Claude, ChatGPT or Copilot.</li>
          <li>Paste the chat's answer here and import it:
            <textarea class="se-answer" rows="4" placeholder='{"headline": "…", "post": "…", "comment": "…", "short": "…"}'></textarea>
            <span class="se-ai-actions"><button type="button" class="button button-small button-dark" data-act="import">Import answer</button><span class="meta se-ai-msg" role="status"></span></span></li>
        </ol>
      </section>
      <section class="se-step">
        <h2 class="se-step-title"><span>3</span> Edit, copy and download</h2>
        <div class="se-grid">
          <div class="se-edit">
            <label class="se-label">Post text <span class="meta">first paragraph = hook, copied in bold</span>
              <textarea class="se-post" rows="12" spellcheck="true"></textarea></label>
            <p class="meta se-count"></p>
            <label class="se-label">First comment <span class="meta">post it right after the post: links go here</span>
              <textarea class="se-comment" rows="3"></textarea></label>
            <div class="draft-actions">
              <button type="button" class="button button-small button-dark" data-act="copy-post">Copy post</button>
              <button type="button" class="button button-small button-ghost" data-act="copy-comment">Copy first comment</button>
              <a class="button button-small button-ghost se-open" target="_blank" rel="noopener">Open LinkedIn with this text ↗</a>
              <button type="button" class="button button-small button-ghost" data-act="reset-text">Reset text</button>
            </div>
            <fieldset class="se-card-fields"><legend>Card image</legend>
              <label class="se-label">Headline <span class="meta se-hcount"></span><input class="se-headline" type="text"></label>
              <label class="se-label">Published line<input class="se-proof" type="text"></label>
              <label class="se-label">Byline<input class="se-byline" type="text"></label>
              <label class="se-label">Photo or figure <span class="meta">optional, shown on the right; stays on your computer</span>
                <input class="se-photo" type="file" accept="image/*"></label>
              <div class="draft-actions">
                <button type="button" class="button button-small button-dark" data-act="copy-card">Copy card image</button>
                <button type="button" class="button button-small button-ghost" data-act="download">Download card (PNG)</button>
                ${canShareFiles() ? '<button type="button" class="button button-small button-ghost" data-act="share">Share…</button>' : ""}
                <button type="button" class="button button-small button-ghost" data-act="reset-card">Reset card</button>
              </div>
              <p class="meta se-howto">LinkedIn cannot receive images from a website. Easiest: <b>Open LinkedIn with this text</b>,
                then <b>Copy card image</b> and paste it into the post (Ctrl/Cmd+V).${canShareFiles() ? " <b>Share…</b> opens your device's share menu with the card (pick LinkedIn); the app may drop the text, so copy the post first." : ""}</p>
            </fieldset>
          </div>
          <div class="se-preview">
            <div class="li-preview" aria-label="LinkedIn preview">
              <div class="li-head"><span class="li-avatar" aria-hidden="true"></span><div><b>Clinical Data Science · Maastricht University</b><br><span class="meta">Just now</span></div></div>
              <div class="li-body"></div>
              ${fig ? `<figure class="se-figure"><img src="${esc(fig.path)}" alt="${esc(fig.alt || "Figure from the paper")}" loading="lazy"><figcaption>${fig.description ? `${esc(fig.description)}<br>` : ""}${esc(fig.credit || "")} · <button type="button" class="link" data-act="copy-figure">copy figure</button> · <a href="${esc(fig.path)}" download>download figure</a> (post it first, the card second)</figcaption></figure>` : ""}
              <canvas class="se-canvas" width="1200" height="627" aria-label="Card image preview"></canvas>
            </div>
            ${draft?.figure_note ? `<p class="meta">${esc(draft.figure_note)}</p>` : ""}
            <p class="meta">Nothing is saved: your edits stay in this tab until you close or reload the page. Tag the co-authors on LinkedIn before posting.</p>
          </div>
        </div>
      </section>`;
    const q = (sel) => box.querySelector(sel);
    const f = { post: q(".se-post"), comment: q(".se-comment"), headline: q(".se-headline"), proof: q(".se-proof"), byline: q(".se-byline") };
    let photo = null;
    const setText = () => { f.post.value = seed.post; f.comment.value = seed.comment; };
    const setCard = () => { f.headline.value = seed.headline; f.proof.value = seed.proof; f.byline.value = seed.byline; photo = null; q(".se-photo").value = ""; };
    const refreshText = () => {
      const post = f.post.value;
      q(".li-body").innerHTML = previewParas(post) + '<span class="li-more">…see more</span>';
      q(".se-count").textContent = `${post.length} of 3000 characters · LinkedIn shows about the first ${FOLD} before "see more" (dimmed text is below the fold)`;
      q(".se-open").href = "https://www.linkedin.com/feed/?shareActive=true&text=" + encodeURIComponent(linkedinText(post));
    };
    // The latest card as a PNG blob, kept ready so Share can run straight from the click (browsers require that).
    let cardBlob = null;
    const refreshCard = () => {
      const n = f.headline.value.trim().length;
      q(".se-hcount").textContent = `${n} characters${n > 60 ? " · shorter reads better (≤ 60)" : ""}`;
      drawCard(q(".se-canvas"), { headline: f.headline.value, proof: f.proof.value, byline: f.byline.value, photo })
        .then(() => q(".se-canvas").toBlob((b) => (cardBlob = b), "image/png"));
    };
    const copyImage = async (b, blobPromise) => {
      const label = b.textContent;
      try {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blobPromise })]);
        b.textContent = "Copied: paste it in LinkedIn";
      } catch {
        b.textContent = "Copy not supported here: use Download";
      }
      setTimeout(() => (b.textContent = label), 2500);
    };
    setText(); setCard(); refreshText(); refreshCard();
    f.post.addEventListener("input", refreshText);
    for (const k of ["headline", "proof", "byline"]) f[k].addEventListener("input", refreshCard);
    q(".se-photo").addEventListener("change", (ev) => {
      const file = ev.target.files[0];
      if (!file) return;
      const img = new Image();
      img.onload = () => { photo = img; refreshCard(); };
      img.src = URL.createObjectURL(file);
    });
    const copy = async (b, text) => {
      const label = b.textContent;
      try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; setTimeout(() => (b.textContent = label), 1500); }
      catch { window.prompt("Copy the text:", text); }
    };
    box.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-act]");
      if (!b) return;
      const act = b.dataset.act;
      if (act === "copy-prompt") copy(b, (opts.prompt || "") + "\n\n" + paperMessage(paper));
      else if (act === "import") {
        const o = parseAnswer(q(".se-answer").value);
        const msg = q(".se-ai-msg");
        if (!o) { msg.textContent = "Could not read that answer: paste the whole JSON (or the ### sections)."; return; }
        if (o.post) f.post.value = String(o.post).trim();
        if (o.comment) f.comment.value = String(o.comment).trim();
        if (o.headline) f.headline.value = String(o.headline).trim();
        refreshText(); refreshCard();
        const flags = (String(o.post || "").match(/\[check[^\]]*\]/g) || []).length;
        msg.textContent = `Imported${flags ? ` · ${flags} point${flags === 1 ? "" : "s"} marked [check]: verify them in the paper` : ""}. Read it before posting.`;
      }
      else if (act === "copy-post") copy(b, linkedinText(f.post.value));
      else if (act === "copy-card") copyImage(b, new Promise((resolve) => q(".se-canvas").toBlob(resolve, "image/png")));
      else if (act === "copy-figure") copyImage(b, fetch(fig.path).then((r) => r.blob()).then((blob) => blob.type === "image/png" ? blob : toPng(blob)));
      else if (act === "share" && cardBlob) {
        const files = [new File([cardBlob], `cds-${paper.id || "paper"}-card.png`, { type: "image/png" })];
        navigator.share({ files, text: linkedinText(f.post.value), title: paper.title }).catch(() => {});
      }
      else if (act === "copy-comment") copy(b, f.comment.value);
      else if (act === "reset-text") { setText(); refreshText(); }
      else if (act === "reset-card") { setCard(); refreshCard(); }
      else if (act === "download")
        q(".se-canvas").toBlob((blob) => {
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = `cds-${paper.id || "paper"}-card.png`;
          a.click();
          setTimeout(() => URL.revokeObjectURL(a.href), 2000);
        }, "image/png");
    });
  }

  // Card image, same design as the generated cards (pubpulse/images.py): 1200x627, navy, headline, proof line, byline,
  // logo band. Logos are loaded once; SVGs get explicit sizes so every browser can draw them on a canvas.
  let cardAssets = null;
  function loadCardAssets() {
    const load = (name) => fetch("assets/" + name).then((r) => r.text()).then((svg) => {
      const vb = (svg.match(/viewBox="([^"]+)"/) || [])[1]?.split(/\s+/).map(Number) || [0, 0, 100, 100];
      if (!/<svg[^>]*\swidth=/.test(svg)) svg = svg.replace("<svg", `<svg width="${vb[2]}" height="${vb[3]}"`);
      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
      });
    }).catch(() => null);
    cardAssets ||= Promise.all(["cds.svg", "cds-mask.svg", "maastricht-umc.svg", "maastro.svg", "maastricht-university.svg"].map(load))
      .then(([cds, mask, umc, maastro, um]) => ({ cds, mask, logos: [[umc, 24], [maastro, 22], [um, 24]] }));
    return cardAssets;
  }

  // Device share menu with files (phones, Safari, Edge); hidden where it is not available.
  function canShareFiles() {
    try {
      return !!navigator.canShare && navigator.canShare({ files: [new File([""], "card.png", { type: "image/png" })] });
    } catch {
      return false;
    }
  }

  // Clipboards only take PNG: convert other image types through a canvas.
  function toPng(blob) {
    return createImageBitmap(blob).then((bmp) => {
      const c = document.createElement("canvas");
      c.width = bmp.width;
      c.height = bmp.height;
      c.getContext("2d").drawImage(bmp, 0, 0);
      return new Promise((resolve) => c.toBlob(resolve, "image/png"));
    });
  }

  function drawCard(canvas, card) {
    const W = 1200, H = 627, M = 84, NAVY = "#001c3d", ACCENT = "#049fd8";
    const font = (size, bold) => `${bold ? "700 " : ""}${size}px "Helvetica Neue", Helvetica, Arial, sans-serif`;
    return loadCardAssets().then((assets) => {
      const ctx = canvas.getContext("2d");
      const bandY = H - 92;
      const textRight = card.photo ? 740 : W - M - 60;
      ctx.fillStyle = NAVY;
      ctx.fillRect(0, 0, W, H);
      if (card.photo) {
        // photo panel on the right, cropped to fill
        const x0 = 780, pw = W - x0, ph = bandY;
        const r = Math.max(pw / card.photo.width, ph / card.photo.height);
        const sw = pw / r, sh = ph / r;
        ctx.drawImage(card.photo, (card.photo.width - sw) / 2, (card.photo.height - sh) / 2, sw, sh, x0, 0, pw, ph);
      } else if (assets.mask) {
        // faint emblem watermark
        const off = document.createElement("canvas");
        off.width = off.height = 460;
        const o = off.getContext("2d");
        o.drawImage(assets.mask, 0, 0, 460, 460);
        o.globalCompositeOperation = "source-in";
        o.fillStyle = "#fff";
        o.fillRect(0, 0, 460, 460);
        ctx.globalAlpha = 0.07;
        ctx.drawImage(off, W - 460 + 40, 70);
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = ACCENT;
      ctx.fillRect(0, 0, 12, H);
      ctx.textBaseline = "top";
      ctx.font = font(20, true);
      ctx.fillText("CLINICAL DATA SCIENCE · MAASTRICHT UNIVERSITY", M, 64);

      const wrap = (text, maxW) => {
        const lines = [];
        let cur = "";
        for (const word of text.split(/\s+/).filter(Boolean)) {
          const trial = (cur + " " + word).trim();
          if (ctx.measureText(trial).width <= maxW || !cur) cur = trial;
          else { lines.push(cur); cur = word; }
        }
        if (cur) lines.push(cur);
        return lines;
      };
      const ellipsis = (text, maxW) => {
        if (ctx.measureText(text).width <= maxW) return text;
        while (text && ctx.measureText(text + " …").width > maxW) text = text.slice(0, -1).trimEnd();
        return text + " …";
      };
      // headline: up to 3 lines, font shrinks to fit
      const width = textRight - M;
      let size = 66, lines;
      for (;;) {
        ctx.font = font(size, true);
        lines = wrap(card.headline.trim(), width);
        if (lines.length <= 3 || size <= 40) break;
        size -= 4;
      }
      if (lines.length > 3) { lines = lines.slice(0, 3); lines[2] = ellipsis(lines[2], width); }
      const lh = Math.round(size * 1.15);
      let y = 150 + Math.floor((3 * Math.round(66 * 1.15) - lines.length * lh) / 2);
      ctx.fillStyle = "#f5f7fa";
      for (const line of lines) { ctx.fillText(line, M, y); y += lh; }
      // accent rule, proof line, byline
      y = 412;
      ctx.fillStyle = ACCENT;
      ctx.fillRect(M, y, 56, 5);
      const lineW = card.photo ? 780 - M - 28 : W - 2 * M;
      // a long byline drops names ("… and 2 more") before it is cut off
      const fitList = (text, maxW) => {
        const m = text.match(/^(\S+\s)(.+)$/);
        if (ctx.measureText(text).width <= maxW || !m || !/,| and /.test(m[2])) return ellipsis(text, maxW);
        const names = m[2].split(/,\s*|\s+and\s+/).filter(Boolean);
        for (let k = names.length - 1; k >= 1; k--) {
          const t = m[1] + names.slice(0, k).join(", ") + ` and ${names.length - k} more`;
          if (ctx.measureText(t).width <= maxW) return t;
        }
        return ellipsis(text, maxW);
      };
      ctx.font = font(27);
      ctx.fillStyle = "#d6e2f0";
      ctx.fillText(ellipsis(card.proof.trim(), lineW), M, y + 26);
      ctx.font = font(23);
      ctx.fillStyle = "#a0b0c4";
      ctx.fillText(fitList(card.byline.trim(), lineW), M, y + 66);
      // footer band: emblem left, partner logos right
      ctx.fillStyle = "#002248";
      ctx.fillRect(12, bandY, W, H - bandY);
      if (assets.cds) ctx.drawImage(assets.cds, M - 8, bandY + 20, 104, 52);
      let right = W - M;
      for (const [logo, h] of assets.logos) {
        if (!logo) continue;
        const lw = (h * logo.width) / logo.height;
        right -= lw;
        ctx.drawImage(logo, right, bandY + 46 - h / 2, lw, h);
        right -= 36;
      }
    });
  }

  window.PubpulseSocial = { mount, parseAnswer, paperMessage, linkedinText };
})();
