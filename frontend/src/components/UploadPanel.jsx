import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { mm } from '../services/constants'

/* CSV upload panel: validates on the backend, then lets the dashboard switch
   its active data source from the synthetic demo cycle to the uploaded file. */
export default function UploadPanel({ source, onSourceChange, backendOnline }) {
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [template, setTemplate] = useState(null)

  useEffect(() => {
    if (!backendOnline) return
    api
      .uploadTemplate()
      .then(setTemplate)
      .catch(() => setTemplate(null))
  }, [backendOnline])

  const upload = async () => {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const res = await api.uploadCsv(file)
      setResult(res)
      onSourceChange('uploaded')
    } catch (err) {
      setError(err.message)
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  const clear = async () => {
    setBusy(true)
    try {
      await api.clearUpload()
      setResult(null)
      setFile(null)
      setError(null)
      onSourceChange('live')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!backendOnline) {
    return (
      <div className="banner">
        <div>
          <strong>Upload needs the backend</strong>
          <div>
            Start the API with <span className="mono">uvicorn app.main:app --reload --port 8000</span>,
            then reload this page to upload a CSV.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="grid">
      <div className="upload-drop">
        <div style={{ marginBottom: 10 }}>
          Upload a CSV of forecasts to post-process with the trained models.
        </div>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null)
            setError(null)
          }}
        />
        <div style={{ marginTop: 12, display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="btn primary" onClick={upload} disabled={!file || busy}>
            {busy ? 'Processing' : 'Process file'}
          </button>
          <button className="btn" onClick={clear} disabled={busy}>
            Clear upload and return to live data
          </button>
        </div>
        <div className="faint small" style={{ marginTop: 8 }}>
          Files stay in the API process memory. Nothing is written to disk or to a database.
        </div>
      </div>

      {error ? (
        <div className="banner error" role="alert">
          <div>
            <strong>The file was not accepted</strong>
            <div>{error}</div>
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="panel">
          <div className="panel-head">
            <h3>{result.filename}</h3>
            <span className="chip online">
              <i className="dot" />
              {source === 'uploaded' ? 'active data source' : 'stored'}
            </span>
          </div>
          <div className="grid kpis">
            <div className="kpi">
              <div className="kpi-label">Rows accepted</div>
              <div className="kpi-value">{result.rows_accepted}</div>
              <div className="kpi-hint">of {result.rows_received} received</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">Heavy rain alerts</div>
              <div className="kpi-value">{result.kpis?.heavy_alerts ?? '-'}</div>
              <div className="kpi-hint">after correction</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">Mean correction</div>
              <div className="kpi-value">{mm(result.kpis?.mean_correction_mm)}<span className="kpi-unit">mm</span></div>
              <div className="kpi-hint">mean change vs raw NWP</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">Observations included</div>
              <div className="kpi-value">{result.has_observations ? 'yes' : 'no'}</div>
              <div className="kpi-hint">
                {result.has_observations ? 'verification available' : 'add observed_rainfall_mm to verify'}
              </div>
            </div>
          </div>
          {result.warnings?.length ? (
            <div style={{ marginTop: 12 }}>
              <h3>Validation notes</h3>
              <ul className="tight small dim">
                {result.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {result.verification ? (
            <div className="small dim" style={{ marginTop: 6 }}>
              Verification on your rows: RMSE {result.verification.raw_nwp.rmse} raw to{' '}
              {result.verification.ai_corrected.rmse} corrected. Open the Verification page for the
              full report.
            </div>
          ) : null}
        </div>
      ) : null}

      {template ? (
        <div className="panel">
          <div className="panel-head">
            <h3>Accepted CSV format</h3>
            <span className="panel-note">
              Maximum file size {Math.round(template.max_bytes / (1024 * 1024))} MB
            </span>
          </div>
          <p className="small dim">
            Required columns: <span className="mono">{template.required_columns.join(', ')}</span>.
            Optional columns are filled with climatological defaults when missing. Include{' '}
            <span className="mono">observed_rainfall_mm</span> to get verification scores for your own data.
          </p>
          <pre>{template.example_csv}</pre>
        </div>
      ) : null}
    </div>
  )
}
