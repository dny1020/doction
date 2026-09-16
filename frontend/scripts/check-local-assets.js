// Fails if the built bundle, its HTML or the design system's CSS asks an external host
// for anything.
//
// doction is served on LANs, over VPNs and sometimes on networks with no route out, where
// a request to fonts.gstatic.com fails exactly where it is most used. This exists so the
// next dependency reaching for a CDN breaks the build rather than a deployment.
//
// Runs inside `npm run check`, after `vite build`.

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, extname } from 'node:path'

const ROOTS = ['../app/static/app', '../app/static/style.css']
const SCAN = new Set(['.html', '.js', '.css'])

// An external host in any form a browser would follow: https://x, http://x, //x.
const EXTERNAL = /(?:https?:)?\/\/(?!\/)([a-z0-9.-]+\.[a-z]{2,})/gi

// Hosts that appear in the bundle but that no browser will request. Each entry says why:
// the list only grows with a reason.
const ALLOWED = new Map([
  ['www.w3.org', 'SVG XML namespaces (xmlns), not downloads'],
  ['reactjs.org', 'a URL inside the text of React errors'],
  ['react.dev', 'the same, in newer versions'],
  ['localhost', 'the deployment itself'],
  ['127.0.0.1', 'the deployment itself'],
])

function files(path) {
  if (statSync(path).isFile()) return [path]
  return readdirSync(path).flatMap((entry) => files(join(path, entry)))
}

const findings = []
for (const root of ROOTS) {
  for (const file of files(root)) {
    if (!SCAN.has(extname(file))) continue
    const text = readFileSync(file, 'utf8')
    for (const match of text.matchAll(EXTERNAL)) {
      const host = match[1].toLowerCase()
      if (ALLOWED.has(host)) continue
      // Reported either way: a comment should not carry a URL that looks loadable.
      const line = text.slice(0, match.index).split('\n').length
      findings.push(`${file}:${line}  ${host}`)
    }
  }
}

if (findings.length > 0) {
  console.error('External assets in the bundle. doction is served with no route out:\n')
  for (const finding of [...new Set(findings)]) console.error('  ' + finding)
  console.error('\nVendor them under app/static/vendor/ and point the code at the local copy.')
  process.exit(1)
}

console.log('assets: all local')
