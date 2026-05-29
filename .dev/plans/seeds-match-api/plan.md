# Orchestrator Plan — seeds-match-api

**Version:** 1.1  
**Status:** Complete  
**Plan name:** `seeds-match-api`  
**Binding spec:** `seeds-match-challenge-spec.md` (repo root, tracked)  
**Skill version:** orchestrator-planning 0.6

---

## §0. Context Map Intake

No context map exists. This is a **greenfield project** — the repository contains only `seeds-match-challenge-spec.md`. All Files to touch are known from the spec §3 Module Structure and §4 Component Specifications. No `_pending/` promotion required.

- **Readiness verdict:** READY (all subtask file paths are fully specified in the binding artifact)
- **Binding artifact:** `seeds-match-challenge-spec.md` — committed at repo root; `git ls-files` will confirm after first commit. The spec is the authoritative source for every implementation detail, including complete code for all seven modules.
- **Ambiguity flags:** None — the spec is post-adversarial-pass and explicitly resolves all 14 findings.

---

## §1. Task Statement

Build a Python FastAPI application exposing a conversational AI agent backed by an explicit ReAct loop and a Yahoo Finance tool, with per-conversation in-process memory and two HTTP endpoints (`POST /chat`, `GET /chat/{conversation_id}`). The application runs in Docker via a single-worker uvicorn process. The primary evaluation signal is the explicit `agent_loop` function in `app/agent/loop.py` that implements termination via `not response.tool_calls` rather than delegating to `AgentExecutor`.

**Non-goals:**
- Persistence across restarts (named limitation; Redis remediation documented in store.py)
- Authentication or authorization
- Rate limiting
- Streaming responses
- Multiple tool providers
- Multi-worker deployment (in-process store requires single worker)
- Any LangChain `AgentExecutor` usage

---

## §2. Shared Contracts

Binding for all subagents. Every executor must read this section in full before touching any file.

### Types / Interfaces

| Symbol | Location | Signature | Owning subtask | Test |
|--------|----------|-----------|----------------|------|
| `Settings` | `app/config.py` | `BaseSettings(openai_api_key: str, model_name: str = "gpt-4o-mini")` | T2 | T8: startup validates missing key |
| `ChatRequest` | `app/schemas.py` | `BaseModel(message: str, conversation_id: Optional[str] = None)` | T2 | T8: POST /chat with and without conversation_id |
| `ChatResponse` | `app/schemas.py` | `BaseModel(conversation_id: str, reply: str)` | T2 | T8: response shape assertion |
| `MessageRecord` | `app/schemas.py` | `BaseModel(role: str, content: str)` | T2 | T8: GET history shape |
| `HistoryResponse` | `app/schemas.py` | `BaseModel(conversation_id: str, messages: list[MessageRecord])` | T2 | T8: GET history |
| `ErrorResponse` | `app/schemas.py` | `BaseModel(error: str, detail: str)` | T2 | T8: 500 error shape |
| `ConversationStore` | `app/memory/store.py` | `.get(id: str) -> List[BaseMessage]`; `.append(id: str, msg: BaseMessage) -> None`; `.exists(id: str) -> bool` — all `async` | T3 | T8: store isolation, concurrent-turn lock |
| `agent_loop` | `app/agent/loop.py` | `async def agent_loop(conversation_id: str, user_message: str, store: ConversationStore) -> str` | T5 | T8: smoke test, multi-turn, MAX_ITERATIONS fallback |
| `init_singletons` | `app/agent/tools.py` | `def init_singletons(llm: BaseChatModel) -> None` | T4 | T8: called once in lifespan |
| `get_llm_with_tools` | `app/agent/tools.py` | `def get_llm_with_tools() -> BaseChatModel` | T4 | T8: not None after lifespan |
| `get_tool_map` | `app/agent/tools.py` | `def get_tool_map() -> dict` | T4 | T8: contains `get_stock_info` key |
| `get_stock_info` | `app/agent/tools.py` | `@tool def get_stock_info(ticker: str) -> str` | T4 | T8: valid ticker returns price block; invalid ticker returns error string; exception returns error string |
| `SYSTEM_PROMPT` | `app/agent/prompts.py` | `str` constant | T2 | T8: injected into messages in agent_loop (verified by mock call args) |
| `ROLE_MAP` | `app/main.py` | `dict[type, str]` mapping `{HumanMessage: "human", AIMessage: "ai", ToolMessage: "tool", SystemMessage: "system"}` | T6 | T8: GET history role serialization |
| `serialize_content` | `app/main.py` | `def serialize_content(message: BaseMessage) -> str` | T6 | T8: AIMessage with list content returns joined text; ToolMessage returns str |
| `MAX_ITERATIONS` | `app/agent/loop.py` | `int = 10` | T5 | T8: loop terminates with fallback string when iteration cap hit |

### Error Envelope

| Condition | HTTP status | Body shape |
|-----------|-------------|------------|
| Successful chat | 200 | `{"conversation_id": str, "reply": str}` |
| Successful history | 200 | `{"conversation_id": str, "messages": [...]}` |
| Unknown conversation_id on GET | 404 | FastAPI default 404 detail string |
| LLM or tool exception in POST /chat | 500 | `{"error": "Agent execution failed", "detail": str(e)}` — delivered as `HTTPException(status_code=500, detail={...})` |
| Missing OPENAI_API_KEY | App fails to start | `ValidationError` from pydantic-settings at import; `RuntimeError` in lifespan as belt-and-suspenders |

