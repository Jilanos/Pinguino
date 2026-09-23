import { useEffect, useState } from 'react'

import { ApiError, get, post, type CampaignRun } from '../api'
import { short, utc } from '../format'
import { t, tDynamic } from '../i18n'

const ACTIVE = new Set(['queued', 'running'])
const RESUMABLE = new Set(['interrupted', 'cancelled', 'partial', 'failed'])
const POLL_MS = 1500

export function RunsPanel(props: { onOpen: (campaignId: string) => void }): JSX.Element {
  const [runs, setRuns] = useState<CampaignRun[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    get<CampaignRun[]>('/api/campaigns', controller.signal)
      .then(setRuns)
      .catch((caught) => {
        if (!controller.signal.aborted) setError(String(caught))
      })
    return () => controller.abort()
  }, [tick])

  const anyActive = runs?.some((run) => ACTIVE.has(run.state)) ?? false
  useEffect(() => {
    if (!anyActive) return
    const timer = setTimeout(() => setTick((value) => value + 1), POLL_MS)
    return () => clearTimeout(timer)
  }, [anyActive, tick])

  async function act(path: string): Promise<void> {
    setError(null)
    try {
      await post(path)
      setTick((value) => value + 1)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    }
  }

  return (
    <section aria-labelledby="runs-heading">
      <h2 id="runs-heading">{t('run.heading')}</h2>
      {runs === null && <p>{t('state.loading')}</p>}
      {runs !== null && runs.length === 0 && <p>{t('state.empty')}</p>}
      {runs?.map((run) => {
        const total = run.preview.preview.base_candidate_count
        const done =
          (run.trial_counts.completed ?? 0) +
          (run.trial_counts.failed ?? 0) +
          (run.trial_counts.cancelled ?? 0)
        return (
          <article key={run.campaign_id} className={`card run-${run.state}`}>
            <h3 title={run.campaign_id}>
              {short(run.campaign_id)} — {tDynamic('runState', run.state)}
            </h3>
            <p>
              {utc(run.created_at)} · {t('run.phase')} : {run.phase ?? '—'}
            </p>
            <progress max={total} value={done} aria-label={run.campaign_id} />
            <p>{t('run.progress', { done, total })}</p>
            {run.duration_seconds !== null && (
              <p>{t('run.duration', { seconds: run.duration_seconds.toFixed(1) })}</p>
            )}
            {run.outcome !== null && (
              <p>{t('run.evaluationsUsed', { count: run.outcome.evaluations_used })}</p>
            )}
            {typeof run.outcome?.worker_peak_memory_mb === 'number' && (
              <p>{t('run.memory', { mb: run.outcome.worker_peak_memory_mb })}</p>
            )}
            {run.outcome?.budget_exhausted && (
              <p className="notice">{t('run.budgetExhausted', { budget: run.outcome.budget_exhausted })}</p>
            )}
            {run.state === 'cancelled' && <p className="notice">{t('state.cancelled')}</p>}
            {run.state === 'interrupted' && <p className="notice">{t('state.interrupted')}</p>}
            {run.state === 'failed' && (
              <p role="alert">{t('run.failed', { error: run.error ?? '?' })}</p>
            )}
            <div className="actions">
              {ACTIVE.has(run.state) && (
                <button type="button" onClick={() => void act(`/api/campaigns/${run.campaign_id}/cancel`)}>
                  {t('run.cancel')}
                </button>
              )}
              {RESUMABLE.has(run.state) && (
                <button type="button" onClick={() => void act(`/api/campaigns/${run.campaign_id}/resume`)}>
                  {t('run.resume')}
                </button>
              )}
              {!ACTIVE.has(run.state) && (
                <button type="button" onClick={() => props.onOpen(run.campaign_id)}>
                  {t('run.open')}
                </button>
              )}
            </div>
          </article>
        )
      })}
      {error !== null && <p role="alert">{error}</p>}
    </section>
  )
}
