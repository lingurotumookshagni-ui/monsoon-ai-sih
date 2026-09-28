import { useEffect } from 'react'
import DistrictResult from './DistrictResult'
import { useT } from '../i18n'

/* Modal wrapper around the district result. Closes on Escape or backdrop
   click, and restores scrolling on unmount. */
export default function DistrictModal({ record, regime, verification, onClose }) {
  const t = useT()

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  if (!record) return null

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={record.district}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h2 style={{ margin: 0 }}>{t('common.viewDetails')}</h2>
          <button className="icon-btn" onClick={onClose} aria-label={t('common.close')}>
            ×
          </button>
        </div>
        <DistrictResult record={record} regime={regime} verification={verification} />
      </div>
    </div>
  )
}