**Binding:** The 500 body shape is `{"error": "Agent execution failed", "detail": "<exception message>"}` embedded in FastAPI's `HTTPException.detail`. This is the shipped value; no other shape is acceptable.

### Naming

All symbols must match exactly (case-sensitive):
- Module files: `app/config.py`, `app/schemas.py`, `app/agent/prompts.py`, `app/agent/tools.py`, `app/agent/loop.py`, `app/memory/store.py`, `app/main.py`
- `SYSTEM_PROMPT`, `TOOLS`, `TOOL_MAP`/`_TOOL_MAP`, `LLM_WITH_TOOLS`/`_LLM_WITH_TOOLS`, `MAX_ITERATIONS`, `ROLE_MAP`
- Tool name registered by `@tool` decorator: `get_stock_info` — this string appears in `tool_map` keys and in `ToolMessage.tool_call_id` matching

### Logging

- No structured logging framework required (demo scope)
- Verbally: "In production, I would add structured logging per turn with conversation_id, model, latency, and tool call count"
- No `print()` statements in production paths

### Tests

- **Framework:** pytest + FastAPI `TestClient` (via `httpx`)
- **Location:** `tests/test_app.py` (single file for demo scope)
- **Naming:** `test_<feature>_<condition>` pattern
- **Coverage expectations:** smoke test, multi-turn continuity, GET history (all message types), 404 on unknown ID, tool error returns graceful string, `serialize_content` unit test, `MAX_ITERATIONS` fallback
- **Mocking:** `unittest.mock.patch` or `pytest-mock` to mock `yfinance.Ticker` and `langchain_openai.ChatOpenAI` — no live API or network calls in tests

### CLI Surface (frozen)

| Consumer | String | Frozen by |
|----------|--------|-----------|
| Dockerfile CMD | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | T7 |
| docker-compose healthcheck | `http://localhost:8000/docs` | T7 |
| Endpoint path POST | `/chat` | T6, consumed by T8 |
| Endpoint path GET | `/chat/{conversation_id}` | T6, consumed by T8 |

**Decision log paths (architectural subtasks):**
- T5: `.dev/decision-logs/T5-agent-loop.md`
- T6: `.dev/decision-logs/T6-main.md`

---

## §3. Dependency DAG

```
graph TD
    T1[T1: Scaffold] --> T2[T2: Config + Schemas + Prompts]
    T1 --> T3[T3: ConversationStore]
    T1 --> T4[T4: Tools module]
    T1 --> T7[T7: Docker config]
    T2 --> T5[T5: Agent loop]
    T3 --> T5
    T4 --> T5
    T5 --> T6[T6: FastAPI main.py]
    T6 --> T8[T8: Test suite]
```

**Parallel groups:**
- `{T2, T3, T4, T7}` — all run in parallel after T1 completes
- `T5` — runs after all of `{T2, T3, T4}` complete (T7 does not block T5)
- `T6` — runs after T5
- `T8` — runs after T6

**Soft dependency note:** T7 can be drafted in parallel with T2/T3/T4, but the `CMD` string must match the frozen CLI surface from §2 — executor must verify against §2 before finalizing.

---

## §4. Subtask Specs

---

### T1 — Project Scaffold

| Field | Value |
|-------|-------|
| **ID** | T1 |
| **Scope** | Create the complete directory skeleton and all non-Python infrastructure files. No Python implementation logic in this subtask. |
| **Files to touch** | `requirements.txt`, `.env.example`, `app/__init__.py`, `app/agent/__init__.py`, `app/memory/__init__.py`, `tests/__init__.py` |
| **Contract bindings** | Naming (module paths), CLI surface (requirements.txt package list) |
| **Inputs** | None |
| **Outputs** | Scaffold with all `__init__.py` files (empty), `requirements.txt`, `.env.example` |
| **Kill criteria** | HALT if `pydantic-settings` is absent from requirements.txt — pydantic BaseSettings import will fail. HALT if the umbrella `langchain` package is included — spec §5 Note explicitly prohibits it. |
| **Log tier** | `trivial` |
| **Risks & mitigations** | Risk: wrong package names in requirements. Mitigation: use exact names from spec §5 Note — `fastapi`, `uvicorn[standard]`, `langchain-core`, `langchain-openai`, `pydantic-settings`, `yfinance`. |

**requirements.txt exact content:**
```
fastapi
uvicorn[standard]
langchain-core
langchain-openai
pydantic-settings
yfinance
```

**.env.example exact content:**
```
# Copy to .env and fill in your key before running docker compose up.
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini
```

---

### T2 — Config, Schemas, Prompts

