import { createContext, useContext, useEffect, useState } from 'react'
import { getOpsSettings } from '../api/client'

const SettingsContext = createContext()

const FALLBACK_SETTINGS = {
  menu_management: {
    default_tax_pct: 5,
    service_charge_pct: 0,
    hide_unavailable_items: true,
    category_ordering_mode: 'manual',
  },
  display_thresholds: {
    cm_green_min: 65,
    cm_yellow_min: 50,
    risk_margin_max: 40,
    risk_popularity_min: 0.5,
    confidence_green_min: 80,
    confidence_yellow_min: 60,
  },
  restaurant_profile: {},
}

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(FALLBACK_SETTINGS)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    getOpsSettings()
      .then((data) => {
        setSettings((prev) => ({ ...prev, ...data }))
      })
      .catch((err) => {
        console.error('Failed to load settings, using defaults:', err)
      })
      .finally(() => setLoaded(true))
  }, [])

  return (
    <SettingsContext.Provider value={{ settings, loaded, setSettings }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}

/** Shortcut: return the tax rate as a number (e.g. 5) */
export function useTaxRate() {
  const { settings } = useSettings()
  return settings.menu_management?.default_tax_pct ?? 5
}

/** Shortcut: return the display_thresholds object */
export function useThresholds() {
  const { settings } = useSettings()
  return { ...FALLBACK_SETTINGS.display_thresholds, ...(settings.display_thresholds || {}) }
}

export default SettingsContext
