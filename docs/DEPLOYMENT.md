# Deployment: Render (backend) + Vercel (frontend)

Nothing in this repository has been deployed. These steps were checked against the current Render Blueprint
reference; the Docker image was built and smoke-tested locally against PostgreSQL 16 and Redis 7.

## Services

| Component | Host | Exposure |
| --- | --- | --- |
| `clauselens-api` (FastAPI, Docker) | Render web service | public HTTPS |
| `clauselens-worker` (Celery, same image) | Render background worker | none |
| `clauselens-db` (PostgreSQL) | Render Postgres | private network (`ipAllowList: []`) |
| `clauselens-redis` (Celery broker) | Render Key Value, `noeviction` | private network (`ipAllowList: []`) |
| Frontend (static Vite build) | Vercel | public |
| TinyFish, Ollama Cloud | external SaaS | called from the worker only |

Investigations run in the worker, so they continue if the browser disconnects; progress is read from the database.

## Backend on Render

1. Push the repository to GitHub.
2. Render Dashboard → **New → Blueprint** → select the repo. Render reads `render.yaml`.
3. When prompted, enter the `sync: false` secrets for both services:
   `TINYFISH_API_KEY`, `LLM_API_KEY` (Ollama API key) and `CORS_ORIGINS` (your Vercel URL, e.g.
   `https://clauselens.vercel.app`; comma-separate several, never `*`).
4. Migrations run via `preDeployCommand: alembic upgrade head` before each API deploy (Render requires a paid
   instance type for pre-deploy commands; on the free tier run `alembic upgrade head` once from the service Shell).
5. Verify: `https://<api>.onrender.com/health` → `{"status":"ok"}` and `/ready` → all checks `ok`.

`DATABASE_URL` and `REDIS_URL` are injected from the managed services; `postgresql://` URLs are converted to the
psycopg driver automatically. In `ENVIRONMENT=production` the app refuses to start with demo providers, a non-durable
queue, a non-PostgreSQL database or wildcard CORS.

## Frontend on Vercel

1. Vercel → **Add New Project** → import the repo, set **Root Directory** to `frontend` (framework: Vite;
   `vercel.json` supplies build, output and SPA rewrites).
2. Environment variable: `VITE_API_BASE_URL=https://<api>.onrender.com` (build-time; no secrets in the frontend).
3. Deploy, then make sure the Vercel domain is in the API's `CORS_ORIGINS`.

## Environment variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `ENVIRONMENT` | yes (prod) | `development` | `production` enables safety checks |
| `DATABASE_URL` | yes | local Postgres | PostgreSQL in production |
| `REDIS_URL` | with celery | `redis://localhost:6379/0` | Celery broker |
| `CORS_ORIGINS` | yes (prod) | `http://localhost:5173` | explicit origins |
| `WEB_RESEARCH_PROVIDER` | | `tinyfish` | `tinyfish` / `fixture` (demo) |
| `TINYFISH_API_KEY` | with tinyfish | none | secret |
| `RESEARCH_MAX_PAGES_PER_VENDOR` | | `6` | ≤ 10 |
| `LLM_PROVIDER` | | `ollama` | `ollama` / `openai_compatible` / `fixture` (demo) |
| `LLM_BASE_URL` | | `https://ollama.com` | `/v1` URL for openai_compatible |
| `LLM_API_KEY` | with Ollama Cloud | none | secret |
| `LLM_MODEL` | | `gpt-oss:120b` | any id from `/api/tags` |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` / `LLM_MAX_CONCURRENCY` | | 120 / 2 / 4 | |
| `LLM_OUTPUT_MODE` | | `prompt` | `prompt`, `json`, `schema` |
| `LLM_THINK` | | `low` | model-specific; empty to omit |
| `JOB_QUEUE_PROVIDER` | | `celery` | `celery`; `inline`/`sync` are dev/test only |
| `MAX_VENDORS_PER_INVESTIGATION` | | `5` | |
| `RATE_LIMIT_INVESTIGATIONS_PER_MINUTE` | | `10` | per client, per API process |
| `SCORING_POLICY_JSON` | | built-in | e.g. `{"longest_refund_window":3}` |
| `STORAGE_PROVIDER` | | `none` | `local` keeps raw research payloads |
| `VITE_API_BASE_URL` | frontend | empty | API origin |

## Moving hosts

Any container platform can run the same image with `uvicorn ...` and `celery -A clauselens.worker worker -Q
investigations`, plus the variables above. Any static host can serve `frontend/dist` with an `index.html` fallback.
No application code changes are needed.