| Field | Value |
|-------|-------|
| **ID** | T2 |
| **Scope** | Implement `app/config.py` (Pydantic BaseSettings), `app/schemas.py` (all request/response models), and `app/agent/prompts.py` (SYSTEM_PROMPT constant). Pure data/config — no I/O, no external deps beyond pydantic-settings. |
| **Files to touch** | `app/config.py`, `app/schemas.py`, `app/agent/prompts.py` |
| **Contract bindings** | Types/interfaces (all schema models + Settings), Error envelope, Naming |
| **Inputs** | T1 (scaffold exists) |
| **Outputs** | `app/config.py`, `app/schemas.py`, `app/agent/prompts.py` — exact code from spec §4.1, §4.6, §4.2 |
| **Kill criteria** | HALT if `Settings.openai_api_key` has a default value — it must have no default so pydantic-settings raises `ValidationError` on missing env var. HALT if `ChatRequest.conversation_id` type is not `Optional[str]` with default `None`. |
| **Log tier** | `standard` |
| **Risks & mitigations** | Risk: Pydantic v1 vs v2 `Config` class syntax. Mitigation: spec uses inner `class Config: env_file = ".env"` which is valid for both pydantic-settings v1 and v2; executor should verify pydantic-settings version installed and adjust if needed (v2 uses `model_config = SettingsConfigDict(...)`). |

---

### T3 — ConversationStore

| Field | Value |
|-------|-------|
| **ID** | T3 |
| **Scope** | Implement `app/memory/store.py` — the in-process conversation store with `asyncio.Lock`. Complete docstring narrating the HARD CONSTRAINT (single-worker, no persistence, Redis remediation path). |
| **Files to touch** | `app/memory/store.py` |
| **Contract bindings** | Types/interfaces (ConversationStore methods: async get, append, exists), Naming |
| **Inputs** | T1 (scaffold exists) |
| **Outputs** | `app/memory/store.py` — exact code from spec §4.4 |
| **Kill criteria** | HALT if lock is `threading.Lock` instead of `asyncio.Lock` — spec adversarial finding A8 explicitly prohibits this. HALT if `.get()` returns the internal list by reference (must return `list(...)` copy). HALT if any method is not `async`. |
| **Log tier** | `standard` |
| **Risks & mitigations** | Risk: async methods called from a thread context (agent_loop runs via asyncio.to_thread in older design). Mitigation: spec §4.5 resolves this — agent_loop is now `async`, so store methods are awaited directly from the event loop. No `asyncio.run()` inside agent_loop. |

---

### T4 — Yahoo Finance Tool Module

| Field | Value |
|-------|-------|
| **ID** | T4 |
| **Scope** | Implement `app/agent/tools.py` — the `@tool`-decorated `get_stock_info` function, module-level singletons (`_LLM_WITH_TOOLS`, `_TOOL_MAP`), and `init_singletons(llm)` / accessor functions. |
| **Files to touch** | `app/agent/tools.py` |
| **Contract bindings** | Types/interfaces (get_stock_info, init_singletons, get_llm_with_tools, get_tool_map, TOOLS list), Naming |
| **Inputs** | T1 (scaffold exists) |
| **Outputs** | `app/agent/tools.py` — exact code from spec §4.3 |
| **Kill criteria** | HALT if `get_stock_info` raises exceptions instead of returning error strings — spec §4.3 explicitly states "Return error as string — never raise from a tool." HALT if `_LLM_WITH_TOOLS` or `_TOOL_MAP` are rebuilt per call (they must be module-level, initialized once by `init_singletons`). HALT if `TOOLS = [get_stock_info]` is absent (needed for `init_singletons`). |
| **Log tier** | `standard` |
| **Risks & mitigations** | Risk: yfinance API field name changes (`regularMarketPrice` → deprecated). Mitigation: the try/except in the tool body handles this; named as accepted fragility (A11) in the spec. Risk: `@tool` decorator from langchain_core.tools registers the function name `get_stock_info` — executor must not rename the function. |

---

### T5 — Agent Loop (evaluation artifact)

| Field | Value |
|-------|-------|
| **ID** | T5 |
| **Scope** | Implement `app/agent/loop.py` — the explicit ReAct loop. This is the primary evaluation artifact. Must implement: history fetch → system prompt prepend → LLM invocation → `while tool_calls` dispatch → store append → final answer on empty tool_calls. Emit architectural decision log. |
| **Files to touch** | `app/agent/loop.py`, `.dev/decision-logs/T5-agent-loop.md` |
| **Contract bindings** | All §2 contracts — especially: `agent_loop` signature, `MAX_ITERATIONS = 10`, system prompt injection strategy (at call time, not stored), `ConversationStore` interface, `get_llm_with_tools` / `get_tool_map` accessors, error envelope (fallback string on MAX_ITERATIONS), Naming |
| **Inputs** | T2 (SYSTEM_PROMPT, SystemMessage import path), T3 (ConversationStore interface), T4 (get_llm_with_tools, get_tool_map, TOOLS) |
| **Outputs** | `app/agent/loop.py` — exact code from spec §4.5; `.dev/decision-logs/T5-agent-loop.md` |
| **Kill criteria** | HALT if loop uses `AgentExecutor` — spec §1 Non-goals and §4.5 explicitly prohibit this. HALT if termination is implemented via string sentinel or special token rather than `not response.tool_calls`. HALT if SYSTEM_PROMPT is stored in the conversation store (it must be prepended at call time only). HALT if `MAX_ITERATIONS` is absent or unbounded. HALT if any `store.get/append` call is not awaited. |
| **Log tier** | `architectural` |
| **Risks & mitigations** | Risk: `llm_with_tools.invoke(messages)` is synchronous inside an async function — blocks the event loop. Mitigation: spec §4.5 explicitly acknowledges this for demo scope; the decision log must document that `await asyncio.to_thread(llm_with_tools.invoke, messages)` is the production-correct call, and the current implementation is intentionally noted as acceptable for demo. |

