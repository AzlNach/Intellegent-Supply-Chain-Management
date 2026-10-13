# React + TypeScript + Vite

## Run with the local agent-service

1. From the repository root, start the IE agent API (it calls the deployed stock backend and the configured 9Router/OpenRouter endpoint):

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir agent-service --host 127.0.0.1 --port 8000
   ```

   Confirm `http://127.0.0.1:8000/health` returns `{"status":"ok"}`. Put `DEV_TOKEN`, `OPENROUTER_BASE_URL`, and `OPENROUTER_API_KEY` in the repository-root `.env`; keep all credentials server-side.

2. In another terminal, from `frontend/`:

   ```powershell
   Copy-Item .env.example .env.local
   npm install
   npm run dev
   ```

   `.env.local` defaults to `VITE_AGENT_URL=http://127.0.0.1:8000`. Restart Vite after changing it. Vite exposes only the agent-service URL; backend and OpenRouter credentials are never put in frontend variables.

3. Switch the header control from **MOCK** to **LIVE**. Mock mode retains local presets. Live mode replaces those controls with chat, event history, connection status, and approval cards.

Live chat keeps one browser `session_id` in `localStorage`. Multiple messages can be submitted
without locking the composer; requests are queued in order so the agent's session memory stays
consistent. The clarification limit is a soft limit: reaching it does not terminate the session.

The agent-service is local in this stage. For a future deployment, set `VITE_AGENT_URL` to the deployed agent-service URL and update its CORS allowlist for the frontend origin.

## Tests

```powershell
npm run build
npm run lint
npm run test:e2e
npm run test:e2e:live
```

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
