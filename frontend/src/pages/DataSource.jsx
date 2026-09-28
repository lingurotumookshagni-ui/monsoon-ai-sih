import UploadPanel from '../components/UploadPanel'
import LiveStatusBadge from '../components/LiveStatusBadge'
import { useT } from '../i18n'

/* Data source page: switch between LIVE (default), Demo/Test mode, and an
   uploaded CSV. Every page in the app reads whichever source is selected
   here - there is no separate "live dashboard" and "demo dashboard", it is
   the same product pointed at a different input. */
export default function DataSource({ source, onSourceChange, backendOnline, uploadMeta, liveStatus }) {
  const t = useT()

  return (
    <div className="grid page-enter">
      <div className="panel">
        <div className="panel-head">
          <h2>{t('nav.data')}</h2>
          <span className="panel-note">every page reads from the source selected here</span>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
          <button
            className={`btn${source === 'live' ? ' active' : ''}`}
            onClick={() => onSourceChange('live')}
          >
            {t('live.mode')} <span className="faint small">({t('common.default')})</span>
          </button>
          <button
            className={`btn${source === 'demo' ? ' active' : ''}`}
            onClick={() => onSourceChange('demo')}
          >
            {t('live.demoMode')}
          </button>
          <button
            className={`btn${source === 'uploaded' ? ' active' : ''}`}
            onClick={() => onSourceChange('uploaded')}
            disabled={!uploadMeta}
          >
            {t('live.uploadedMode')}{uploadMeta ? ` (${uploadMeta.rows_accepted} rows)` : ' (none yet)'}
          </button>
        </div>

        {source === 'live' ? (
          <div style={{ marginBottom: 10 }}>
            <LiveStatusBadge status={liveStatus} onRetry={() => onSourceChange('live')} />
          </div>
        ) : null}

        <p className="small dim" style={{ marginBottom: 0 }}>{t('live.defaultNote')}</p>
        <p className="small dim" style={{ marginBottom: 0, marginTop: 6 }}>
          {t('app.disclaimerShort')} Uploading a CSV runs your own rows through the same trained
          regime classifier, correction models and probability models used by live and demo mode.
        </p>
      </div>

      <UploadPanel source={source} onSourceChange={onSourceChange} backendOnline={backendOnline} />
    </div>
  )
}
