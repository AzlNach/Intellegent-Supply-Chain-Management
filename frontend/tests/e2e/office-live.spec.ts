import { expect, test } from '@playwright/test';

test.describe('virtual office live connectivity @live', () => {
  const agentUrl = process.env.AGENT_SERVICE_URL ?? 'http://127.0.0.1:8000';

  test('agent service health, LLM health, and websocket handshake', async ({ page, request }) => {
    test.setTimeout(120_000);
    const agentHealth = await request.get(`${agentUrl}/health`);
    expect(agentHealth.status()).toBe(200);
    expect((await agentHealth.json()).status).toBe('ok');

    await page.goto('/');
    const wsBase = agentUrl.replace(/^http/, 'ws');
    const wsResult = await page.evaluate(async (baseUrl) => new Promise<string>((resolve) => {
      const wsUrl = baseUrl;
      const socket = new WebSocket(`${wsUrl}/ws/TEST-VO-PLAYWRIGHT`);
      const timeout = window.setTimeout(() => { socket.close(); resolve('timeout'); }, 8000);
      socket.addEventListener('open', () => {
        window.clearTimeout(timeout);
        socket.close();
        resolve('open');
      }, { once: true });
      socket.addEventListener('error', () => {
        window.clearTimeout(timeout);
        resolve('error');
      }, { once: true });
    }), wsBase);
    expect(wsResult).toBe('open');
  });

  test('direct OpenRouter health is connected @live', async ({ request }) => {
    const response = await request.get(`${agentUrl}/health/llm`, { timeout: 100_000 });
    expect(response.status()).toBe(200);
    const body = await response.json();
    test.skip(!body.connected, 'Set OPENROUTER_API_KEY in the ISCM root .env to enable authenticated live LLM checks.');
    expect(body.available_models_count).toBeGreaterThan(0);
  });

  test('frontend live mode connects and exposes chat/event panels @live', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'MOCK' }).click();
    await expect(page.getByText('IE AGENT — LIVE')).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Tulis pesan untuk IE Agent...' })).toBeVisible();
    await expect(page.getByText('Terhubung')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/EVENT LOG/)).toBeVisible();
  });
});
