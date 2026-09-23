import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const fr = JSON.parse(
  readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../src/i18n/fr.json'), 'utf-8'),
)

// Opt-in: requires Windows, the MetaTrader5 package and a connected demo terminal.
const START = process.env.PINGUINO_E2E_MT5_START
const END = process.env.PINGUINO_E2E_MT5_END
const SYMBOL = process.env.PINGUINO_E2E_MT5_SYMBOL ?? 'EURUSD'

test.skip(!START || !END, 'set PINGUINO_E2E_MT5_START and PINGUINO_E2E_MT5_END (UTC, YYYY-MM-DDTHH:MM)')

test('real MT5 journey: diagnose, import, campaign, inspect, export', async ({ page }) => {
  test.setTimeout(900_000)
  const started = Date.now()
  await page.goto('/')
  await expect(page.getByText(fr.source.available)).toBeVisible()
  await expect(page.getByText(/Symboles disponibles dans le terminal/)).toBeVisible()

  await page.getByRole('button', { name: fr.nav.datasets }).click()
  await page.getByLabel(fr.datasets.symbol).selectOption(SYMBOL)
  await page.getByLabel(fr.datasets.timeframe).selectOption('H1')
  await page.getByLabel(fr.datasets.start).fill(START as string)
  await page.getByLabel(fr.datasets.end).fill(END as string)
  const importStarted = Date.now()
  await page.getByRole('button', { name: fr.datasets.importMt5 }).click()
  const card = page.getByRole('heading', { name: new RegExp(`${SYMBOL} H1 — .* · Terminal MetaTrader 5`) })
  await expect(card).toBeVisible({ timeout: 600_000 })
  const importSeconds = (Date.now() - importStarted) / 1000
  const heading = (await card.textContent()) ?? ''
  expect(heading).not.toContain('Rejeté')

  await page.getByRole('button', { name: fr.nav.campaign }).click()
  await page.getByRole('checkbox', { name: /Terminal MetaTrader 5/ }).first().check()
  await page.getByRole('button', { name: fr.campaign.suggest }).click()
  await page.getByRole('button', { name: fr.campaign.preview }).click()
  await expect(page.getByText(/Candidats de base : 32/)).toBeVisible()
  const campaignStarted = Date.now()
  await page.getByRole('button', { name: fr.campaign.start }).click()
  await expect(page.getByRole('region', { name: fr.run.heading }).getByRole('heading', { level: 3 }).first()).toHaveText(/— (Terminée|Partielle)/, {
    timeout: 900_000,
  })
  const campaignSeconds = (Date.now() - campaignStarted) / 1000
  await page.getByRole('button', { name: fr.run.open }).first().click()
  await expect(page.locator('tbody tr').first()).toBeVisible()

  await page.locator('tbody tr').first().getByRole('button', { name: fr.results.details }).click()
  await expect(page.getByRole('img', { name: fr.detail.equity })).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('link', { name: fr.detail.export }).click()
  const bytes = readFileSync(await (await download).path())
  expect(bytes.subarray(0, 2).toString()).toBe('PK')

  for (const [type, value] of [
    ['dataset_heading', heading],
    ['import_seconds', importSeconds.toFixed(1)],
    ['campaign_seconds', campaignSeconds.toFixed(1)],
    ['total_seconds', ((Date.now() - started) / 1000).toFixed(1)],
  ]) {
    test.info().annotations.push({ type, description: value })
  }
})
