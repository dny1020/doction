import { useRouteError } from 'react-router-dom'

// A failure of navigation itself, caught by the router. No i18n, like ErrorBoundary: it
// can fire outside the providers.
export default function ErrorPage() {
  const error = useRouteError()
  console.error('route error:', error)
  return (
    <div className="placeholder placeholder--standalone placeholder--error">
      <h1>Something went wrong</h1>
      <p className="muted">This page could not be loaded. Reload to continue.</p>
      <button className="btn btn-primary" type="button" onClick={() => window.location.reload()}>
        Reload
      </button>
    </div>
  )
}
