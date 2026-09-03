// Envoltorio mínimo sobre fetch para hablar con la API de FastAPI.
//
// - Siempre manda la cookie de sesión (credentials: 'same-origin').
// - Manda y recibe JSON.
// - Si la respuesta no es OK, lanza un Error con el mensaje del backend
//   (el campo `detail`) y el código en `error.status`.

// El workspace activo viaja en cada petición como ?ws=<slug>, no en el estado de
// la sesión. Así dos pestañas abiertas en workspaces distintos no se pisan, y un
// enlace a una página abre esa página y no la del workspace que hubiera activo.
// Lo fija el shell desde la URL antes de que ningún hijo pida nada: aquí porque
// olvidarlo en una sola llamada significa leer del workspace equivocado, y hay
// una docena de llamadas.
let workspace = null

export function setWorkspace(slug) {
  workspace = slug || null
}

export function withWorkspace(url) {
  if (!workspace) return url
  return url + (url.includes('?') ? '&' : '?') + 'ws=' + encodeURIComponent(workspace)
}

async function request(method, url, body, signal) {
  const options = {
    method: method,
    credentials: 'same-origin',
    headers: {},
    // `signal` cancela la petición cuando quien la pidió ya no está: navegar a
    // otra página mientras carga la anterior, o teclear otra búsqueda. Sin esto
    // una respuesta lenta llegaba tarde y pintaba encima de la vista nueva.
    signal: signal,
  }
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(withWorkspace(url), options)
  } catch (cause) {
    // Cancelar no es un fallo: es que a nadie le interesa ya la respuesta. Se
    // propaga tal cual para que quien llama lo distinga y no pinte un error.
    if (cause && cause.name === 'AbortError') throw cause
    // fetch solo rechaza cuando la petición no llegó a salir o no volvió: servidor
    // caído, DNS, red. Un 500 sí resuelve. Se distinguen porque quien llama hace
    // cosas distintas: un error del servidor se enseña, una caída se espera.
    const offline = new Error('Network request failed')
    offline.offline = true
    throw offline
  }

  if (response.status === 204) {
    return null
  }

  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (!response.ok) {
    let message = 'Error ' + response.status
    if (data && data.detail) {
      message = data.detail
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }

  return data
}

export const api = {
  get: (url, signal) => request('GET', url, undefined, signal),
  post: (url, body) => request('POST', url, body),
  put: (url, body) => request('PUT', url, body),
  del: (url) => request('DELETE', url),
}

// Una petición cancelada no es un error que enseñar. Los `.catch` que pintan algo
// tienen que preguntar por esto antes.
export function isAbort(error) {
  return Boolean(error) && error.name === 'AbortError'
}
