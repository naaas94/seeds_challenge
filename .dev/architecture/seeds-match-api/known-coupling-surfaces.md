Section:      known-coupling-surfaces
Version:      1.0.0
Last updated: 2026-05-28

```
Surface:      Tool registry key get_stock_info
Shared by:    app/agent/tools.py (@tool name) ↔ app/agent/prompts.py (SYSTEM_PROMPT text) ↔ app/agent/loop.py (tool_map dispatch)
Failure mode: Renaming the tool function or decorator without updating the prompt and tests causes LLM calls that do not dispatch or map to None
Confirmed:    yes — source: tools.py, prompts.py, loop.py
```

```
Surface:      History API role strings (human | ai | tool | system)
Shared by:    app/main.py ROLE_MAP ↔ app/schemas.py MessageRecord comment ↔ seeds-match-challenge-spec.md §2
Failure mode: Drift between ROLE_MAP values and client/evaluator expectations breaks history contract tests
Confirmed:    yes — source: main.py, schemas.py, spec
```

```
Surface:      Yahoo Finance validity signal regularMarketPrice
Shared by:    app/agent/tools.py ↔ tests/test_tools.py ↔ spec §4 (accepted fragility A11)
Failure mode: Yahoo changes info schema; tool may return misleading data or false negatives for valid tickers
Confirmed:    yes — source: tools.py, plan adversarial notes
```

```
Surface:      Module-level ConversationStore singleton (main.store)
Shared by:    app/main.py ↔ tests/conftest.py (monkeypatch) ↔ agent_loop(store=...) parameter defaulting to injected instance in tests only via main
Failure mode: Multi-worker uvicorn splits conversations across processes; POST on worker A + GET on worker B → 404
Confirmed:    yes — source: store.py docstring, Dockerfile single-worker CMD
```

```
Surface:      init_singletons must complete before first agent_loop
Shared by:    app/main.py lifespan ↔ app/agent/tools.py globals ↔ app/agent/loop.py getters
Failure mode: First request before lifespan finishes could use None singletons [needs confirmation — FastAPI lifespan ordering typically prevents this]
Confirmed:    suspected — basis: module-level _LLM_WITH_TOOLS = None until init
```

```
Surface:      Environment variable names OPENAI_API_KEY / MODEL_NAME
Shared by:    app/config.py (pydantic field names) ↔ .env.example ↔ docker-compose.yml environment
Failure mode: Misnamed env vars in deployment → startup ValidationError or wrong model
Confirmed:    yes — source: config.py, .env.example, docker-compose.yml
```

none at this time — additional human-known coupling (DB columns, shared constants beyond above) pending user input (2026-05-28)
