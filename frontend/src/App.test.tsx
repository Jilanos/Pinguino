import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { messages, t } from './i18n'

function mockDiagnostic(body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('French shell', () => {
  it('renders the French title and the no-order disclaimer', async () => {
    mockDiagnostic({ synthetic_mode_only: false })
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(t('app.title'))
    expect(await screen.findByText(t('source.available'))).toBeInTheDocument()
    expect(screen.getByText(t('disclaimer.noOrders'))).toBeInTheDocument()
  })

  it('shows synthetic-only state instead of an error when MT5 is absent', async () => {
    mockDiagnostic({ synthetic_mode_only: true, message: 'Message du serveur' })
    render(<App />)
    expect(await screen.findByText('Message du serveur')).toBeInTheDocument()
  })

  it('shows an unreachable-service state when the API does not answer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('offline')
      }),
    )
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent(t('source.unreachable'))
  })

  it('has no empty message in the French source catalogue', () => {
    for (const [key, value] of Object.entries(messages())) {
      expect(value.trim(), `empty message for ${key}`).not.toBe('')
    }
  })
})
