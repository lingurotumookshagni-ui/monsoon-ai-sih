/* Offline fallback dataset.

   Used ONLY when the FastAPI backend cannot be reached, so the dashboard can
   still be demonstrated. Everything here is generated in the browser from a
   fixed seed and is labelled "DEMO DATA" in the interface. It is not a
   forecast, not real weather data, and the "AI corrected" column here comes
   from a simple heuristic rather than the trained models - the trained models
   live in the backend.

   The verification numbers below are *computed* from this generated sample
   with the same score definitions as the backend, so no improvement figure is
   hard-coded anywhere. */

import {
  CATEGORY_ORDER,
  REGIME_DESCRIPTIONS,
  REGIME_LABELS,
  REGIME_ORDER,
} from './constants'

const DISTRICTS = [
  ['Kasaragod', 'Kerala', 12.5, 74.99, 20, 5],
  ['Kozhikode', 'Kerala', 11.25, 75.78, 10, 3],
  ['Wayanad', 'Kerala', 11.69, 76.13, 780, 55],
  ['Idukki', 'Kerala', 9.85, 76.97, 1100, 75],
  ['Ernakulam', 'Kerala', 9.98, 76.28, 8, 5],
  ['Thiruvananthapuram', 'Kerala', 8.52, 76.94, 10, 4],
  ['Chennai', 'Tamil Nadu', 13.08, 80.27, 7, 2],
  ['Nilgiris', 'Tamil Nadu', 11.41, 76.7, 2200, 80],
  ['Coimbatore', 'Tamil Nadu', 11.02, 76.96, 420, 95],
  ['Udupi', 'Karnataka', 13.34, 74.75, 25, 4],
  ['Kodagu', 'Karnataka', 12.42, 75.74, 1150, 80],
  ['Bengaluru Urban', 'Karnataka', 12.97, 77.59, 910, 180],
  ['Mumbai Suburban', 'Maharashtra', 19.13, 72.9, 14, 3],
  ['Ratnagiri', 'Maharashtra', 16.99, 73.31, 25, 4],
  ['Pune', 'Maharashtra', 18.52, 73.86, 560, 90],
  ['Nagpur', 'Maharashtra', 21.15, 79.09, 310, 620],
  ['Puri', 'Odisha', 19.81, 85.83, 6, 3],
  ['Khordha', 'Odisha', 20.18, 85.62, 45, 35],
  ['Kolkata', 'West Bengal', 22.57, 88.36, 9, 60],
  ['Darjeeling', 'West Bengal', 27.04, 88.26, 2050, 550],
  ['Kamrup Metropolitan', 'Assam', 26.14, 91.74, 55, 520],
  ['Dibrugarh', 'Assam', 27.47, 94.91, 105, 720],
  ['Visakhapatnam', 'Andhra Pradesh', 17.69, 83.22, 45, 4],
  ['Hyderabad', 'Telangana', 17.39, 78.49, 540, 290],
  ['Surat', 'Gujarat', 21.17, 72.83, 13, 20],
  ['Jaipur', 'Rajasthan', 26.91, 75.79, 430, 560],
  ['Dehradun', 'Uttarakhand', 30.32, 78.03, 640, 850],
  ['Shimla', 'Himachal Pradesh', 31.1, 77.17, 2200, 900],
]

// Same structure as the backend error model, simplified.
const REGIME_STATS = {
  ACTIVE_MONSOON: { base: 42, mult: 0.86, dry: 0.05, rh: 88, t: 26, p: 998, ws: 11 },
  BREAK_MONSOON: { base: 3, mult: 1.15, dry: 0.55, rh: 60, t: 33.5, p: 1006, ws: 4 },
  MONSOON_DEPRESSION: { base: 95, mult: 0.7, dry: 0.02, rh: 93, t: 25, p: 991, ws: 16 },
  COASTAL_RAINFALL: { base: 52, mult: 0.74, dry: 0.07, rh: 86, t: 27.8, p: 1002, ws: 9 },
  OROGRAPHIC_RAINFALL: { base: 58, mult: 0.55, dry: 0.06, rh: 90, t: 21.5, p: 1000, ws: 8.5 },
  WESTERN_DISTURBANCE: { base: 14, mult: 0.88, dry: 0.25, rh: 70, t: 12.5, p: 1012, ws: 7 },
  NORMAL_MONSOON: { base: 13, mult: 0.95, dry: 0.3, rh: 76, t: 29, p: 1004, ws: 6 },
}

const CORRECTION_FACTORS = {
  ACTIVE_MONSOON: 1.14,
  BREAK_MONSOON: 0.8,
  MONSOON_DEPRESSION: 1.38,
  COASTAL_RAINFALL: 1.32,
  OROGRAPHIC_RAINFALL: 1.72,
  WESTERN_DISTURBANCE: 1.1,
  NORMAL_MONSOON: 1.04,
}

