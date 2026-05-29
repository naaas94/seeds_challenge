Section:      external-input-sources
Version:      1.0.0
Last updated: 2026-05-28

```
Source:               API clients (POST /chat, GET /chat/{id})
Format:               JSON over HTTP
Parser:               FastAPI / Pydantic (ChatRequest, path params)
Trust level:          untrusted — no authentication; conversation_id and message content are client-controlled
Surfaces extracted:   message text, optional conversation_id
Surfaces NOT extracted: no file uploads, no headers beyond standard HTTP
Volume:               low (challenge / demo scope)
Sensitivity:          messages forwarded to OpenAI; treat as user PII if deployed beyond demo
Owner module:         app/main.py
```

```
Source:               Yahoo Finance responses via yfinance
Format:               Python dict (Ticker.info)
Parser:               yfinance (unpinned in requirements.txt)
Trust level:          partially trusted — third-party market data; not validated beyond regularMarketPrice presence
Surfaces extracted:   longName, regularMarketPrice, currency, marketCap, trailingPE, fiftyTwoWeekHigh/Low, longBusinessSummary (truncated to 400 chars)
Surfaces NOT extracted: full raw info dict not returned to client; no historical series in v1
Volume:               one lookup per tool invocation
Sensitivity:          public market data; incorrect ticker handling affects answer quality not security boundary
Owner module:         app/agent/tools.py
```

```
Source:               OpenAI model outputs (tool_calls and text)
Format:               LangChain AIMessage / tool_calls structures
Parser:               langchain-openai invoke path
Trust level:          partially trusted — tool args drive yfinance calls; unknown tool names handled in loop
Surfaces extracted:   tool name, args, textual content
Surfaces NOT extracted: no arbitrary code execution path; tools limited to registered TOOLS list
Volume:               up to MAX_ITERATIONS (10) LLM calls per user turn
Sensitivity:          model may hallucinate tickers or financial claims; mitigated by tool-first prompt, not by hard guardrails
Owner module:         app/agent/loop.py
```

```
Source:               Environment / .env configuration
Format:               KEY=VALUE env vars
Parser:               pydantic-settings
Trust level:          trusted in deployment (operator-supplied secrets)
Surfaces extracted:   OPENAI_API_KEY, MODEL_NAME
Surfaces NOT extracted: no multi-tenant secret routing
Volume:               static at process start
Sensitivity:          API key compromise exposes OpenAI account
Owner module:         app/config.py
```