**Decision log path:** `.dev/decision-logs/T5-agent-loop.md`

---

### T6 — FastAPI Application (main.py)

| Field | Value |
|-------|-------|
| **ID** | T6 |
| **Scope** | Implement `app/main.py` — lifespan hook (startup validation + LLM init + `init_singletons`), `ROLE_MAP`, `serialize_content`, `POST /chat` route, `GET /chat/{conversation_id}` route. Emit architectural decision log. |
| **Files to touch** | `app/main.py`, `.dev/decision-logs/T6-main.md` |
| **Contract bindings** | All §2 contracts — especially: ROLE_MAP shape, serialize_content behavior (list content handling), error envelope (500 body), endpoint paths, ChatResponse/HistoryResponse schemas, CLI surface (frozen endpoint paths) |
| **Inputs** | T5 (agent_loop async signature), T3 (ConversationStore), T2 (all schemas, Settings), T4 (agent_tools.init_singletons import path) |
| **Outputs** | `app/main.py` — exact code from spec §4.7; `.dev/decision-logs/T6-main.md` |
| **Kill criteria** | HALT if `ROLE_MAP` derives role from class name string (e.g. `type(m).__name__`) instead of explicit `dict[type, str]` — spec adversarial finding A9. HALT if the lifespan hook does not call `agent_tools.init_singletons(llm)`. HALT if `POST /chat` catches exceptions with a raw 500 instead of `{"error": ..., "detail": ...}` shape. HALT if the GET endpoint returns empty history instead of 404 for unknown conversation_id — spec §2 Conversation ID Contract. |
| **Log tier** | `architectural` |
| **Risks & mitigations** | Risk: FastAPI `HTTPException.detail` is polymorphic — passing a dict as detail is valid but may serialize differently depending on FastAPI version. Mitigation: test T8 must assert the dict shape in the 500 response. Risk: `serialize_content` for `AIMessage` with `List` content may return empty string if no text-type blocks present — the `"[tool call — no text content]"` fallback handles this; test must cover it. |

**Decision log path:** `.dev/decision-logs/T6-main.md`

---

### T7 — Docker Configuration

| Field | Value |
|-------|-------|
| **ID** | T7 |
| **Scope** | Implement `Dockerfile`, `docker-compose.yml`. The single-worker constraint must be encoded in CMD and documented inline. |
| **Files to touch** | `Dockerfile`, `docker-compose.yml` |
| **Contract bindings** | CLI surface (frozen CMD string), Naming (module path `app.main:app`) |
| **Inputs** | T1 (requirements.txt exists) |
| **Outputs** | `Dockerfile`, `docker-compose.yml` — exact content from spec §5 |
| **Kill criteria** | HALT if `CMD` includes `--workers N` with N > 1 — violates single-worker constraint required by ConversationStore. HALT if `env_file` is absent from docker-compose service — OPENAI_API_KEY must load from `.env`. |
| **Log tier** | `standard` |
| **Risks & mitigations** | Risk: `version: "3.9"` in docker-compose.yml is deprecated in newer Docker Compose v2. Mitigation: spec prescribes it; use as-is for demo; note verbally that the top-level `version` key is optional in Compose v2. |

---

### T8 — Test Suite

| Field | Value |
|-------|-------|
| **ID** | T8 |
| **Scope** | Implement `tests/test_app.py` — pytest tests covering the spec's Phase 1, 2 build checklist: smoke test, multi-turn continuity, GET history (all role types present), 404 on unknown ID, tool error graceful handling, `serialize_content` unit test, `MAX_ITERATIONS` fallback. All tests must mock external calls (yfinance, OpenAI). |
| **Files to touch** | `tests/test_app.py`, `tests/conftest.py` (fixtures) |
| **Contract bindings** | All §2 contracts — especially error envelope shapes, endpoint paths, role serialization, ConversationStore isolation |
| **Inputs** | T6 (full app implementation) |
| **Outputs** | `tests/test_app.py`, `tests/conftest.py` |
| **Kill criteria** | HALT if any test makes live network calls to OpenAI or Yahoo Finance — all external calls must be mocked. HALT if the POST /chat 500 test does not assert `{"error": "Agent execution failed", "detail": ...}` shape. HALT if multi-turn test does not verify the second request receives prior context (inspect mock call args for history length). |
| **Log tier** | `standard` |
| **Risks & mitigations** | Risk: mocking `langchain_openai.ChatOpenAI` is non-trivial (invoke returns an AIMessage, not a plain string). Mitigation: use `unittest.mock.MagicMock` with spec or return value fixtures that return `AIMessage(content="...", tool_calls=[])` objects. Risk: `agent_loop` being async requires `pytest-asyncio` or `anyio`. Mitigation: add `pytest-asyncio` to test dependencies (not in production requirements.txt). |

---

## §5. Adversarial Pass

*Answered using the packet-only executor persona: "If I only had T\<n\>'s packet and the executor SKILL.md, what would cause me to halt?"*

### 5.1 Rejected Decompositions

**Alternative A — Single "implement everything" subtask.**
Rejected: The spec is 692 lines with 7 distinct modules. A single executor packet is unparallelizable and produces a monolithic diff unreviable by the evaluator. The evaluation signal (agent_loop) is buried.