const THRESHOLDS = [64.5, 115.6, 204.5]

/* deterministic pseudo-random generator (mulberry32) */
function rng(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const normal = (r) => {
  const u = Math.max(r(), 1e-9)
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r())
}
const exponential = (r, mean) => -mean * Math.log(Math.max(r(), 1e-9))

function pickRegime(r, [, , , , elevation, coast], month) {
  const coastal = Math.exp(-coast / 45)
  const oro = Math.min(Math.max((elevation - 350) / 900, 0), 2.2)
  const monsoon = month >= 6 && month <= 9 ? 1 : 0
  const weights = {
    ACTIVE_MONSOON: 1.4 * monsoon,
    BREAK_MONSOON: 1.0 * monsoon,
    MONSOON_DEPRESSION: 0.5 * monsoon,
    COASTAL_RAINFALL: 0.4 + 2.2 * coastal,
    OROGRAPHIC_RAINFALL: 0.1 + oro,
    WESTERN_DISTURBANCE: monsoon ? 0.05 : 0.9,
    NORMAL_MONSOON: 0.9,
  }
  const total = Object.values(weights).reduce((a, b) => a + b, 0)
  let u = r() * total
  for (const key of REGIME_ORDER) {
    u -= weights[key]
    if (u <= 0) return key
  }
  return 'NORMAL_MONSOON'
}

function category(v) {
  if (v < 15) return 'LIGHT'
  if (v <= 64.4) return 'MODERATE'
  if (v <= 115.5) return 'HEAVY'
  if (v <= 204.4) return 'VERY_HEAVY'
  return 'EXTREMELY_HEAVY'
}

/* Same public condition bands as the backend (app/config.py PUBLIC_CONDITIONS). */
function publicCondition(v) {
  if (v >= 115.6) return 'VERY_HEAVY'
  if (v >= 64.5) return 'HEAVY'
  if (v >= 15) return 'MODERATE'
  if (v >= 5) return 'NORMAL'
  return 'LOW'
}

function riskBand(p) {
  if (p >= 0.7) return 'VERY_HIGH'
  if (p >= 0.45) return 'HIGH'
  if (p >= 0.2) return 'MODERATE'
  return 'LOW'
}

const logistic = (x) => 1 / (1 + Math.exp(-x))

function buildRows(days = 30) {
  const r = rng(20240715)
  const month = 7
  const rows = []
  for (let d = 0; d < days; d += 1) {
    for (const district of DISTRICTS) {
      const [name, state, lat, lon, elevation, coast] = district
      const regime = pickRegime(r, district, month)
      const s = REGIME_STATS[regime]
      const coastal = Math.exp(-coast / 60)
      const gain = 1 + Math.min(elevation, 2600) / 1150
      const humidity = Math.min(100, Math.max(25, s.rh + normal(r) * 4))
      const wet = r() > s.dry
      const meanMm = s.base * gain * (1 + 0.55 * coastal)
      const observed = wet ? Math.min(650, exponential(r, meanMm)) : 0
      const noise = Math.exp(normal(r) * 0.3)
      const raw = Math.max(0, observed * s.mult * noise + 2 + normal(r) * 3)
      const corrected = Math.max(0, raw * CORRECTION_FACTORS[regime] - 1)
      const pHeavy = logistic((corrected - 64.5) / 24)
      const pVery = Math.min(pHeavy, logistic((corrected - 115.6) / 42))
      rows.push({
        day: d,
        district: name,
        state,
        lat,
        lon,
        elevation,
        distance_from_coast: coast,
        regime,
        regime_confidence: Math.round((0.62 + r() * 0.34) * 1000) / 1000,
        humidity: Math.round(humidity * 10) / 10,
        temperature: Math.round((s.t - 0.006 * elevation + normal(r) * 1.5) * 10) / 10,
        pressure: Math.round((s.p - 0.11 * elevation) * 10) / 10,
        wind_speed: Math.round(Math.max(0.5, s.ws + normal(r) * 2) * 10) / 10,
        raw_nwp_mm: Math.round(raw * 10) / 10,
        corrected_mm: Math.round(corrected * 10) / 10,
        correction_mm: Math.round((corrected - raw) * 10) / 10,
        observed_rainfall_mm: Math.round(observed * 10) / 10,
        heavy_probability: Math.round(pHeavy * 1000) / 1000,
        very_heavy_probability: Math.round(pVery * 1000) / 1000,
        category: category(corrected),
        condition: publicCondition(corrected),
        raw_category: category(raw),
        risk_band: riskBand(pHeavy),
      })
    }
  }
  return rows
}

/* -------------------------------------------------- verification in JS
   Same formulas as backend/app/services/verification.py. */
