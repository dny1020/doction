import { defineConfig } from 'vitest/config'

// jsdom porque DOMPurify sanea contra un DOM real: sin él no hay nada que sanear.
// Los tests viven junto al módulo que prueban (src/*.test.js) — son pocos y todos
// del renderer de markdown, que es el único límite de seguridad del cliente.
//
// El `define` repite el de vite.config.js porque vitest no lo hereda, y config.js
// lo lee al importarse. Sin esto el suite entero cae con un ReferenceError en
// cuanto un módulo bajo prueba toca la configuración del despliegue. Va fijo al
// valor por defecto: lo que se prueba aquí no depende de dónde responda MCP.
export default defineConfig({
  // El mismo `base` que el build por defecto: los wikilinks salen como <a href>
  // dentro del documento y tienen que llevarlo, así que un entorno de test montado
  // en la raíz no probaría nada.
  base: '/app/',
  define: {
    __DOCTION_MCP_PATH__: JSON.stringify('/api/mcp'),
  },
  test: { environment: 'jsdom', include: ['src/**/*.test.js'] },
})
