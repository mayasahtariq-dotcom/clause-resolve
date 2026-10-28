# Architecture

## Layers and the dependency rule

```
api ─┐
     ├─► container / registry ─► adapters ─► ports ◄─ services ◄─ domain
worker┘                              (httpx, SQLAlchemy, Celery)
```

* **domain/** is pure: standard library and pydantic only. It contains the policy field catalogue, value types
  (`Duration`, `Fee`, `Channel`, `Party`), evidence verification, claim aggregation and the comparison engine.
* **ports/** define what the application needs from the outside world as `typing.Protocol`s plus provider-neutral
  data contracts (`ResearchRequest`, `ResearchResult`, `RetrievedSource`, `LLMRequest`, `LLMResponse`,
  `InvestigationRecord`, ...).
* **services/** implement the use cases (extraction, explanation, orchestration) against ports only.
* **adapters/** implement ports for concrete providers and translate every provider failure into
  `clauselens.domain.errors` (`ResearchError`, `LLMError`, `ConfigurationError`) with a category
  (`authentication`, `quota`, `rate_limited`, `timeout`, `unavailable`, `blocked`, `malformed_output`, ...).
* **config.py / registry.py / container.py** form the composition root: validated settings name a provider, the
  registry maps the name to an adapter factory (imported lazily), and the container wires everything once.

`tests/architecture/test_boundaries.py` enforces this mechanically: domain, ports and services may not import
httpx, SQLAlchemy, Celery, FastAPI or any adapter; the comparison engine is imported in a clean interpreter and
must not load provider modules; API routes may not import adapters; every registry entry must import; unknown or
misconfigured providers must fail at startup; demo providers are refused in production.

## Investigation pipeline

| Status | What really happens | Code |
| --- | --- | --- |
| `queued` | record persisted, job submitted | `InvestigationSubmitter` |
| `running` | research provider finds the official domain and retrieves policy pages (vendors in parallel) | `InvestigationService._research` |
| `extracting` | LLM proposes claims: field + verbatim quote + typed value | `services/extraction.py` |
| `validating` | quotes checked against retrieved text; claims aggregated into findings; snapshot persisted | `domain/aggregation.py` |
| `comparing` | deterministic scoring, then an optional LLM explanation of the computed result | `domain/comparison.py`, `services/explanation.py` |
| `completed` / `partial` / `failed` | partial = at least one vendor failed; failed = all failed (no report) | `InvestigationService._run` |

Every transition writes an `investigation_events` row; the UI streams those rows over SSE, so progress is never
simulated. Jobs claim investigations with a database lease (`claim_investigation`), so a redelivered Celery task
(after a worker crash) can resume, and two workers never process the same investigation.

## Evidence and unknowns

* A claim becomes **FOUND** only if its quote is located in the retrieved page text (exact, or after normalising
  whitespace, typography and markdown; `...` fragments must appear in order; no fuzzy matching).
* Otherwise it is **UNVERIFIED** and excluded from scoring. Claims citing an unknown source id are discarded.
* Several verified values that disagree (14 vs 30 days) yield **CONTRADICTORY**, not a silent pick.
* Relevant but indeterminate wording yields **AMBIGUOUS**; nothing stated yields **NOT_FOUND**; a vendor whose research
  or extraction failed yields **UNKNOWN** for every field.
* A fee is zero only when the text says so (`fee.kind = none` with a verified quote). An omitted fee stays NOT_FOUND.

## Comparison and scoring

Only FOUND values are scored, each criterion on a 0–1 scale (longest duration relative to the best; stated zero fee
= 1, comparable non-zero fees ≤ 0.5, incomparable fee types 0.25; cancellation channel ease online 1.0 > app store 0.8
> email/chat 0.6 > phone 0.4 > mail/in person 0.2; vendor pays return shipping 1, varies 0.5, customer 0).
Unknown values score nothing and reduce **coverage** (weight share backed by evidence). User priorities replace the
default policy (`DEFAULT_SCORING_POLICY`, overridable with `SCORING_POLICY_JSON`). No recommendation is made when the
top vendors are within 0.02, when the leader's coverage is below 34 %, or when nothing could be verified. The LLM
explanation sees only the computed facts and is rejected if it introduces any number not present in them.

## Security

* Retrieved pages are untrusted: wrapped in `<<<SOURCE>>>` delimiters (look-alike delimiters stripped), the system
  prompt forbids following embedded instructions, pages with injection patterns are flagged in the UI, and quote
  verification means injected text cannot create a value that is not literally on the vendor's page.
* SSRF: user domains are normalised and rejected if they are IPs, localhost, internal suffixes or metadata hosts.
  TinyFish performs the fetching and documents rejecting private IPs and metadata endpoints; returned URLs are
  re-validated and must stay on the vendor's registrable domain (off-site redirects are dropped).
  `validate_public_url(resolve_dns=True)` is provided for any future adapter that fetches directly.
* Limits: ≤ 10 pages per vendor, `MAX_SOURCE_CHARS` per page, `LLM_MAX_INPUT_CHARS` per prompt, 64 KB request
  bodies, per-client rate limit on investigation creation, bounded retries with capped backoff (transient errors only).
* Secrets live only in backend settings (`SecretStr`), are never returned by `/api/meta`, and are redacted from logs.

## Observability

JSON logs carry `investigation_id`, `vendor`, `stage`, `provider`, `retry_count`, `failure_category` through
`contextvars`. `/metrics` exposes per-process counters: investigations by outcome, provider errors by category,
research failures, LLM requests/failures, prompt and completion tokens, extraction validation failures, unverified
evidence, and duration sums for research, extraction, provider calls and whole investigations.

---

## Replacing a provider

Each replacement is: **implement the port → register → run the shared contract tests → change configuration.**
The domain, services, API schema, database schema and frontend do not change.

### LLM provider (e.g. Anthropic, OpenAI, vLLM)

1. Create `clauselens/adapters/llm/<name>.py` with a class exposing `name`, `model`, `is_demo`,
   `generate(LLMRequest) -> LLMResponse` and `health_check()`, plus `create(settings)`.
   Map HTTP/SDK errors to `LLMError` categories (`send_with_retries` in `adapters/http.py` does this for HTTP).
   If the provider supports schema-constrained output, honour `LLM_OUTPUT_MODE=schema` using `request.json_schema`.
2. Add `"<name>": "clauselens.adapters.llm.<name>:create"` to `REGISTRY["llm"]`.
3. Add a case to `CASES` in `tests/contract/test_llm_providers.py` (mocked HTTP). The shared tests check the
   response contract, error translation, retries and that the unchanged extraction pipeline works with it.
4. Set `LLM_PROVIDER=<name>`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.

Any OpenAI-compatible server needs no code at all: `LLM_PROVIDER=openai_compatible`,
`LLM_BASE_URL=https://host/v1`.

### Research provider (e.g. another crawler or search API)

1. Create `clauselens/adapters/research/<name>.py` implementing `investigate_vendor(ResearchRequest) ->
   ResearchResult` and `health_check()`. Return `RetrievedSource`s keyed `S1..Sn` with content, hash, UTC timestamp;
   report per-page problems as `SourceFailure`; raise `ResearchError` for whole-vendor failures; never fabricate pages.
   Reuse `security.normalize_domain / is_same_site / validate_public_url / detect_prompt_injection`.
   If the provider is asynchronous, poll inside the adapter (the worker is already a background job) and set
   `capabilities`.
2. Register it in `REGISTRY["research"]`, add it to `CASES` in `tests/contract/test_research_providers.py`.
3. Set `WEB_RESEARCH_PROVIDER=<name>` and its credentials.

### Database

The `Repository` protocol (`ports/repository.py`) is the boundary. Any SQLAlchemy-supported database works through
the existing adapter by changing `DATABASE_URL` (tests already run on SQLite and PostgreSQL); add an Alembic
revision if dialect-specific DDL is needed. For a non-SQL store, implement every `Repository` method in a new
adapter, register it under `REGISTRY["persistence"]`, and run `tests/integration/test_repository.py` against it by
adding a fixture to the `repo` parametrisation. `claim_investigation` must be atomic.

### Job queue (e.g. RQ, Dramatiq, AWS SQS, Cloud Tasks)

Implement `JobQueue` (`submit_investigation(id)`, `health_check()`, `durable`) whose worker calls
`container.service.run(investigation_id, worker_id=<stable per delivery>)`. Register it under `REGISTRY["jobs"]`
and set `JOB_QUEUE_PROVIDER`. The orchestrator's database lease already provides duplicate-work protection and
restart safety, so the queue only needs at-least-once delivery.

### Hosting

The backend is a standard container (`backend/Dockerfile`) with two commands (uvicorn, celery) and needs
PostgreSQL + Redis URLs; any container host (Fly.io, Railway, ECS, Cloud Run + a worker) works with the same env
vars. The frontend is a static Vite build configured only by `VITE_API_BASE_URL`; any static host works (add an
SPA fallback to `index.html`). An alternative frontend can use the documented HTTP API (`/docs`).
