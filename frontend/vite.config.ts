import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const API_PORT = process.env.PINGUINO_PORT ?? '8787'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': `http://127.0.0.1:${API_PORT}`,
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
