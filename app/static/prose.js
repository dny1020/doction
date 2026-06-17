/* Mejora client-side de .prose: diagramas Mermaid + resaltado de código.
   Ambas librerías se cargan de forma perezosa (vendadas) solo si la página las necesita,
   así que no hay coste cuando no hay diagramas ni bloques de código. */
(function () {
  'use strict';

  var loaded = {};
  function loadScript(src) {
    if (loaded[src]) return loaded[src];
    loaded[src] = new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = src;
      s.defer = true;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return loaded[src];
  }

  document.querySelectorAll('.prose').forEach(function (prose) {
    /* --- Mermaid: <pre><code class="language-mermaid"> → <div class="mermaid"> --- */
    var mermaidBlocks = prose.querySelectorAll('pre > code.language-mermaid');
    if (mermaidBlocks.length) {
      mermaidBlocks.forEach(function (code) {
        var div = document.createElement('div');
        div.className = 'mermaid';
        div.textContent = code.textContent;
        code.closest('pre').replaceWith(div);
      });
      loadScript('/static/vendor/mermaid.min.js').then(function () {
        if (typeof mermaid === 'undefined') return;
        var dark = document.documentElement.getAttribute('data-theme') === 'dark';
        mermaid.initialize({
          startOnLoad: false,
          theme: dark ? 'dark' : 'default',
          securityLevel: 'strict',
        });
        mermaid.run({ nodes: prose.querySelectorAll('.mermaid') });
      }).catch(function () {});
    }

    /* --- Resaltado de sintaxis sobre los bloques con clase de lenguaje --- */
    var codeBlocks = prose.querySelectorAll(
      'pre > code[class*="language-"]:not(.language-mermaid)'
    );
    if (codeBlocks.length) {
      loadScript('/static/vendor/highlight.min.js').then(function () {
        if (typeof hljs === 'undefined') return;
        codeBlocks.forEach(function (block) { hljs.highlightElement(block); });
      }).catch(function () {});
    }
  });
})();
