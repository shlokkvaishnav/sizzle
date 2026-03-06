/** Number formatting utilities — locale and currency configurable via env */
import { NUMBER_LOCALE, CURRENCY_SYMBOL } from '../config'

const numFormatter = new Intl.NumberFormat(NUMBER_LOCALE, {
  maximumFractionDigits: 0,
})

const numDecimalFormatter = new Intl.NumberFormat(NUMBER_LOCALE, {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
})

/** Format currency amount with symbol and locale grouping */
export function formatRupees(value) {
  if (value == null || isNaN(value)) return `${CURRENCY_SYMBOL}0`
  return `${CURRENCY_SYMBOL}${numFormatter.format(value)}`
}

/** Format large currency amounts: ₹1.2L, ₹45K etc. */
export function formatRupeesShort(value) {
  if (value == null || isNaN(value)) return `${CURRENCY_SYMBOL}0`
  if (value >= 100000) return `${CURRENCY_SYMBOL}${(value / 100000).toFixed(1)}L`
  if (value >= 1000) return `${CURRENCY_SYMBOL}${(value / 1000).toFixed(1)}K`
  return `${CURRENCY_SYMBOL}${numFormatter.format(value)}`
}

/** Format percentage to 1 decimal max */
export function formatPct(value) {
  if (value == null || isNaN(value)) return '0%'
  return `${Number(value).toFixed(1)}%`
}

/** Format a decimal like 0.12 to '12% of orders' */
export function formatSupport(value) {
  if (value == null || isNaN(value)) return '0%'
  return `${Math.round(value * 100)}% of orders`
}

/** Format confidence decimal to percentage: 0.78 → '78%' */
export function formatConfidence(value) {
  if (value == null || isNaN(value)) return '0%'
  return `${Math.round(value * 100)}%`
}

/** Format lift: 2.3 → '2.3×' */
export function formatLift(value) {
  if (value == null || isNaN(value)) return '0×'
  return `${Number(value).toFixed(1)}×`
}
