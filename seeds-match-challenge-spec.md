# Seeds Match Challenge — Build Specification

> Version: v1.0 (post-adversarial-pass)
> Status: Build-ready. 14 adversarial findings reviewed; 12 addressed in this spec, 2 noted as accepted constraints.
> Context: Live technical session — code written collaboratively in real time. This document is internalization material, not a pre-submission artifact.

---

## 1. Challenge Context

### What Is Being Built

A Python API exposing a conversational agent with per-conversation memory and a Yahoo Finance tool. Two HTTP endpoints. Runs in Docker. The explicit constraint — `definir explícitamente la función de agent_loop` — is the primary evaluation signal: it distinguishes candidates who understand the ReAct loop mechanics from those who treat `AgentExecutor` as a black box.

### What the Live Session Actually Tests

1. **ReAct loop comprehension** — Can you write an explicit termination-condition loop (`while tool_calls`) vs. delegate to `AgentExecutor`?
2. **Conversation isolation** — Separate history per `conversation_id`, correctly scoped across concurrent requests.
3. **Production-oriented design thinking** — Naming the limitations proactively (in-process memory, blocking I/O, yfinance fragility) rather than waiting to be asked.
4. **Tool design** — Docstring as LLM interface contract; error handling that keeps the loop coherent.
5. **Docker literacy** — Environment-variable-driven config, service startup behavior.

### Non-Goals

- Persistence across restarts (named explicitly as a known limitation)
- Authentication / authorization
- Rate limiting
- Streaming responses
- Multiple tool providers

---

## 2. Interface Contract

### Endpoints

```
POST /chat
  Request:  { "message": string, "conversation_id": string | null }
  Response: { "conversation_id": string, "reply": string }
  Errors:   { "error": string, "detail": string }

GET /chat/{conversation_id}
  Response: {
    "conversation_id": string,
    "messages": [{ "role": "human"|"ai"|"tool"|"system", "content": string }]
  }
  Errors: 404 if conversation_id not found in store
```

### Conversation ID Contract

This is the critical multi-turn continuity path. State it explicitly during the session:

- If `POST /chat` receives `conversation_id: null` (or the field is absent), the server generates a UUID and returns it in `ChatResponse.conversation_id`.
- The client **must** echo this ID in all subsequent POSTs for the same conversation thread.
- A `GET /chat/{id}` for an ID not yet present in the store returns **404** — not an empty history.
- History includes all message types: human, AI (even turns with no text content, only tool calls), and tool results. This is intentional — the evaluator will inspect intermediate tool turns.

### HTTP Status Codes

| Condition | Status |
|---|---|
| Successful chat turn | 200 |
| Successful history fetch | 200 |
| Unknown conversation_id on GET | 404 |
| LLM or tool error (caught) | 500 with `{"error": ..., "detail": ...}` |
| Missing/invalid API key at startup | Application fails to start (lifespan validation) |

---

## 3. Architecture

### Module Structure

```
app/
├── main.py              # FastAPI app, lifespan hook, route handlers
├── agent/
│   ├── loop.py          # agent_loop — explicit ReAct loop (the evaluation artifact)
│   ├── tools.py         # YahooFinanceTool + TOOLS list + LLM_WITH_TOOLS + TOOL_MAP
│   └── prompts.py       # SYSTEM_PROMPT constant
├── memory/
│   └── store.py         # ConversationStore — in-process, single-worker
├── schemas.py           # Pydantic request/response/error models
└── config.py            # Settings (Pydantic BaseSettings, env-driven)
Dockerfile
docker-compose.yml
.env.example
requirements.txt
```

### Request Flow

