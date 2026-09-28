/* Loading, error and empty states. Copy explains what happened and what to do. */

export function Loading({ label = 'Loading forecast data', rows = 3 }) {
  return (
    <div className="grid" aria-live="polite" aria-busy="true">
      <div className="dim small">{label}...</div>
      {Array.from({ length: rows }).map((_, i) => (
        <div className="skeleton" key={i} />
      ))}
    </div>
  )
}

export function ErrorState({ title = 'Backend unavailable', message, onRetry }) {
  return (
    <div className="banner error" role="alert">
      <div>
        <strong>{title}</strong>
        <div>{message}</div>
        {onRetry ? (
          <button className="btn" style={{ marginTop: 8 }} onClick={onRetry}>
            Try again
          </button>
        ) : null}
      </div>
    </div>
  )
}

export function EmptyState({ title, message, children }) {
  return (
    <div className="state-box">
      <strong>{title}</strong>
      <div className="small">{message}</div>
      {children}
    </div>
  )
}
