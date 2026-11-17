import { expect, test } from '@playwright/test'
import { mohanamWav } from './synth'

test('upload a Mohanam clip and see Mohanam in the result', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Which raga is this?')).toBeVisible()
  await page.getByLabel('Upload a recording').setInputFiles({
    name: 'mohanam.wav', mimeType: 'audio/wav', buffer: mohanamWav(),
  })
  await expect(page.getByText('Mohanam').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('Detected shruti:')).toBeVisible()
  // the result is remembered on the device
  await page.getByRole('link', { name: 'Recent' }).click()
  await expect(page.getByText(/mohanam\.wav/)).toBeVisible()
})

test('live listening records from the microphone and returns a result', async ({ page }) => {
  await page.goto('/#/listen')
  await expect(page.getByText("We'll listen for about 45 seconds. Audio is analysed and never stored.")).toBeVisible()
  await page.getByRole('button', { name: 'Start listening' }).click()
  await expect(page.getByRole('button', { name: 'Stop & identify' })).toBeVisible()
  await page.waitForTimeout(11_500)
  await page.getByRole('button', { name: 'Stop & identify' }).click()
  // Chromium's fake microphone plays beeps: any result screen proves the capture → WAV → API path.
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 60_000 })
  await expect(page).toHaveURL(/#\/result/)
})

test('a raga page loads from search-free deep link', async ({ page }) => {
  await page.goto('/#/raga/mohanam')
  await expect(page.getByRole('heading', { name: 'Mohanam' })).toBeVisible()
  await expect(page.getByText('S R2 G3 P D2 S')).toBeVisible()
})
