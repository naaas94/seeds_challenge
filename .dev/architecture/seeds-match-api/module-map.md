Section:      module-map
Version:      1.0.0
Last updated: 2026-05-28

| Module path | Role | Key files | Stability |
|-------------|------|-----------|-----------|
| `app` | Application root: HTTP surface, lifespan, message serialization for history API | `main.py` | active |
| `app/config` | Environment-driven settings; fail-fast on missing `OPENAI_API_KEY` at import | `config.py` | stable |
| `app/schemas` | Pydantic request/response models for `/chat` endpoints | `schemas.py` | stable |
| `app/agent` | ReAct agent: explicit loop, tools, system prompt | `loop.py`, `tools.py`, `prompts.py` | stable |
| `app/memory` | In-process per-`conversation_id` LangChain message store | `store.py` | stable |
| `tests` | Pytest suite; mocks OpenAI and yfinance; no live network | `conftest.py`, `test_*.py` | active |

**Notes**

- Packages use implicit namespace layout (no `__init__.py` markers in tree); imports use `app.*` paths.
- `tests` is out of runtime deployment but defines falsifiers for several architectural constraints (scaffold, loop, tools).
