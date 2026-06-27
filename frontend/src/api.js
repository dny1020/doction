// Envoltorio mínimo sobre fetch para hablar con la API de FastAPI.
//
// - Siempre manda la cookie de sesión (credentials: 'same-origin').
// - Manda y recibe JSON.
// - Si la respuesta no es OK, lanza un Error con el mensaje del backend
//   (el campo `detail`) y el código en `error.status`.

async function request(method, url, body) {
  const options = {
    method: method,
    credentials: 'same-origin',
    headers: {},
  }
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  const response = await fetch(url, options)

  if (response.status === 204) {
    return null
  }

  let data = null
  try {
    data = await response.json()
  } catch (e) {
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
  get: (url) => request('GET', url),
  post: (url, body) => request('POST', url, body),
  put: (url, body) => request('PUT', url, body),
  del: (url) => request('DELETE', url),
}