```
POST /chat
  │
  ▼
main.py: route handler
  │  generates conversation_id if absent
  │  calls asyncio.to_thread(agent_loop, ...)       ← non-blocking wrapper (A3)
  │
  ▼
agent/loop.py: agent_loop(conversation_id, message, store)
  │  prepends SYSTEM_PROMPT to messages at call time (not stored)
  │  invokes LLM_WITH_TOOLS (module-level singleton)
  │
  ┌──────── ReAct Loop ────────────────────┐
  │  while response.tool_calls:            │
  │    execute each tool call              │
  │    append ToolMessage to store         │
  │    re-invoke LLM_WITH_TOOLS            │
  └────────────────────────────────────────┘
  │  response.tool_calls is empty → final answer
  │
  ▼
main.py: return ChatResponse(conversation_id, reply)

GET /chat/{conversation_id}
  │
  ▼
store.get(conversation_id) → list[BaseMessage]
serialize with explicit ROLE_MAP and per-type content extraction
return HistoryResponse
```

---

## 4. Component Specifications

### 4.1 config.py

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    model_name: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

`pydantic-settings` (not `python-dotenv`) is the correct pattern for FastAPI. `openai_api_key` has no default — `pydantic-settings` will raise `ValidationError` at import time if the env var is absent, which surfaces as a startup failure before any request is served.

---

### 4.2 prompts.py

```python
# app/agent/prompts.py

SYSTEM_PROMPT = """You are a financial information assistant with access to a tool that retrieves real-time stock data from Yahoo Finance.

When a user asks about a company's stock, financials, price, market cap, or performance, use the get_stock_info tool with the appropriate ticker symbol.

Guidelines:
- Always use the tool to retrieve data before answering financial questions. Do not answer from memory.
- Provide factual information from the tool result: price, market cap, P/E ratio, 52-week range.
- Do not provide investment advice, buy/sell recommendations, or price predictions.
- If the user's request is conversational or non-financial, respond directly without calling the tool.
- If a ticker symbol is ambiguous (e.g., user says "Apple" not "AAPL"), use the most commonly known symbol and confirm it in your response.
- State clearly when data may be delayed (Yahoo Finance typically has 15-minute delays on free tier).
"""
```

The system prompt is the behavioral contract between the developer and the LLM. It must define: when to call the tool, what not to do (financial advice), and how to handle ambiguous input. This is injected at call time — not stored in the conversation history.

---

### 4.3 tools.py

```python
# app/agent/tools.py
from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel
import yfinance as yf

@tool
def get_stock_info(ticker: str) -> str:
    """
    Retrieves current financial data for a publicly traded company using its ticker symbol.
    Returns price, market cap, P/E ratio, 52-week high/low, and a brief business description.
    Use this tool when the user asks about a company's stock, valuation, or financial performance.
    The ticker must be a valid exchange symbol (e.g., AAPL for Apple, MSFT for Microsoft, TSLA for Tesla).
    """
    try:
        t = yf.Ticker(ticker.upper().strip())
        info = t.info
        # yfinance returns an empty dict or minimal dict for invalid tickers
        # regularMarketPrice being None is the canonical signal for "no data"
        if not info or info.get("regularMarketPrice") is None:
            return (
                f"No data found for ticker '{ticker.upper()}'. "
                "Verify the symbol is correct. Common mistakes: use 'GOOGL' not 'GOOGLE', "
                "'BRK-B' not 'Berkshire'."
            )
        return (
            f"Ticker: {ticker.upper()}\n"
            f"Company: {info.get('longName', 'N/A')}\n"
            f"Current Price: {info.get('regularMarketPrice')} {info.get('currency', 'USD')}\n"
            f"Market Cap: {info.get('marketCap')}\n"
            f"P/E Ratio (trailing): {info.get('trailingPE', 'N/A')}\n"
            f"52-Week High: {info.get('fiftyTwoWeekHigh')}\n"
            f"52-Week Low: {info.get('fiftyTwoWeekLow')}\n"
            f"Business Summary: {str(info.get('longBusinessSummary', 'N/A'))[:400]}\n"
            f"Note: Data may be delayed up to 15 minutes."
        )
    except Exception as e:
        # Return error as string — never raise from a tool.
        # The agent loop will receive this as a ToolMessage and can report it to the user.
        return f"Failed to retrieve data for '{ticker}': {str(e)}. This may be a temporary yfinance connectivity issue."

TOOLS = [get_stock_info]

# Module-level singletons — initialized once, not per agent_loop call.
# Populated in main.py after LLM is initialized: tools.init_singletons(llm)
_LLM_WITH_TOOLS: object = None
_TOOL_MAP: dict = {}

def init_singletons(llm: BaseChatModel) -> None:
    """Called once at application startup. Binds tools to LLM and builds the dispatch map."""
    global _LLM_WITH_TOOLS, _TOOL_MAP
    _LLM_WITH_TOOLS = llm.bind_tools(TOOLS)
    _TOOL_MAP = {t.name: t for t in TOOLS}

def get_llm_with_tools():
    return _LLM_WITH_TOOLS

def get_tool_map():
    return _TOOL_MAP
```

