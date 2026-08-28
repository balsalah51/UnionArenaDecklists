(function () {
  var COPY_LABEL = "Copy list";

  function textList(root) {
    return Array.prototype.map.call(root.querySelectorAll(".text-line"), function (line) {
      var qty = (line.querySelector(".qty") || {}).textContent || "";
      var id = (line.querySelector(".card-id") || {}).textContent || "";
      qty = qty.replace(/\s+/g, "");
      id = id.trim();
      if (!qty || !id) return "";
      if (qty.slice(-1) !== "x") qty += "x";
      return qty + id;
    }).filter(Boolean).join("\n");
  }

  function listText(btn) {
    var raw = btn.getAttribute("data-sim");
    if (raw && raw.trim()) return raw.trim().split(/\s+/).join("\n");
    var root = btn.closest(".text-deck") || document;
    return textList(root);
  }

  function initCopy() {
    document.querySelectorAll("[data-copy-sim]").forEach(function (btn) {
      if (btn.dataset.bound) return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var text = listText(btn);
        if (!text) return;
        var done = function () {
          var prev = btn.textContent;
          btn.textContent = "Copied";
          setTimeout(function () { btn.textContent = prev; }, 1400);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done).catch(function () {
            window.prompt("Copy this Union Arena list", text);
          });
        } else {
          window.prompt("Copy this Union Arena list", text);
        }
      });
    });
  }

  function ensureCopyButtons() {
    document.querySelectorAll(".text-deck .section-title").forEach(function (title) {
      var existing = title.querySelector("[data-copy-sim]");
      if (existing) return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "copy-sim";
      btn.setAttribute("data-copy-sim", "");
      btn.textContent = COPY_LABEL;
      title.appendChild(btn);
    });
  }

  function initFilters() {
    document.querySelectorAll("[data-hub-filters]").forEach(function (bar) {
      if (bar.dataset.bound) return;
      bar.dataset.bound = "1";
      var section = bar.closest(".deck-index");
      if (!section) return;
      var items = section.querySelectorAll("ul.list > li");
      var countEl = section.querySelector(".section-title .muted");
      var total = items.length;
      function apply() {
        var q = ((bar.querySelector("[data-filter=q]") || {}).value || "").toLowerCase();
        var shown = 0;
        items.forEach(function (li) {
          var hay = (li.textContent || "").toLowerCase();
          var ok = !q || hay.indexOf(q) >= 0;
          li.hidden = !ok;
          if (ok) shown += 1;
        });
        if (countEl) countEl.textContent = shown === total ? total + " lists" : shown + " of " + total;
      }
      bar.addEventListener("input", apply);
      bar.addEventListener("change", apply);
    });
  }

  function withAffiliate(url) {
    var base = String(window.UADB_TCGPLAYER_PARTNER || "").trim();
    if (!base || !url) return url;
    if (url.indexOf("partner.tcgplayer.com") >= 0) return url;
    if (!/tcgplayer\.com/i.test(url)) return url;
    var sep = base.indexOf("?") >= 0 ? "&" : "?";
    return base.replace(/[?&]+$/, "") + sep + "u=" + encodeURIComponent(url);
  }

  function initBuyLinks() {
    document.querySelectorAll("a.buy-tcg").forEach(function (a) {
      var dest = a.getAttribute("href");
      if (!dest) return;
      var wrapped = withAffiliate(dest);
      if (wrapped === dest) return;
      a.setAttribute("href", wrapped);
      var rel = (a.getAttribute("rel") || "").split(/\s+/).filter(Boolean);
      if (rel.indexOf("sponsored") < 0) rel.push("sponsored");
      if (rel.indexOf("noopener") < 0) rel.push("noopener");
      a.setAttribute("rel", rel.join(" "));
    });
  }

  function initCharSearch() {
    var boxes = document.querySelectorAll("[data-char-search]");
    if (!boxes.length) return;
    var data = null;
    var pending = [];
    function load(done) {
      if (data) { done(); return; }
      pending.push(done);
      if (pending.length > 1) return;
      fetch("/data/character-search.json")
        .then(function (res) { return res.json(); })
        .then(function (json) {
          data = json;
          pending.forEach(function (fn) { fn(); });
          pending = [];
        })
        .catch(function () {
          pending.forEach(function (fn) { fn(); });
          pending = [];
        });
    }
    function escapeHtml(s) {
      return String(s || "").replace(/[&<>"']/g, function (ch) {
        return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
      });
    }
    function render(box, q) {
      var out = box.querySelector("[data-char-results]");
      if (!out) return;
      q = (q || "").trim().toLowerCase();
      if (!q) {
        out.hidden = true;
        out.innerHTML = "";
        return;
      }
      out.hidden = false;
      if (!data || (!data.characters && !data.series)) {
        out.innerHTML = "<p class=\"muted char-search-empty\">Could not load character lists.</p>";
        return;
      }
      function aliasHit(row, q) {
        var aliases = row.aliases || [];
        for (var i = 0; i < aliases.length; i++) {
          var al = String(aliases[i] || "").toLowerCase();
          if (al === q) return 2;
          if (q.length >= 3 && (al.indexOf(q) >= 0 || (row.norm || "").indexOf(q) >= 0)) return 1;
        }
        if ((row.norm || "").indexOf(q) >= 0 || (row.name || "").toLowerCase().indexOf(q) >= 0) return 1;
        return 0;
      }
      function nameHit(row, q) {
        var name = (row.name || "").toLowerCase();
        var norm = row.norm || "";
        if (name === q || norm === q) return 2;
        if (norm.indexOf(q) >= 0 || name.indexOf(q) >= 0) return 1;
        return 0;
      }
      var seriesHits = (data.series || []).filter(function (row) { return aliasHit(row, q) > 0; });
      seriesHits.sort(function (a, b) { return aliasHit(b, q) - aliasHit(a, q) || (b.lists || []).length - (a.lists || []).length; });
      var charHits = (data.characters || []).filter(function (row) { return nameHit(row, q) > 0; });
      charHits.sort(function (a, b) { return nameHit(b, q) - nameHit(a, q) || (b.lists || []).length - (a.lists || []).length; });
      var seriesExact = seriesHits.length && aliasHit(seriesHits[0], q) === 2;
      var charExact = charHits.length && nameHit(charHits[0], q) === 2;
      if (seriesExact && !charExact) {
        seriesHits = seriesHits.slice(0, 1);
        charHits = [];
      } else {
        seriesHits = seriesHits.slice(0, 3);
        charHits = charHits.slice(0, seriesHits.length ? 5 : 8);
      }
      if (!seriesHits.length && !charHits.length) {
        out.innerHTML = "<p class=\"muted char-search-empty\">No character or title matching \"" + escapeHtml(q) + "\".</p>";
        return;
      }
      function listItems(row, tight) {
        var hubs = (row.hubs || []).map(function (hub) {
          var bits = [hub.label || row.name];
          if (hub.color) bits.push(hub.color);
          if (hub.n) bits.push(hub.n + (hub.n === 1 ? " list" : " lists"));
          return "<a href=\"" + escapeHtml(hub.href) + "\">" + escapeHtml(bits.join(" · ")) + "</a>";
        }).join("");
        var all = row.lists || [];
        var shown = tight ? all : all.slice(0, 24);
        var lists = shown.map(function (list) {
          var meta = [list.sub, list.date].filter(Boolean).join(" · ");
          return "<li><a href=\"" + escapeHtml(list.href) + "\"><div class=\"who\">" + escapeHtml(list.title || "Decklist") + "</div>" +
            (meta ? "<div class=\"muted meta\">" + escapeHtml(meta) + "</div>" : "") +
            "</a></li>";
        }).join("");
        var more = all.length > shown.length
          ? "<p class=\"muted char-search-empty\">" + (all.length - shown.length) + " more lists.</p>"
          : "";
        var kind = row.kind === "series" ? "Title" : "Character";
        var heading = escapeHtml(row.name);
        if (row.href) heading = "<a href=\"" + escapeHtml(row.href) + "\">" + heading + "</a>";
        return "<article class=\"char-hit\">" +
          "<h4 class=\"char-hit-name\">" + heading + " · " + kind + " · " + all.length + (all.length === 1 ? " list" : " lists") + "</h4>" +
          (hubs ? "<div class=\"char-hit-hubs\">" + hubs + "</div>" : "") +
          (lists ? "<ul class=\"char-hit-lists\">" + lists + "</ul>" : "") +
          more +
          "</article>";
      }
      var tightSeries = seriesHits.length === 1 && aliasHit(seriesHits[0], q) === 2;
      var tightChar = charHits.length === 1 && nameHit(charHits[0], q) === 2 && !seriesHits.length;
      out.innerHTML = seriesHits.map(function (row) { return listItems(row, tightSeries); }).join("") +
        charHits.map(function (row) { return listItems(row, tightChar); }).join("");
    }
    boxes.forEach(function (box) {
      if (box.dataset.bound) return;
      box.dataset.bound = "1";
      var input = box.querySelector("input[type=search]");
      if (!input) return;
      var timer = null;
      function go() {
        load(function () { render(box, input.value); });
      }
      input.addEventListener("focus", go);
      input.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(go, 80);
      });
    });
  }

  function ready() {
    ensureCopyButtons();
    initCopy();
    initFilters();
    initBuyLinks();
    initCharSearch();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready);
  else ready();
})();
