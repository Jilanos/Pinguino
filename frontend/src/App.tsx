import { useEffect, useState } from 'react'

import { fetchSourceDiagnostic, type SourceDiagnostic } from './api'
import { t } from './i18n'

type Status =
  | { kind: 'loading' }
  | { kind: 'ready'; diagnostic: SourceDiagnostic }
  | { kind: 'unreachable' }

export function SourcePanel(): JSX.Element {
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchSourceDiagnostic(controller.signal)
      .then((diagnostic) => setStatus({ kind: 'ready', diagnostic }))
      .catch(() => setStatus({ kind: 'unreachable' }))
    return () => controller.abort()
  }, [])

  return (
    <section aria-labelledby="source-heading">
      <h2 id="source-heading">{t('source.heading')}</h2>
      {status.kind === 'loading' && <p>{t('source.checking')}</p>}
      {status.kind === 'unreachable' && <p role="alert">{t('source.unreachable')}</p>}
      {status.kind === 'ready' && (
        <p>
          {status.diagnostic.synthetic_mode_only
            ? (status.diagnostic.message ?? t('source.syntheticOnly'))
            : t('source.available')}
        </p>
      )}
    </section>
  )
}

export function App(): JSX.Element {
  return (
    <main lang="fr">
      <h1>{t('app.title')}</h1>
      <p>{t('app.subtitle')}</p>
      <SourcePanel />
      <footer>
        <p>{t('disclaimer.noOrders')}</p>
      </footer>
    </main>
  )
}
