import { expect, test } from '@playwright/test';

declare global {
  interface Window {
    __VO_DEV__?: {
      getState: () => {
        agentState: string;
        bubbleText: string;
        boardData: { fields: Record<string, { value: unknown; status: string; source: string }> };
        solverState: string;
        character: { x: number; y: number; seated: boolean; walking: boolean };
      };
      getCanvasMetrics: () => {
        backingWidth: number;
        backingHeight: number;
        displayWidth: number;
        displayHeight: number;
        sourceWidth: number;
        sourceHeight: number;
        scaleMode: string;
        tickerStarted: boolean;
      };
      pauseTicker: () => void;
      resumeTicker: () => void;
    };
  }
}

test.describe('virtual office mock UI @mock', () => {
  test('starts, exposes a sharp canvas, and has no fatal browser errors or secrets in browser requests', async ({ page }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    const browserRequests: string[] = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));
    page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()); });
    page.on('request', (request) => {
      const headers = request.headers();
      expect(headers['x-dev-token']).toBeUndefined();
      expect(headers.authorization).toBeUndefined();
      browserRequests.push(request.url());
    });

    await page.goto('/?qaFreeze=1');
    await expect(page.locator('.office-canvas-wrapper canvas')).toBeVisible();
    await expect(page.getByText('OFFICE 3D DEBUG PANEL')).toBeVisible();
    await expect.poll(() => page.evaluate(() => Boolean(window.__VO_DEV__))).toBe(true);

    const metrics = await page.evaluate(() => window.__VO_DEV__!.getCanvasMetrics());
    expect(metrics.backingWidth).toBe(960);
    expect(metrics.backingHeight).toBe(540);
    expect(metrics.scaleMode).toBe('nearest');
    expect(metrics.sourceWidth).toBeGreaterThanOrEqual(352);
    expect(metrics.sourceHeight).toBeGreaterThanOrEqual(196);
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
    expect(browserRequests.some((url) => /stock-copilot-backend|20128|openrouter/i.test(url))).toBe(false);
    expect(browserRequests.every((url) => !/[?&](token|key|api_key)=/i.test(url))).toBe(true);
  });

  test('debug panel triggers every agent state with the required bubble label', async ({ page }) => {
    await page.goto('/?qaFreeze=1');
    await expect.poll(() => page.evaluate(() => Boolean(window.__VO_DEV__))).toBe(true);
    const stateCases = [
      ['Idle', 'idle', 'Menunggu tugas'],
      ['Reading Board', 'reading_board', 'Membaca papan'],
      ['Working', 'working', 'Memproses data'],
      ['Waiting', 'waiting', 'Menunggu jawaban Anda'],
      ['Reporting', 'reporting', 'Melapor'],
    ] as const;

    const agentButtons = [
      page.getByRole('button', { name: /Idle.*Duduk & ketik santai/ }),
      page.getByRole('button', { name: /Reading Board.*Jalan ke papan tulis/ }),
      page.getByRole('button', { name: /Working.*Ketik cepat aktif/ }),
      page.getByRole('button', { name: /Waiting.*Duduk \+ ikon/ }),
      page.getByRole('button', { name: /Reporting.*Jalan ke meja Head/ }),
    ];
    for (const [button, state, bubble] of stateCases) {
      const index = stateCases.findIndex(([label]) => label === button);
      await agentButtons[index].click();
      await expect.poll(() => page.evaluate(() => window.__VO_DEV__!.getState().agentState)).toBe(state);
      await expect.poll(() => page.evaluate(() => window.__VO_DEV__!.getState().bubbleText)).toBe(bubble);
    }
  });

  test('mock/live switch swaps panels; live client uses localhost agent-service only', async ({ page }) => {
    const serviceRequests: string[] = [];
    page.on('request', (request) => {
      if (request.url().includes('127.0.0.1:8000')) serviceRequests.push(request.url());
    });
    page.on('websocket', (socket) => {
      if (socket.url().includes('127.0.0.1:8000')) serviceRequests.push(socket.url());
    });
    await page.goto('/?qaFreeze=1');
    await page.getByRole('button', { name: 'MOCK' }).click();
    await expect(page.getByText('IE AGENT — LIVE')).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Tulis pesan untuk IE Agent...' })).toBeVisible();
    await expect(page.getByText(/EVENT LOG/)).toBeVisible();
    await expect(page.getByText('Terhubung')).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: 'LIVE' }).click();
    await expect(page.getByText('OFFICE 3D DEBUG PANEL')).toBeVisible();
    expect(serviceRequests.some((url) => url.endsWith('/ws/')) || serviceRequests.some((url) => url.includes('/ws/'))).toBe(true);
    expect(serviceRequests.every((url) => url.includes('127.0.0.1:8000'))).toBe(true);
  });

  test('board debug toggles update field status and sources; solver state updates neon state', async ({ page }) => {
    await page.goto('/?qaFreeze=1');
    await expect.poll(() => page.evaluate(() => Boolean(window.__VO_DEV__))).toBe(true);

    await page.getByRole('button', { name: 'On Hand: Conflict' }).click();
    let state = await page.evaluate(() => window.__VO_DEV__!.getState());
    expect(state.boardData.fields.on_hand_qty.status).toBe('conflict');
    expect(state.boardData.fields.on_hand_qty.source).toBe('user_vs_db');

    await page.getByRole('button', { name: 'Outgoing: Undefined' }).click();
    state = await page.evaluate(() => window.__VO_DEV__!.getState());
    expect(state.boardData.fields.expected_outgoing_qty.status).toBe('undefined');

    await page.getByRole('button', { name: /Working \(Pulsing\)/ }).click();
    await expect.poll(() => page.evaluate(() => window.__VO_DEV__!.getState().solverState)).toBe('working');
    await page.getByRole('button', { name: /Done \(Ready\)/ }).click();
    await expect.poll(() => page.evaluate(() => window.__VO_DEV__!.getState().solverState)).toBe('done');
  });

  test('canvas fits desktop, tablet, and mobile without clipping its wrapper', async ({ page }) => {
    await page.goto('/?qaFreeze=1');
    const viewports = [
      { width: 1440, height: 900 },
      { width: 768, height: 1024 },
      { width: 390, height: 844 },
    ];
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const bounds = await page.locator('.office-canvas-wrapper').boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds!.x).toBeGreaterThanOrEqual(0);
      expect(bounds!.y).toBeGreaterThanOrEqual(0);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width + 1);
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport.height + 1);
    }
  });

  test('pixel-office baseline @visual', async ({ page }) => {
    await page.goto('/?qaFreeze=1');
    const canvas = page.locator('.office-canvas-wrapper canvas');
    await expect(canvas).toBeVisible();
    const states = [
      ['Idle', 'idle'], ['Reading Board', 'reading_board'], ['Working', 'working'],
      ['Waiting', 'waiting'], ['Reporting', 'reporting'],
    ] as const;
    for (const [label, expectedState] of states) {
      const agentButton = {
        Idle: /Idle.*Duduk & ketik santai/,
        'Reading Board': /Reading Board.*Jalan ke papan tulis/,
        Working: /Working.*Ketik cepat aktif/,
        Waiting: /Waiting.*Duduk \+ ikon/,
        Reporting: /Reporting.*Jalan ke meja Head/,
      }[label];
      await page.getByRole('button', { name: agentButton }).click();
      await expect.poll(() => page.evaluate(() => window.__VO_DEV__!.getState().agentState)).toBe(expectedState);
      if (expectedState === 'reading_board') {
        await expect.poll(() => page.evaluate(() => window.__VO_DEV__!.getState().character.walking), { timeout: 8_000 }).toBe(false);
      }
      if (expectedState === 'reporting') {
        await expect.poll(() => page.evaluate(() => {
          const c = window.__VO_DEV__!.getState().character;
          return !c.walking && Math.abs(c.x - 3.17) < 0.3 && Math.abs(c.y - 4.7) < 0.3;
        }), { timeout: 12_000 }).toBe(true);
      }
      await page.evaluate(() => window.__VO_DEV__!.pauseTicker());
      try {
        await expect(canvas).toHaveScreenshot(`office-${expectedState.replace('_', '-')}.png`, {
          animations: 'disabled',
          maxDiffPixelRatio: 0.015,
          timeout: 10_000,
        });
      } finally {
        await page.evaluate(() => window.__VO_DEV__!.resumeTicker());
      }
    }
  });

});
