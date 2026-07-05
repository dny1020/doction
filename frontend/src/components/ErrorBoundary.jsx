import React from 'react'

// Barrera de errores de render: sin ella, cualquier excepción al pintar deja la
// pantalla en blanco. Va por fuera de los providers, así que el texto es fijo
// (inglés, el idioma por defecto) — aquí no hay i18n del que depender.
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
