/* doction UI polish: toasts, styled confirm dialogs, command palette (⌘K),
   and an unsaved-changes guard for the editor. Vanilla JS, no deps. */
(function () {
  "use strict";

  /* ── Toasts ─────────────────────────────────────────────────────────── */
  function toast(message, type) {
    var wrap = document.getElementById("toasts");
    if (!wrap || !message) return;
    var el = document.createElement("div");
    el.className = "toast toast--" + (type || "info");
    el.textContent = message;
    wrap.appendChild(el);
    requestAnimationFrame(function () { el.classList.add("show"); });
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () { el.remove(); }, 200);
    }, 3200);
  }
  window.toast = toast;

  /* El servidor puede disparar un toast en respuestas HTMX vía
     HX-Trigger: {"doctionToast": {"message": "...", "type": "ok"}} */
  if (document.body) {
    document.body.addEventListener("doctionToast", function (e) {
      if (e.detail) toast(e.detail.message, e.detail.type);
    });
  }

  /* ── Diálogo de confirmación con estilo (reemplaza confirm() nativo) ──── */
  /* Cualquier <form data-confirm="mensaje"> pide confirmación antes de enviar. */
  var dialog = document.getElementById("confirm-dialog");
  var dialogMsg = document.getElementById("confirm-dialog-msg");
  var dialogOk = document.getElementById("confirm-dialog-ok");
  var pendingForm = null;

  if (dialog && dialogOk) {
    document.addEventListener("submit", function (e) {
      var form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      var msg = form.getAttribute("data-confirm");
      if (!msg || form.dataset.confirmed === "1") return;
      e.preventDefault();
      pendingForm = form;
      if (dialogMsg) dialogMsg.textContent = msg;
      dialog.showModal();
    });
    dialogOk.addEventListener("click", function () {
      dialog.close();
      if (pendingForm) {
        pendingForm.dataset.confirmed = "1";
        pendingForm.submit();  // submit() no re-dispara el evento submit
        pendingForm = null;
      }
    });
    dialog.addEventListener("close", function () { pendingForm = null; });
  }

  /* ── Command palette (⌘K / Ctrl-K) ──────────────────────────────────── */
  (function () {
    var overlay = document.getElementById("palette");
    if (!overlay) return;
    var input = document.getElementById("palette-input");
    var list = document.getElementById("palette-list");
    var items = [];
    var sel = 0;

    function collect() {
      items = Array.prototype.map.call(
        document.querySelectorAll('.page-list a[href^="/pages/"]'),
        function (a) { return { title: a.textContent.trim(), href: a.getAttribute("href") }; }
      );
    }
    function render(q) {
      var ql = q.toLowerCase();
      var matches = items.filter(function (it) {
        return it.title.toLowerCase().indexOf(ql) !== -1;
      }).slice(0, 50);
      list.innerHTML = "";
      if (!matches.length) {
        var empty = document.createElement("li");
        empty.className = "palette-empty";
        empty.textContent = overlay.getAttribute("data-empty") || "No pages";
        list.appendChild(empty);
        sel = -1;
        return;
      }
      matches.forEach(function (it, i) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = it.href;
        a.textContent = it.title;
        a.className = "palette-item" + (i === 0 ? " active" : "");
        li.appendChild(a);
        list.appendChild(li);
      });
      sel = 0;
    }
    function open() {
      collect();
      overlay.classList.add("open");
      overlay.setAttribute("aria-hidden", "false");
      input.value = "";
      render("");
      input.focus();
    }
    function close() {
      overlay.classList.remove("open");
      overlay.setAttribute("aria-hidden", "true");
    }
    function move(d) {
      var links = list.querySelectorAll(".palette-item");
      if (!links.length) return;
      if (links[sel]) links[sel].classList.remove("active");
      sel = (sel + d + links.length) % links.length;
      links[sel].classList.add("active");
      links[sel].scrollIntoView({ block: "nearest" });
    }

    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        overlay.classList.contains("open") ? close() : open();
        return;
      }
      if (!overlay.classList.contains("open")) return;
      if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") {
        var links = list.querySelectorAll(".palette-item");
        if (sel >= 0 && links[sel]) { e.preventDefault(); window.location.href = links[sel].href; }
      }
    });
    input.addEventListener("input", function () { render(input.value); });
    overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });
  })();

  /* ── Aviso de cambios sin guardar en el editor ──────────────────────── */
  (function () {
    var form = document.querySelector("form.editor");
    if (!form) return;
    var dirty = false, submitting = false;
    form.addEventListener("input", function () { dirty = true; });
    form.addEventListener("submit", function () { submitting = true; });
    window.addEventListener("beforeunload", function (e) {
      if (dirty && !submitting) { e.preventDefault(); e.returnValue = ""; }
    });
  })();
})();
