(function () {
  "use strict";

  var API = "/api/comments";
  var filename = window.__REPORT_FILENAME__ || null;
  var savedRange = null;
  var savedElement = null;
  var savedElementLabel = null;
  var allComments = [];

  function el(id) { return document.getElementById(id); }

  /* ── schwebende Kommentar-Übersicht ─────────────────────────── */

  function buildListPanel() {
    var panel = document.createElement("div");
    panel.id = "comment-list-panel";
    panel.className = "comment-list-panel";
    panel.hidden = true;
    panel.innerHTML =
      '<div class="clp-header">' +
      '  <span class="clp-title">💬 Kommentare</span>' +
      '  <span class="clp-count" id="clp-count"></span>' +
      '  <button id="clp-close" class="clp-close" aria-label="Schließen">✕</button>' +
      '</div>' +
      '<div id="clp-list" class="clp-list"></div>';
    document.body.appendChild(panel);
    return panel;
  }

  function buildToggleBtn() {
    var btn = document.createElement("button");
    btn.id = "comment-toggle";
    btn.className = "comment-toggle";
    btn.title = "Kommentare anzeigen";
    btn.textContent = "💬";
    document.body.appendChild(btn);
    return btn;
  }

  function showListPanel() {
    var panel = el("comment-list-panel") || buildListPanel();
    panel.hidden = false;
    renderList();
  }

  function hideListPanel() {
    var panel = el("comment-list-panel");
    if (panel) panel.hidden = true;
  }

  function renderList() {
    var list = el("clp-list");
    var count = el("clp-count");
    if (!list) return;
    if (count) count.textContent = allComments.length + " " + (allComments.length === 1 ? "Kommentar" : "Kommentare");

    if (!allComments.length) {
      list.innerHTML = '<p class="clp-empty">Noch keine Kommentare zu diesem Bericht.</p>';
      return;
    }
    list.innerHTML = "";
    allComments.forEach(function (c) {
      var item = document.createElement("div");
      item.className = "clp-item";

      if (c.quote) {
        var q = document.createElement("blockquote");
        q.className = "clp-quote";
        q.textContent = "„" + c.quote + "“";
        item.appendChild(q);
      }

      var meta = document.createElement("div");
      meta.className = "clp-meta";
      meta.textContent = (c.author || "Anonym") + " · " + (c.created || "").replace("T", " ");
      item.appendChild(meta);

      var body = document.createElement("div");
      body.className = "clp-body";
      body.textContent = c.text;
      item.appendChild(body);

      var del = document.createElement("button");
      del.className = "clp-delete";
      del.title = "Löschen";
      del.textContent = "✕";
      del.addEventListener("click", function () { deleteComment(c.id); });
      item.appendChild(del);

      list.appendChild(item);
    });
  }

  /* ── Popover beim Markieren ─────────────────────────────────── */

  function showPopover(x, y) {
    var pop = el("comment-popover");
    if (!pop) return;
    pop.hidden = false;
    var w = pop.offsetWidth, h = pop.offsetHeight;
    pop.style.left = Math.min(x, window.innerWidth - w - 12) + "px";
    pop.style.top = Math.min(y, window.innerHeight - h - 12) + "px";
  }

  function hidePopover() {
    var pop = el("comment-popover");
    if (pop) pop.hidden = true;
  }

  function getSelectionRect() {
    var sel = window.getSelection();
    if (!sel.rangeCount) return null;
    return sel.getRangeAt(0).getBoundingClientRect();
  }

  document.addEventListener("mouseup", function (e) {
    if (e.target.closest("#comment-popover")) return;
    var sel = window.getSelection();
    if (!sel.rangeCount) return;
    var text = sel.toString().trim();
    if (!text || text.length < 2) { hidePopover(); return; }
    savedRange = sel.getRangeAt(0).cloneRange();
    var rect = getSelectionRect();
    if (rect) showPopover(rect.left + rect.width / 2 - 60, rect.top - 48);
  });

  document.addEventListener("touchend", function (e) {
    if (e.target.closest("#comment-popover")) return;
    var sel = window.getSelection();
    if (!sel.rangeCount) return;
    var text = sel.toString().trim();
    if (!text || text.length < 2) { hidePopover(); return; }
    savedRange = sel.getRangeAt(0).cloneRange();
    var rect = getSelectionRect();
    if (rect) showPopover(rect.left + rect.width / 2 - 60, rect.top - 48);
  }, { passive: true });

  document.addEventListener("mousedown", function (e) {
    if (!e.target.closest("#comment-popover")) hidePopover();
  });

  /* ── Zitat speichern ────────────────────────────────────────── */

  function addQuoteComment() {
    var quote = "";
    if (savedRange) {
      quote = savedRange.toString().trim();
    } else if (savedElement) {
      quote = "[Element: " + savedElementLabel + "]";
    }
    if (!quote) return;

    var authorEl = el("popover-author");
    var textEl = el("popover-text");
    var author = authorEl ? authorEl.value.trim() : "";
    var text = textEl ? textEl.value.trim() : "";
    if (!text) { if (textEl) textEl.focus(); return; }

    var sel = window.getSelection();
    if (sel) sel.removeAllRanges();
    hidePopover();
    if (textEl) textEl.value = "";
    savedRange = null;
    savedElement = null;
    savedElementLabel = null;

    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: filename,
        author: author || "Anonym",
        text: text,
        quote: quote
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function () {
        loadComments();
      });
  }

  /* ── Thread (Klick auf Highlight) ───────────────────────────── */

  function showCommentThread(commentId, quote, anchorRect) {
    var thread = el("comment-thread");
    if (!thread) return;
    thread.hidden = false;
    thread.dataset.commentId = commentId;

    var quoteEl = el("thread-quote");
    if (quoteEl) quoteEl.textContent = "„" + quote + "“";

    var list = el("thread-comments");
    if (list) {
      list.innerHTML = "";
      var comments = getCommentsForQuote(quote);
      if (!comments.length) {
        list.innerHTML = '<p class="thread-empty">Keine Kommentare zu diesem Zitat.</p>';
      } else {
        comments.forEach(function (c) {
          var row = document.createElement("div");
          row.className = "thread-comment";
          var metaDiv = document.createElement("div");
          metaDiv.className = "thread-meta";
          metaDiv.textContent = (c.author || "Anonym") + " · " + (c.created || "").replace("T", " ");
          var bodyDiv = document.createElement("div");
          bodyDiv.className = "thread-body";
          bodyDiv.textContent = c.text;
          row.appendChild(metaDiv);
          row.appendChild(bodyDiv);
          list.appendChild(row);
        });
      }
    }

    /* Positionierung: über dem Element/Highlight wenn anchorRect gegeben, sonst im Viewport fix */
    if (anchorRect) {
      var tw = thread.offsetWidth, th = thread.offsetHeight;
      var tx = anchorRect.left + anchorRect.width / 2 - tw / 2;
      var ty = anchorRect.top - th - 8;
      if (ty < 8) ty = anchorRect.bottom + 8;
      tx = Math.max(8, Math.min(tx, window.innerWidth - tw - 8));
      ty = Math.max(8, Math.min(ty, window.innerHeight - th - 8));
      thread.style.left = tx + "px";
      thread.style.top = ty + "px";
      thread.style.right = "auto";
      thread.style.bottom = "auto";
    } else {
      /* Fallback: schwebend unten rechts wie bisher */
      thread.style.left = "auto";
      thread.style.top = "auto";
      thread.style.right = "24px";
      thread.style.bottom = "84px";
    }
  }

  function hideCommentThread() {
    var thread = el("comment-thread");
    if (thread) thread.hidden = true;
  }

  /* ── Kommentare laden ───────────────────────────────────────── */

  function getCommentsForQuote(quote) {
    return allComments.filter(function (c) {
      return c.quote && c.quote.trim() === quote.trim();
    });
  }

  function loadComments() {
    if (!filename) return;
    fetch(API + "?filename=" + encodeURIComponent(filename))
      .then(function (r) { return r.json(); })
      .then(function (items) {
        allComments = items;
        renderHighlights();
        /* Badge am Toggle-Button aktualisieren */
        var btn = el("comment-toggle");
        if (btn) {
          if (allComments.length) {
            btn.textContent = "💬 " + allComments.length;
          } else {
            btn.textContent = "💬";
          }
        }
      });
  }

  function renderHighlights() {
    /* Entferne alte Highlights */
    document.querySelectorAll("mark.comment-highlight").forEach(function (m) {
      var parent = m.parentNode;
      if (parent) {
        parent.replaceChild(document.createTextNode(m.textContent), m);
        parent.normalize();
      }
    });

    /* Setze neue Highlights für jeden Kommentar mit quote */
    allComments.forEach(function (c) {
      if (!c.quote) return;
      highlightText(c.quote, c.id);
    });
  }

  function highlightText(quote, commentId) {
    var walker = document.createTreeWalker(
      document.body,
      window.NodeFilter.SHOW_TEXT,
      {
        acceptNode: function (node) {
          if (!node.nodeValue.trim()) return window.NodeFilter.FILTER_REJECT;
          var parent = node.parentNode;
          if (parent && (parent.tagName === "SCRIPT" || parent.tagName === "STYLE" ||
              parent.tagName === "MARK" || parent.tagName === "TEXTAREA" ||
              parent.tagName === "INPUT" || parent.tagName === "BUTTON")) {
            return window.NodeFilter.FILTER_REJECT;
          }
          return window.NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    var node;
    while ((node = walker.nextNode())) {
      var idx = node.nodeValue.indexOf(quote);
      if (idx === -1) continue;

      var range = document.createRange();
      range.setStart(node, idx);
      range.setEnd(node, idx + quote.length);

      var mark = document.createElement("mark");
      mark.className = "comment-highlight";
      mark.dataset.comment = commentId;
      mark.addEventListener("click", function (e) {
        e.stopPropagation();
        var r = mark.getBoundingClientRect();
        showCommentThread(commentId, quote, r);
      });

      try {
        range.surroundContents(mark);
      } catch (err) {
        console.warn("highlight failed:", err);
      }
      break;
    }
  }

  function deleteComment(id) {
    fetch(API + "/" + id, { method: "DELETE" })
      .then(function () { loadComments(); });
  }

  /* ── Element-Klick (Dashboards, Grafiken, Bilder) ─────────────── */

  /* Markierbare Elemente: canvas, img, svg, .card, .chart, [data-chart] */
  var SELECTABLE = "canvas, img, svg, .card, .chart, [data-chart], [data-commentable]";

  document.addEventListener("click", function (e) {
    /* Ignoriere Klicks auf UI-Elemente */
    if (e.target.closest("#comment-popover, #comment-list-panel, #comment-thread, .comment-toggle, .comment-highlight")) return;
    /* Ignoriere Klicks auf Inputs/Textareas */
    if (e.target.closest("input, textarea, button, a, select")) return;

    var target = e.target.closest(SELECTABLE);
    if (!target) return;

    /* Ignoriere Excalidraw-Canvas (der hat seine eigene Logik) */
    if (target.closest("#excalidraw-app")) return;

    /* Element-Identität bestimmen */
    var label = target.tagName.toLowerCase();
    if (target.id) label += "#" + target.id;
    if (target.className && typeof target.className === "string") {
      var cls = target.className.trim().split(/\s+/).slice(0, 2).join(".");
      if (cls) label += "." + cls;
    }

    /*BoundingClientRect für Position */
    var rect = target.getBoundingClientRect();
    var x = rect.left + rect.width / 2 - 60;
    var y = rect.top - 48;

    /* Prüfe ob dieses Element bereits Kommentare hat */
    var elementQuote = "[Element: " + label + "]";
    var existing = getCommentsForQuote(elementQuote);

    if (existing.length) {
      /* Bereits Kommentare vorhanden → Thread über dem Element öffnen */
      showCommentThread(existing[0].id, elementQuote, rect);
      /* Element kurz hervorheben */
      target.classList.add("comment-element-highlight");
      setTimeout(function () { target.classList.remove("comment-element-highlight"); }, 600);
      return;
    }

    /* Kein Kommentar vorhanden → Popover für neuen Kommentar */
    target.classList.add("comment-element-highlight");
    setTimeout(function () {
      target.classList.remove("comment-element-highlight");
    }, 300);

    savedRange = null;
    savedElement = target;
    savedElementLabel = label;
    showPopover(x, y);

    var textEl = el("popover-text");
    if (textEl) {
      textEl.placeholder = "Kommentar zu " + label + " …";
      textEl.focus();
    }
  });

  /* ── Init ───────────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    if (!filename) return;

    /* Toggle-Button (schwebend, unten rechts) */
    var toggleBtn = buildToggleBtn();
    toggleBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      var panel = el("comment-list-panel");
      if (panel && !panel.hidden) hideListPanel();
      else showListPanel();
    });

    /* Panel schließen */
    var closeBtn = el("clp-close");
    if (closeBtn) closeBtn.addEventListener("click", hideListPanel);

    /* Popover-Buttons */
    var cancelBtn = el("popover-cancel");
    if (cancelBtn) cancelBtn.addEventListener("click", function () {
      hidePopover();
      var sel = window.getSelection();
      if (sel) sel.removeAllRanges();
      savedRange = null;
      savedElement = null;
      savedElementLabel = null;
    });

    var saveBtn = el("popover-save");
    if (saveBtn) saveBtn.addEventListener("click", addQuoteComment);

    var textEl = el("popover-text");
    if (textEl) textEl.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault(); addQuoteComment();
      }
    });

    /* Thread schließen */
    var closeThread = el("thread-close");
    if (closeThread) closeThread.addEventListener("click", hideCommentThread);

    /* Laden */
    loadComments();
  });
})();
