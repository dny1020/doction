import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// La SPA vive bajo /app (mismo path en dev y en producción).
// - build: genera el bundle en app/static/app/, con las URLs de assets bajo /app/.
// - dev: el servidor de Vite proxya la API y los archivos del backend a FastAPI (:8000),
//   para que /api, /uploads y /static/style.css funcionen igual que en producción.
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  build: {
    outDir: '../app/static/app',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/uploads': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
    },
  },
})
