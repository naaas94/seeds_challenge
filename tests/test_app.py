import uuid
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from app.agent.loop import MAX_ITERATIONS, agent_loop
from app.agent.tools import get_stock_info
from app.main import serialize_content
from app.memory.store import ConversationStore


# ── POST /chat ────────────────────────────────────────────────────────────────


def test_chat_generates_conversation_id(client):
    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    uuid.UUID(data["conversation_id"])
    assert "reply" in data


def test_chat_uses_provided_conversation_id(client):
    cid = "test-conv-123"
    response = client.post("/chat", json={"message": "Hello", "conversation_id": cid})
    assert response.status_code == 200
    assert response.json()["conversation_id"] == cid


def test_chat_multi_turn_continuity(client, mock_llm):
    """Second request's LLM invoke must include prior human message in history."""
    response1 = client.post("/chat", json={"message": "First message"})
    assert response1.status_code == 200
    cid = response1.json()["conversation_id"]

    response2 = client.post(
        "/chat", json={"message": "Follow-up", "conversation_id": cid}
    )
    assert response2.status_code == 200

    assert mock_llm.invoke.call_count >= 2
    second_invoke_messages = mock_llm.invoke.call_args_list[1][0][0]
    human_contents = [
        m.content
        for m in second_invoke_messages
        if isinstance(m, HumanMessage)
    ]
    assert "First message" in human_contents
    assert "Follow-up" in human_contents

    history = client.get(f"/chat/{cid}").json()
    roles = [m["role"] for m in history["messages"]]
    assert roles.count("human") == 2


def test_chat_missing_message_returns_422(client):
    response = client.post("/chat", json={})
    assert response.status_code == 422


def test_chat_500_on_agent_exception(client, monkeypatch):
    import app.main as main_module

    async def raise_exc(*args, **kwargs):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr(main_module, "agent_loop", raise_exc)
    response = client.post("/chat", json={"message": "Crash me"})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["error"] == "Agent execution failed"
    assert "LLM exploded" in detail["detail"]


# ── GET /chat/{conversation_id} ───────────────────────────────────────────────


def test_get_history_returns_messages(client):
    response = client.post("/chat", json={"message": "Hello"})
    cid = response.json()["conversation_id"]
    history = client.get(f"/chat/{cid}")
    assert history.status_code == 200
    data = history.json()
    assert data["conversation_id"] == cid
    assert len(data["messages"]) >= 2
    roles = {m["role"] for m in data["messages"]}
    assert "human" in roles
    assert "ai" in roles


def test_get_history_includes_tool_role(client, mock_llm):
    tool_step = AIMessage(
        content="",
        tool_calls=[
            {"name": "get_stock_info", "args": {"ticker": "AAPL"}, "id": "call_1"},
        ],
    )
    final_step = AIMessage(content="AAPL is $195", tool_calls=[])
    mock_llm.invoke.side_effect = [tool_step, final_step]

    mock_tool = MagicMock()
    mock_tool.invoke.return_value = "Ticker: AAPL price block"

    with patch(
        "app.agent.loop.get_tool_map",
        return_value={"get_stock_info": mock_tool},
    ):
        response = client.post("/chat", json={"message": "What is AAPL?"})
    assert response.status_code == 200
    cid = response.json()["conversation_id"]

    history = client.get(f"/chat/{cid}")
    assert history.status_code == 200
    roles = {m["role"] for m in history.json()["messages"]}
    assert {"human", "ai", "tool"}.issubset(roles)


def test_get_history_404_unknown_id(client):
    response = client.get("/chat/nonexistent-id-xyz")
    assert response.status_code == 404


# ── serialize_content ─────────────────────────────────────────────────────────


def test_serialize_content_str():
    msg = AIMessage(content="Hello world", tool_calls=[])
    assert serialize_content(msg) == "Hello world"


def test_serialize_content_list_with_text_block():
    msg = AIMessage(
        content=[{"type": "text", "text": "Hello"}, {"type": "tool_use"}],
        tool_calls=[],
    )
    result = serialize_content(msg)
    assert "Hello" in result


def test_serialize_content_list_no_text_blocks():
    msg = AIMessage(content=[], tool_calls=[])
    result = serialize_content(msg)
    assert result == "[tool call — no text content]"


# ── get_stock_info ────────────────────────────────────────────────────────────


def test_get_stock_info_valid_ticker():
    mock_info = {
        "regularMarketPrice": 195.23,
        "longName": "Apple Inc.",
        "currency": "USD",
        "marketCap": 3_000_000_000_000,
        "trailingPE": 28.5,
        "fiftyTwoWeekHigh": 220.0,
        "fiftyTwoWeekLow": 164.0,
        "longBusinessSummary": "Apple Inc. designs...",
    }
    with patch("app.agent.tools.yf.Ticker") as mock_cls:
        mock_cls.return_value.info = mock_info
        result = get_stock_info.invoke({"ticker": "AAPL"})
    assert "195.23" in result
    assert "Apple Inc." in result


def test_get_stock_info_invalid_ticker_no_price():
    with patch("app.agent.tools.yf.Ticker") as mock_cls:
        mock_cls.return_value.info = {"symbol": "BADTICK"}
        result = get_stock_info.invoke({"ticker": "BADTICK"})
    assert "No data found" in result


def test_get_stock_info_yfinance_exception():
    with patch("app.agent.tools.yf.Ticker", side_effect=Exception("Network error")):
        result = get_stock_info.invoke({"ticker": "AAPL"})
    assert "Failed to retrieve data" in result


# ── MAX_ITERATIONS fallback ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_max_iterations_fallback():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="",
        tool_calls=[
            {"name": "get_stock_info", "args": {"ticker": "AAPL"}, "id": "call_1"},
        ],
    )
    mock_tool = MagicMock()
    mock_tool.invoke.return_value = "price data"

    store = ConversationStore()
    with (
        patch("app.agent.loop.get_llm_with_tools", return_value=mock_llm),
        patch(
            "app.agent.loop.get_tool_map",
            return_value={"get_stock_info": mock_tool},
        ),
    ):
        result = await agent_loop("test-id", "What is AAPL?", store)

    assert "unable to complete" in result.lower()
    assert mock_llm.invoke.call_count == MAX_ITERATIONS


@pytest.mark.asyncio
async def test_fresh_store_fixture_starts_without_conversations(fresh_store):
    assert not await fresh_store.exists("never-written")


# ── ConversationStore isolation ───────────────────────────────────────────────

_stashed_conversation_ids: list[str] = []


def test_client_store_isolation_seed(client):
    """Record a conversation ID; a later test must not see it on a fresh store."""
    response = client.post("/chat", json={"message": "isolation seed"})
    _stashed_conversation_ids.append(response.json()["conversation_id"])


def test_client_store_isolation_verify(client):
    """Fresh store from conftest must not retain IDs from prior test functions."""
    for cid in _stashed_conversation_ids:
        assert client.get(f"/chat/{cid}").status_code == 404
