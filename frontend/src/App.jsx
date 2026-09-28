import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { API_BASE, api } from './services/api'
import { buildFallbackBundle } from './services/demoData'
import { I18nProvider, useI18n } from './i18n'
import { Loading } from './components/States'
import LanguageSelector from './components/LanguageSelector'
import LiveStatusBadge from './components/LiveStatusBadge'
import ToastHost from './components/Toast'
import DistrictModal from './components/DistrictModal'
import Home from './pages/Home'
import CheckDistrict from './pages/CheckDistrict'
import Alerts from './pages/Alerts'
import Forecast from './pages/Forecast'
import Regimes from './pages/Regimes'
import PostProcessing from './pages/PostProcessing'
import Verification from './pages/Verification'
import DataSource from './pages/DataSource'
import About from './pages/About'

const PAGES = [
  { id: 'home', key: 'nav.home', icon: '◉' },
  { id: 'check', key: 'nav.checkDistrict', icon: '🌧️' },
  { id: 'alerts', key: 'nav.alerts', icon: '⚠️' },
  { id: 'all', key: 'nav.allDistricts', icon: '▤' },
  { id: 'regimes', key: 'nav.regimes', icon: '◍' },
  { id: 'postprocessing', key: 'nav.postprocessing', icon: '⇄' },
  { id: 'metrics', key: 'nav.metrics', icon: '📊' },
  { id: 'data', key: 'nav.data', icon: '⇪' },
  { id: 'about', key: 'nav.about', icon: 'ℹ' },
]

/* Data-source truth table this shell enforces:

   source='live', provider reachable      -> real Open-Meteo forecast through
                                              the trained models, banner "LIVE"
   source='live', provider unreachable    -> NO data shown. An explicit
                                              "LIVE DATA UNAVAILABLE" state with
                                              retry and a manual switch to
                                              Demo/Test mode. Never silently
                                              substituted.
   source='demo'                          -> the backend's synthetic cycle.
   source='demo', backend itself down     -> only here, a browser-generated
                                              fallback is used, and it is
                                              labelled "DEMO DATA (offline
                                              fallback)" - still never "LIVE".
   source='uploaded'                      -> the user's CSV, unaffected by
                                              live/demo state. */