const safeDiv = (a, b) => (b === 0 ? null : a / b)
const round = (v, n = 4) => (v === null || !Number.isFinite(v) ? null : Number(v.toFixed(n)))

function continuous(rows, col) {
  const n = rows.length
  if (!n) return { rmse: null, mae: null, bias: null, n: 0 }
  let se = 0
  let ae = 0
  let bias = 0
  rows.forEach((row) => {
    const e = row[col] - row.observed_rainfall_mm
    se += e * e
    ae += Math.abs(e)
    bias += e
  })
  return { rmse: round(Math.sqrt(se / n), 3), mae: round(ae / n, 3), bias: round(bias / n, 3), n }
}

function categorical(rows, col, threshold) {
  let hits = 0
  let fa = 0
  let misses = 0
  let cn = 0
  rows.forEach((row) => {
    const f = row[col] >= threshold
    const o = row.observed_rainfall_mm >= threshold
    if (f && o) hits += 1
    else if (f && !o) fa += 1
    else if (!f && o) misses += 1
    else cn += 1
  })
  const total = hits + fa + misses + cn
  const hitsRandom = total ? ((hits + misses) * (hits + fa)) / total : 0
  return {
    threshold_mm: threshold,
    hits,
    misses,
    false_alarms: fa,
    correct_negatives: cn,
    pod: round(safeDiv(hits, hits + misses)),
    far: round(safeDiv(fa, hits + fa)),
    csi: round(safeDiv(hits, hits + misses + fa)),
    ets: round(safeDiv(hits - hitsRandom, hits + misses + fa - hitsRandom)),
    observed_events: hits + misses,
  }
}

function haversine(a, b) {
  const toRad = (x) => (x * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLon = toRad(b.lon - a.lon)
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(Math.min(1, h)))
}

/* Simplified district-neighbourhood Fractions Skill Score (prototype). */
function fss(rows, col, threshold, radiusKm = 150) {
  const byDay = new Map()
  rows.forEach((row) => {
    if (!byDay.has(row.day)) byDay.set(row.day, [])
    byDay.get(row.day).push(row)
  })
  const mses = []
  const refs = []
  byDay.forEach((day) => {
    if (day.length < 2) return
    const pf = []
    const po = []
    day.forEach((a) => {
      let f = 0
      let o = 0
      let count = 0
      day.forEach((b) => {
        if (haversine(a, b) <= radiusKm) {
          count += 1
          if (b[col] >= threshold) f += 1
          if (b.observed_rainfall_mm >= threshold) o += 1
        }
      })
      pf.push(f / Math.max(count, 1))
      po.push(o / Math.max(count, 1))
    })
    const n = pf.length
    let mse = 0
    let ref = 0
    for (let i = 0; i < n; i += 1) {
      mse += (pf[i] - po[i]) ** 2
      ref += pf[i] ** 2 + po[i] ** 2
    }
    mses.push(mse / n)
    refs.push(ref / n)
  })
  if (!mses.length) return null
  const mse = mses.reduce((a, b) => a + b, 0) / mses.length
  const ref = refs.reduce((a, b) => a + b, 0) / refs.length
  return ref <= 1e-12 ? null : round(1 - mse / ref)
}

function evaluate(rows, col) {
  const block = { ...continuous(rows, col) }
  const byThreshold = {}
  THRESHOLDS.forEach((t) => {
    byThreshold[String(t)] = { ...categorical(rows, col, t), fss: fss(rows, col, t) }
  })
  const primary = byThreshold[String(THRESHOLDS[0])]
  return {
    ...block,
    pod: primary.pod,
    far: primary.far,
    csi: primary.csi,
    ets: primary.ets,
    fss: primary.fss,
    primary_threshold_mm: THRESHOLDS[0],
    by_threshold: byThreshold,
  }
}

function improvement(raw, ai) {
  const out = {}
  const drop = (k) =>
    raw[k] ? Number((((raw[k] - ai[k]) / raw[k]) * 100).toFixed(2)) : null
  const rise = (k) =>
    raw[k] ? Number((((ai[k] - raw[k]) / Math.abs(raw[k])) * 100).toFixed(2)) : null
  out.rmse_reduction_pct = drop('rmse')
  out.mae_reduction_pct = drop('mae')
  out.far_reduction_pct = drop('far')
  out.csi_change_pct = rise('csi')
  out.pod_change_pct = rise('pod')
  out.ets_change_pct = rise('ets')
  out.fss_change_pct = rise('fss')
  return out
}

