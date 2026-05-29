Section:      dependency-graph
Version:      1.0.0
Last updated: 2026-05-28

## Internal dependencies

| Dependent | Depends on | Nature of coupling | Risk if changed independently |
|-----------|-----------|--------------------|------------------------------|
| `app/main` | `app/agent/tools` | Lifespan must call `init_singletons(llm)` before any `agent_loop` invocation; module-level `_LLM_WITH_TOOLS` / `_TOOL_MAP` | Requests hit uninitialized singletons → runtime errors |
| `app/agent/loop` | `app/agent/tools` | Accessors assume startup initialization; uses sync `invoke` on bound LLM inside async handler | Event-loop blocking; behavior change if switched to `ainvoke` without thread offload |
| `app/agent/loop` | `app/memory/store` | Contract is only `get` / `append` / `exists`; stores LangChain types | Replacing store backend requires preserving message type fidelity |
| `app/main` | `app/agent/loop` | Route passes module-level `store` singleton | Tests monkeypatch `main.store`; production multi-worker breaks GET after POST on different worker |
| `app/agent/loop` | `app/agent/prompts` | `SYSTEM_PROMPT` prepended each iteration, not in store | Prompt edits apply immediately; stored histories lack system turns by design |
| `app/agent/tools` | tool name `get_stock_info` | `SYSTEM_PROMPT` references tool by name; `_TOOL_MAP` keys from `@tool` name | Rename tool without updating prompt → LLM calls fail or map miss |
| `tests/conftest` | `app/main.store` | Monkeypatches module-level store per test | Tests may not reflect multi-instance deployment |
| `tests/*` | production modules | Direct imports of internals (`agent_loop`, `ROLE_MAP`, etc.) | Test breakage on refactors even if HTTP contract unchanged |

**Obvious import direction (not duplicated):** `main` → `schemas`, `config`, `memory`, `agent`; `loop` → `prompts`, `tools`, `memory`; `tools` → yfinance/langchain only.

## External dependencies

| Dependency | Version pinned | Role in project | Sensitivity |
|------------|---------------|-----------------|-------------|
| `fastapi` | no (requirements.txt unpinned) | HTTP app, routing, HTTPException | medium |
| `uvicorn[standard]` | no | ASGI server (Docker CMD) | low |
| `langchain-core` | no | Messages, `@tool`, tool binding types | high |
| `langchain-openai` | no | `ChatOpenAI`, `bind_tools`, `invoke` | high |
| `pydantic` | transitive | Schema models | medium |
| `pydantic-settings` | no | `Settings` / env loading | medium |
| `yfinance` | no | Yahoo Finance `Ticker.info` access | high |
| OpenAI API | service | Chat completions via LangChain | high |
| Yahoo Finance (via yfinance) | external data | Stock tool data source | high |

**Deployment constraint (documented in Dockerfile / store):** single uvicorn worker required while `ConversationStore` remains in-process.
