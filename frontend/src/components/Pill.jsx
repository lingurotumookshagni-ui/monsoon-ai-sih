import { categoryLabel } from '../services/constants'
import { useT } from '../i18n'

/* Condition glyphs so rainfall severity is never signalled by colour alone. */
const CONDITION_GLYPH = {
  LOW: '○',
  NORMAL: '◔',
  MODERATE: '◑',
  HEAVY: '◕',
  VERY_HEAVY: '●',
  UNKNOWN: '–',
}

export function ConditionPill({ condition }) {
  const t = useT()
  const key = condition || 'UNKNOWN'
  return (
    <span className={`cond cond-${key}`}>
      <span className="glyph" aria-hidden="true">{CONDITION_GLYPH[key] || '–'}</span>
      {t(`condition.${key}`)}
    </span>
  )
}

export function CategoryPill({ category }) {
  if (!category) return <span className="faint">-</span>
  return <span className={`pill cat-${category}`}>{categoryLabel(category)}</span>
}

export function RiskPill({ band }) {
  if (!band) return <span className="faint">-</span>
  return <span className={`pill risk-${band}`}>{band.replace('_', ' ').toLowerCase()}</span>
}