**Alternative B — Merge T2 + T3 + T4 into one "core modules" subtask.**
Rejected: T3 (ConversationStore) and T4 (tools.py) have zero coupling. Merging them defeats parallel execution. T2 (schemas) is shared-contract-anchoring for T5 and T6 — separating it makes the dependency explicit and verifiable.

**Alternative C — Include Docker in T1 scaffold.**
Rejected: T7 depends on T1 (requirements.txt) but does not depend on T2–T6 (Python code). Merging into T1 would serialize Docker work with Python module work unnecessarily. Separate T7 is the correct parallelization.

### 5.2 Load-Bearing Assumptions

All entries use the required tuple shape: `(claim | contract surface | failure mode | subtask IDs)`

1. `(pydantic-settings raises ValidationError on missing openai_api_key | §2 Types: Settings.openai_api_key has no default | If pydantic-settings version installs pydantic v1 compat shim, the field may silently default to None | T2, T6)`

2. `(agent_loop is async and store methods are awaited directly from event loop | §2 Types: agent_loop signature; ConversationStore methods are async | If agent_loop were called via asyncio.to_thread (old design), store.get/append would need asyncio.run() wrappers, causing "no running event loop" errors | T5, T6)`

3. `(llm_with_tools.invoke() is synchronous and its result is a valid AIMessage with .tool_calls attribute | §2 Types: agent_loop contract; get_llm_with_tools return type | If langchain-openai changes invoke() return shape, the loop breaks silently | T5, T8)`

4. `(yfinance.Ticker(ticker).info["regularMarketPrice"] is the canonical signal for no data | §2 Types: get_stock_info contract; tool docstring | If Yahoo Finance API changes field names, the validity check fails silently and the tool returns garbage | T4, T8)`

5. `(ROLE_MAP lookup uses type() identity not isinstance() | §2 Types: ROLE_MAP dict[type, str]; serialize_content | If a LangChain subclass of AIMessage is returned, type() won't match and role falls back to "unknown" | T6, T8)`

### 5.3 Highest Re-Plan Risk

**T5 (Agent Loop)** is the highest technical re-plan risk. The sync `llm_with_tools.invoke()` call inside an async function is the only deliberate spec compromise. If the evaluator runs under asyncio debug mode, the event loop will emit "coroutine was never awaited" or blocking call warnings. This is acknowledged in the spec and in the T5 kill criteria, but it could surface as a test failure or a runtime complaint requiring the `asyncio.to_thread` wrapper — which is a scope expansion into T5 without changing T6.

**Process risk note:** T2 (schemas) anchors all downstream contract surfaces. If the `ChatRequest.conversation_id` field type is wrong (e.g. `str` instead of `Optional[str]`), T5 and T6 both fail silently — T6 would never generate a UUID for null values.

### 5.4 Hidden Couplings

All entries use the required tuple shape: `(claim | contract surface | failure mode | subtask IDs)`

1. **SUSPECTED** — `(init_singletons sets module-level globals _LLM_WITH_TOOLS and _TOOL_MAP in tools.py; agent_loop reads them via get_llm_with_tools() / get_tool_map() | §2 Types: init_singletons, get_llm_with_tools, get_tool_map | If T4 and T6 are executed by different executors and the import path changes, the singleton is initialized in a different module namespace than the one agent_loop reads | T4, T5, T6)`. What would disprove: both T4 and T6 use `from app.agent import tools as agent_tools` / `from app.agent.tools import get_llm_with_tools` consistently — executor must verify import paths match.

2. **CONFIRMED** — `(SYSTEM_PROMPT is imported in agent_loop from app.agent.prompts | §2 Naming: SYSTEM_PROMPT; §2 Types: agent_loop | If T2 places SYSTEM_PROMPT in a different module path (e.g. app/prompts.py), T5 import fails | T2, T5)`. Evidence: spec §4.5 import block explicitly references `from app.agent.prompts import SYSTEM_PROMPT`.

3. **CONFIRMED** — `(POST /chat test in T8 must mock agent_loop or mock the LLM at the TestClient level | §2 Tests: no live API calls; §2 Types: agent_loop signature | If T8 mocks at the wrong layer (e.g. patches tools.py but not the LLM invoke), the async agent_loop still blocks waiting for a real OpenAI response | T6, T8)`. Evidence: async agent_loop is awaited directly by the route handler; mocking must occur at `app.agent.loop.agent_loop` or at `langchain_openai.ChatOpenAI`.

4. **SUSPECTED** — `(ConversationStore._lock is an asyncio.Lock created at import time; if tests run in a different event loop than the one that created the lock, lock operations may panic | §2 Types: ConversationStore; §2 Tests: pytest framework | In pytest-asyncio with "auto" mode, each test function may run in a fresh event loop, but the store instance is shared if created in a module-level fixture | T3, T8)`. What would disprove: conftest.py creates a fresh ConversationStore per test function.

---

## §6. Executor Packets

Packets are saved at:
- `packets/T1.md`
- `packets/T2.md`
- `packets/T3.md`
- `packets/T4.md`
- `packets/T5.md`
- `packets/T6.md`
- `packets/T7.md`
- `packets/T8.md`

