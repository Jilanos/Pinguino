import { useState } from 'react'

import { ApiError, get, post, type CampaignConfig, type CampaignRun, type Dataset, type Preview } from '../api'
import { fromInput, toInput, utc } from '../format'
import { t, tDynamic } from '../i18n'

type Section = 'cost_policy' | 'sizing_policy' | 'budget'

function NumberField(props: {
  label: string
  value: string | number
  onChange: (value: string) => void
  step?: string
}): JSX.Element {
  return (
    <label>
      {props.label}
      <input
        type="number"
        step={props.step ?? 'any'}
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
      />
    </label>
  )
}

export function CampaignPanel(props: {
  datasets: Dataset[]
  onStarted: (campaignId: string) => void
}): JSX.Element {
  const usable = props.datasets.filter((dataset) => dataset.manifest.status !== 'rejected')
  const [selected, setSelected] = useState<string[]>([])
  const [config, setConfig] = useState<CampaignConfig | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [previewedJson, setPreviewedJson] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggle(dataset: Dataset): void {
    const key = `${dataset.manifest.symbol}-${dataset.manifest.timeframe}`
    setSelected((current) => {
      if (current.includes(dataset.dataset_id)) {
        return current.filter((id) => id !== dataset.dataset_id)
      }
      // One dataset per pair and timeframe: a new choice replaces the previous one.
      const others = current.filter((id) => {
        const other = usable.find((item) => item.dataset_id === id)
        return other && `${other.manifest.symbol}-${other.manifest.timeframe}` !== key
      })
      return [...others, dataset.dataset_id]
    })
    setConfig(null)
    setPreview(null)
  }

  async function guarded(action: () => Promise<void>): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    } finally {
      setBusy(false)
    }
  }

  const suggest = (): Promise<void> =>
    guarded(async () => {
      const query = selected.map((id) => `dataset_id=${encodeURIComponent(id)}`).join('&')
      setConfig(await get<CampaignConfig>(`/api/campaigns/suggested-config?${query}`))
      setPreview(null)
    })

  const runPreview = (): Promise<void> =>
    guarded(async () => {
      if (config === null) return
      setPreview(await post<Preview>('/api/campaigns/preview', config))
      setPreviewedJson(JSON.stringify(config))
    })

  const start = (): Promise<void> =>
    guarded(async () => {
      if (config === null) return
      const run = await post<CampaignRun>('/api/campaigns', config)
      props.onStarted(run.campaign_id)
    })

  function update(section: Section, field: string, value: string): void {
    if (config === null) return
    const numeric = section === 'budget' ? Number(value) : value
    setConfig({ ...config, [section]: { ...config[section], [field]: numeric } })
  }

  function updateSpan(field: 'requested_start' | 'requested_end', value: string): void {
    if (config === null) return
    setConfig({ ...config, window_policy: { ...config.window_policy, [field]: fromInput(value) } })
  }

  const stale = preview !== null && previewedJson !== JSON.stringify(config)

  return (
    <section aria-labelledby="campaign-heading">
      <h2 id="campaign-heading">{t('campaign.heading')}</h2>
      <fieldset>
        <legend>{t('campaign.selectDatasets')}</legend>
        {usable.length === 0 && <p>{t('campaign.noDataset')}</p>}
        {usable.map((dataset) => (
          <label key={dataset.dataset_id} className="check">
            <input
              type="checkbox"
              checked={selected.includes(dataset.dataset_id)}
              onChange={() => toggle(dataset)}
            />
            {dataset.manifest.symbol} {dataset.manifest.timeframe} ·{' '}
            {tDynamic('provenance', dataset.manifest.provenance)} ·{' '}
            {tDynamic('status', dataset.manifest.status)} · {utc(dataset.manifest.coverage.actual_start)} →{' '}
            {utc(dataset.manifest.coverage.actual_end)}
          </label>
        ))}
        <button type="button" disabled={busy || selected.length === 0} onClick={() => void suggest()}>
          {t('campaign.suggest')}
        </button>
      </fieldset>

      {config !== null && (
        <>
          <fieldset>
            <legend>{t('campaign.span')}</legend>
            <div className="form-row">
              <label>
                {t('campaign.spanStart')}
                <input
                  type="datetime-local"
                  value={toInput(config.window_policy.requested_start)}
                  onChange={(event) => updateSpan('requested_start', event.target.value)}
                />
              </label>
              <label>
                {t('campaign.spanEnd')}
                <input
                  type="datetime-local"
                  value={toInput(config.window_policy.requested_end)}
                  onChange={(event) => updateSpan('requested_end', event.target.value)}
                />
              </label>
            </div>
          </fieldset>
          <fieldset>
            <legend>{t('campaign.budget')}</legend>
            <div className="form-row">
              <NumberField
                label={t('campaign.maxCandidates')}
                step="1"
                value={config.budget.max_candidates}
                onChange={(value) => update('budget', 'max_candidates', value)}
              />
              <NumberField
                label={t('campaign.maxEvaluations')}
                step="1"
                value={config.budget.max_evaluations}
                onChange={(value) => update('budget', 'max_evaluations', value)}
              />
              <NumberField
                label={t('campaign.maxMinutes')}
                step="1"
                value={config.budget.max_active_minutes}
                onChange={(value) => update('budget', 'max_active_minutes', value)}
              />
            </div>
          </fieldset>
          <fieldset>
            <legend>{t('campaign.costs')}</legend>
            <div className="form-row">
              <NumberField
                label={t('campaign.commission')}
                value={String(config.cost_policy.commission_per_lot_per_side)}
                onChange={(value) => update('cost_policy', 'commission_per_lot_per_side', value)}
              />
              <NumberField
                label={t('campaign.slippage')}
                value={String(config.cost_policy.adverse_slippage_points)}
                onChange={(value) => update('cost_policy', 'adverse_slippage_points', value)}
              />
              <NumberField
                label={t('campaign.swapLong')}
                value={String(config.cost_policy.swap_long_points_per_day)}
                onChange={(value) => update('cost_policy', 'swap_long_points_per_day', value)}
              />
              <NumberField
                label={t('campaign.swapShort')}
                value={String(config.cost_policy.swap_short_points_per_day)}
                onChange={(value) => update('cost_policy', 'swap_short_points_per_day', value)}
              />
            </div>
          </fieldset>
          <fieldset>
            <legend>{t('campaign.sizing')}</legend>
            <div className="form-row">
              <NumberField
                label={t('campaign.balance')}
                value={config.sizing_policy.initial_balance}
                onChange={(value) => update('sizing_policy', 'initial_balance', value)}
              />
              <NumberField
                label={t('campaign.volume')}
                value={config.sizing_policy.fixed_volume}
                onChange={(value) => update('sizing_policy', 'fixed_volume', value)}
              />
            </div>
          </fieldset>
          <button type="button" disabled={busy} onClick={() => void runPreview()}>
            {busy ? t('campaign.previewing') : t('campaign.preview')}
          </button>
        </>
      )}

      {preview !== null && (
        <div className="card" aria-labelledby="preview-heading">
          <h3 id="preview-heading">{t('campaign.previewHeading')}</h3>
          <p>{t('campaign.candidates', { count: preview.preview.base_candidate_count })}</p>
          <p>{t('campaign.evaluations', { count: preview.preview.planned_evaluation_count })}</p>
          <ul>
            <li>
              {t('campaign.training')} : {utc(preview.preview.training_start)} →{' '}
              {utc(preview.preview.training_end)}
            </li>
            <li>
              {t('campaign.validation')} : {utc(preview.preview.validation_start)} →{' '}
              {utc(preview.preview.validation_end)}
            </li>
            <li>
              {t('campaign.finalHoldout')} : {utc(preview.preview.final_holdout_start)} →{' '}
              {utc(preview.preview.final_holdout_end)}
            </li>
          </ul>
          {stale && <p className="notice">{t('campaign.configChanged')}</p>}
          {!preview.startable && <p className="notice">{t('campaign.notStartable')}</p>}
          <button
            type="button"
            disabled={busy || stale || !preview.startable}
            onClick={() => void start()}
          >
            {t('campaign.start')}
          </button>
        </div>
      )}
      {error !== null && <p role="alert">{error}</p>}
    </section>
  )
}