**Design decisions to articulate:**
- The docstring is the LLM's interface specification — precise about when to call the tool and what format the input should take.
- Errors returned as strings, never raised — a tool exception would crash the agent loop; a string error gets fed back as a `ToolMessage` and the agent can handle it gracefully.
- `longBusinessSummary` truncated at 400 chars — full summaries are 500-1000 tokens, which bloats the context on multi-turn sessions.
- `yfinance` is a scraper, not an official Yahoo Finance API. It breaks semi-regularly when Yahoo modifies their internal endpoints. The `try/except` is the correct mitigation. In production, you would use the Yahoo Finance official API or a Bloomberg/Refinitiv data provider.

---

### 4.4 store.py

```python
# app/memory/store.py
import asyncio
from typing import Dict, List
from langchain_core.messages import BaseMessage

class ConversationStore:
    """
    In-process conversation store keyed by conversation_id.

    HARD CONSTRAINT: This store is process-local.
    - Data does not persist across application restarts.
    - With uvicorn --workers N, each worker has its own store instance.
      A POST to worker 1 followed by a GET to worker 2 returns 404.
    - DEPLOYMENT REQUIREMENT: Run with a single worker (default uvicorn behavior).
    - PRODUCTION REMEDIATION: Replace with Redis (with TTL, e.g. 24h session window).
      The interface is backend-agnostic — get/append/exists are the only methods
      agent_loop depends on. Swapping the backend is a one-class change.

    Thread safety: asyncio.Lock() is correct for the async FastAPI event loop.
    The lock protects against concurrent turns on the same conversation_id.
    """

    def __init__(self):
        self._store: Dict[str, List[BaseMessage]] = {}
        self._lock = asyncio.Lock()

    async def get(self, conversation_id: str) -> List[BaseMessage]:
        async with self._lock:
            return list(self._store.get(conversation_id, []))

    async def append(self, conversation_id: str, message: BaseMessage) -> None:
        async with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = []
            self._store[conversation_id].append(message)

    async def exists(self, conversation_id: str) -> bool:
        async with self._lock:
            return conversation_id in self._store
```

**On `asyncio.Lock` vs `threading.Lock`:** `asyncio.Lock` is correct for FastAPI's asyncio event loop. `threading.Lock` would also technically work (it doesn't deadlock async code since agent_loop runs via `to_thread`), but is semantically mismatched. Note: since agent_loop runs in a thread pool via `asyncio.to_thread`, the store methods must be awaited from the event loop thread — agent_loop itself calls `asyncio.run(store.get(...))` or is restructured to pass messages as an argument. See §4.5 for the clean resolution.

---

### 4.5 loop.py

