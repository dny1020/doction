// Minimal fetch wrapper for the FastAPI backend: always sends the session cookie, speaks
// JSON, and throws an Error carrying the backend's `detail` and `error.status`.

// The active workspace travels on every request as ?ws=<slug>, not session state, so tabs
// in different workspaces do not collide. Set here so no call can forget it.
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
    // `signal` cancels when the caller is gone — navigating away mid-load, or typing a
    // new search — so a slow response cannot paint over the newer view.
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
    // Cancelling is not a failure; it propagates as-is so callers can tell it apart.
    if (cause && cause.name === 'AbortError') throw cause
    // fetch only rejects when the request never left or never came back; a 500 resolves.
    // Callers treat them differently: a server error is shown, an outage is waited out.
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

// A cancelled request is not an error to show; any `.catch` that paints must ask first.
export function isAbort(error) {
  return Boolean(error) && error.name === 'AbortError'
}
