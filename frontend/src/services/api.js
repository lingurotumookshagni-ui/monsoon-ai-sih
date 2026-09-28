/* MonsoonAI API client.
   Plain fetch, no extra dependency. Every call has a timeout so the dashboard
   can fall back to local demo data instead of hanging when the backend is down. */

const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

export const API_BASE = BASE

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request(path, { method = 'GET', body, params, timeout = 15000, isForm } = {}) {
  const url = new URL(BASE + path)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    })
  }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const res = await fetch(url.toString(), {
      method,
      signal: controller.signal,
      headers: isForm ? undefined : body ? { 'Content-Type': 'application/json' } : undefined,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    })
    const text = await res.text()
    const payload = text ? safeJson(text) : null
    if (!res.ok) {
      throw new ApiError(errorMessage(payload, res.status), res.status, payload?.detail)
    }
    return payload
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err.name === 'AbortError') throw new ApiError('The request timed out.', 0)
    throw new ApiError('Backend unavailable', 0)
  } finally {
    clearTimeout(timer)
  }
}

function safeJson(text) {
  try {
    return JSON.parse(text)
  } catch {
    return { detail: text }
  }
}

function errorMessage(payload, status) {
  const d = payload?.detail
  if (typeof d === 'string') return d
  if (d?.message) return [d.message, ...(d.errors || [])].join(' ')
  if (Array.isArray(d) && d[0]?.msg) return d.map((x) => `${x.loc?.slice(-1)}: ${x.msg}`).join('; ')
  return `Request failed (HTTP ${status}).`
}

export const api = {
  health: () => request('/api/health', { timeout: 6000 }),
  config: () => request('/api/config'),
  overview: (source = 'live') => request('/api/overview', { params: { source }, timeout: 30000 }),
  forecast: (params = {}) => request('/api/forecast', { params, timeout: 30000 }),
  districts: () => request('/api/districts'),
  districtDetail: (name, params = {}) =>
    request(`/api/districts/${encodeURIComponent(name)}`, { params }),
  process: (params = {}) => request('/api/process', { method: 'POST', params, timeout: 60000 }),

  // LIVE mode
  liveStatus: () => request('/api/live/status', { timeout: 12000 }),
  liveRainfall: (district, refresh = false) =>
    request(`/api/live/rainfall/${encodeURIComponent(district)}`, {
      params: refresh ? { refresh: true } : {},
      timeout: 20000,
    }),
  liveRefresh: () => request('/api/live/refresh', { method: 'POST', timeout: 30000 }),
  regimes: (source = 'live') => request('/api/regimes', { params: { source } }),
  heavyRainfall: (params = {}) => request('/api/heavy-rainfall', { params }),
  verification: (params = {}) => request('/api/verification', { params, timeout: 25000 }),
  modelMetrics: () => request('/api/model-metrics'),
  predictRegime: (features) => request('/api/predict-regime', { method: 'POST', body: features }),
  postprocess: (features) => request('/api/postprocess', { method: 'POST', body: features }),
  heavyProbability: (features) =>
    request('/api/heavy-rainfall-probability', { method: 'POST', body: features }),
  uploadTemplate: () => request('/api/upload-data/template'),
  uploadStatus: () => request('/api/upload-data'),
  uploadCsv: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/upload-data', { method: 'POST', body: form, isForm: true, timeout: 40000 })
  },
  clearUpload: () => request('/api/upload-data', { method: 'DELETE' }),
}