Each packet is self-contained: §1, §2 (verbatim), the subtask's §4 block, filtered §5.2 and §5.4 items, and resolved inputs.

---

## §7. Amendment Subtasks

*None at v1.0. Populated if audit produces blocking findings.*

---

## §8. Auditor Handoff

Produced at plan version 1.1. All 8 subtasks committed; 59 tests passing.

---

### §8.1 Completion Snapshot

**Tree SHA at handoff:** `ada6731c3a56a159c5772d779c19174cb45bb32b`

**Verification command (clean checkout of handoff SHA):**
```
python -m pytest tests/ -v --tb=short
```

**Result:**
```
59 passed, 2 warnings in 0.83s   exit_code=0
Python 3.14.2, pytest-9.0.2, pluggy-1.6.0
asyncio: mode=Mode.STRICT
```

**Warnings (non-blocking):**
1. `langchain_core/utils/pydantic.py`: `UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater` — upstream library issue, not our code.
2. `app/config.py:3`: `PydanticDeprecatedSince20: Support for class-based config is deprecated, use ConfigDict instead` — our `class Config:` inner class is functional via compat shim but should be updated to `model_config = SettingsConfigDict(...)` for production. No test failures.

**Lastfailed cache note:** `.pytest_cache/v/cache/lastfailed` contains a stale entry for `tests/test_config.py::test_settings_raises_validation_error_without_openai_api_key` — this test was renamed by the T2 executor to `test_settings_openai_api_key_has_no_default` and `test_config_module_import_fails_without_openai_api_key`. The entry is stale; both replacement tests PASSED in the handoff run. Not a blocking issue.

**Commit history (T1→T8, all on `master`):**
```
ada6731  T8: Add integration test suite
3d0e404  T6: FastAPI main with /chat routes, lifespan, and ROLE_MAP serialization
51982ab  T5: Implement explicit ReAct agent_loop with MAX_ITERATIONS cap and architectural decision log
f8083f0  T4: Add Yahoo Finance tool module with singleton accessors
421a6fc  T2: Add config, schemas, and SYSTEM_PROMPT
17914bf  T3: Implement ConversationStore with async lock and copy-on-get
4f6bc0d  T7: Add Dockerfile and docker-compose for single-worker API
5da03b7  T1: Add project scaffold with package layout and dependencies
```

---

### §8.2 Artifact Chain

All paths resolve at `git show HEAD:<path>` at the handoff SHA.

| Artifact | Repo path |
|----------|-----------|
| Binding spec | `seeds-match-challenge-spec.md` |
| Plan (this file) | `.dev/plans/seeds-match-api/plan.md` |
| T1 packet | `.dev/plans/seeds-match-api/packets/T1.md` |
| T2 packet | `.dev/plans/seeds-match-api/packets/T2.md` |
| T3 packet | `.dev/plans/seeds-match-api/packets/T3.md` |
| T4 packet | `.dev/plans/seeds-match-api/packets/T4.md` |
| T5 packet | `.dev/plans/seeds-match-api/packets/T5.md` |
| T6 packet | `.dev/plans/seeds-match-api/packets/T6.md` |
| T7 packet | `.dev/plans/seeds-match-api/packets/T7.md` |
| T8 packet | `.dev/plans/seeds-match-api/packets/T8.md` |
| T5 decision log | `.dev/decision-logs/T5-agent-loop.md` |
| T6 decision log | `.dev/decision-logs/T6-main.md` |
| Changelog | `CHANGELOG.MD` |

No out-of-tree binding artifacts. The `seeds-match-challenge-spec.md` spec is at repo root and tracked.

---

### §8.3 §2 Evidence

Per-row landed signals for every binding in §2.

#### Types / Interfaces

