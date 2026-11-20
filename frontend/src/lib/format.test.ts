import { describe, expect, it } from 'vitest'
import { formatCompact, formatDateTick, formatValue } from './format'

const en = { locale: 'en-US' }

describe('formatValue', () => {
  it('formats integers with grouping', () => {
    expect(formatValue(1234, 'integer', en)).toBe('1,234')
  })

  it('formats numbers with at most two decimals', () => {
    expect(formatValue(1234.5678, 'number', en)).toBe('1,234.57')
    expect(formatValue(10, 'number', en)).toBe('10')
  })

  it('formats currency with the code when known', () => {
    expect(formatValue(1234.5, 'currency', { ...en, currency: 'USD' })).toBe('$1,234.50')
    expect(formatValue(1234.5, 'currency', { locale: 'pt-BR', currency: 'BRL' })).toMatch(/R\$\s1\.234,50/)
  })

  it('uses the currency home locale when no locale is forced', () => {
    expect(formatValue(1351.71, 'currency', { currency: 'BRL' })).toMatch(/^R\$\s1\.351,71$/)
    expect(formatValue(1351.71, 'currency', { currency: 'USD' })).toBe('$1,351.71')
  })

  it('formats currency without a code as a two-decimal number', () => {
    expect(formatValue(1234.5, 'currency', en)).toBe('1,234.50')
  })

  it('formats percent values given in 0..100', () => {
    expect(formatValue(12.5, 'percent', en)).toBe('12.5%')
  })

  it('renders missing values as an em dash', () => {
    expect(formatValue(null, 'number', en)).toBe('—')
  })

  it('passes non-numeric values through', () => {
    expect(formatValue('Ana', undefined, en)).toBe('Ana')
    expect(formatValue(true, undefined, en)).toBe('yes')
  })

  it('falls back gracefully on an invalid currency code', () => {
    expect(formatValue(5, 'currency', { ...en, currency: 'XX' })).toBe('5.00')
  })
})

describe('formatCompact', () => {
  it('keeps small numbers in full and compacts large ones', () => {
    expect(formatCompact(950, en)).toBe('950')
    expect(formatCompact(12900, en)).toBe('12.9K')
    expect(formatCompact(4_200_000, en)).toBe('4.2M')
  })
})

describe('formatDateTick', () => {
  it('shows month and year for month starts', () => {
    expect(formatDateTick('2024-03-01', true, en)).toBe('Mar 2024')
  })

  it('shows day and month otherwise', () => {
    expect(formatDateTick('2024-03-15', false, en)).toBe('Mar 15')
  })

  it('handles timestamps and non-dates', () => {
    expect(formatDateTick('2024-03-01T00:00:00', true, en)).toBe('Mar 2024')
    expect(formatDateTick('not a date', false, en)).toBe('not a date')
  })
})
