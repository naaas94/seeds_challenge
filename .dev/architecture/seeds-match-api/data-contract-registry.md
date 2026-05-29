Section:      data-contract-registry
Version:      1.0.0
Last updated: 2026-05-28

```
Contract:       ChatRequest
Module:         app/schemas.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Inbound body for POST /chat
Fields:
  - message: str — user utterance for this turn
  - conversation_id: Optional[str] — existing thread id; null/absent triggers server UUID generation
Validators:     none (beyond Pydantic type coercion)
Consumers:      app/main.py (POST /chat)
Last changed:   2026-05-28
```

```
Contract:       ChatResponse
Module:         app/schemas.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Successful POST /chat response
Fields:
  - conversation_id: str — thread id (generated or echoed)
  - reply: str — final agent text for this turn
Validators:     none
Consumers:      HTTP clients, tests
Last changed:   2026-05-28
```

```
Contract:       HistoryResponse
Module:         app/schemas.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Successful GET /chat/{conversation_id} response
Fields:
  - conversation_id: str
  - messages: list[MessageRecord] — full stored transcript (human, ai, tool; not system)
Validators:     none
Consumers:      HTTP clients, tests
Last changed:   2026-05-28
```

```
Contract:       MessageRecord
Module:         app/schemas.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Serialized LangChain message for history API
Fields:
  - role: str — one of human | ai | tool | system (system not persisted in store today)
  - content: str — output of serialize_content()
Validators:     none at schema layer; role vocabulary enforced in main.py ROLE_MAP
Consumers:      HistoryResponse, GET /chat handler
Last changed:   2026-05-28
```

```
Contract:       ErrorResponse
Module:         app/schemas.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Documented error envelope (spec); partial use in implementation
Fields:
  - error: str
  - detail: str
Validators:     none
Consumers:      Spec / clients; POST /chat 500 uses HTTPException detail dict with same keys
Last changed:   2026-05-28
```

```
Contract:       Settings
Module:         app/config.py
Serialization:  pydantic-settings BaseSettings
Version:        unversioned — tracked by git blame
Purpose:        Application configuration from environment and optional .env file
Fields:
  - openai_api_key: str — required, no default
  - model_name: str — default gpt-4o-mini
Validators:     missing openai_api_key → ValidationError at import
Consumers:      app/main.py lifespan, ChatOpenAI construction
Last changed:   2026-05-28
```

```
Contract:       ConversationHistory (implicit)
Module:         app/memory/store.py
Serialization:  in-memory dict[str, list[BaseMessage]] (LangChain message objects)
Version:        unversioned — tracked by git blame
Purpose:        Per-conversation ReAct transcript inside one process
Fields:
  - key: conversation_id (str)
  - value: ordered list of HumanMessage, AIMessage, ToolMessage (SystemMessage not stored)
Validators:     asyncio.Lock serializes concurrent access per process
Consumers:      agent_loop, GET /chat history
Last changed:   2026-05-28
```

```
Contract:       Tool dispatch payload (implicit)
Module:         app/agent/loop.py (from AIMessage.tool_calls)
Serialization:  LangChain tool_calls list elements (dict with name, args, id)
Version:        unversioned — governed by langchain-openai bind_tools
Purpose:        Bridge LLM tool invocation to get_stock_info
Fields:
  - name: str — must match tool registry key (get_stock_info)
  - args: dict — ticker and other tool parameters
  - id: str — correlated in ToolMessage.tool_call_id
Validators:     unknown tool name → error string ToolMessage; tool exceptions → error string ToolMessage
Consumers:      agent_loop, get_tool_map
Last changed:   2026-05-28
```
