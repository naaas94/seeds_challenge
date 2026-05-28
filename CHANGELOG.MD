# Changelog

## seeds-match-api — 2026-05-28

- T1 (Project scaffold): Added empty Python package markers under `app/`, `app/agent/`, and `app/memory/`, plus `requirements.txt`, `.env.example`, and `tests/__init__.py`. Establishes the module path structure and dependency list for downstream subtasks. + added tests/test_scaffold.py
- T3 (Conversation store): Implemented `app/memory/store.py` with async `get`/`append`/`exists`, `asyncio.Lock`, and list-copy return discipline for in-process per-conversation memory. Enables T5/T6 to persist LangChain messages without cross-worker persistence. + added tests/test_store.py
- T7 (Docker configuration): Added `Dockerfile` (single-worker uvicorn CMD, curl for healthcheck) and `docker-compose.yml` (`api` service, `.env` loading, `/docs` healthcheck). Single-worker CMD preserves in-process `ConversationStore` semantics. Test coverage deferred per plan: Docker correctness is validated by `docker compose up --build` in Phase 3 (no unit-test slice for compose files).
