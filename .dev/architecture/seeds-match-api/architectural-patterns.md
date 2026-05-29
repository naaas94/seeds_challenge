Section:      architectural-patterns
Version:      1.0.0
Last updated: 2026-05-28

none at this time — pending user input (2026-05-28)

**Code-inferred candidates for Phase 8 confirmation** (not recorded as patterns until you supply falsifiers):

| Candidate | Observed in code/tests |
|-----------|------------------------|
| Explicit ReAct loop (no `AgentExecutor`) | `app/agent/loop.py`; spec non-goals |
| Tool functions never raise — errors as return strings | `get_stock_info`, loop tool dispatch |
| System prompt injected at invoke time, not stored | `agent_loop` prepends `SystemMessage` only in memory for LLM call |
| Explicit `ROLE_MAP` for history roles | `app/main.py` |
| No umbrella `langchain` package in requirements | `tests/test_scaffold.py` |
| Single uvicorn worker with in-process store | `Dockerfile` CMD comment, `ConversationStore` docstring |
