# Decision Log — T6: FastAPI main.py

**Plan:** seeds-match-api v1.0  
**Subtask:** T6  
**Log tier:** architectural  

## Decision: ROLE_MAP as explicit dict[type, str] instead of class name derivation

**Context:** Adversarial finding A9 identified that deriving roles via `type(m).__name__.lower().replace("message", "")` breaks on any LangChain class rename or subclassing.

**Decision:** Explicit `ROLE_MAP: dict[type, str]` using Python `type()` identity as the key. Falls back to `"unknown"` if a new message type is encountered — safe and observable (test for this in T8).

**Alternatives rejected:**
1. `type(m).__name__` string manipulation — fragile, noted as A9.
2. `isinstance` chain — verbose and order-dependent.
3. LangChain's `.type` property — undocumented contract; different property name across versions.

## Decision: serialize_content handles Union[str, List] content

**Context:** Adversarial finding A2: `AIMessage.content` is `Union[str, List]` when tool calls are present. `str()` on a list produces `"[...]"` garbage in the history response.

**Decision:** `serialize_content()` extracts text blocks from list content and joins them. If no text blocks are present (pure tool-call turns), returns `"[tool call — no text content]"` — a human-readable sentinel that accurately describes the turn.

## Decision: Module-level ConversationStore singleton

**Context:** The store must survive the full lifetime of the application. Each request must read from the same store instance.

**Decision:** `store = ConversationStore()` at module level. FastAPI's single-worker uvicorn (the required deployment) ensures one store instance per process. This is the documented constraint in store.py.

## Decision: Lifespan hook for startup validation and singleton initialization

**Context:** Startup validation (OPENAI_API_KEY) and singleton initialization (init_singletons) must run before the first request, not lazily.

**Decision:** `@asynccontextmanager async def lifespan(app)` handles both. Belt-and-suspenders key check in lifespan — pydantic-settings already raises at import, but the explicit check in lifespan makes the failure message visible in the FastAPI startup logs.