```python
# app/agent/loop.py
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import get_llm_with_tools, get_tool_map
from app.memory.store import ConversationStore

MAX_ITERATIONS = 10  # Hard cap. Never let an agent loop unbounded in production.

async def agent_loop(
    conversation_id: str,
    user_message: str,
    store: ConversationStore,
) -> str:
    """
    Explicit ReAct agent loop.

    Termination condition: the LLM produces a response with no tool_calls.
    This is the definition of a final answer — not a special token, not a flag,
    not a string sentinel. An empty tool_calls list IS the termination signal.

    The loop runs until:
    - response.tool_calls is empty (final answer) → return response.content
    - MAX_ITERATIONS is reached → return fallback string

    System prompt is injected at invocation time, not stored in history.
    This allows prompt iteration without migrating stored conversation records.
    """
    await store.append(conversation_id, HumanMessage(content=user_message))

    llm_with_tools = get_llm_with_tools()
    tool_map = get_tool_map()

    for iteration in range(MAX_ITERATIONS):
        # Prepend system prompt at call time — not persisted in store.
        history = await store.get(conversation_id)
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + history

        response: AIMessage = llm_with_tools.invoke(messages)
        await store.append(conversation_id, response)

        # No tool calls → this is the final answer.
        if not response.tool_calls:
            return response.content if isinstance(response.content, str) else str(response.content)

        # Execute all tool calls in this step, append each result.
        for tool_call in response.tool_calls:
            tool = tool_map.get(tool_call["name"])
            if tool is None:
                result = f"Error: tool '{tool_call['name']}' not found. Available tools: {list(tool_map.keys())}"
            else:
                try:
                    result = tool.invoke(tool_call["args"])
                except Exception as e:
                    result = f"Tool execution error: {str(e)}"

            await store.append(
                conversation_id,
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"],
                ),
            )
        # Loop continues — the tool results are now in history, re-invoke the LLM.

    # MAX_ITERATIONS reached without a final answer.
    return "I was unable to complete this request within the allowed steps. Please try rephrasing your question."
```

**The key insight to articulate verbally:** "The termination condition is `not response.tool_calls`. An empty `tool_calls` list IS the final answer signal — there is no special return value, no flag, no sentinel string. Any response with tool calls is an intermediate step. Any response without them is the answer. The loop structure makes this explicit and auditable."

**On `MAX_ITERATIONS`:** "Ten is a reasonable cap for a financial query agent — the use case is shallow (one or two tool calls at most). An unbounded loop is not deployable. The cap is named, not magic."

**On `asyncio.to_thread` resolution:** Since `agent_loop` is now `async`, it can be called directly with `await` from the route handler. `llm_with_tools.invoke()` is still synchronous (blocking) — for a production system, `await asyncio.to_thread(llm_with_tools.invoke, messages)` would be the correct call. For the live demo, synchronous invoke inside an async function is acceptable and should be noted verbally, not silently elided.

---

### 4.6 schemas.py

```python
# app/schemas.py
from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    reply: str

class MessageRecord(BaseModel):
    role: str       # "human" | "ai" | "tool" | "system"
    content: str    # Serialized message content (see ROLE_MAP in main.py)

class HistoryResponse(BaseModel):
    conversation_id: str
    messages: list[MessageRecord]

class ErrorResponse(BaseModel):
    error: str
    detail: str
```

---

### 4.7 main.py

```python
# app/main.py
import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage, BaseMessage

from app.schemas import ChatRequest, ChatResponse, HistoryResponse, MessageRecord, ErrorResponse
from app.memory.store import ConversationStore
from app.agent.loop import agent_loop
from app.agent import tools as agent_tools
from app.config import settings

# ─── Role serialization ─────────────────────────────────────────────────────
# Explicit map — not derived from class name strings.
# Fragility (A9): class name derivation breaks on any upstream LangChain rename.
ROLE_MAP: dict[type, str] = {
    HumanMessage:  "human",
    AIMessage:     "ai",
    ToolMessage:   "tool",
    SystemMessage: "system",
}

def serialize_content(message: BaseMessage) -> str:
    """
    Safe content extraction per message type.
    AIMessage.content is Union[str, List] when tool calls are present.
    ToolMessage.content is always str.
    """
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # List of content blocks — extract text blocks, join.
        text_parts = [
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return " ".join(text_parts) if text_parts else "[tool call — no text content]"
    return str(content)

# ─── Application state ────────────────────────────────────────────────────────
store = ConversationStore()
llm: ChatOpenAI | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: validate config, initialize LLM, bind tools.
    Shutdown: nothing required for demo scope.
    """
    global llm
    # Fail fast if required config is missing.
    # settings.openai_api_key will raise ValidationError at import if absent,
    # but this is an explicit signal during the session.
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Set it in .env or as an environment variable.")

    llm = ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
    )
    # Initialize module-level singletons once — not per request.
    agent_tools.init_singletons(llm)
    yield
    # Shutdown (no teardown needed for in-process store)

app = FastAPI(lifespan=lifespan)

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid.uuid4())
    try:
        reply = await agent_loop(
            conversation_id=conversation_id,
            user_message=request.message,
            store=store,
        )
    except Exception as e:
        # Return 500 with structured error — never expose raw stack traces.
        raise HTTPException(
            status_code=500,
            detail={"error": "Agent execution failed", "detail": str(e)},
        )
    return ChatResponse(conversation_id=conversation_id, reply=reply)


@app.get("/chat/{conversation_id}", response_model=HistoryResponse)
async def get_history(conversation_id: str):
    if not await store.exists(conversation_id):
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
    raw = await store.get(conversation_id)
    messages = [
        MessageRecord(
            role=ROLE_MAP.get(type(m), "unknown"),
            content=serialize_content(m),
        )
        for m in raw
    ]
    return HistoryResponse(conversation_id=conversation_id, messages=messages)
```

