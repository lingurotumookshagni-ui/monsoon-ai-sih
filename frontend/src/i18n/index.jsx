/* Centralised translation system.

   Flat dot-separated keys, one JSON file per language, English as the fallback
   for any key a translation has not covered yet. Switching language re-renders
   through React context - there is no page reload. Scientific abbreviations
   (RMSE, ETS, CSI, POD, FAR, FSS) are deliberately left untranslated, and so
   are numeric values. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import en from './en.json'
import ml from './ml.json'
import hi from './hi.json'
import ta from './ta.json'
import te from './te.json'
import bn from './bn.json'
import mr from './mr.json'

const DICTIONARIES = { en, ml, hi, ta, te, bn, mr }

export const LANGUAGES = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
]

const STORAGE_KEY = 'monsoonai.language'

const I18nContext = createContext({ lang: 'en', setLang: () => {}, t: (k) => k })

function readStoredLanguage() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved && DICTIONARIES[saved]) return saved
  } catch {
    // storage can be blocked; fall through to the default
  }
  return 'en'
}

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(readStoredLanguage)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((next) => {
    if (!DICTIONARIES[next]) return
    setLangState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // ignore storage failures, the language still applies for this session
    }
  }, [])

  const t = useCallback(
    (key, vars) => {
      const dict = DICTIONARIES[lang] || en
      let text = dict[key]
      if (text === undefined) text = en[key]
      if (text === undefined) return key
      if (vars) {
        Object.entries(vars).forEach(([name, value]) => {
          text = text.replaceAll(`{${name}}`, String(value))
        })
      }
      return text
    },
    [lang],
  )

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  return useContext(I18nContext)
}

/* Convenience hook when only the translate function is needed. */
export function useT() {
  return useContext(I18nContext).t
}
