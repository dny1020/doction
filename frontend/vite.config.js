import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Where each surface is served. A deployment that wants something else says so through
// the environment rather than by editing this file.
//
// DOCTION_APP_PATH has to match the backend's (app/main.py): the HTML requests its assets
// by absolute path, so a bundle built for /app and served at /wiki cannot find its own
// JavaScript.
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

// The backend serves these from fixed paths, so they cannot carry a hash in their names
// like Vite's assets do; each carries its content hash in the query instead. A browser
// with the old sheet cached and the new bundle paints new markup with old rules, which is
// a broken screen and not a stale style — and a favicon without a version outlives any
// brand change, because browsers keep favicons in a cache of their own.
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

// index.html references the backend's CSS, favicon and manifest by absolute path, and
// Vite leaves absolute URLs alone, so the substitution happens here. It runs at 'pre'
// because Vite decodes hrefs as URIs while parsing, and an unsubstituted placeholder is
// not a valid URI.
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
