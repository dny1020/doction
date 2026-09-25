import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Where each surface is served, set through the environment. DOCTION_APP_PATH must match
// app/main.py: assets load by absolute path.
function path(name, fallback) {
  const value = process.env[name] ?? fallback
  if (!value.startsWith('/')) {
    throw new Error(`${name} must start with "/" (received: "${value}")`)
  }
  return value.length > 1 ? value.replace(/\/$/, '') : value
}

const appPath = path('DOCTION_APP_PATH', '/app')
const staticPath = path('DOCTION_STATIC_PATH', '/static')
const mcpPath = path('DOCTION_MCP_PATH', '/api/mcp')

// Served from fixed paths, so the content hash goes in the query: a cached old stylesheet
// with a new bundle is a broken screen, and favicons have their own long-lived cache.
const HASHED_STATIC = ['style.css', 'favicon.svg', 'manifest.webmanifest', 'apple-touch-icon.png']

function fileHash(name) {
  try {
    return createHash('sha256')
      .update(readFileSync(new URL('../app/static/' + name, import.meta.url)))
      .digest('hex')
      .slice(0, 8)
  } catch {
    // The Dockerfile's `web` stage copies these before building, so this only fires in
    // an incomplete tree: without a hash the file is still served.
    return ''
  }
}

// Vite leaves absolute URLs alone, so the placeholder is substituted here, at 'pre': an
// unsubstituted placeholder is not a valid URI.
const staticUrls = {
  name: 'doction-static-urls',
  transformIndexHtml: {
    order: 'pre',
    handler: (html) => {
      for (const name of HASHED_STATIC) {
        const hash = fileHash(name)
        html = html.replaceAll(
          '__STATIC__/' + name,
          staticPath + '/' + name + (hash ? '?v=' + hash : ''),
        )
      }
      return html.replaceAll('__STATIC__', staticPath)
    },
  },
}

export default defineConfig({
  plugins: [react(), staticUrls],
  base: appPath === '/' ? '/' : appPath + '/',
  define: {
    __DOCTION_MCP_PATH__: JSON.stringify(mcpPath),
    // The router basename, from the same `appPath` as `base`. Through define rather than
    // import.meta.env.BASE_URL, which only the build pipeline fills in: vitest does not
    // inherit `base` from here, and setting it in its own config stopped propagating.
    __DOCTION_APP_BASE__: JSON.stringify(appPath === '/' ? '' : appPath),
  },
  build: {
    outDir: '../app/static/app',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/uploads': 'http://127.0.0.1:8000',
      [staticPath]: 'http://127.0.0.1:8000',
    },
  },
})
