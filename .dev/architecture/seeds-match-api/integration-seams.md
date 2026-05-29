Section:      integration-seams
Version:      1.0.0
Last updated: 2026-05-28

```
Seam:          OpenAI Chat Completions (via LangChain OpenAI)
Direction:     outbound
Protocol:      HTTPS REST (encapsulated by langchain-openai ChatOpenAI)
Auth:          API key from OPENAI_API_KEY / settings.openai_api_key
Data sent:     Conversation messages (system prompt + stored history) per agent_loop iteration
Data received: AIMessage with optional tool_calls and text content
Error modes:   Network failures, auth failures, rate limits, model errors — bubble to POST /chat as 500
Retry policy:  none
Owner module:  app/main.py (client construction), app/agent/loop.py (invoke)
```

```
Seam:          Yahoo Finance market data (via yfinance)
Direction:     inbound (data fetch triggered by agent tool)
Protocol:      yfinance library HTTP/scrape to Yahoo endpoints
Auth:          none (public market data)
Data sent:     Ticker symbol (uppercased, stripped)
Data received: Ticker.info dict (price, cap, ratios, summary fields)
Error modes:   Invalid ticker (empty info or missing regularMarketPrice), network/parse exceptions, stale or delayed quotes
Retry policy:  none at application layer; tool returns error string
Owner module:  app/agent/tools.py
```

```
Seam:          HTTP clients (challenge evaluator / API consumers)
Direction:     inbound
Protocol:      HTTP/JSON (FastAPI)
Auth:          none (non-goal per spec)
Data sent:     ChatRequest on POST /chat
Data received: ChatResponse, HistoryResponse, or error payloads (404 plain detail string; 500 structured dict)
Error modes:   404 unknown conversation on GET; 500 agent execution failure
Retry policy:  none
Owner module:  app/main.py
```

```
Seam:          Docker host environment
Direction:     inbound (configuration)
Protocol:      environment variables / .env file
Auth:          n/a
Data sent:     OPENAI_API_KEY, MODEL_NAME
Data received: none
Error modes:   Missing key → ValidationError at import; empty key → lifespan RuntimeError (belt-and-suspenders)
Retry policy:  none
Owner module:  app/config.py, docker-compose.yml
```
