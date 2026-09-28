/* Display names, descriptions, colours and small formatters shared by the pages. */

export const REGIME_ORDER = [
  'ACTIVE_MONSOON',
  'BREAK_MONSOON',
  'MONSOON_DEPRESSION',
  'COASTAL_RAINFALL',
  'OROGRAPHIC_RAINFALL',
  'WESTERN_DISTURBANCE',
  'NORMAL_MONSOON',
]

export const REGIME_LABELS = {
  ACTIVE_MONSOON: 'Active monsoon',
  BREAK_MONSOON: 'Break monsoon',
  MONSOON_DEPRESSION: 'Monsoon low / depression',
  COASTAL_RAINFALL: 'Coastal rainfall',
  OROGRAPHIC_RAINFALL: 'Orographic rainfall',
  WESTERN_DISTURBANCE: 'Western disturbance',
  NORMAL_MONSOON: 'Normal monsoon',
}

export const REGIME_DESCRIPTIONS = {
  ACTIVE_MONSOON: 'Strong organised monsoon flow with widespread rain over central and peninsular India.',
  BREAK_MONSOON: 'Weak monsoon flow and a subsident dry spell, with suppressed rainfall over the plains.',
  MONSOON_DEPRESSION: 'Low-pressure system or depression, usually Bay of Bengal origin, with very heavy localised rain.',
  COASTAL_RAINFALL: 'Onshore-flow rainfall concentrated along the coastal belt.',
  OROGRAPHIC_RAINFALL: 'Terrain-forced uplift over the Ghats and Himalayan foothills, where models often under-forecast peaks.',
  WESTERN_DISTURBANCE: 'Extratropical system affecting north-west India and the western Himalaya, mostly outside the monsoon.',
  NORMAL_MONSOON: 'Climatologically ordinary conditions with no dominant forcing.',
}

export const REGIME_COLORS = {
  ACTIVE_MONSOON: '#3a82f7',
  BREAK_MONSOON: '#d7a54a',
  MONSOON_DEPRESSION: '#d62246',
  COASTAL_RAINFALL: '#2fd4e8',
  OROGRAPHIC_RAINFALL: '#8b6df2',
  WESTERN_DISTURBANCE: '#7fa8c4',
  NORMAL_MONSOON: '#4d7a93',
}

export const CONDITION_ORDER = ['LOW', 'NORMAL', 'MODERATE', 'HEAVY', 'VERY_HEAVY']

export const CONDITION_COLORS = {
  LOW: '#7fa8c4',
  NORMAL: '#63b7e8',
  MODERATE: '#3a82f7',
  HEAVY: '#f2a63b',
  VERY_HEAVY: '#d62246',
  UNKNOWN: '#6d879b',
}

export const CATEGORY_ORDER = ['LIGHT', 'MODERATE', 'HEAVY', 'VERY_HEAVY', 'EXTREMELY_HEAVY']

export const CATEGORY_LABELS = {
  LIGHT: 'Light',
  MODERATE: 'Moderate',
  HEAVY: 'Heavy',
  VERY_HEAVY: 'Very heavy',
  EXTREMELY_HEAVY: 'Extremely heavy',
}

export const CATEGORY_COLORS = {
  LIGHT: '#63b7e8',
  MODERATE: '#3a82f7',
  HEAVY: '#f2a63b',
  VERY_HEAVY: '#f2673d',
  EXTREMELY_HEAVY: '#d62246',
}

export const RISK_COLORS = {
  LOW: '#63b7e8',
  MODERATE: '#3a82f7',
  HIGH: '#f2a63b',
  VERY_HIGH: '#d62246',
}

export const CATEGORY_RANGES = {
  LIGHT: 'below 15 mm',
  MODERATE: '15 - 64.4 mm',
  HEAVY: '64.5 - 115.5 mm',
  VERY_HEAVY: '115.6 - 204.4 mm',
  EXTREMELY_HEAVY: '204.5 mm and above',
}

export const regimeLabel = (r) => REGIME_LABELS[r] || String(r || '').replace(/_/g, ' ')
export const categoryLabel = (c) => CATEGORY_LABELS[c] || String(c || '-').replace(/_/g, ' ')

export const mm = (v, digits = 1) =>
  v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : Number(v).toFixed(digits)

export const pct = (v, digits = 0) =>
  v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : `${(Number(v) * 100).toFixed(digits)}%`

export const signed = (v, digits = 1) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-'
  const n = Number(v)
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}`
}

export const num = (v, digits = 3) =>
  v === null || v === undefined || Number.isNaN(Number(v)) ? 'n/a' : Number(v).toFixed(digits)
