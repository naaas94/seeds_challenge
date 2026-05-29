Section:      public-interface-inventory
Version:      1.0.0
Last updated: 2026-05-28

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `settings` | `app/config` | constant | Singleton `Settings` instance from env | `app/main` | stable |
| `Settings` | `app/config` | class | `openai_api_key: str`, `model_name: str` (default `gpt-4o-mini`) | tests | stable |
| `ChatRequest` | `app/schemas` | class | `message: str`, `conversation_id: Optional[str] = None` | `app/main` (FastAPI) | stable |
| `ChatResponse` | `app/schemas` | class | `conversation_id: str`, `reply: str` | `app/main` (FastAPI) | stable |
| `HistoryResponse` | `app/schemas` | class | `conversation_id: str`, `messages: list[MessageRecord]` | `app/main` (FastAPI) | stable |
| `MessageRecord` | `app/schemas` | class | `role: str`, `content: str` | `app/main` | stable |
| `ErrorResponse` | `app/schemas` | class | `error: str`, `detail: str` | documented contract; 500 uses dict shape in `HTTPException` | stable |
| `SYSTEM_PROMPT` | `app/agent/prompts` | constant | Multi-line financial-assistant system instructions | `app/agent/loop` | stable |
| `agent_loop` | `app/agent/loop` | function | `async (conversation_id, user_message, store) -> str` — explicit ReAct loop | `app/main` | stable |
| `MAX_ITERATIONS` | `app/agent/loop` | constant | `10` — hard cap on ReAct iterations | tests | stable |
| `get_stock_info` | `app/agent/tools` | function (`@tool`) | `(ticker: str) -> str` — Yahoo Finance snapshot as formatted text | LLM via `bind_tools`; `TOOL_MAP` | stable |
| `TOOLS` | `app/agent/tools` | constant | `[get_stock_info]` | `init_singletons` | stable |
| `init_singletons` | `app/agent/tools` | function | `(llm: BaseChatModel) -> None` — binds tools, builds `_TOOL_MAP` | `app/main` lifespan | stable |
| `get_llm_with_tools` | `app/agent/tools` | function | Returns module-level bound LLM singleton | `app/agent/loop` | stable |
| `get_tool_map` | `app/agent/tools` | function | Returns `dict` name → tool for dispatch | `app/agent/loop` | stable |
| `ConversationStore` | `app/memory/store` | class | Async `get` / `append` / `exists` over in-process `BaseMessage` lists | `app/main`, `app/agent/loop`, tests | stable |
| `ROLE_MAP` | `app/main` | constant | Maps LangChain message types → API role strings | `get_history` route | stable |
| `serialize_content` | `app/main` | function | `(message: BaseMessage) -> str` — safe content extraction for history | `get_history` route, tests | stable |
| `app` | `app/main` | constant | FastAPI application instance with lifespan | uvicorn, tests (`TestClient`) | stable |
| `lifespan` | `app/main` | function | Async context manager: init LLM, `init_singletons`, API key check | FastAPI | stable |
| `store` | `app/main` | constant | Module-level `ConversationStore` singleton | routes, tests (monkeypatched) | stable |

**HTTP surface (external callers)**

| Route | Method | Handler | Stability |
|-------|--------|---------|-----------|
| `/chat` | POST | `chat` | stable |
| `/chat/{conversation_id}` | GET | `get_history` | stable |
