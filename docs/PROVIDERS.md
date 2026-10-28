# External providers: verified contracts

Verified on 2026-10-28 by reading the official documentation (docs.ollama.com, docs.tinyfish.ai, the TinyFish
OpenAPI spec and `https://ollama.com/api/tags`). The adapters were tested against mocked responses shaped like
these contracts. **They have not been exercised against the live APIs from this environment**: no API keys were
available and the container's network policy blocks ollama.com and tinyfish.ai. Run
`tests/test_live_providers.py` with real keys before going live.

## Ollama Cloud (LLM)

| Item | Verified value |
| --- | --- |
| Endpoint | `POST https://ollama.com/api/chat` (native); OpenAI-compatible `POST https://ollama.com/v1/chat/completions` |
| Auth | `Authorization: Bearer $OLLAMA_API_KEY` (keys do not expire; keep out of browser code) |
| Request | `{model, messages, stream:false, format?, options?{temperature,num_predict}, think?}` |
| Response | `{model, message:{role, content, thinking?}, done, done_reason, prompt_eval_count, eval_count, total_duration}` |
| Models | names from `GET https://ollama.com/api/tags`; no download needed |
| Structured output | docs: *"Ollama's cloud currently does not support structured outputs."* |

Consequences in `adapters/llm/ollama.py`:

* `LLM_OUTPUT_MODE=prompt` (default) sends no `format`; the JSON contract is in the prompt and the output is parsed
  and validated strictly (`services/extraction.py`), with one bounded repair attempt. `json`/`schema` modes are
  available for local Ollama or if cloud support arrives.
* `think` is sent from `LLM_THINK` (default `low`, valid for gpt-oss) so reasoning goes to `message.thinking`, not
  the answer.
* Token counts from `prompt_eval_count` / `eval_count` are recorded as metrics.

### Model choice: `gpt-oss:120b`

Chosen from the live cloud model list because it is: listed for cloud since 2025-08 (more stable than very recent
additions, lowering retirement risk); a strong instruction-following reasoning model with a 128k context window
(room for several policy pages); published with open weights under Apache-2.0, so the same model can be
self-hosted later through the `openai_compatible` adapter without changing behaviour. Larger options
(`deepseek-v4-pro`, `kimi-k3`, `mistral-large-4`, `glm-5.3`) are available on the same endpoint; switch with
`LLM_MODEL` and re-run the live smoke test. Hosted availability does not imply downloadable weights; check each
model's licence before self-hosting. Pricing and usage limits are plan-based; see the Ollama usage page for your
account (not verifiable without an account).

## TinyFish (web research)

| Item | Verified value |
| --- | --- |
| Auth | `X-API-Key: $TINYFISH_API_KEY` on all REST calls |
| Search | `GET https://api.search.tinyfish.ai?query=&location=&language=&include_domains=&exclude_domains=&page=` → `{query, results:[{position, site_name, title, snippet, url, date?}], total_results, page}` |
| Fetch | `POST https://api.fetch.tinyfish.ai` `{urls:[≤10], format:"markdown", links, image_links, purpose?, per_url_timeout_ms?}` → `{results:[{url, final_url, title, description, language, format, text, ...}], errors:[{url, error, status?}]}` |
| Fetch safety | URLs must be http/https; private IPs, localhost and cloud metadata endpoints are rejected by TinyFish |
| Per-URL errors | `page_not_found`, `target_http_error`, `target_unreachable`, `timeout`, `bot_blocked`, `empty_content`, `login_required`, `content_too_large`, `invalid_url`, ... |
| HTTP errors | 400 `INVALID_INPUT`, 401 `MISSING_API_KEY`/`INVALID_API_KEY`, 402 `INSUFFICIENT_CREDITS`/`FREE_ALLOWANCE_EXHAUSTED`, 403 `FORBIDDEN`, 429 `RATE_LIMIT_EXCEEDED` (+`Retry-After`), 5xx `BACKEND_UNAVAILABLE`/`SERVICE_BUSY` |
| Limits | Search: 30 req/min (personal), 12,000 free/day; Fetch: 1,000 free URLs/day, then wallet |

### Integration method

The adapter uses **Search + Fetch** (synchronous, cheap, deterministic) rather than the goal-driven Agent API:

1. Official domain: the user-supplied domain, or a search for "`<vendor>` official website" that skips aggregator
   hosts and requires the vendor name in the domain. If none qualifies, the vendor fails with a request to enter
   the domain; nothing is guessed. Search-inferred domains are labelled in the UI.
2. Discovery: five topic searches (refund, cancellation, terms/renewal, free trial, returns) restricted with
   `include_domains`; off-domain and unsafe results are dropped; URLs are ranked by policy keywords.
3. Retrieval: one Fetch call for the top `RESEARCH_MAX_PAGES_PER_VENDOR` URLs as markdown; redirects off the vendor's
   domain, empty pages and per-URL errors become `SourceFailure`s shown in the activity log.

The Agent API (`/v1/automation/run-async`, `GET /v1/runs/{id}`) could be added as a second research adapter for sites
whose policies need clicking through; the port already supports it.
