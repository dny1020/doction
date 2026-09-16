import { Link } from 'react-router-dom'

// An empty state says what is empty and, when one action fills it, offers that one and
// no other. Not used for what is optional: a page without children is not empty, it just
// has no children, and there the right move is to not render the section.
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
