import React from 'react'

// Render error boundary: without it any exception while painting leaves a blank screen.
// It sits outside the providers, so its text is fixed English — there is no i18n here to
// depend on.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    console.error('render error:', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div className="placeholder placeholder--error">
        <h1>Something went wrong</h1>
        <p className="muted">An unexpected error occurred. Reload the page to continue.</p>
        <button className="btn btn-primary" type="button" onClick={() => window.location.reload()}>
          Reload
        </button>
      </div>
    )
  }
}
