import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

os.environ.setdefault("OPENAI_API_KEY", "test-key-for-unit-tests")

from app.main import ROLE_MAP, serialize_content


def test_role_map_is_explicit_type_keyed_dict():
    assert isinstance(ROLE_MAP, dict)
    assert all(isinstance(k, type) for k in ROLE_MAP)
    assert ROLE_MAP[HumanMessage] == "human"
    assert ROLE_MAP[AIMessage] == "ai"


def test_serialize_content_string():
    assert serialize_content(HumanMessage(content="hello")) == "hello"


def test_serialize_content_list_text_blocks():
    msg = AIMessage(content=[{"type": "text", "text": "part one"}, {"type": "text", "text": "part two"}])
    assert serialize_content(msg) == "part one part two"


def test_serialize_content_empty_list_returns_tool_call_sentinel():
    msg = AIMessage(content=[], tool_calls=[{"name": "get_stock_info", "args": {}, "id": "c1"}])
    assert serialize_content(msg) == "[tool call — no text content]"


@pytest.fixture
def client():
    with (
        patch("app.main.ChatOpenAI", return_value=MagicMock()),
        patch("app.main.agent_tools.init_singletons"),
    ):
        from app.main import app

        with TestClient(app) as test_client:
            yield test_client


def test_get_history_unknown_conversation_returns_404(client):
    response = client.get("/chat/does-not-exist")
    assert response.status_code == 404
    assert "does-not-exist" in response.json()["detail"]


def test_post_chat_agent_failure_returns_structured_500(client):
    with patch("app.main.agent_loop", side_effect=RuntimeError("boom")):
        response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 500
    body = response.json()["detail"]
    assert body["error"] == "Agent execution failed"
    assert body["detail"] == "boom"
