import { Link } from 'react-router-dom'

// Un estado vacío dice qué está vacío y, cuando hay una acción que lo llena,
// ofrece esa y ninguna más. No se usa para lo que es opcional: una página sin
// subpáginas no está vacía, simplemente no tiene subpáginas, y ahí lo correcto es
// no pintar la sección.
export default function EmptyState({ title, hint, actionLabel, actionTo }) {
  return (
    <div className="placeholder">
      <h1>{title}</h1>
      {hint && <p className="muted">{hint}</p>}
      {actionLabel && actionTo && (
        <Link className="btn btn-primary" to={actionTo}>
          {actionLabel}
        </Link>
      )}
    </div>
  )
}
