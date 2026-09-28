import { useT } from '../i18n'

/* Small always-visible status indicator required by the LIVE mode spec:

     LIVE ●          Source: Open-Meteo    Updated: 10:42 AM
     OFFLINE ●       Live data unavailable   [Retry]

   This reflects the live PROVIDER's reachability (GET /api/live/status),
   independent of which data source the dashboard is currently displaying -
   a judge can be looking at Demo mode and still see whether live is up. */

function formatTime(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return null
  }
}

export default function LiveStatusBadge({ status, checking, onRetry }) {
  const t = useT()

  if (checking && !status) {
    return (
      <span className="chip">
        <i className="dot" aria-hidden="true" />
        {t('common.loading')}
      </span>
    )
  }

  if (!status || !status.reachable) {
    return (
      <span className="live-status">
        <span className="chip offline">
          <i className="dot" aria-hidden="true" />
          {t('live.offline')}
        </span>
        <button className="btn" onClick={onRetry} disabled={checking}>
          {t('common.retry')}
        </button>
      </span>
    )
  }

  const updated = formatTime(status.sample_fetched_at)
  return (
    <span className="live-status">
      <span className="chip online">
        <i className="dot" aria-hidden="true" />
        {t('live.live')}
      </span>
      <span className="faint small live-status-meta">
        {t('live.source')}: {status.source}
        {updated ? ` · ${t('live.updated')}: ${updated}` : ''}
      </span>
    </span>
  )
}
