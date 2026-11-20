import type { CellValue, ValueFormat } from '../api/types'

export interface FormatOptions {
  locale?: string // undefined = the viewer's browser locale
  currency?: string | null
}

const cache = new Map<string, Intl.NumberFormat>()

function numberFormat(locale: string | undefined, options: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = `${locale}|${JSON.stringify(options)}`
  let format = cache.get(key)
  if (!format) {
    format = new Intl.NumberFormat(locale, options)
    cache.set(key, format)
  }
  return format
}

/** Where a currency is written natively; used when the caller does not force a locale. */
const CURRENCY_LOCALES: Record<string, string> = { BRL: 'pt-BR', USD: 'en-US', GBP: 'en-GB', JPY: 'ja-JP' }

function currencyFormat(locale: string | undefined, currency: string | null | undefined) {
  if (currency) {
    try {
      return numberFormat(locale ?? CURRENCY_LOCALES[currency.toUpperCase()], { style: 'currency', currency })
    } catch {
      // invalid ISO code: fall through to a plain two-decimal number
    }
  }
  return numberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function formatValue(value: CellValue | undefined, format: ValueFormat | undefined, options: FormatOptions = {}) {
  const { locale, currency } = options
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (typeof value !== 'number') return String(value)

  switch (format) {
    case 'integer':
      return numberFormat(locale, { maximumFractionDigits: 0 }).format(value)
    case 'currency':
      return currencyFormat(locale, currency).format(value)
    case 'percent':
      return `${numberFormat(locale, { maximumFractionDigits: 1 }).format(value)}%`
    default:
      return numberFormat(locale, { maximumFractionDigits: 2 }).format(value)
  }
}

/** Axis ticks: in full below 10,000, compact above (12.9K, 4.2M). */
export function formatCompact(value: number, options: FormatOptions = {}) {
  if (Math.abs(value) < 10_000) return numberFormat(options.locale, { maximumFractionDigits: 2 }).format(value)
  return numberFormat(options.locale, { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})/

export function formatDateTick(value: CellValue, monthStarts: boolean, options: FormatOptions = {}) {
  const match = typeof value === 'string' ? ISO_DATE.exec(value) : null
  if (!match) return String(value)
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])))
  const parts: Intl.DateTimeFormatOptions = monthStarts
    ? { month: 'short', year: 'numeric', timeZone: 'UTC' }
    : { month: 'short', day: 'numeric', timeZone: 'UTC' }
  return new Intl.DateTimeFormat(options.locale, parts).format(date)
}

export function allMonthStarts(values: CellValue[]): boolean {
  return values.length > 0 && values.every((v) => typeof v === 'string' && /^\d{4}-\d{2}-01/.test(v))
}
