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