function Shell() {
  const { t } = useI18n()
  const [page, setPage] = useState('home')
  const [theme, setTheme] = useState('dark')
  const [source, setSource] = useState('live')
  const [menuOpen, setMenuOpen] = useState(false)

  const [health, setHealth] = useState(null)
  const [liveStatus, setLiveStatus] = useState(null)
  const [overview, setOverview] = useState(null)
  const [regimeCatalog, setRegimeCatalog] = useState(null)
  const [verification, setVerification] = useState(null)
  const [uploadMeta, setUploadMeta] = useState(null)
  const [selectedDistrict, setSelectedDistrict] = useState(null)

  const [loading, setLoading] = useState(true)
  const [checkingLive, setCheckingLive] = useState(false)
  const [backendUnreachable, setBackendUnreachable] = useState(false)
  const [liveUnavailable, setLiveUnavailable] = useState(false)
  const [liveUnavailableReason, setLiveUnavailableReason] = useState(null)
  const [usingOfflineFallback, setUsingOfflineFallback] = useState(false)
  const [verificationError, setVerificationError] = useState(null)
  const [refreshingLive, setRefreshingLive] = useState(false)

  const [toasts, setToasts] = useState([])
  const toastId = useRef(0)

  const pushToast = useCallback((message, tone) => {
    const id = (toastId.current += 1)
    setToasts((list) => [...list, { id, message, tone }])
    setTimeout(() => setToasts((list) => list.filter((x) => x.id !== id)), 4200)
  }, [])

  const dismissToast = useCallback((id) => {
    setToasts((list) => list.filter((x) => x.id !== id))
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  const refreshLiveStatus = useCallback(async () => {
    setCheckingLive(true)
    try {
      setLiveStatus(await api.liveStatus())
    } catch {
      setLiveStatus(null)
    } finally {
      setCheckingLive(false)
    }
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setVerificationError(null)
    setLiveUnavailable(false)
    setLiveUnavailableReason(null)
    setUsingOfflineFallback(false)

    try {
      const status = await api.health()
      setHealth(status)
      setBackendUnreachable(false)

      // The LIVE ● / OFFLINE ● badge reflects provider reachability
      // regardless of which source tab is active.
      refreshLiveStatus()

      try {
        const [ov, cat] = await Promise.all([api.overview(source), api.regimes(source)])
        setOverview(ov)
        setRegimeCatalog(cat)

        try {
          setVerification(await api.verification({ source }))
        } catch (err) {
          setVerification(null)
          setVerificationError(err.message)
        }
      } catch (err) {
        if (source === 'live' && err.status === 503) {
          // Backend is fine; the live provider itself could not be reached.
          // No fake numbers are substituted here.
          setLiveUnavailable(true)
          setLiveUnavailableReason(err.message)
          setOverview(null)
          setRegimeCatalog(null)
          setVerification(null)
        } else {
          throw err
        }
      }

      try {
        const up = await api.uploadStatus()
        setUploadMeta(up.has_upload ? up.meta : null)
      } catch {
        setUploadMeta(null)
      }
    } catch (err) {
      // The backend process itself could not be reached at all.
      setBackendUnreachable(true)
      setHealth(null)
      setLiveStatus(null)
      if (source === 'demo') {
        // Demo/testing mode is explicitly allowed to fall back to a
        // browser-generated sample so the UI can still be reviewed - always
        // labelled as offline demo data, never as live.
        const bundle = buildFallbackBundle()
        setOverview(bundle.overview)
        setRegimeCatalog(bundle.regimeCatalog)
        setVerification(bundle.verification)
        setUsingOfflineFallback(true)
      } else {
        setOverview(null)
        setRegimeCatalog(null)
        setVerification(null)
      }
    } finally {
      setLoading(false)
    }
  }, [source, refreshLiveStatus])

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source])

  useEffect(() => {
    if (usingOfflineFallback && !loading) pushToast(t('toast.offline'), 'warn')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usingOfflineFallback, loading])

  const rows = useMemo(() => overview?.map_points || [], [overview])

  const go = (next) => {
    setPage(next)
    setMenuOpen(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const switchSource = (next) => {
    setSource(next)
  }

  const doRefreshLive = useCallback(async () => {
    if (refreshingLive) return // never allow overlapping refresh requests
    setRefreshingLive(true)
    try {
      await api.liveRefresh()
      await load()
      await refreshLiveStatus()
      pushToast(t('live.refreshed'))
    } catch (err) {
      pushToast(`${t('live.refreshFailed')}: ${err.message}`, 'error')
    } finally {
      setRefreshingLive(false)
    }
  }, [refreshingLive, load, refreshLiveStatus, pushToast, t])

  const bannerClass = usingOfflineFallback || source === 'demo'
    ? 'demo-chip'
    : liveUnavailable
      ? 'chip offline'
      : 'chip online'

  const banner = usingOfflineFallback
    ? `${t('app.demoData')} (${t('common.backendOffline').toLowerCase()})`
    : source === 'demo'
      ? t('app.demoBanner')
      : source === 'uploaded'
        ? `${t('live.uploadedMode')}`
        : liveUnavailable
          ? t('live.offline')
          : t('live.live')

  const dataUnavailable = source === 'live' && liveUnavailable
  const nothingToShow = dataUnavailable || (backendUnreachable && source !== 'demo')

  const content = () => {
    if (loading) return <Loading label={t('common.loadingData')} />

    if (nothingToShow && ['check', 'alerts', 'all', 'regimes', 'postprocessing', 'metrics', 'home'].includes(page)) {
      return (
        <div className="live-banner">
          <div>
            <strong>
              {source === 'live' ? t('live.unavailableTitle') : t('live.backendUnreachableTitle')}
            </strong>
            <div>
              {source === 'live'
                ? (liveUnavailableReason || t('live.unavailableBody'))
                : t('live.backendUnreachableBody')}
            </div>
            <div className="actions">
              <button className="btn primary" onClick={load}>{t('common.retry')}</button>
              {source === 'live' ? (
                <button className="btn" onClick={() => switchSource('demo')}>
                  {t('live.tryDemo')}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      )
    }

    switch (page) {
      case 'check':
        return (
          <CheckDistrict
            rows={rows}
            source={source}
            backendOnline={!backendUnreachable}
            verification={verification}
            onToast={pushToast}
          />
        )
      case 'alerts':
        return <Alerts rows={rows} onSelectDistrict={setSelectedDistrict} onNavigate={go} />
      case 'all':
        return <Forecast rows={rows} onSelectDistrict={setSelectedDistrict} />
      case 'regimes':
        return <Regimes regimeCatalog={regimeCatalog} overview={overview} />
      case 'postprocessing':
        return (
          <PostProcessing
            rows={rows}
            source={source}
            backendOnline={!backendUnreachable}
            verification={verification}
            onToast={pushToast}
          />
        )
      case 'metrics':
        return <Verification verification={verification} error={verificationError} onRetry={load} />
      case 'data':
        return (
          <DataSource
            source={source}
            onSourceChange={(next) => {
              switchSource(next)
              go('home')
            }}
            backendOnline={!backendUnreachable}
            uploadMeta={uploadMeta}
            liveStatus={liveStatus}
          />
        )
      case 'about':
        return <About health={health} />
      default:
        return (
          <Home
            overview={overview}
            rows={rows}
            onNavigate={go}
            onSelectDistrict={setSelectedDistrict}
          />
        )
    }
  }

  return (
    <div className="app">
      <aside className={menuOpen ? 'rail open' : 'rail'}>
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">MA</div>
          <div>
            <div className="brand-name">MonsoonAI</div>
            <div className="brand-sub">{t('app.tagline')}</div>
          </div>
          {menuOpen ? (
            <button
              className="icon-btn"
              style={{ marginLeft: 'auto' }}
              onClick={() => setMenuOpen(false)}
              aria-label={t('nav.close')}
            >
              ×
            </button>
          ) : null}
        </div>

        <nav className="nav" aria-label={t('nav.sections')}>
          {PAGES.map((p) => (
            <button
              key={p.id}
              className={page === p.id ? 'active' : undefined}
              onClick={() => go(p.id)}
              aria-current={page === p.id ? 'page' : undefined}
            >
              <span className="nav-index" aria-hidden="true">{p.icon}</span>
              {t(p.key)}
            </button>
          ))}
        </nav>

        <div className="rail-foot">
          <button className="btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            {theme === 'dark' ? t('common.theme.dark') : t('common.theme.light')}
          </button>
          <div className="rail-note">{t('app.disclaimerShort')}</div>
        </div>
      </aside>

      <main className="main">
        <div className="mobile-bar">
          <button
            className="icon-btn"
            onClick={() => setMenuOpen(true)}
            aria-label={t('nav.menu')}
            aria-expanded={menuOpen}
          >
            ☰
          </button>
          <span className="brand-name">MonsoonAI</span>
          <LanguageSelector onChanged={() => pushToast(t('toast.languageChanged'))} />
        </div>

        <header className="topbar">
          <div className="topbar-left">
            <span className="topbar-title">
              {t(PAGES.find((p) => p.id === page)?.key || 'nav.home')}
            </span>
            <span className={bannerClass}>{banner}</span>
          </div>
          <div className="topbar-actions">
            <LiveStatusBadge
              status={liveStatus}
              checking={checkingLive}
              onRetry={refreshLiveStatus}
            />
            <span className="topbar-meta mono">{API_BASE}</span>
            <LanguageSelector onChanged={() => pushToast(t('toast.languageChanged'))} />
            {source === 'live' ? (
              <button className="btn primary" onClick={doRefreshLive} disabled={refreshingLive}>
                {refreshingLive ? `↻ ${t('live.refreshing')}` : `↻ ${t('live.refresh')}`}
              </button>
            ) : (
              <button className="btn" onClick={load} disabled={loading}>
                {loading ? t('common.refreshing') : t('common.refresh')}
              </button>
            )}
          </div>
        </header>

        <div className="content">
          {usingOfflineFallback ? (
            <div className="banner error">
              <div>
                <strong>{t('live.backendUnreachableTitle')}</strong>
                <div>{t('error.offlineFallback')}</div>
                <div className="mono small" style={{ marginTop: 6 }}>
                  uvicorn app.main:app --reload --port 8000
                </div>
                <button className="btn" style={{ marginTop: 8 }} onClick={load}>
                  {t('common.retry')}
                </button>
              </div>
            </div>
          ) : null}
          {content()}
        </div>
      </main>

      {selectedDistrict ? (
        <DistrictModal
          record={selectedDistrict}
          verification={verification}
          onClose={() => setSelectedDistrict(null)}
        />
      ) : null}

      <ToastHost toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

export default function App() {
  return (
    <I18nProvider>
      <Shell />
    </I18nProvider>
  )
}
