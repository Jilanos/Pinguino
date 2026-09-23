import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const fr = JSON.parse(
  readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../src/i18n/fr.json'), 'utf-8'),
)

test('synthetic fixture journey: import, campaign, inspect, final evaluation, export', async ({
  page,
}) => {
  const started = Date.now()
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(fr.app.title)
  await expect(page.getByText(fr.disclaimer.noOrders)).toBeVisible()
  await expect(page.getByText(fr.source.checking)).toBeHidden()

  await page.getByRole('button', { name: fr.nav.datasets }).click()
  await page.getByRole('button', { name: fr.datasets.importFixture }).click()
  await expect(page.getByRole('heading', { name: /EURUSD H1 — Approximatif · Fixture synthétique/ })).toBeVisible()
  await expect(page.getByText(fr.disclaimer.synthetic).first()).toBeVisible()

  await page.getByRole('button', { name: fr.nav.campaign }).click()
  await page.getByRole('checkbox', { name: /Fixture synthétique/ }).first().check()
  await page.getByRole('button', { name: fr.campaign.suggest }).click()
  await page.getByLabel(fr.campaign.maxCandidates).fill('4')
  await page.getByRole('button', { name: fr.campaign.preview }).click()
  await expect(page.getByText('Candidats de base : 4')).toBeVisible()
  await page.getByRole('button', { name: fr.campaign.start }).click()

  await expect(page.getByRole('region', { name: fr.run.heading }).getByRole('heading', { level: 3 }).first()).toHaveText(/— Terminée/, { timeout: 120_000 })
  // Runs are listed newest first.
  await page.getByRole('button', { name: fr.run.open }).first().click()
  await expect(page.getByText(fr.state.noCandidate)).toBeVisible()
  const rows = page.locator('tr.verdict-inconclusive')
  await expect(rows).toHaveCount(4)

  await rows.first().getByRole('button', { name: fr.results.details }).click()
  await expect(page.getByRole('img', { name: fr.detail.equity })).toBeVisible()

  await page.getByLabel(fr.holdout.reason).fill('candidat figé pour la preuve e2e')
  await page.getByRole('button', { name: fr.holdout.open }).click()
  await expect(page.getByText(/Échantillon final ouvert/)).toBeVisible()

  const download = page.waitForEvent('download')
  await page.getByRole('link', { name: fr.detail.export }).click()
  const file = await (await download).path()
  const bytes = readFileSync(file)
  expect(bytes.subarray(0, 2).toString()).toBe('PK')

  test.info().annotations.push({
    type: 'duration_seconds',
    description: ((Date.now() - started) / 1000).toFixed(1),
  })
})
