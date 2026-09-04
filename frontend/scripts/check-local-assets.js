// Falla si el bundle construido, su HTML o el CSS del design system piden algo a
// un host externo.
//
// doction se sirve en LAN, en VPN y a veces en redes sin salida: una petición a
// fonts.gstatic.com falla justo donde más se usa. Hoy no hay ninguna —Inter,
// lucide, highlight.js y mermaid están todos autohospedados— y este script existe
// para que la próxima dependencia que estire la mano hacia un CDN rompa la
// construcción en vez de romper un despliegue sin internet.
//
// Corre dentro de `npm run check`, después de `vite build`.

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, extname } from 'node:path'

const ROOTS = ['../app/static/app', '../app/static/style.css']
const SCAN = new Set(['.html', '.js', '.css'])

// Un host externo escrito en cualquier forma que un navegador seguiría:
// https://x, http://x, //x.
const EXTERNAL = /(?:https?:)?\/\/(?!\/)([a-z0-9.-]+\.[a-z]{2,})/gi

// Hosts que aparecen en el bundle pero que ningún navegador va a pedir. Cada
// entrada dice por qué: la lista solo crece con una razón, y su motivo es dejar
// que el chequeo siga detectando el host nuevo de verdad.
const ALLOWED = new Map([
  ['www.w3.org', 'espacios de nombres XML de los SVG (xmlns), no son descargas'],
  ['reactjs.org', 'URL dentro del texto de los errores de React'],
  ['react.dev', 'idem, en las versiones nuevas'],
  ['localhost', 'el propio despliegue'],
  ['127.0.0.1', 'el propio despliegue'],
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
      // El contexto ayuda a distinguir un asset real de una URL en un comentario
      // o en un mensaje; se reporta igual, porque un comentario no debería
      // llevar una URL que parezca cargable.
      const line = text.slice(0, match.index).split('\n').length
      findings.push(`${file}:${line}  ${host}`)
    }
  }
}

if (findings.length > 0) {
  console.error('Assets externos en el bundle. doction se sirve sin salida a internet:\n')
  for (const finding of [...new Set(findings)]) console.error('  ' + finding)
  console.error('\nVendorízalos bajo app/static/vendor/ y apunta el código a la copia local.')
  process.exit(1)
}

console.log('assets: todo local')
