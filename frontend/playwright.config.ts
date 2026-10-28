import { defineConfig, devices } from "@playwright/test";

// Deterministic end-to-end run: real FastAPI backend with clearly labelled demo
// fixture providers (no paid APIs), SQLite created by Alembic, in-process jobs.
const backendEnv = [
  "ENVIRONMENT=test",
  "WEB_RESEARCH_PROVIDER=fixture",
  "LLM_PROVIDER=fixture",
  "JOB_QUEUE_PROVIDER=inline",
  "DATABASE_URL=sqlite:///./var/e2e.db",
  "CORS_ORIGINS=http://localhost:4174",
  "RATE_LIMIT_INVESTIGATIONS_PER_MINUTE=1000",
].join(" ");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  use: { baseURL: "http://localhost:4174", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `cd ../backend && rm -f var/e2e.db && mkdir -p var && env ${backendEnv} .venv/bin/alembic upgrade head && env ${backendEnv} .venv/bin/uvicorn clauselens.main:app --port 8001`,
      url: "http://localhost:8001/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run build && CLAUSELENS_DEV_BACKEND=http://localhost:8001 npx vite preview --port 4174 --strictPort",
      url: "http://localhost:4174",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
