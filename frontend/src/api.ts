export interface SourceDiagnostic {
  package_available: boolean
  terminal_available: boolean
  platform: string
  synthetic_mode_only: boolean
  code: string | null
  message?: string
}

export async function fetchSourceDiagnostic(
  signal?: AbortSignal,
): Promise<SourceDiagnostic> {
  const response = await fetch('/api/source/diagnostic', { signal })
  if (!response.ok) {
    throw new Error(`source diagnostic failed with status ${response.status}`)
  }
  return (await response.json()) as SourceDiagnostic
}
