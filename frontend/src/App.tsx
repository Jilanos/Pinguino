import { useCallback, useEffect, useState } from 'react'

import { get, type Dataset } from './api'
import { t, type MessageKey } from './i18n'
import { CampaignPanel } from './panels/CampaignPanel'
import { DatasetsPanel } from './panels/DatasetsPanel'
import { ResultsPanel } from './panels/ResultsPanel'
import { RunsPanel } from './panels/RunsPanel'
import { SourcePanel } from './panels/SourcePanel'

export { SourcePanel }

type Tab = 'setup' | 'datasets' | 'campaign' | 'results'
const TABS: Tab[] = ['setup', 'datasets', 'campaign', 'results']

export function App(): JSX.Element {
  const [tab, setTab] = useState<Tab>('setup')
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [campaignId, setCampaignId] = useState<string | null>(null)
  const [opened, setOpened] = useState(0)

  function openCampaign(id: string): void {
    setCampaignId(id)
    setOpened((value) => value + 1)
  }

  const loadDatasets = useCallback(() => {
    get<Dataset[]>('/api/datasets')
      .then((loaded) => setDatasets(Array.isArray(loaded) ? loaded : []))
      .catch(() => setDatasets([]))
  }, [])

  useEffect(() => {
    if (tab === 'datasets' || tab === 'campaign') loadDatasets()
  }, [tab, loadDatasets])

  return (
    <main lang="fr">
      <h1>{t('app.title')}</h1>
      <p>{t('app.subtitle')}</p>
      <nav aria-label="Sections">
        {TABS.map((value) => (
          <button
            key={value}
            type="button"
            aria-current={tab === value ? 'page' : undefined}
            onClick={() => setTab(value)}
          >
            {t(`nav.${value}` as MessageKey)}
          </button>
        ))}
      </nav>
      {tab === 'setup' && <SourcePanel />}
      {tab === 'datasets' && <DatasetsPanel datasets={datasets} onImported={loadDatasets} />}
      {tab === 'campaign' && (
        <CampaignPanel
            datasets={datasets}
            onStarted={(id) => {
              openCampaign(id)
              setTab('results')
            }}
          />
      )}
      {tab === 'results' && (
        <>
          <RunsPanel onOpen={openCampaign} />
          <ResultsPanel key={`${campaignId ?? 'none'}-${opened}`} campaignId={campaignId} />
        </>
      )}
      <footer>
        <p>{t('disclaimer.noOrders')}</p>
      </footer>
    </main>
  )
}
