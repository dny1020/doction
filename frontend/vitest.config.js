import { defineConfig } from 'vitest/config'

// jsdom, because DOMPurify sanitizes against a real DOM.
//
// The `define` repeats vite.config.js's because vitest does not inherit it and config.js
// reads it at import time; without it the whole suite fails with a ReferenceError.
export default defineConfig({
  define: {
    __DOCTION_MCP_PATH__: JSON.stringify('/api/mcp'),
    // The same basename as the default build: wikilinks come out as <a href> inside the
    // document and have to carry it, so a test environment mounted at the root would
    // prove nothing.
    __DOCTION_APP_BASE__: JSON.stringify('/app'),
  },
  test: { environment: 'jsdom', include: ['src/**/*.test.js'] },
})
