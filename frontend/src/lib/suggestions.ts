import type { Dataset } from '../api/types'

const MAX = 4

const words = (name: string) => name.replace(/_/g, ' ')

/** Short starter questions built from the loaded tables' column profiles. */
export function suggestQuestions(datasets: Dataset[]): string[] {
  const out: string[] = []
  for (const d of datasets.filter((x) => x.status === 'loaded')) {
    const cols = d.columns
    const metric = cols.find((c) => c.semantic_type === 'currency') ?? cols.find((c) => c.semantic_type === 'numeric')
    const category = cols.find((c) => c.semantic_type === 'categorical')
    const time = cols.find((c) => c.semantic_type === 'temporal')
    if (metric && category) out.push(`Total ${words(metric.name)} by ${words(category.name)}`)
    if (metric && time) out.push(`${words(metric.name)} per month`.replace(/^./, (c) => c.toUpperCase()))
    if (category) out.push(`Top 10 ${words(category.name)}`)
    out.push(`How many rows in ${words(d.table_name)}?`)
  }
  return [...new Set(out)].slice(0, MAX)
}