| §2 Symbol | Shipped file:symbol | Proving test |
|-----------|---------------------|--------------|
| `Settings(openai_api_key: str, model_name: str = "gpt-4o-mini")` | `app/config.py:3-5` — `class Settings(BaseSettings)` with no-default `openai_api_key: str` | `tests/test_config.py::test_settings_openai_api_key_has_no_default` PASSED; `test_settings_model_name_defaults_to_gpt_4o_mini` PASSED |
| `ChatRequest(message: str, conversation_id: Optional[str] = None)` | `app/schemas.py` | `tests/test_schemas.py::test_chat_request_conversation_id_optional_defaults_none` PASSED |
| `ChatResponse(conversation_id: str, reply: str)` | `app/schemas.py` | `tests/test_schemas.py::test_chat_response_shape` PASSED |
| `MessageRecord(role: str, content: str)` | `app/schemas.py` | `tests/test_schemas.py::test_message_record_shape` PASSED |
| `HistoryResponse(conversation_id: str, messages: list[MessageRecord])` | `app/schemas.py` | `tests/test_schemas.py::test_history_response_shape` PASSED |
| `ErrorResponse(error: str, detail: str)` | `app/schemas.py` | `tests/test_schemas.py::test_error_response_shape` PASSED |
| `ConversationStore` async `.get` / `.append` / `.exists` | `app/memory/store.py:5-38` | `tests/test_store.py::test_store_methods_are_async` PASSED; `test_store_uses_asyncio_lock` PASSED; `test_get_returns_copy_not_internal_reference` PASSED |
| `agent_loop(conversation_id, user_message, store) -> str` (async) | `app/agent/loop.py:8-12` | `tests/test_loop.py::test_agent_loop_smoke_no_tool_calls` PASSED; `test_agent_loop_tool_call_then_final_answer` PASSED |
| `init_singletons(llm: BaseChatModel) -> None` | `app/agent/tools.py:47-51` | `tests/test_tools.py::test_init_singletons_registers_get_stock_info_in_tool_map` PASSED |
| `get_llm_with_tools()` | `app/agent/tools.py:53-54` | Indirectly: all `test_agent_loop_*` tests invoke through this accessor PASSED |
| `get_tool_map() -> dict` | `app/agent/tools.py:56-57` | `tests/test_tools.py::test_init_singletons_registers_get_stock_info_in_tool_map` PASSED |
| `get_stock_info(ticker: str) -> str` `@tool` | `app/agent/tools.py:5-38` | `tests/test_tools.py::test_get_stock_info_valid_ticker` PASSED; `test_get_stock_info_invalid_ticker_no_price` PASSED; `test_get_stock_info_yfinance_exception` PASSED |
| `SYSTEM_PROMPT` str constant | `app/agent/prompts.py` | `tests/test_prompts.py::test_system_prompt_matches_contract_exactly` PASSED; `test_system_prompt_mentions_get_stock_info_tool` PASSED |
| `ROLE_MAP: dict[type, str]` | `app/main.py:17-22` — `{HumanMessage: "human", AIMessage: "ai", ToolMessage: "tool", SystemMessage: "system"}` | `tests/test_main.py::test_role_map_is_explicit_type_keyed_dict` PASSED |
| `serialize_content(message: BaseMessage) -> str` | `app/main.py:24-41` | `tests/test_main.py::test_serialize_content_string` PASSED; `test_serialize_content_list_text_blocks` PASSED; `test_serialize_content_empty_list_returns_tool_call_sentinel` PASSED |
| `MAX_ITERATIONS = 10` | `app/agent/loop.py:6` | `tests/test_loop.py::test_agent_loop_max_iterations_fallback` PASSED; `tests/test_app.py::test_agent_loop_max_iterations_fallback` PASSED |

#### Error Envelope

| Condition | Shipped file:line | Proving test |
|-----------|-------------------|--------------|
| POST 500 `{"error": "Agent execution failed", "detail": str(e)}` | `app/main.py:84-87` — `HTTPException(status_code=500, detail={...})` | `tests/test_main.py::test_post_chat_agent_failure_returns_structured_500` PASSED |
| GET 404 unknown conversation_id | `app/main.py:93-94` | `tests/test_main.py::test_get_history_unknown_conversation_returns_404` PASSED; `tests/test_app.py::test_get_history_404_unknown_id` PASSED |
| Startup failure on missing key | `app/config.py:4` (no-default field) + `app/main.py:57-58` (lifespan belt-and-suspenders check) | `tests/test_config.py::test_settings_openai_api_key_has_no_default` PASSED; `test_config_module_import_fails_without_openai_api_key` PASSED |

#### Naming

All module paths, class names, function names, and constant names confirmed identical to spec §3/§4 by direct file read at handoff SHA. No drift detected.

#### Logging

No `print()` statements in production paths. Verbally communicated limitation documented in T5 decision log (sync `invoke` in async context → `asyncio.to_thread` for production).

#### Tests

Framework: pytest 9.0.2. Location: `tests/` (9 test files, 59 test functions). Naming: `test_<feature>_<condition>`. All external calls mocked (yfinance via `unittest.mock.patch`, ChatOpenAI via conftest fixture). Coverage: all §2 surfaces covered (see table above).

#### CLI Surface

| String | Shipped in | Proving check |
|--------|-----------|---------------|
| `uvicorn app.main:app --host 0.0.0.0 --port 8000` | `Dockerfile` CMD | Phase 3 manual `docker compose up --build` (no unit test — per plan T7) |
| `POST /chat` | `app/main.py:73` — `@app.post("/chat", ...)` | `tests/test_app.py::test_chat_generates_conversation_id` PASSED |
| `GET /chat/{conversation_id}` | `app/main.py:91` — `@app.get("/chat/{conversation_id}", ...)` | `tests/test_app.py::test_get_history_returns_messages` PASSED |

---

### §8.4 §5 Disposition

#### §5.2 Load-Bearing Assumptions

