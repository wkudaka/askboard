export interface DateGroup<T> {
  label: string
  items: T[]
}

const DAY = 24 * 60 * 60 * 1000

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
}

function labelFor(date: Date, now: Date): string {
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days <= 7) return 'Previous 7 days'
  if (days <= 30) return 'Previous 30 days'
  if (date.getFullYear() === now.getFullYear()) return date.toLocaleString('en', { month: 'long' })
  return String(date.getFullYear())
}

/** Groups items (already sorted newest first) into chat-sidebar buckets, keeping their order. */
export function groupByDate<T>(items: T[], dateOf: (item: T) => string, now: Date = new Date()): DateGroup<T>[] {
  const groups: DateGroup<T>[] = []
  for (const item of items) {
    const label = labelFor(new Date(dateOf(item)), now)
    const last = groups[groups.length - 1]
    if (last && last.label === label) last.items.push(item)
    else groups.push({ label, items: [item] })
  }
  return groups
}
