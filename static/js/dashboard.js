/* Report-Viewer — Dashboard: Klick öffnet, Long-Press (500ms) öffnet Kontextmenü */
(function () {
  "use strict";

  var API = "/api/comments";
  var ctx = null;
  var pressTimer = null;
  var longPressed = false;
  var startX = 0, startY = 0;

  function buildContext() {
    var menu = document.createElement("div");
    menu.id = "ctx-menu";
    menu.className = "ctx-menu";
    menu.hidden = true;
    menu.innerHTML =
      '<button data-act="view">📄 Ansehen</button>' +
      '<button data-act="comment">💬 Kommentare</button>' +
      '<button data-act="download">⬇️ Herunterladen</button>' +
      '<button data-act="delete" class="danger">🗑️ Löschen</button>';
    document.body.appendChild(menu);
    return menu;
  }

  function showContext(x, y, filename) {
    if (!ctx) ctx = buildContext();
    ctx.dataset.filename = filename;
    ctx.hidden = false;
    var w = ctx.offsetWidth, h = ctx.offsetHeight;
    ctx.style.left = Math.min(x, window.innerWidth - w - 8) + "px";
    ctx.style.top = Math.min(y, window.innerHeight - h - 8) + "px";
  }

  function hideContext() {
    if (ctx) ctx.hidden = true;
  }

  function onContextAction(act, filename) {
    hideContext();
    if (act === "view") {
      window.location.href = "/view/" + encodeURIComponent(filename);
    } else if (act === "comment") {
      window.location.href = "/view/" + encodeURIComponent(filename);
    } else if (act === "download") {
      var a = document.createElement("a");
      a.href = "/view/" + encodeURIComponent(filename);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else if (act === "delete") {
      if (!confirm('Report "' + filename + '" wirklich löschen?')) return;
      fetch("/api/reports/" + encodeURIComponent(filename), { method: "DELETE" })
        .then(function () { location.reload(); });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    /* Kontext-Menü aufbauen */
    ctx = buildContext();
    ctx.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      onContextAction(btn.dataset.act, ctx.dataset.filename);
    });

    /* Karten verdrahten */
    document.querySelectorAll(".card[data-filename]").forEach(function (card) {
      var filename = card.dataset.filename;

      /* Einfacher Klick → Bericht öffnen */
      card.addEventListener("click", function (e) {
        /* Ignoriere Klick auf Kontextmenü */
        if (e.target.closest("#ctx-menu")) return;
        /* Ignoriere wenn Long-Press gerade ausgelöst hat */
        if (longPressed) { longPressed = false; return; }
        window.location.href = "/view/" + encodeURIComponent(filename);
      });

      /* Rechtsklick → Kontextmenü */
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        showContext(e.clientX, e.clientY, filename);
      });

      /* Long-Press (Maus, 500ms) → Kontextmenü */
      card.addEventListener("mousedown", function (e) {
        if (e.button !== 0) return;
        if (e.target.closest("#ctx-menu")) return;
        longPressed = false;
        pressTimer = setTimeout(function () {
          longPressed = true;
          showContext(e.clientX, e.clientY, filename);
        }, 500);
      });
      card.addEventListener("mouseup", function () { clearTimeout(pressTimer); });
      card.addEventListener("mouseleave", function () { clearTimeout(pressTimer); });

      /* Long-Press (Touch, 500ms) → Kontextmenü */
      card.addEventListener("touchstart", function (e) {
        if (e.touches.length !== 1) return;
        var t = e.touches[0];
        startX = t.clientX; startY = t.clientY;
        longPressed = false;
        pressTimer = setTimeout(function () {
          longPressed = true;
          showContext(startX, startY, filename);
        }, 500);
      }, { passive: true });

      card.addEventListener("touchend", function () { clearTimeout(pressTimer); });
      card.addEventListener("touchmove", function (e) {
        if (e.touches.length !== 1) return;
        var t = e.touches[0];
        if (Math.abs(t.clientX - startX) > 10 || Math.abs(t.clientY - startY) > 10) {
          clearTimeout(pressTimer);
        }
      }, { passive: true });
      card.addEventListener("touchcancel", function () { clearTimeout(pressTimer); });
    });

    /* Schließen bei Klick außerhalb */
    document.addEventListener("click", function (e) {
      if (ctx && !ctx.hidden && !ctx.contains(e.target)) hideContext();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") hideContext();
    });
  });
})();