/* ------------------------------------------------------------- bundle */
export function buildFallbackBundle() {
  const rows = buildRows(30)
  const snapshot = rows.filter((row) => row.day === 0).map(({ day, observed_rainfall_mm, ...rest }) => rest)

  const heavyAlerts = snapshot.filter((d) => ['HEAVY', 'VERY_HEAVY', 'EXTREMELY_HEAVY'].includes(d.category)).length
  const veryHeavy = snapshot.filter((d) => ['VERY_HEAVY', 'EXTREMELY_HEAVY'].includes(d.category)).length
  const mean = (arr, key) => arr.reduce((a, b) => a + b[key], 0) / (arr.length || 1)

  const categories = {}
  CATEGORY_ORDER.forEach((c) => {
    const n = snapshot.filter((d) => d.category === c).length
    if (n) categories[c] = n
  })

  const regimes = REGIME_ORDER.map((regime) => {
    const g = snapshot.filter((d) => d.regime === regime)
    return {
      regime,
      districts: g.length,
      avg_raw_mm: Number(mean(g, 'raw_nwp_mm').toFixed(2)),
      avg_corrected_mm: Number(mean(g, 'corrected_mm').toFixed(2)),
      avg_correction_mm: Number(mean(g, 'correction_mm').toFixed(2)),
      avg_confidence: Number(mean(g, 'regime_confidence').toFixed(3)),
      avg_heavy_probability: Number(mean(g, 'heavy_probability').toFixed(3)),
      heavy_alerts: g.filter((d) => ['HEAVY', 'VERY_HEAVY', 'EXTREMELY_HEAVY'].includes(d.category)).length,
      states: [...new Set(g.map((d) => d.state))],
    }
  }).filter((entry) => entry.districts > 0)

  const rawBlock = evaluate(rows, 'raw_nwp_mm')
  const aiBlock = evaluate(rows, 'corrected_mm')
  const verification = {
    sample_size: rows.length,
    thresholds_mm: THRESHOLDS,
    raw_nwp: rawBlock,
    ai_corrected: aiBlock,
    improvement: improvement(rawBlock, aiBlock),
    dataset: 'BROWSER_FALLBACK_DEMO',
    source: 'demo',
    districts: DISTRICTS.length,
    notes: [
      'The purpose of this comparison is to determine whether regime-aware post-processing improves forecast skill relative to the raw NWP forecast.',
      'Offline fallback: scores are computed in the browser from generated demo data using a heuristic correction, not the trained models. Start the backend for model-based results.',
      'FSS is a simplified district-neighbourhood prototype implementation.',
    ],
  }

  const kpis = {
    districts: snapshot.length,
    states: new Set(snapshot.map((d) => d.state)).size,
    heavy_alerts: heavyAlerts,
    very_heavy_alerts: veryHeavy,
    active_regimes: new Set(snapshot.map((d) => d.regime)).size,
    mean_raw_mm: Number(mean(snapshot, 'raw_nwp_mm').toFixed(2)),
    mean_corrected_mm: Number(mean(snapshot, 'corrected_mm').toFixed(2)),
    mean_correction_mm: Number(mean(snapshot, 'correction_mm').toFixed(2)),
    max_corrected_mm: Number(Math.max(...snapshot.map((d) => d.corrected_mm)).toFixed(2)),
    top_district: [...snapshot].sort((a, b) => b.corrected_mm - a.corrected_mm)[0].district,
    demo_mode_banner: 'DEMO DATA - offline fallback, backend unavailable',
  }

  const overview = {
    banner: 'DEMO DATA - offline fallback, backend unavailable',
    source: 'demo',
    forecast_date: null,
    kpis: { ...kpis, conditions: snapshot.reduce((acc, d) => {
      acc[d.condition] = (acc[d.condition] || 0) + 1
      return acc
    }, {}) },
    verification: {
      available: true,
      raw_rmse: rawBlock.rmse,
      ai_rmse: aiBlock.rmse,
      raw_mae: rawBlock.mae,
      ai_mae: aiBlock.mae,
      rmse_reduction_pct: verification.improvement.rmse_reduction_pct,
      sample_size: rows.length,
    },
    regimes,
    categories,
    top_districts: [...snapshot].sort((a, b) => b.corrected_mm - a.corrected_mm).slice(0, 10),
    map_points: snapshot,
  }

  const regimeCatalog = {
    regimes: REGIME_ORDER.map((regime) => ({
      regime,
      label: REGIME_LABELS[regime],
      description: REGIME_DESCRIPTIONS[regime],
      current: regimes.find((x) => x.regime === regime) || {
        districts: 0,
        avg_raw_mm: 0,
        avg_corrected_mm: 0,
        avg_correction_mm: 0,
        avg_confidence: 0,
        avg_heavy_probability: 0,
        heavy_alerts: 0,
        states: [],
      },
    })),
    note: 'Offline fallback catalogue. Regime classes are project-defined prototype classes.',
  }

  return { overview, verification, regimeCatalog, rows: snapshot }
}
