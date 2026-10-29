# ClauseLens

**See beyond the fine print.** ClauseLens investigates vendors' official websites, extracts refund, cancellation,
renewal, trial and return terms with an LLM, verifies every quote against the retrieved page, and compares vendors
with a deterministic engine. Each value links back to the exact source text.

ClauseLens provides policy analysis, not legal advice.

```
React (Vercel) ──HTTPS──► FastAPI (Render web) ──► PostgreSQL
                                 │  enqueue                ▲
                                 ▼                         │
                           Redis (Key Value) ──► Celery worker (Render)
                                                   │            │
                     TinyFish Search + Fetch (browse) │ OpenRouter chat/completions (analyse)
```

| Layer | Path | Notes |
| --- | --- | --- |
| Domain (pure) | `backend/clauselens/domain` | policy schema, evidence verification, aggregation, deterministic comparison |
| Ports | `backend/clauselens/ports` | `ResearchProvider`, `LLMProvider`, `Repository`, `JobQueue`, `ArtifactStorage` |
| Services | `backend/clauselens/services` | extraction, explanation, orchestration |
| Adapters | `backend/clauselens/adapters` | TinyFish, Ollama, OpenAI-compatible, SQLAlchemy/Postgres, Celery, local storage, demo fixtures |
| Composition | `backend/clauselens/{config,registry,container}.py` | configuration selects adapters |
| API | `backend/clauselens/api` | thin FastAPI routes, SSE progress |
| Frontend | `frontend/` | React + TS (strict) + Vite + Tailwind + TanStack Query, styled from the product deck |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (boundaries and how to replace each provider),
[docs/PROVIDERS.md](docs/PROVIDERS.md) (verified TinyFish / Ollama contracts and model choice) and
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (Render + Vercel).

## How TinyFish and OpenRouter work together

They have separate jobs:

1. **TinyFish** browses: it finds each vendor's official policy pages and returns their text.
2. **OpenRouter** analyses that text with the model in `OPENROUTER_MODEL`. It is used for:
   - policy-term extraction (refund window, fees, ...) that feeds the comparison table, and
   - the **risky-clause scan**, which returns per vendor a list of
     `{clause, risk_level, explanation, reason, category, evidence: {quote, source_url, retrieved_at, verification}}`.
3. The backend validates every model answer: JSON is schema-checked (with one repair attempt), and every quote is
   matched against the TinyFish page text. Quotes that are not on the page are shown as "unconfirmed".

Long pages are split into sections (`RISK_CHUNK_CHARS`) with a per-vendor cap (`RISK_MAX_CHUNKS_PER_VENDOR`); the
report says when a document was truncated. Rate limits (HTTP 429 with `Retry-After`), provider outages, errors that
OpenRouter returns inside an HTTP 200 body, empty or truncated outputs and malformed JSON are retried where it makes
sense and otherwise reported per vendor without failing the whole report.

### OpenRouter setup

1. Create a key at https://openrouter.ai/keys and add credits if your model is not free.
2. In `backend/.env` (copied from `backend/.env.example`):

   ```
   LLM_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-...
   OPENROUTER_MODEL=google/gemini-2.5-flash
   ```

3. Restart the backend. `/api/meta` should show `"llm_provider": "openrouter"`.

The key is read only by the backend (`SecretStr`, redacted from logs, never returned by the API or sent to the
browser). `.env` is git-ignored; only `.env.example` with placeholders is committed.

## Quick start (local)

Prerequisites: Python 3.12, Node 22, PostgreSQL 16, Redis 7 (or use `docker compose up`).

```bash
cd backend && uv venv -p 3.12 .venv && uv pip install -e ".[dev]"
```

```bash
cp backend/.env.example backend/.env   # then fill in TINYFISH_API_KEY and LLM_API_KEY
```

```bash
cd backend && .venv/bin/alembic upgrade head
```

```bash
cd backend && .venv/bin/uvicorn clauselens.main:app --reload --port 8000
```

```bash
cd backend && .venv/bin/celery -A clauselens.worker worker --loglevel INFO -Q investigations
```

```bash
cd frontend && npm ci && npm run dev    # http://localhost:5173 (proxies /api to :8000)
```

### Demo mode (no credentials)

Set `WEB_RESEARCH_PROVIDER=fixture` and `LLM_PROVIDER=fixture` in `backend/.env`. The UI shows a permanent
**DEMO DATA** banner and offers five fictional vendors (StudyNest, CourseCove, SkillForge, GarbledAI, OfflineCo) that
exercise contradictions, prompt injection, hallucinated quotes, stated vs. omitted fees, inaccessible pages, malformed
model output and total failure. Production configuration refuses to start with fixture providers.

## Tests

```bash
cd backend && .venv/bin/ruff check clauselens tests && .venv/bin/mypy clauselens && .venv/bin/pytest -q
```

```bash
cd frontend && npm run typecheck && npm test && npm run build && npm run e2e
```

Backend tests use SQLite by default; the repository tests also run against PostgreSQL (schema created by Alembic) when
`TEST_DATABASE_URL` is reachable, and the Celery test runs a real worker when `TEST_REDIS_URL` is reachable. Paid
provider smoke tests are opt-in:

```bash
cd backend && RUN_LIVE_TESTS=1 TINYFISH_API_KEY=... LLM_API_KEY=... .venv/bin/pytest tests/test_live_providers.py -v
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/investigations` | start (202); body `{vendors:[{name, domain?}], priorities:[{criterion, weight}]}`; `Idempotency-Key` header supported |
| GET | `/api/investigations` | paginated list |
| GET | `/api/investigations/{id}` | status, per-vendor state, retrieved sources |
| GET | `/api/investigations/{id}/events` | SSE progress (`?stream=false` for JSON, `Last-Event-ID` resume) |
| GET | `/api/vendors/{id}/policies` | policy snapshot history (paginated) |
| POST | `/api/comparisons` | re-score stored snapshots with new priorities (no re-crawl) |
| GET | `/api/reports/{id}` | comparison report |
| GET | `/api/reports/{id}/evidence` | quotes, URLs, timestamps, verification status |
| GET | `/api/meta` | field catalogue, criteria, active providers, demo flag |
| GET | `/health`, `/ready`, `/metrics` | liveness, dependency readiness, Prometheus counters |

Interactive OpenAPI docs: `http://localhost:8000/docs`.
