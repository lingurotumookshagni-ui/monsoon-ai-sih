/* Toast notifications. The host is rendered once by App; messages are pushed
   through the pushToast callback it hands down. */
export default function ToastHost({ toasts = [], onDismiss }) {
  if (!toasts.length) return null
  return (
    <div className="toast-host" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast${toast.tone ? ` ${toast.tone}` : ''}`}>
          <span aria-hidden="true">
            {toast.tone === 'error' ? '⚠' : toast.tone === 'warn' ? '!' : '✓'}
          </span>
          <span style={{ flex: 1 }}>{toast.message}</span>
          <button
            className="icon-btn"
            style={{ width: 24, height: 24 }}
            onClick={() => onDismiss(toast.id)}
            aria-label="Close"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
