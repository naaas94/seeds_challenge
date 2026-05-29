# Seeds Match API

A conversational financial agent exposed as a small HTTP API: explicit ReAct loop, per-conversation memory, and Yahoo Finance tooling. Built for the Seeds Match live technical challenge — the evaluation signal is an auditable `agent_loop` (no `AgentExecutor`), not a black-box agent wrapper.

---

## Quick Start

```bash
git clone <repo>
cd seeds_challenge
# Set OPENAI_API_KEY in your environment (Windows user/system env var is fine)
docker compose up --build
# API: http://localhost:8000
# Interactive docs: http://localhost:8000/docs
```

**Smoke test (first turn — save `conversation_id` from the response):**

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Apple stock price?", "conversation_id": null}'

curl -s http://localhost:8000/chat/<conversation_id>
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key from the host environment (or optional `.env` for local runs); missing → startup failure |
| `MODEL_NAME` | `gpt-4o-mini` | Chat model for ReAct turns |

Docker Compose passes `OPENAI_API_KEY` from the shell where you run `docker compose` (including Windows user/system variables). A project `.env` file is not required for Compose; copy `.env.example` → `.env` only if you want overrides for local `uvicorn` / tests.

### Service ports

| Service | Port |
|---|---|
| `api` | 8000 |

---

## Architecture Overview

Single-container Docker Compose layout:

```
┌──────────────────────────────────────────────────────────┐
│  docker-compose.yml                                      │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  api — FastAPI + uvicorn (single worker)           │  │
│  │  :8000                                             │  │
│  │                                                    │  │
│  │  POST /chat  ──► agent_loop (ReAct)                │  │
│  │  GET  /chat/{id} ──► ConversationStore             │  │
│  │                                                    │  │
│  │  Outbound: OpenAI (langchain-openai)               │  │
│  │            Yahoo Finance (yfinance tool)           │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Module layout**

```
app/
├── main.py           # FastAPI routes, lifespan, ROLE_MAP, history serialization
├── config.py         # Pydantic Settings (env-driven)
├── schemas.py        # ChatRequest / ChatResponse / HistoryResponse
├── agent/
│   ├── loop.py       # agent_loop — explicit ReAct (evaluation artifact)
│   ├── tools.py      # get_stock_info + singleton LLM/tool binding
│   └── prompts.py    # SYSTEM_PROMPT
└── memory/
    └── store.py      # In-process ConversationStore (asyncio.Lock)
```

---

## Agent Loop (ReAct)

```
POST /chat { message, conversation_id? }
    │
    ▼
main.py — generate UUID if conversation_id absent
    │
    ▼
agent_loop(conversation_id, message, store)
    │  append HumanMessage
    │  prepend SYSTEM_PROMPT at invoke time (not stored)
    │
    ┌──────── ReAct loop (max 10 iterations) ────────────┐
    │  invoke LLM_WITH_TOOLS                             │
    │  if not response.tool_calls → return final reply   │
    │  else execute tools → append ToolMessage → repeat  │
    └────────────────────────────────────────────────────┘
    │
    ▼
ChatResponse { conversation_id, reply }
```

**Termination:** `not response.tool_calls` on the LLM response — not a sentinel string or `AgentExecutor` flag.

**Multi-turn contract:** The client must echo `conversation_id` from the first `POST /chat` on every follow-up. `GET /chat/{id}` returns the full trace (human, AI with tool calls, tool results). Unknown IDs return **404**, not an empty history.

---

## Architecture Decision Table

| Decision | Why | Tradeoff |
|---|---|---|
| Explicit `agent_loop` (no `AgentExecutor`) | Challenge evaluation signal; auditable termination | More code than a one-liner agent wrapper |
| `not response.tool_calls` as stop condition | Canonical OpenAI/LangChain “final answer” signal | Assumes well-formed `AIMessage` from the model |
| System prompt at invoke time, not in store | Prompt iteration without migrating history; cleaner GET trace | Small token overhead each turn |
| `MAX_ITERATIONS = 10` | Prevents unbounded loops in production-shaped code | Rare multi-tool chains may hit fallback message |
| In-process `ConversationStore` | Simplest demo; matches single-worker uvicorn | No persistence across restarts; breaks with `--workers > 1` |
| `asyncio.Lock` on store | Correct for async FastAPI concurrency | Not cross-process; Redis needed for scale-out |
| Tool errors as return strings (never raise) | Keeps ReAct loop coherent; LLM can explain failures | Caller must parse text, not structured error codes |
| `ROLE_MAP` for history roles | Stable API roles vs fragile class-name derivation | Must update map if new message types appear |
| `serialize_content()` for history | `AIMessage.content` can be `List` when tool calls present | Extra serialization logic in `main.py` |
| `langchain-core` + `langchain-openai` only | Avoids umbrella `langchain` meta-package weight | Manual imports per integration |
| Single uvicorn worker in Docker | In-process store is process-local | Throughput ceiling on one machine |
| Sync `invoke()` inside async loop | Acceptable for live demo / single-client eval | Blocks event loop under concurrent load |

---

## Engineering approach

Built contract-first against `seeds-match-challenge-spec.md`, then staged implementation (scaffold → config/schemas → store → tools → loop → routes → Docker → integration tests).

- Explicit ReAct loop as the primary artifact (`app/agent/loop.py`)
- Tiered pytest coverage (unit modules + `tests/test_app.py` integration slice)
- Fail-fast config (`OPENAI_API_KEY` required at import; lifespan belt-and-suspenders)
- Documented production deltas in code (`ConversationStore` docstring, tool delay note)

Process artifacts (plans, audits, architecture index) live under `.dev/` — see [`.dev/architecture/seeds-match-api/INDEX.md`](.dev/architecture/seeds-match-api/INDEX.md).

---

## Reviewer notes

- **API key required:** Set `OPENAI_API_KEY` in your environment (or in `.env` for local non-Docker runs) before `docker compose up`.
- **Single worker:** The `Dockerfile` runs one uvicorn worker so in-process memory stays consistent. Multi-worker needs a Redis-backed store (interface is already `get` / `append` / `exists`).
- **External calls:** OpenAI for inference; Yahoo Finance via `yfinance` for tool data (~15 min delay on free tier).
- **History includes tool turns:** `GET /chat/{id}` returns AI messages that may have empty text but tool calls, plus all `ToolMessage` results — intentional for evaluator inspection.
- **404 on unknown conversation:** `GET /chat/{id}` for an ID never seen returns 404 with a plain detail string.
- **500 envelope on agent failure:** `POST /chat` returns `{"error": "Agent execution failed", "detail": "..."}` (no raw stack traces).

---

## Test suite

Integration and unit tests mock OpenAI and `yfinance` — no live network required.

From the repo root:

```bash
pip install -r requirements.txt pytest
pytest
```

**Current status:** 59 passed (as of 2026-05-28 audit).

Coverage highlights:

| Area | Module(s) |
|---|---|
| Scaffold / deps | `tests/test_scaffold.py` |
| Config & schemas | `tests/test_config.py`, `tests/test_schemas.py` |
| Store isolation | `tests/test_store.py` |
| Tool contract (no raise) | `tests/test_tools.py` |
| ReAct termination & max iterations | `tests/test_loop.py` |
| Routes, 404/500, history serialization | `tests/test_main.py`, `tests/test_app.py` |

---

## API reference

### `POST /chat`

**Request**

```json
{
  "message": "What is Tesla's stock price?",
  "conversation_id": null
}
```

**Response (200)**

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "reply": "Tesla (TSLA) is currently trading at ..."
}
```

