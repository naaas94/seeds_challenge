import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from unittest.mock import MagicMock, patch

from app.main import app
from app.memory.store import ConversationStore


@pytest.fixture
def fresh_store():
    """Fresh ConversationStore per test — avoids event-loop lock sharing."""
    return ConversationStore()


@pytest.fixture
def client(monkeypatch):
    """
    TestClient with lifespan. Patches ChatOpenAI to avoid live API calls.
    Resets the module-level store to a fresh ConversationStore per test.
    """
    import app.main as main_module

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(content="Test reply", tool_calls=[])

    fresh = ConversationStore()
    monkeypatch.setattr(main_module, "store", fresh)

    with patch("app.main.ChatOpenAI", return_value=mock_llm):
        with TestClient(app, raise_server_exceptions=True) as test_client:
            yield test_client


@pytest.fixture
def mock_llm(client):
    """The patched ChatOpenAI instance used by the running app's lifespan."""
    import app.agent.tools as tools_module

    return tools_module.get_llm_with_tools()
