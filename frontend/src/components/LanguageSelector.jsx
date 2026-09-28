import { useEffect, useRef, useState } from 'react'
import { LANGUAGES, useI18n } from '../i18n'

/* Language menu. Keyboard accessible, closes on Escape or outside click,
   and switches language in place with no page reload. */
export default function LanguageSelector({ onChanged }) {
  const { lang, setLang, t } = useI18n()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const current = LANGUAGES.find((l) => l.code === lang) || LANGUAGES[0]

  useEffect(() => {
    if (!open) return undefined
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const choose = (code) => {
    setLang(code)
    setOpen(false)
    if (onChanged) onChanged(code)
  }

  return (
    <div className="lang" ref={ref}>
      <button
        className="btn"
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t('common.language')}
      >
        <span aria-hidden="true">🌐</span> {current.native}
      </button>
      {open ? (
        <div className="lang-menu" role="listbox" aria-label={t('common.language')}>
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              role="option"
              aria-selected={l.code === lang}
              onClick={() => choose(l.code)}
            >
              <span>{l.native}</span>
              <span className="native">{l.label}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
