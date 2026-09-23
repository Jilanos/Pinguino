import { useEffect, useState } from 'react'

import {
  ApiError,
  get,
  post,
  type Candidate,
  type CampaignRun,
  type WindowDetail,
  type WindowMetrics,
} from '../api'
import { money, percent, short, utc } from '../format'
import { t, tDynamic } from '../i18n'

const PAGE = 20

export function ResultsPanel({ campaignId }: { campaignId: string | null }): JSX.Element {
  const [run, setRun] = useState<CampaignRun | null>(null)
  const [candidates, setCandidates] = useState<Candidate[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    if (campaignId === null) return
    const controller = new AbortController()
    Promise.all([
      get<CampaignRun>(`/api/campaigns/${campaignId}`, controller.signal),
      get<Candidate[]>(`/api/campaigns/${campaignId}/candidates`, controller.signal),
    ])
      .then(([loadedRun, loaded]) => {
        setRun(loadedRun)
        setCandidates(loaded)
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(String(caught))
      })
    return () => controller.abort()
  }, [campaignId, version])

  const active = run?.state === 'queued' || run?.state === 'running'
  useEffect(() => {
    if (!active) return
    const timer = setTimeout(() => setVersion((value) => value + 1), 1500)
    return () => clearTimeout(timer)
  }, [active, version])

  if (campaignId === null) {
    return (
      <section aria-labelledby="results-heading">
        <h2 id="results-heading">{t('results.heading')}</h2>
        <p>{t('results.choose')}</p>
      </section>
    )
  }

  const synthetic = (run?.preview as { datasets?: { provenance: string }[] } | undefined)?.datasets?.some(
    (item) => item.provenance === 'synthetic_fixture',
  )
  const eligible = candidates?.filter((item) => item.verdict === 'eligible') ?? []
  const current = candidates?.find((item) => item.candidate_id === selected) ?? null

  return (
    <section aria-labelledby="results-heading">
      <h2 id="results-heading">{t('results.heading')}</h2>
      <p className="help">{t('results.heuristic')}</p>
      <p className="help">{t('results.individual')}</p>
      {synthetic && <p className="notice">{t('disclaimer.synthetic')}</p>}
      {run?.state === 'cancelled' && <p className="notice">{t('state.cancelled')}</p>}
      {run?.state === 'interrupted' && <p className="notice">{t('state.interrupted')}</p>}
      {candidates === null && <p>{t('state.loading')}</p>}
      {candidates !== null && candidates.length === 0 && <p>{t('state.empty')}</p>}
      {candidates !== null && candidates.length > 0 && eligible.length === 0 && (
        <p className="notice">{t('state.noCandidate')}</p>
      )}

      {run?.baselines && (
        <div className="card">
          <h3>{t('results.baselines')}</h3>
          {run.baselines.map((baseline) => (
            <p key={`${baseline.symbol}-${baseline.timeframe}`}>
              {baseline.symbol} {baseline.timeframe} — {t('results.cash')}{' '}
              {t('results.alwaysLong', {
                ret: percent(baseline.always_long.validation?.net_return),
                dd: percent(baseline.always_long.validation?.max_drawdown),
              })}
            </p>
          ))}
        </div>
      )}

      {candidates !== null && candidates.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('results.rank')}</th>
                <th>{t('results.candidate')}</th>
                <th>{t('results.family')}</th>
                <th>{t('results.pair')}</th>
                <th>{t('results.verdict')}</th>
                <th>{t('results.trainingTrades')}</th>
                <th>{t('results.validationReturn')}</th>
                <th>{t('results.validationDrawdown')}</th>
                <th>{t('results.reasons')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {candidates.map((item) => (
                <tr key={item.candidate_id} className={`verdict-${item.verdict}`}>
                  <td>{item.rank ?? '—'}</td>
                  <td title={item.candidate_id}>{short(item.candidate_id)}</td>
                  <td>{item.definition.family}</td>
                  <td>
                    {item.definition.symbol} {item.definition.timeframe}
                  </td>
                  <td>
                    <span className={`badge badge-${item.verdict}`}>
                      {tDynamic('verdict', item.verdict)}
                    </span>
                  </td>
                  <td>{item.windows[0]?.trade_count}</td>
                  <td>{percent(item.windows[1]?.net_return)}</td>
                  <td>{percent(item.windows[1]?.max_drawdown)}</td>
                  <td className="reasons">{item.reasons.join(' ; ')}</td>
                  <td>
                    <button type="button" onClick={() => setSelected(item.candidate_id)}>
                      {t('results.details')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {error !== null && <p role="alert">{error}</p>}
      {current !== null && (
        <CandidateDetail
          key={current.candidate_id}
          campaignId={campaignId}
          candidate={current}
          onChanged={() => setVersion((value) => value + 1)}
        />
      )}
    </section>
  )
}

function WindowRows({ windows }: { windows: WindowMetrics[] }): JSX.Element {
  return (
    <tbody>
      {windows.map((window) => (
        <tr key={window.label}>
          <td>{window.label}</td>
          <td>
            {utc(window.start)} → {utc(window.end)}
          </td>
          <td>{percent(window.net_return)}</td>
          <td>{percent(window.max_drawdown)}</td>
          <td>{window.trade_count}</td>
          <td>{window.win_rate === null ? t('detail.undefined') : percent(window.win_rate)}</td>
          <td>
            {window.profit_factor === null
              ? t('detail.undefined')
              : Number(window.profit_factor).toFixed(2)}
          </td>
          <td>
            {money(window.commission_cost)} / {money(window.spread_cost)} / {money(window.swap_cost)} /{' '}
            {money(window.slippage_cost)}
          </td>
        </tr>
      ))}
    </tbody>
  )
}

function check(value: boolean | null): string {
  if (value === null) return t('detail.notRun')
  return value ? t('detail.passed') : t('detail.failedCheck')
}

function CandidateDetail(props: {
  campaignId: string
  candidate: Candidate
  onChanged: () => void
}): JSX.Element {
  const { candidate, campaignId } = props
  const base = `/api/campaigns/${campaignId}/candidates/${candidate.candidate_id}`
  const labels = [
    ...candidate.windows.map((window) => window.label),
    ...(candidate.final_holdout ? ['final_holdout'] : []),
  ]
  const [label, setLabel] = useState('validation')
  const [offset, setOffset] = useState(0)
  const [detail, setDetail] = useState<WindowDetail | null>(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setDetail(null)
    get<WindowDetail>(`${base}/windows/${label}?offset=${offset}&limit=${PAGE}`, controller.signal)
      .then(setDetail)
      .catch((caught) => {
        if (!controller.signal.aborted) setError(caught instanceof ApiError ? caught.message : String(caught))
      })
    return () => controller.abort()
  }, [base, label, offset])

  async function openHoldout(): Promise<void> {
    setError(null)
    try {
      await post(`${base}/final-evaluation`, { reason })
      props.onChanged()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    }
  }

  const holdout = candidate.final_holdout?.metrics

  return (
    <article className="card" aria-labelledby="detail-heading">
      <h3 id="detail-heading">{t('detail.heading', { id: short(candidate.candidate_id) })}</h3>
      <p>
        <span className={`badge badge-${candidate.verdict}`}>{tDynamic('verdict', candidate.verdict)}</span>{' '}
        {candidate.reasons.join(' ; ')}
      </p>
      <h4>{t('detail.parameters')}</h4>
      <p>
        {candidate.definition.family} · {candidate.definition.symbol} {candidate.definition.timeframe} ·{' '}
        {Object.entries(candidate.definition.parameters)
          .filter(([, value]) => value !== null)
          .map(([name, value]) => `${name}=${value}`)
          .join(', ')}
      </p>
      <h4>{t('detail.windows')}</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t('detail.window')}</th>
              <th>{t('detail.period')}</th>
              <th>{t('detail.netReturn')}</th>
              <th>{t('detail.drawdown')}</th>
              <th>{t('detail.trades')}</th>
              <th>{t('detail.winRate')}</th>
              <th>{t('detail.profitFactor')}</th>
              <th>{t('detail.costs')}</th>
            </tr>
          </thead>
          <WindowRows windows={candidate.windows} />
        </table>
      </div>
      <h4>{t('detail.robustness')}</h4>
      <p>{t('detail.stress', { value: check(candidate.stress_passed) })}</p>
      <p>
        {t('detail.neighborhood', {
          value: candidate.neighborhood === null ? t('detail.notRun') : tDynamic('verdict', candidate.neighborhood),
        })}
      </p>
      <h4>{t('detail.flags')}</h4>
      <p>{candidate.approximation_flags.join(', ') || '—'}</p>
      <p>{t('detail.ambiguity', { count: candidate.ambiguity_count })}</p>

      <label>
        {t('detail.replayWindow')}
        <select
          value={label}
          onChange={(event) => {
            setLabel(event.target.value)
            setOffset(0)
          }}
        >
          {labels.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      {detail === null && error === null && <p>{t('state.loading')}</p>}
      {detail !== null && (
        <>
          <h4>{t('detail.equity')}</h4>
          <EquityChart points={detail.equity.map((point) => Number(point.equity))} />
          <h4>
            {t('detail.tradeList', {
              from: detail.trade_total === 0 ? 0 : offset + 1,
              to: Math.min(offset + PAGE, detail.trade_total),
              total: detail.trade_total,
            })}
          </h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('detail.opened')}</th>
                  <th>{t('detail.closed')}</th>
                  <th>{t('detail.direction')}</th>
                  <th>{t('detail.exit')}</th>
                  <th>{t('detail.pnl')}</th>
                </tr>
              </thead>
              <tbody>
                {detail.trades.map((trade) => (
                  <tr key={`${trade.opened_at}-${trade.closed_at}`}>
                    <td>{utc(trade.opened_at)}</td>
                    <td>{utc(trade.closed_at)}</td>
                    <td>{trade.direction}</td>
                    <td>{trade.exit_reason}</td>
                    <td>{money(trade.net_pnl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="actions">
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              {t('detail.previous')}
            </button>
            <button
              type="button"
              disabled={offset + PAGE >= detail.trade_total}
              onClick={() => setOffset(offset + PAGE)}
            >
              {t('detail.next')}
            </button>
          </div>
        </>
      )}

      <h4>{t('holdout.heading')}</h4>
      {holdout ? (
        <p>
          {t('holdout.done', {
            ret: percent(holdout.net_return),
            dd: percent(holdout.max_drawdown),
            trades: holdout.trade_count,
          })}
        </p>
      ) : (
        <>
          <p className="notice">{t('holdout.warning')}</p>
          <label>
            {t('holdout.reason')}
            <input value={reason} onChange={(event) => setReason(event.target.value)} />
          </label>
          <button type="button" disabled={reason.trim().length < 3} onClick={() => void openHoldout()}>
            {t('holdout.open')}
          </button>
        </>
      )}
      <p>
        <a href={`${base}/export`} download>
          {t('detail.export')}
        </a>
      </p>
      {error !== null && <p role="alert">{error}</p>}
    </article>
  )
}

function EquityChart({ points }: { points: number[] }): JSX.Element {
  if (points.length < 2) return <p>{t('state.empty')}</p>
  const width = 640
  const height = 160
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const path = points
    .map((value, index) => {
      const x = (index / (points.length - 1)) * width
      const y = height - ((value - min) / span) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t('detail.equity')}>
        <polyline points={path} fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
      <figcaption>
        {min.toFixed(2)} – {max.toFixed(2)} USD
      </figcaption>
    </figure>
  )
}