---

## 5. Docker Configuration

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Single worker — required for in-process ConversationStore.
# Multi-worker deployment requires Redis-backed store (see store.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - MODEL_NAME=gpt-4o-mini
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/docs"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

### .env.example

```
# Copy to .env and fill in your key before running docker compose up.
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini
```

### requirements.txt

```
fastapi
uvicorn[standard]
langchain-core
langchain-openai
pydantic-settings
yfinance
```

**Note on dependencies:** `langchain` (the umbrella meta-package) is not listed. The correct dependency set for this stack is `langchain-core` (base types and abstractions) + `langchain-openai` (ChatOpenAI integration). The umbrella package installs ~40 unused integrations.

---

## 6. Conversation Management Contract

### Thread Lifecycle

```
First turn (no conversation_id provided):
  POST /chat {"message": "...", "conversation_id": null}
  → server generates UUID
  → appends HumanMessage to store[UUID]
  → runs agent_loop
  → returns {"conversation_id": "UUID", "reply": "..."}

  !! CLIENT MUST STORE AND ECHO THIS ID !!

Subsequent turns:
  POST /chat {"message": "...", "conversation_id": "UUID"}
  → agent_loop receives full history from store[UUID]
  → LLM sees system_prompt + all prior turns
  → new messages appended to store[UUID]

History retrieval:
  GET /chat/UUID
  → returns all messages including AI turns with only tool_calls (content may be empty)
  → and all ToolMessage results
  → 404 if UUID not in store
```

### What Is Stored per Turn

For a single tool-using turn, the store receives:
1. `HumanMessage("What is Apple's stock price?")`
2. `AIMessage(content="", tool_calls=[{"name": "get_stock_info", "args": {"ticker": "AAPL"}, "id": "..."}])`
3. `ToolMessage(content="Ticker: AAPL\nCurrent Price: 195.23...", tool_call_id="...")`
4. `AIMessage(content="Apple (AAPL) is currently trading at $195.23...")`

The history endpoint returns all four. This is correct and intentional — the full reasoning trace is visible.

---

## 7. Known Limitations and Production Delta

### Stated Constraints (articulate proactively)

| Limitation | Root Cause | Production Remediation |
|---|---|---|
| Memory lost on restart | In-process dict | Redis with TTL (e.g. 24h session window) |
| Single-worker only | In-process `ConversationStore` | Redis-backed store; interface is already abstraction-ready |
| Blocking LLM calls in async handler | `langchain-openai` invoke() is synchronous | `asyncio.to_thread()` wrapping or native async client |
| `yfinance` instability | Scraper, not official API | Yahoo Finance API (paid) or Bloomberg/Refinitiv |
| No conversation TTL or pruning | Unbounded growth in demo | Redis TTL, or explicit conversation expiry endpoint |
| No auth | Demo scope | API key header, OAuth2 |
| Data freshness | yfinance has ~15-min delay | Real-time feed subscription |

### The Hierarchy of Things to Say

