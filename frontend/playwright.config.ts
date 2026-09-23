import { rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from '@playwright/test'

const PORT = process.env.PINGUINO_E2E_PORT ?? '8799'
const DATA_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '.e2e-data')

// Every run starts from an empty local store. Test workers re-evaluate this file while
// the server is running, so only the main process clears it.
if (process.env.TEST_WORKER_INDEX === undefined) {
  rmSync(DATA_DIR, { recursive: true, force: true })
}

export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  // Both journeys share one server and one store.
  workers: 1,
  fullyParallel: false,
  expect: { timeout: 60_000 },
  reporter: [['list'], ['json', { outputFile: 'test-results/e2e-report.json' }]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, headless: true },
  webServer: {
    command: 'uv run --project ../backend python -m pinguino',
    url: `http://127.0.0.1:${PORT}/api/health`,
    timeout: 120_000,
    reuseExistingServer: false,
    env: { PINGUINO_PORT: PORT, PINGUINO_DATA_DIR: DATA_DIR },
  },
})
