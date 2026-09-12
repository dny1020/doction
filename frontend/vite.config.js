import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dónde se sirve cada cosa. Por defecto, exactamente lo de hoy: la SPA en /app y
// el backend en la raíz. Un despliegue que quiera otra cosa lo dice por entorno y
// no tocando este archivo — es autoalojable, y editar el código fuente para
// cambiar una ruta no es configurar.
//
// DOCTION_APP_PATH tiene que coincidir con el del backend (app/main.py): el HTML
// pide sus assets por ruta absoluta, así que un bundle construido para /app
// servido en /wiki no encuentra su propio JavaScript.
function path(name, fallback) {
  const value = process.env[name] ?? fallback
  if (!value.startsWith('/')) {
    throw new Error(`${name} debe empezar por "/" (recibido: "${value}")`)
  }
  return value.length > 1 ? value.replace(/\/$/, '') : value
}

const appPath = path('DOCTION_APP_PATH', '/app')
const staticPath = path('DOCTION_STATIC_PATH', '/static')
const mcpPath = path('DOCTION_MCP_PATH', '/api/mcp')

// El CSS lo sirve el backend desde una ruta fija, así que no puede llevar el hash
// en el nombre como los assets de Vite. Lleva el mismo hash de contenido en la
// consulta, calculado igual y en el mismo momento: un navegador con la hoja vieja
// cacheada y el bundle nuevo pinta el marcado nuevo con las reglas viejas, que es
// una pantalla rota y no un estilo desactualizado.
function styleHash() {
  try {
    return createHash('sha256')
      .update(readFileSync(new URL('../app/static/style.css', import.meta.url)))
      .digest('hex')
      .slice(0, 8)
  } catch {
    // En el stage `web` del Dockerfile el CSS se copia antes de construir, así que
    // esto solo salta en un árbol incompleto: sin hash se sigue sirviendo, igual
    // que antes de este cambio.
    return ''
  }
}

// index.html referencia el CSS, el favicon y el manifest del backend por ruta
// absoluta, y Vite no toca las URLs absolutas: la sustitución va aquí. Corre en
// 'pre' porque Vite decodifica los href como URI al parsear el HTML, y un
// marcador sin sustituir no es una URI válida.
const staticUrls = {
  name: 'doction-static-urls',
  transformIndexHtml: {
    order: 'pre',
    handler: (html) => {
      const hash = styleHash()
      return html
        .replaceAll('__STATIC__/style.css', staticPath + '/style.css' + (hash ? '?v=' + hash : ''))
        .replaceAll('__STATIC__', staticPath)
    },
  },
}

export default defineConfig({
  plugins: [react(), staticUrls],
  base: appPath === '/' ? '/' : appPath + '/',
  define: {
    __DOCTION_MCP_PATH__: JSON.stringify(mcpPath),
    // El basename del router, del mismo `appPath` que `base`. Va por define y no
    // leyendo import.meta.env.BASE_URL porque eso solo lo rellena el pipeline de
    // build: vitest no hereda el `base` de aquí, y fijarlo en su propia config
    // dejó de propagarse a BASE_URL. Un constante de construcción vale igual en
    // los dos y no depende de por dónde se resuelva.
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
