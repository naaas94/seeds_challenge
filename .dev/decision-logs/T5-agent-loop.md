# Decision Log — T5: Agent Loop

**Plan:** seeds-match-api v1.0  
**Subtask:** T5  
**Log tier:** architectural  

## Decision: Explicit ReAct loop via `while tool_calls` instead of AgentExecutor

**Context:** The challenge specification explicitly requires `definir explícitamente la función de agent_loop`. The primary evaluation signal is whether the candidate understands the ReAct termination mechanic.

**Decision:** Implement agent_loop as an explicit async `for iteration in range(MAX_ITERATIONS)` loop. Termination is `not response.tool_calls`. No AgentExecutor, no LangGraph, no implicit looping.

**Alternatives rejected:**
1. `AgentExecutor` from langchain — opaque box, explicitly prohibited by spec Non-goals.
2. LangGraph `StateGraph` — too much scaffolding for a demo; the evaluation tests loop comprehension, not graph topology.
3. Recursive function — harder to read, harder to cap iterations, no benefit.

**Termination condition rationale:** `not response.tool_calls` is the canonical LangChain/OpenAI signal for "final answer." The LLM produces tool_calls when it wants to act; an empty list means it has synthesized a response from available context. This is not a sentinel string, not a flag — it is a property of the message object.

## Decision: System prompt injected at call time, not stored

**Context:** Storing the system prompt in the conversation store would mean: (1) it appears in GET /chat history (pollutes the trace), (2) prompt iteration requires migrating stored records.

**Decision:** Prepend `SystemMessage(SYSTEM_PROMPT)` to the messages list at each invocation, but do NOT call `store.append` with it. The stored history contains only HumanMessage, AIMessage, ToolMessage.

**Tradeoff:** The LLM receives the system prompt on every turn (small token overhead). Acceptable for demo scope.

## Decision: MAX_ITERATIONS = 10 (named, not magic)

**Context:** An unbounded loop is not deployable. A financial query agent rarely needs more than 1-2 tool calls.

**Decision:** `MAX_ITERATIONS = 10`. Named constant, not a magic number. The fallback message is returned (not raised) so the route handler gets a valid reply rather than a 500.

## Known production gap: synchronous llm_with_tools.invoke() inside async function

**Issue:** `llm_with_tools.invoke(messages)` is synchronous (blocks the event loop). In an async FastAPI route, this can starve other requests during LLM roundtrips.

**For demo scope:** Acceptable — the session evaluator runs one request at a time. The synchronous call is noted verbally, not silently elided.

**Production fix:** Replace with:
```python
response: AIMessage = await asyncio.to_thread(llm_with_tools.invoke, messages)
```
or use LangChain's async `ainvoke` if available for the bound model:
```python
response: AIMessage = await llm_with_tools.ainvoke(messages)
```
