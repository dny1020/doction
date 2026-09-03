import { defineConfig } from 'vitest/config'

// jsdom porque DOMPurify sanea contra un DOM real: sin él no hay nada que sanear.
// Los tests viven junto al módulo que prueban (src/*.test.js) — son pocos y todos
// del renderer de markdown, que es el único límite de seguridad del cliente.
export default defineConfig({
  test: { environment: 'jsdom', include: ['src/**/*.test.js'] },
})
