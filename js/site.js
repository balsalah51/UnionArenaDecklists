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

  function ready() {
    ensureCopyButtons();
    initCopy();
    initFilters();
    initBuyLinks();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready);
  else ready();
})();
