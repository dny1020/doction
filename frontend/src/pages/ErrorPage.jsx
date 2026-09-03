import { useRouteError } from 'react-router-dom'

// Fallo de la propia navegación: una ruta que revienta al pintarse, o un error que
// el router atrapa antes de que llegue a ninguna barrera nuestra. Sin esto se veía
// la pantalla de error por defecto de React Router, que enseña el stack.
//
// Sin i18n a propósito, igual que ErrorBoundary: esto puede dispararse antes o por
// debajo de los providers, y depender de uno de ellos aquí sería depender justo de
// lo que puede estar roto.
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
