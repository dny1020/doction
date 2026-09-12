// Dónde vive cada superficie del despliegue. Sale del entorno en tiempo de
// construcción y todo tiene por defecto lo de hoy, así que un despliegue que no
// configure nada no nota este archivo.
//
// Existe porque doction se autoaloja: quien lo monta detrás de su propio nginx no
// debería editar el código fuente para servirlo en /wiki o en la raíz. Aquí solo
// van rutas — nada de secretos: lo que entra en el bundle se publica a quien lo
// cargue.
//
// La ruta de /api no es configurable a propósito: la sirve este mismo backend y no
// hay despliegue que la mueva. Lo que sí varía es dónde se monta la SPA, dónde se
// sirven los estáticos y dónde responde MCP.

// El basename del router, sin barra final y vacío para la raíz. Lo sustituye vite
// (define) desde el mismo DOCTION_APP_PATH que fija el `base` del build.
export const APP_BASE = __DOCTION_APP_BASE__

export const MCP_PATH = __DOCTION_MCP_PATH__
