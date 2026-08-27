(function () {
  function ready(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  ready(function () {
    var input = document.querySelector("[data-discord-filter]");
    if (!input) return;
    var channels = document.querySelectorAll("[data-filterable]");

    function apply() {
      var q = (input.value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
      channels.forEach(function (el) {
        var hay = (el.getAttribute("data-channel") || el.textContent || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
        var hide = Boolean(q) && hay.indexOf(q) < 0;
        el.hidden = hide;
        el.style.display = hide ? "none" : "";
      });
    }

    input.addEventListener("input", apply);
    input.addEventListener("keyup", apply);
    input.addEventListener("search", apply);
  });
})();
