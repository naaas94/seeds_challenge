from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.loop import MAX_ITERATIONS, agent_loop
from app.memory.store import ConversationStore

FALLBACK = (
    "I was unable to complete this request within the allowed steps. "
    "Please try rephrasing your question."
)


@pytest.fixture
def store() -> ConversationStore:
    return ConversationStore()


@pytest.mark.asyncio
async def test_agent_loop_smoke_no_tool_calls(store: ConversationStore):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Hello!", tool_calls=[])

    with (
        patch("app.agent.loop.get_llm_with_tools", return_value=mock_llm),
        patch("app.agent.loop.get_tool_map", return_value={}),
    ):
        result = await agent_loop("conv-1", "Hi", store)

    assert result == "Hello!"
    history = await store.get("conv-1")
    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert isinstance(history[1], AIMessage)
    assert not any(isinstance(m, SystemMessage) for m in history)

    call_messages = mock_llm.invoke.call_args[0][0]
    assert isinstance(call_messages[0], SystemMessage)
    assert call_messages[0].content  # SYSTEM_PROMPT injected at call time


@pytest.mark.asyncio
async def test_agent_loop_tool_call_then_final_answer(store: ConversationStore):
    tool_call_response = AIMessage(
        content="",
        tool_calls=[
            {"name": "get_stock_info", "args": {"ticker": "AAPL"}, "id": "call_1"},
        ],
    )
    final_response = AIMessage(content="AAPL is at $195", tool_calls=[])

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [tool_call_response, final_response]

    mock_tool = MagicMock()
    mock_tool.invoke.return_value = "Ticker: AAPL..."

    with (
        patch("app.agent.loop.get_llm_with_tools", return_value=mock_llm),
        patch(
            "app.agent.loop.get_tool_map",
            return_value={"get_stock_info": mock_tool},
        ),
    ):
        result = await agent_loop("conv-1", "What's AAPL price?", store)

    assert result == "AAPL is at $195"
    mock_tool.invoke.assert_called_once_with({"ticker": "AAPL"})
    history = await store.get("conv-1")
    assert len(history) == 4
    assert isinstance(history[2], ToolMessage)


@pytest.mark.asyncio
async def test_agent_loop_max_iterations_fallback(store: ConversationStore):
    tool_call_response = AIMessage(
        content="",
        tool_calls=[
            {"name": "get_stock_info", "args": {"ticker": "AAPL"}, "id": "call_1"},
        ],
    )

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = tool_call_response

    mock_tool = MagicMock()
    mock_tool.invoke.return_value = "data"

    with (
        patch("app.agent.loop.get_llm_with_tools", return_value=mock_llm),
        patch(
            "app.agent.loop.get_tool_map",
            return_value={"get_stock_info": mock_tool},
        ),
    ):
        result = await agent_loop("conv-1", "loop forever", store)

    assert result == FALLBACK
    assert mock_llm.invoke.call_count == MAX_ITERATIONS


@pytest.mark.asyncio
async def test_agent_loop_unknown_tool_returns_error_tool_message(store: ConversationStore):
    tool_call_response = AIMessage(
        content="",
        tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_x"}],
    )
    final_response = AIMessage(content="Sorry, no tool.", tool_calls=[])

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [tool_call_response, final_response]

    with (
        patch("app.agent.loop.get_llm_with_tools", return_value=mock_llm),
        patch("app.agent.loop.get_tool_map", return_value={}),
    ):
        await agent_loop("conv-1", "use bad tool", store)

    history = await store.get("conv-1")
    tool_msgs = [m for m in history if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert "not found" in tool_msgs[0].content
    assert "missing_tool" in tool_msgs[0].content
