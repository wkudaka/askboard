import { describe, expect, it } from 'vitest'
import { loaded, preview } from '../test/fixtures'
import { suggestQuestions } from './suggestions'

describe('suggestQuestions', () => {
  it('builds questions from the column profiles of loaded tables', () => {
    expect(suggestQuestions([loaded])).toEqual([
      'Total valor total by cliente',
      'Valor total per month',
      'Top 10 cliente',
      'How many rows in pedidos?',
    ])
  })

  it('ignores tables that are not loaded', () => {
    expect(suggestQuestions([preview])).toEqual([])
  })
})