When asked "what would you change for production?", answer in this order:
1. **Store:** Redis. The interface is already storage-agnostic. One implementation swap.
2. **Concurrency:** `asyncio.to_thread` for LLM calls. Or LangChain's async `ainvoke`.
3. **Data source:** Replace yfinance with an official financial data API.
4. **Observability:** Structured logging per turn (conversation_id, model, latency, tool calls). The history endpoint is a start, but logs need to be external.

---

## 8. Build Checklist

### Phase 1 — Core (first 30–40 min)

- [ ] `config.py` — Pydantic BaseSettings, fail fast on missing `OPENAI_API_KEY`
- [ ] `prompts.py` — SYSTEM_PROMPT with tool-use guidance and financial advice disclaimer
- [ ] `store.py` — `ConversationStore` with `asyncio.Lock`, documented constraints
- [ ] `tools.py` — `get_stock_info` tool with docstring contract, TOOLS list, `init_singletons()`
- [ ] `loop.py` — `agent_loop` async, explicit ReAct loop, system prompt injection, MAX_ITERATIONS
- [ ] `schemas.py` — Request/response/error models
- [ ] `main.py` — lifespan hook, `ROLE_MAP`, `serialize_content()`, two routes with error handling
- [ ] Smoke test: `POST /chat` with "What is Tesla's stock price?" → tool called, price returned

### Phase 2 — Multi-turn and History (next 20 min)

- [ ] Test multi-turn: follow-up question uses prior context
- [ ] Test `GET /chat/{id}` — confirm all message types present and correctly serialized
- [ ] Test unknown conversation_id → 404
- [ ] Test tool failure (invalid ticker) → graceful error message in reply

### Phase 3 — Docker (final 15 min)

- [ ] `Dockerfile` with single-worker CMD
- [ ] `docker-compose.yml` with env_file and healthcheck
- [ ] `.env.example`
- [ ] `requirements.txt` (no umbrella `langchain` package)
- [ ] `docker compose up --build` → smoke test both endpoints

---

## 9. Adversarial Findings Log (Pre-Build Audit)

All 12 findings from the adversarial pass that informed this spec.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| A1 | System prompt never injected in agent_loop; `prompts.py` unreachable from loop | Critical | Prepend `SystemMessage(SYSTEM_PROMPT)` at call time in loop.py; not stored |
| A2 | `AIMessage.content` is `Union[str, List]` when tool calls present; `str()` produces garbage in history | Critical | `serialize_content()` function with explicit per-type extraction |
| A3 | Synchronous agent_loop inside async FastAPI route blocks event loop | Critical | agent_loop is now `async`; `llm.invoke()` is the remaining sync call, noted verbally |
| A4 | No error handling in POST /chat — LLM/tool exceptions surface as raw 500s | Critical | try/except wrapping agent_loop call; `ErrorResponse` schema |
| A5 | config.py referenced but unspecified; app cannot start | Critical | Fully specified Pydantic BaseSettings in §4.1 |
| A6 | No startup validation of OPENAI_API_KEY; silent failure on first request | Critical | FastAPI lifespan hook validates at startup; pydantic-settings raises on missing field |
| A7 | `llm_with_tools` and `tool_map` rebuilt on every agent_loop call | Structural | Module-level singletons in tools.py; `init_singletons(llm)` called once in lifespan |
| A8 | `threading.Lock()` wrong for async FastAPI; breaks under multi-worker | Structural | `asyncio.Lock()`; single-worker constraint documented explicitly |
| A9 | Role derivation via class name string manipulation is fragile | Structural | Explicit `ROLE_MAP: dict[type, str]` in main.py |
| A10 | Multi-turn continuity contract (client must echo conversation_id) never documented | Structural | Explicit thread lifecycle in §6 |
| A11 | `yfinance` is a scraper; breaks on Yahoo API changes | Named fragility | Named in tool docstring and §7 limitations table |
| A12 | `langchain` meta-package in requirements; installs unused weight | Structural | `langchain-core` + `langchain-openai` only |
| A13 | No `.env.example` in project structure | Structural | Added to project structure and §5 |
| A14 | No financial advice disclaimer in system prompt | Product quality | SYSTEM_PROMPT includes explicit disclaimer in §4.2 |
