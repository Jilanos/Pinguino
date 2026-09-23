import fr from './fr.json'

export const SOURCE_LOCALE = 'fr'

type Catalog = typeof fr

/** Dotted paths of the source catalogue, so an unknown key fails type checking. */
export type MessageKey = {
  [Group in keyof Catalog & string]: `${Group}.${keyof Catalog[Group] & string}`
}[keyof Catalog & string]

export function t(key: MessageKey, values?: Record<string, string | number>): string {
  const [group, leaf] = key.split('.') as [keyof Catalog, string]
  const template = (fr[group] as Record<string, string>)[leaf]
  if (values === undefined) return template
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in values ? String(values[name]) : match,
  )
}

/** Look up a message whose leaf comes from server data, e.g. a status value. */
export function tDynamic(group: keyof Catalog, leaf: string): string {
  return (fr[group] as Record<string, string>)[leaf] ?? leaf
}

/** Every leaf message, used by catalogue completeness checks. */
export function messages(): Record<string, string> {
  return Object.fromEntries(
    Object.entries(fr).flatMap(([group, leaves]) =>
      Object.entries(leaves).map(([leaf, value]) => [`${group}.${leaf}`, value as string]),
    ),
  )
}
