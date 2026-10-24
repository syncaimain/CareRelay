import { test, expect } from '@playwright/test';

test('source → genuine extraction → review → consent → handoff', async ({page}) => {
  await page.goto('/');
  await page.getByRole('button', {name:'Create fictional care circle'}).click();
  await expect(page.getByRole('heading', {name:'Good to see you, Alex.'})).toBeVisible();
  await page.getByRole('button', {name:'Import messages', exact:true}).click();
  await page.getByLabel('Messages and notes').fill('Alex will book transport to Oak Clinic on 2026-10-26 at 09:00.');
  await expect(page.getByRole('button', {name:'Find coordination tasks'})).toBeEnabled({timeout:20_000});
  await page.getByRole('button', {name:'Find coordination tasks'}).click();
  await expect(page.getByRole('heading', {name:'Review queue',exact:true})).toBeVisible({timeout:240_000});
  const card = page.locator('.review-card').first();
  await expect(card.locator('blockquote')).toContainText('Alex will book transport');
  // Review includes confirming the source's date, including when a model leaves it unresolved.
  await card.getByLabel('Due date & time (PKT)').fill('2026-10-26T09:00');
  await card.getByLabel('Open questions / uncertainty').fill('');
  await card.getByLabel('I checked the source', {exact:false}).check();
  await card.getByRole('button', {name:'Approve suggestion'}).click();
  await expect(card).not.toBeVisible();
  await page.getByRole('button', {name:'Responsibility board',exact:true}).click();
  await page.getByRole('button', {name:'I can take this'}).first().click();
  await expect(page.getByText('Accepted responsibility')).toBeVisible();
  await page.getByRole('button', {name:'Handoffs',exact:true}).click();
  await page.getByRole('button', {name:'Prepare day brief'}).click();
  await expect(page.locator('.handoff-text')).toContainText('source #', {timeout:240_000});
  await expect(page.getByRole('button', {name:'Copy approved handoff'})).not.toBeVisible();
  await page.getByRole('button', {name:'Approve for manual sharing'}).click();
  await expect(page.getByRole('button', {name:'Copy approved handoff'})).toBeVisible();
});
