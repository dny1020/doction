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

// index.html referencia el CSS, el favicon y el manifest del backend por ruta
// absoluta, y Vite no toca las URLs absolutas: la sustitución va aquí. Corre en
// 'pre' porque Vite decodifica los href como URI al parsear el HTML, y un
// marcador sin sustituir no es una URI válida.
const staticUrls = {
  name: 'doction-static-urls',
  transformIndexHtml: {
    order: 'pre',
    handler: (html) => html.replaceAll('__STATIC__', staticPath),
  },
}

export default defineConfig({
  plugins: [react(), staticUrls],
  base: appPath === '/' ? '/' : appPath + '/',
  define: {
    __DOCTION_MCP_PATH__: JSON.stringify(mcpPath),
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
