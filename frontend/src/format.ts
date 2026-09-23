export function percent(value: string | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${(Number(value) * 100).toFixed(2)} %`
}

export function money(value: string): string {
  return Number(value).toFixed(2)
}

export function utc(value: string): string {
  return value.replace('T', ' ').replace(/(:\d\d)(\.\d+)?(Z|\+00:00)$/, '$1 UTC')
}

/** Value for an <input type="datetime-local"> interpreted as UTC. */
export function toInput(value: string): string {
  return value.slice(0, 16)
}

export function fromInput(value: string): string {
  return `${value}:00Z`
}

export function short(id: string): string {
  return id.length > 14 ? `${id.slice(0, 14)}…` : id
}