**Errors (500)**

```json
{
  "error": "Agent execution failed",
  "detail": "..."
}
```

### `GET /chat/{conversation_id}`

**Response (200)**

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    { "role": "human", "content": "What is Tesla's stock price?" },
    { "role": "ai", "content": "[tool call — no text content]" },
    { "role": "tool", "content": "Ticker: TSLA\nCurrent Price: ..." },
    { "role": "ai", "content": "Tesla (TSLA) is currently trading at ..." }
  ]
}
```

**Errors:** 404 if `conversation_id` is not in the store.

---

## Scale-out

1. **Conversation memory** — Swap `ConversationStore` for Redis (TTL per session). `agent_loop` only depends on `get` / `append` / `exists`.

2. **Multiple API workers** — After Redis backing, run uvicorn with `--workers N` behind a load balancer. Sticky sessions or shared store required.

3. **Concurrent LLM calls** — Wrap `llm_with_tools.invoke` in `asyncio.to_thread` or use `ainvoke` so the event loop is not blocked during OpenAI round-trips.

4. **Market data** — Replace `yfinance` with a licensed financial data API (Bloomberg, Refinitiv, paid Yahoo API) for stability and freshness.

---

## Production delta

| Limitation | Root cause | Remediation |
|---|---|---|
| Memory lost on restart | In-process dict | Redis with TTL |
| Single-worker only | Process-local store | Shared store + multi-worker |
| Blocking LLM in async handler | Sync `invoke()` | `asyncio.to_thread` / `ainvoke` |
| `yfinance` fragility | Scraper, not official API | Licensed market-data API |
| No conversation TTL | Demo scope | Redis TTL or expiry endpoint |
| No auth / rate limits | Challenge non-goals | API key header, gateway rate limiting |
| Delayed quotes | Yahoo free tier | Real-time feed subscription |

When asked “what would you change for production?”, prioritize: **store → concurrency → data source → observability** (structured logs per `conversation_id`, tool latency, model id).

---

## Limitations

- **No persistence** — Restart clears all conversations.
- **No streaming** — Full reply returned per `POST /chat`.
- **yfinance reliability** — Invalid tickers and connectivity issues return tool error strings; the agent may still complete with a user-facing explanation.
- **Financial advice** — System prompt disclaims buy/sell recommendations; model may still overreach — not validated by automated judge in this repo.
- **Sync LLM in async route** — Fine for sequential evaluation; degrades under parallel load.
- **Open questions** — See [`.dev/architecture/seeds-match-api/open-questions.md`](.dev/architecture/seeds-match-api/open-questions.md) (empty API key behavior, dependency pinning, etc.).

---

## Related docs

| Document | Purpose |
|---|---|
| [`seeds-match-challenge-spec.md`](seeds-match-challenge-spec.md) | Binding build specification |
| [`.dev/architecture/seeds-match-api/INDEX.md`](.dev/architecture/seeds-match-api/INDEX.md) | Architecture index (module map, contracts, seams) |
| [`CHANGELOG.MD`](CHANGELOG.MD) | Implementation changelog by subtask |
| [`README_EXAMPLE_NOT_THIS_PROJECTS.md`](README_EXAMPLE_NOT_THIS_PROJECTS.md) | README template reference (different project) |
