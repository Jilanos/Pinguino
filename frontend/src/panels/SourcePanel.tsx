import { useCallback, useEffect, useState } from 'react'

import { fetchSourceDiagnostic, type SourceDiagnostic } from '../api'
import { t } from '../i18n'

type Status =
  | { kind: 'loading' }
  | { kind: 'ready'; diagnostic: SourceDiagnostic }
  | { kind: 'unreachable' }

export function SourcePanel(): JSX.Element {
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  const load = useCallback((signal?: AbortSignal) => {
    setStatus({ kind: 'loading' })
    fetchSourceDiagnostic(signal)
      .then((diagnostic) => setStatus({ kind: 'ready', diagnostic }))
      .catch(() => {
        if (!signal?.aborted) setStatus({ kind: 'unreachable' })
      })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  const diagnostic = status.kind === 'ready' ? status.diagnostic : null
  const symbols = Object.entries(diagnostic?.available_symbols ?? {})

  return (
    <section aria-labelledby="source-heading">
      <h2 id="source-heading">{t('source.heading')}</h2>
      {status.kind === 'loading' && <p>{t('source.checking')}</p>}
      {status.kind === 'unreachable' && <p role="alert">{t('source.unreachable')}</p>}
      {diagnostic !== null && (
        <>
          <p className={diagnostic.code ? 'notice' : 'ok'}>
            {diagnostic.code || diagnostic.synthetic_mode_only
              ? (diagnostic.message ?? t('source.syntheticOnly'))
              : t('source.available')}
          </p>
          {diagnostic.terminal_available && (
            <>
              <p>
                {t('source.build', {
                  build: diagnostic.terminal_build ?? '?',
                  version: diagnostic.package_version ?? '?',
                })}
              </p>
              <p>
                {symbols.length > 0
                  ? t('source.symbols', {
                      symbols: symbols.map(([pair, name]) => `${pair} → ${name}`).join(', '),
                    })
                  : t('source.noSymbols')}
              </p>
            </>
          )}
        </>
      )}
      <p className="help">{t('source.setupHelp')}</p>
      <button type="button" onClick={() => load()}>
        {t('source.refresh')}
      </button>
    </section>
  )
}
