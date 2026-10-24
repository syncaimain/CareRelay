import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', timeout: 300_000, workers: 1,
  use: {baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3104', trace: 'retain-on-failure', screenshot: 'only-on-failure'},
  projects: [{name: 'chromium', use: {...devices['Desktop Chrome']}}],
  // Start the backend and frontend separately. Tests use genuine model inference.
});
