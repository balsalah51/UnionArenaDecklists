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
      var rel = (a.getAttribute("rel") or "").split(/\s+/).filter(Boolean);
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
      if (!data || !data.characters) {
        out.innerHTML = "<p class=\"muted char-search-empty\">Could not load character lists.</p>";
        return;
      }
      var hits = data.characters.filter(function (row) {
        return (row.norm || "").indexOf(q) >= 0 || (row.name || "").toLowerCase().indexOf(q) >= 0;
      });
      hits.sort(function (a, b) {
        var an = (a.name || "").toLowerCase();
        var bn = (b.name || "").toLowerCase();
        var aExact = an === q || a.norm === q ? 1 : 0;
        var bExact = bn === q || b.norm === q ? 1 : 0;
        if (aExact !== bExact) return bExact - aExact;
        return (b.lists || []).length - (a.lists || []).length;
      });
      var tight = hits.length === 1 || (hits[0] && ((hits[0].name || "").toLowerCase() === q || hits[0].norm === q));
      hits = hits.slice(0, tight ? 1 : 8);
      if (!hits.length) {
        out.innerHTML = "<p class=\"muted char-search-empty\">No character matching “" + escapeHtml(q) + "”.</p>";
        return;
      }
      out.innerHTML = hits.map(function (row) {
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
          ? "<p class=\"muted char-search-empty\">" + (all.length - shown.length) + " more lists on the character page.</p>"
          : "";
        return "<article class=\"char-hit\">" +
          "<h4 class=\"char-hit-name\">" + escapeHtml(row.name) + " · " + all.length + (all.length === 1 ? " list" : " lists") + "</h4>" +
          (hubs ? "<div class=\"char-hit-hubs\">" + hubs + "</div>" : "") +
          (lists ? "<ul class=\"char-hit-lists\">" + lists + "</ul>" : "") +
          more +
          "</article>";
      }).join("");
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
