// Un borrador vive en el navegador de quien escribe, no en el servidor.
//
// El editor guarda con un botón y avisa al salir con cambios sin guardar, pero eso
// cubre irse, no que el servidor se vaya: si la Pi deja de responder a mitad de un
// párrafo, el texto solo existe en el estado de React y una recarga se lo lleva.
//
// No se autoguarda contra la API a propósito: cada guardado del servidor es un
// commit de git, y autoguardar convertiría el historial de una página en un commit
// por pausa al teclear. El borrador es local y el historial sigue teniendo una
// versión por vez que alguien decide guardar.
//
// La clave lleva workspace y slug: dos páginas a medio escribir no se pisan.

const PREFIX = 'doction:draft:'

function key(ws, slug) {
  return PREFIX + ws + ':' + (slug || 'new')
}

export function readDraft(ws, slug) {
  try {
    const raw = localStorage.getItem(key(ws, slug))
    return raw ? JSON.parse(raw) : null
  } catch {
    // Almacenamiento bloqueado (ventana privada) o contenido corrupto: no hay
    // borrador, que es exactamente lo que había antes de todo esto.
    return null
  }
}

export function writeDraft(ws, slug, draft) {
  try {
    localStorage.setItem(key(ws, slug), JSON.stringify(draft))
  } catch {
    // Bloqueado o lleno. Se sigue editando, solo que sin red de seguridad: no es
    // un error que interrumpa a nadie.
  }
}

export function clearDraft(ws, slug) {
  try {
    localStorage.removeItem(key(ws, slug))
  } catch {
    // idem
  }
}