| # | Assumption tuple | Disposition |
|---|-----------------|-------------|
| 1 | `(pydantic-settings raises ValidationError on missing openai_api_key \| Settings.openai_api_key no-default \| pydantic v1 compat shim may silently default to None \| T2, T6)` | **CLOSED** — `test_settings_openai_api_key_has_no_default` PASSED; `test_config_module_import_fails_without_openai_api_key` PASSED. Note: `class Config:` deprecation warning is cosmetic; behavior is correct. |
| 2 | `(agent_loop is async and store methods are awaited directly from event loop \| agent_loop signature; ConversationStore methods async \| asyncio.to_thread design would require asyncio.run() wrappers \| T5, T6)` | **CLOSED** — `app/main.py:77` uses `await agent_loop(...)`; `app/agent/loop.py:8` declares `async def agent_loop`; all async store awaits confirmed at lines 27, 34, 38, 55. `test_agent_loop_smoke_no_tool_calls` PASSED. |
| 3 | `(llm_with_tools.invoke() is synchronous and returns a valid AIMessage with .tool_calls \| agent_loop contract; get_llm_with_tools return type \| langchain-openai return shape change breaks loop silently \| T5, T8)` | **CLOSED** — `test_agent_loop_tool_call_then_final_answer` PASSED with `AIMessage(content="...", tool_calls=[...])` mock. Production gap documented in T5 decision log (`ainvoke` / `asyncio.to_thread`). |
| 4 | `(yfinance.Ticker(ticker).info["regularMarketPrice"] is the canonical no-data signal \| get_stock_info contract \| Yahoo Finance field rename breaks validity check silently \| T4, T8)` | **CLOSED** — `test_get_stock_info_invalid_ticker_no_price` PASSED; `test_get_stock_info_empty_info_dict` PASSED; named accepted fragility A11. |
| 5 | `(ROLE_MAP lookup uses type() identity not isinstance() \| ROLE_MAP dict[type, str]; serialize_content \| LangChain subclass returns "unknown" role \| T6, T8)` | **CLOSED** — `test_role_map_is_explicit_type_keyed_dict` PASSED; `app/main.py:98` uses `ROLE_MAP.get(type(m), "unknown")`; "unknown" fallback present and observable. |

#### §5.4 Hidden Couplings

| # | Coupling tuple | Disposition |
|---|----------------|-------------|
| 1 | **SUSPECTED** `(init_singletons sets module-level globals _LLM_WITH_TOOLS / _TOOL_MAP; agent_loop reads via accessors \| init_singletons, get_llm_with_tools, get_tool_map \| different import namespace if paths diverge \| T4, T5, T6)` | **CLOSED** — `app/main.py:11` imports `from app.agent import tools as agent_tools`; `app/agent/loop.py:3` imports `from app.agent.tools import get_llm_with_tools, get_tool_map`. Same module object via Python's import cache. `test_init_singletons_registers_get_stock_info_in_tool_map` PASSED; `test_agent_loop_tool_call_then_final_answer` PASSED. |
| 2 | **CONFIRMED** `(SYSTEM_PROMPT imported from app.agent.prompts \| §2 Naming: SYSTEM_PROMPT \| path drift breaks T5 import \| T2, T5)` | **CLOSED** — `app/agent/loop.py:2` imports `from app.agent.prompts import SYSTEM_PROMPT`; `tests/test_prompts.py::test_system_prompt_matches_contract_exactly` PASSED. No path drift. |
| 3 | **CONFIRMED** `(POST /chat integration tests must mock agent_loop at the right layer \| §2 Tests: no live API calls \| yfinance-only mock still blocks on real OpenAI \| T6, T8)` | **CLOSED** — `tests/conftest.py` patches `langchain_openai.ChatOpenAI` at TestClient startup; all integration tests PASSED with no live calls. `test_chat_generates_conversation_id` et al PASSED. |
| 4 | **SUSPECTED** `(ConversationStore._lock created at import; tests in different event loop may panic \| ConversationStore; pytest-asyncio \| T3, T8)` | **CLOSED** — `tests/conftest.py` monkeypatches `app.main.store` with a fresh `ConversationStore()` per test; async tests instantiate their own store. `test_client_store_isolation_seed/verify` PASSED; `test_concurrent_appends_on_same_id` PASSED. |

---

### §8.5 Cold-Read Seeds

Files recommended for the auditor's narrative-blind Phase 0 read — highest drift-surface risk first:

1. `app/agent/loop.py` — primary evaluation artifact; termination condition `not response.tool_calls`; `MAX_ITERATIONS`; system prompt injection (not stored); sync `invoke` gap.
2. `app/main.py` — `ROLE_MAP` (A9 fix: type-keyed, not string-derived); `serialize_content` (A2 fix: list content); 500 error envelope shape; lifespan singleton init.
3. `app/memory/store.py` — `asyncio.Lock` discipline (A8 fix: not `threading.Lock`); copy-on-get; single-worker constraint documented.
4. `app/agent/tools.py` — error-as-string contract (never raise from tool); module-level singletons (A7 fix: not per-call); `TOOLS` list and `_TOOL_MAP` key matching.
5. `tests/test_loop.py` — `MAX_ITERATIONS` fallback falsifier; termination condition via `tool_calls` presence; unknown tool error path.
6. `.dev/decision-logs/T5-agent-loop.md` — architectural rationale: why explicit loop over AgentExecutor; sync invoke gap acknowledgement; system prompt injection tradeoff.

---

### §8.6 Audit Remediation Cross-Link

*No §7 amendments fired during plan v1.0–v1.1. §8.6 omitted.*

---

**Deferred items noted in CHANGELOG (non-blocking, all flagged as accepted):**
1. `app/config.py` `class Config:` → `SettingsConfigDict` migration (Pydantic v2 deprecation warning, cosmetic)
2. Invalid `model_name` env value not validated until LLM init at startup (T2 CHANGELOG note)
3. `AIMessage.content` non-str list coercion has no dedicated standalone falsifier test (T5 CHANGELOG note; covered implicitly by `test_serialize_content_list_*`)
4. Lifespan `RuntimeError` on empty-string `OPENAI_API_KEY` not falsified by T8 (T6/T8 CHANGELOG note; pydantic-settings import-time check covers the missing-key case)
