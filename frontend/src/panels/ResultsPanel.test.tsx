import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { t } from '../i18n'
import { ResultsPanel } from './ResultsPanel'

const WINDOW = {
  start: '2024-01-01T00:00:00Z',
  end: '2024-02-01T00:00:00Z',
  net_return: '0.01',
  max_drawdown: '0.02',
  trade_count: 12,
  win_rate: '0.5',
  profit_factor: '1.1',
  exposure_fraction: '0.1',
  commission_cost: '0',
  spread_cost: '1',
  swap_cost: '0',
  slippage_cost: '0.1',
  undefined_reasons: [],
}

function candidate(id: string, verdict: string, rank: number | null) {
  return {
    candidate_id: id,
    definition: { family: 'trend', symbol: 'EURUSD', timeframe: 'H1', parameters: {} },
    windows: [
      { ...WINDOW, label: 'training' },
      { ...WINDOW, label: 'validation' },
    ],
    verdict,
    reasons: [`motif ${id}`],
    rank,
    stress_passed: null,
    neighborhood: null,
    approximation_flags: [],
    ambiguity_count: 0,
    final_holdout: null,
  }
}

const RUN = {
  campaign_id: 'camp-1',
  state: 'completed',
  preview: { preview: {}, datasets: [{ provenance: 'synthetic_fixture' }] },
  baselines: null,
}

function serve(candidates: unknown[]): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const body = url.endsWith('/candidates') ? candidates : RUN
      return new Response(JSON.stringify(body), { status: 200 })
    }),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('Candidate comparison', () => {
  it('labels rejected and inconclusive candidates without the eligible styling', async () => {
    serve([candidate('cand-a', 'rejected', null), candidate('cand-b', 'inconclusive', null)])
    render(<ResultsPanel campaignId="camp-1" />)
    const rejected = await screen.findByText(t('verdict.rejected'))
    expect(rejected).toHaveClass('badge-rejected')
    expect(rejected).not.toHaveClass('badge-eligible')
    expect(screen.getByText(t('verdict.inconclusive'))).toHaveClass('badge-inconclusive')
    expect(screen.getByText('motif cand-a')).toBeInTheDocument()
  })

  it('states that no eligible candidate is a valid outcome', async () => {
    serve([candidate('cand-a', 'inconclusive', null)])
    render(<ResultsPanel campaignId="camp-1" />)
    expect(await screen.findByText(t('state.noCandidate'))).toBeInTheDocument()
    expect(screen.getByText(t('disclaimer.synthetic'))).toBeInTheDocument()
  })

  it('shows the rank only for eligible candidates', async () => {
    serve([candidate('cand-a', 'eligible', 1), candidate('cand-b', 'rejected', null)])
    render(<ResultsPanel campaignId="camp-1" />)
    const eligible = await screen.findByText(t('verdict.eligible'))
    const row = eligible.closest('tr')
    expect(row).not.toBeNull()
    expect(within(row as HTMLElement).getByText('1')).toBeInTheDocument()
    expect(screen.queryByText(t('state.noCandidate'))).not.toBeInTheDocument()
  })
})
