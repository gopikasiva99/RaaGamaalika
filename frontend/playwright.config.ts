import { defineConfig } from '@playwright/test'

// Runs against a running server (docker run -p 8080:8080 raagamaalika, or uvicorn) at E2E_BASE_URL.
export default defineConfig({
  testDir: 'e2e',
  timeout: 90_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    viewport: { width: 390, height: 844 },
    launchOptions: {
      executablePath: process.env.PW_CHROMIUM_PATH || undefined,
      args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
    },
    permissions: ['microphone'],
  },
  reporter: [['list']],
})
