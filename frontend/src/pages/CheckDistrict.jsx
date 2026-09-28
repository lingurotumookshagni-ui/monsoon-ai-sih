import { useMemo, useState } from 'react'
import DistrictResult from '../components/DistrictResult'
import { ErrorState } from '../components/States'
import { api } from '../services/api'
import { useT } from '../i18n'

/* "Check your district": the single most-used screen for a normal visitor.
   Select a district, optionally a date, press the button, get a plain answer.
   When the backend is reachable the lookup calls GET /api/districts/{name};
   offline it reads the same record from the locally generated demo rows. */
export default function CheckDistrict({ rows, source, backendOnline, verification, onToast }) {
  const t = useT()
  const [district, setDistrict] = useState('')
  const [date, setDate] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [regime, setRegime] = useState(null)
  const [error, setError] = useState(null)

  const districts = useMemo(
    () => [...rows].sort((a, b) => a.district.localeCompare(b.district)),
    [rows],
  )

  const check = async () => {
    if (!district) {
      setError(t('check.chooseFirst'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      if (backendOnline) {
        const params = { source }
        if (date && source === 'demo') params.date = date
        const res = await api.districtDetail(district, params)
        setResult(res.district)
        setRegime(res.regime)
      } else {
        const local = rows.find((r) => r.district === district)
        if (!local) throw new Error(t('error.notFound'))
        setResult(local)
        setRegime(null)
      }
      if (onToast) onToast(t('toast.districtLoaded'))
    } catch (err) {
      setResult(null)
      setError(err.message || t('error.generic'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid page-enter">
      <div className="panel">
        <div className="panel-head">
          <h2>{t('check.title')}</h2>
        </div>
        <p className="dim small">{t('check.subtitle')}</p>

        <div className="lookup">
          <div className="field">
            <label htmlFor="district-select">{t('check.district')}</label>
            <select
              id="district-select"
              value={district}
              onChange={(e) => {
                setDistrict(e.target.value)
                setError(null)
              }}
            >
              <option value="">{t('check.selectDistrict')}</option>
              {districts.map((d) => (
                <option key={`${d.district}-${d.state}`} value={d.district}>
                  {d.district} - {d.state}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="date-input">{t('check.date')}</label>
            <input
              id="date-input"
              type="date"
              value={date}
              disabled={source !== 'demo'}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <button className="btn primary" onClick={check} disabled={busy}>
            {busy ? t('check.checking') : t('check.submit')}
          </button>
        </div>
      </div>

      {error ? <ErrorState title={t('error.generic')} message={error} onRetry={check} /> : null}

      {result ? (
        <div>
          <DistrictResult record={result} regime={regime} verification={verification} />
          <button
            className="btn"
            style={{ marginTop: 12 }}
            onClick={() => {
              setResult(null)
              setDistrict('')
            }}
          >
            {t('check.again')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
