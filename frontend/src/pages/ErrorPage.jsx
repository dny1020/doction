import { useRouteError } from 'react-router-dom'

// A failure of the navigation itself: a route that throws while painting, or an error the
// router catches before it reaches any boundary of ours. Without this, React Router shows
// its default screen with the stack.
//
// No i18n on purpose, like ErrorBoundary: this can fire before or below the providers, and
// depending on one here is depending on exactly what may be broken.
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
