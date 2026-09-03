import { useEffect, useState } from 'react'

// Marcador de carga con la forma de lo que va a llegar. Antes cada vista ponía la
// palabra "Cargando…", que en la Pi sobre una VPN queda en pantalla el tiempo justo
// para leerla y no dice nada de lo que viene ni de si algo va mal.
//
// El retardo es la mitad del asunto: por debajo de él no se pinta nada, porque un
// esqueleto que aparece y desaparece en 80 ms se ve como un parpadeo y se lee como
// un fallo. Solo aparece cuando la espera ya se nota.
const DELAY = 250

function useVisibleAfterDelay(delay = DELAY) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), delay)
    return () => clearTimeout(timer)
  }, [delay])
  return visible
}

// Árbol lateral: filas a la altura y con el sangrado reales, para que al llegar el
// árbol de verdad nada se mueva de sitio.
export function TreeSkeleton({ rows = 7 }) {
  const visible = useVisibleAfterDelay()
  if (!visible) return null
  // Sangrado fijo y no aleatorio: un árbol que baila en cada carga llama la
  // atención justo cuando no hay nada que mirar.
  const levels = [0, 0, 1, 1, 2, 0, 1]
  return (
    <div className="skeleton-tree" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton-row" data-level={levels[i % levels.length]}>
          <span className="skeleton-bar" />
        </div>
      ))}
    </div>
  )
}

// Cuerpo del documento: un titular y unos párrafos al ancho de la columna de
// lectura.
export function DocumentSkeleton() {
  const visible = useVisibleAfterDelay()
  if (!visible) return null
  return (
    <div className="skeleton-doc" aria-hidden="true">
      <span className="skeleton-bar skeleton-bar--title" />
      <span className="skeleton-bar" />
      <span className="skeleton-bar" />
      <span className="skeleton-bar skeleton-bar--short" />
      <span className="skeleton-bar" />
      <span className="skeleton-bar skeleton-bar--short" />
    </div>
  )
}

// Filas de una lista (papelera, bandeja, ajustes).
export function ListSkeleton({ rows = 4 }) {
  const visible = useVisibleAfterDelay()
  if (!visible) return null
  return (
    <div className="skeleton-list" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <span key={i} className="skeleton-bar" />
      ))}
    </div>
  )
}
