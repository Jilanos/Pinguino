export interface SourceDiagnostic {
  package_available: boolean
  terminal_available: boolean
  terminal_connected?: boolean
  terminal_build?: number | null
  package_version?: string | null
  available_symbols?: Record<string, string>
  platform?: string
  synthetic_mode_only: boolean
  code?: string | null
  message?: string
}

export type Symbol = 'EURUSD' | 'GBPUSD' | 'USDJPY'
export type SignalTimeframe = 'H1' | 'H4'
export type DatasetStatus = 'qualified' | 'approximate' | 'rejected'
export type Verdict = 'eligible' | 'rejected' | 'inconclusive'
export type RunState =
  | 'queued'
  | 'running'
  | 'completed'
  | 'partial'
  | 'cancelled'
  | 'failed'
  | 'interrupted'

export interface Finding {
  code: string
  detail: string
  at: string | null
  range_start: string | null
  range_end: string | null
}

export interface Dataset {
  dataset_id: string
  manifest: {
    symbol: Symbol
    timeframe: SignalTimeframe
    provenance: 'synthetic_fixture' | 'mt5_terminal'
    status: DatasetStatus
    content_hash: string
    source_note: string
    imported_at: string
    coverage: {
      requested_start: string
      requested_end: string
      actual_start: string
      actual_end: string
      bar_count: number
      quarantined_ranges: [string, string][]
      rejected_bar_count: number
      execution_start?: string | null
      execution_end?: string | null
    }
  }
  findings: Finding[]
  finding_counts: Record<string, number>
}

// The configuration is edited field by field and sent back verbatim.
export interface CampaignConfig {
  config_version: string
  dataset_ids: string[]
  cost_policy: Record<string, string | boolean>
  sizing_policy: Record<string, string | number>
  window_policy: Record<string, string | number> & {
    requested_start: string
    requested_end: string
  }
  eligibility_policy: Record<string, string | number>
  budget: {
    seed: number
    workers: number
    max_candidates: number
    max_evaluations: number
    max_active_minutes: number
  }
  resumed_from_campaign_id: string | null
}

export interface Preview {
  preview: {
    campaign_id: string
    base_candidate_count: number
    planned_evaluation_count: number
    training_start: string
    training_end: string
    validation_start: string
    validation_end: string
    final_holdout_start: string
    final_holdout_end: string
  }
  validation_subwindows: { start: string; end: string }[]
  startable: boolean
}

export interface CampaignRun {
  campaign_id: string
  state: RunState
  phase: string | null
  created_at: string
  duration_seconds: number | null
  error: string | null
  config: CampaignConfig
  preview: Preview
  trial_counts: Record<string, number>
  outcome: {
    completed: number
    cancelled: number
    failed: number
    not_run: number
    evaluations_used: number
    budget_exhausted: string | null
    worker_peak_memory_mb?: number | null
  } | null
  baselines:
    | {
        symbol: string
        timeframe: string
        always_long: Record<string, { net_return: string | null; max_drawdown: string | null }>
      }[]
    | null
}

export interface WindowMetrics {
  label: string
  start: string
  end: string
  net_return: string
  max_drawdown: string
  trade_count: number
  win_rate: string | null
  profit_factor: string | null
  exposure_fraction: string
  commission_cost: string
  spread_cost: string
  swap_cost: string
  slippage_cost: string
  undefined_reasons: string[]
}

export interface Candidate {
  candidate_id: string
  definition: {
    family: string
    symbol: string
    timeframe: string
    parameters: Record<string, string | number | null>
  }
  windows: WindowMetrics[]
  verdict: Verdict
  reasons: string[]
  rank: number | null
  stress_passed: boolean | null
  neighborhood: Verdict | null
  approximation_flags: string[]
  ambiguity_count: number
  final_holdout: { metrics: WindowMetrics } | null
}

export interface Trade {
  opened_at: string
  closed_at: string
  direction: string
  volume: string
  entry_price: string
  exit_price: string
  exit_reason: string
  net_pnl: string
}

export interface WindowDetail {
  window: string
  trade_total: number
  offset: number
  limit: number
  trades: Trade[]
  equity: { observed_at: string; equity: string }[]
  max_drawdown: string
}

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message)
  }
}

let tokenPromise: Promise<string> | null = null

async function token(): Promise<string> {
  tokenPromise ??= fetch('/api/session')
    .then((response) => response.json() as Promise<{ token: string }>)
    .then((body) => body.token)
  return tokenPromise
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let code = 'HTTP_' + response.status
    let message = `Erreur ${response.status}`
    try {
      const body = (await response.json()) as { code?: string; message?: string; detail?: unknown }
      if (body.code) code = body.code
      if (body.message) message = body.message
      else if (body.detail) message = JSON.stringify(body.detail)
    } catch {
      // Non-JSON error body: keep the status message.
    }
    throw new ApiError(code, message)
  }
  return (await response.json()) as T
}

export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  return parse<T>(await fetch(path, { signal }))
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-pinguino-token': await token() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return parse<T>(response)
}

export function fetchSourceDiagnostic(signal?: AbortSignal): Promise<SourceDiagnostic> {
  return get<SourceDiagnostic>('/api/source/diagnostic', signal)
}
