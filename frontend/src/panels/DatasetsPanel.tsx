import { useState } from 'react'

import { ApiError, post, type Dataset, type SignalTimeframe, type Symbol } from '../api'
import { fromInput, short, utc } from '../format'
import { t, tDynamic } from '../i18n'

const SYMBOLS: Symbol[] = ['EURUSD', 'GBPUSD', 'USDJPY']
const TIMEFRAMES: SignalTimeframe[] = ['H1', 'H4']

function fiveYearsAgo(): string {
  const now = new Date()
  const start = new Date(Date.UTC(now.getUTCFullYear() - 5, now.getUTCMonth(), now.getUTCDate()))
  return start.toISOString().slice(0, 16)
}

function today(): string {
  const now = new Date()
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
    .toISOString()
    .slice(0, 16)
}

export function DatasetsPanel(props: {
  datasets: Dataset[]
  onImported: () => void
}): JSX.Element {
  const [symbol, setSymbol] = useState<Symbol>('EURUSD')
  const [timeframe, setTimeframe] = useState<SignalTimeframe>('H1')
  const [start, setStart] = useState(fiveYearsAgo())
  const [end, setEnd] = useState(today())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(source: 'mt5' | 'fixture'): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      const body =
        source === 'mt5'
          ? { symbol, timeframe, start: fromInput(start), end: fromInput(end) }
          : { symbol, timeframe }
      await post<Dataset>(`/api/datasets/import/${source}`, body)
      props.onImported()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="datasets-heading">
      <h2 id="datasets-heading">{t('datasets.heading')}</h2>
      <div className="form-row">
        <label>
          {t('datasets.symbol')}
          <select value={symbol} onChange={(event) => setSymbol(event.target.value as Symbol)}>
            {SYMBOLS.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          {t('datasets.timeframe')}
          <select
            value={timeframe}
            onChange={(event) => setTimeframe(event.target.value as SignalTimeframe)}
          >
            {TIMEFRAMES.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          {t('datasets.start')}
          <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          {t('datasets.end')}
          <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
      </div>
      <p className="help">{t('datasets.mt5Help')}</p>
      <div className="actions">
        <button type="button" disabled={busy} onClick={() => void run('mt5')}>
          {t('datasets.importMt5')}
        </button>
        <button type="button" disabled={busy} onClick={() => void run('fixture')}>
          {t('datasets.importFixture')}
        </button>
        {busy && <span>{t('datasets.importing')}</span>}
      </div>
      {error !== null && <p role="alert">{error}</p>}

      <h3>{t('datasets.list')}</h3>
      {props.datasets.length === 0 && <p>{t('state.empty')}</p>}
      {props.datasets.map((dataset) => (
        <DatasetCard key={dataset.dataset_id} dataset={dataset} />
      ))}
    </section>
  )
}

function DatasetCard({ dataset }: { dataset: Dataset }): JSX.Element {
  const { manifest } = dataset
  const coverage = manifest.coverage
  return (
    <article className={`card status-${manifest.status}`} aria-label={dataset.dataset_id}>
      <h4>
        {manifest.symbol} {manifest.timeframe} — {tDynamic('status', manifest.status)} ·{' '}
        {tDynamic('provenance', manifest.provenance)}
      </h4>
      {manifest.status === 'rejected' && <p role="alert">{t('state.rejected')}</p>}
      {manifest.provenance === 'synthetic_fixture' && (
        <p className="notice">{t('disclaimer.synthetic')}</p>
      )}
      <dl>
        <dt>{t('datasets.requested')}</dt>
        <dd>
          {utc(coverage.requested_start)} → {utc(coverage.requested_end)}
        </dd>
        <dt>{t('datasets.coverage')}</dt>
        <dd>
          {utc(coverage.actual_start)} → {utc(coverage.actual_end)}
        </dd>
        <dt>{t('datasets.execution')}</dt>
        <dd>
          {coverage.execution_start && coverage.execution_end
            ? `${utc(coverage.execution_start)} → ${utc(coverage.execution_end)}`
            : t('datasets.noExecution')}
        </dd>
        <dt>{t('datasets.bars')}</dt>
        <dd>{coverage.bar_count}</dd>
        <dt>{t('datasets.rejectedBars')}</dt>
        <dd>{coverage.rejected_bar_count}</dd>
        <dt>{t('datasets.quarantined')}</dt>
        <dd>{coverage.quarantined_ranges.length}</dd>
        <dt>{t('datasets.fingerprint')}</dt>
        <dd title={manifest.content_hash}>{short(manifest.content_hash)}</dd>
        <dt>{t('datasets.note')}</dt>
        <dd>{manifest.source_note}</dd>
      </dl>
      <details>
        <summary>
          {t('datasets.findings')} ({dataset.findings.length})
        </summary>
        {dataset.findings.length === 0 ? (
          <p>{t('datasets.noFinding')}</p>
        ) : (
          <ul>
            {Object.entries(dataset.finding_counts).map(([code, count]) => (
              <li key={code}>
                {code} × {count} — {dataset.findings.find((f) => f.code === code)?.detail}
              </li>
            ))}
          </ul>
        )}
      </details>
    </article>
  )
}
