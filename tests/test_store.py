import asyncio
import inspect

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.memory.store import ConversationStore


@pytest.fixture
def store() -> ConversationStore:
    return ConversationStore()


def test_store_uses_asyncio_lock(store: ConversationStore):
    assert type(store._lock) is asyncio.Lock


def test_store_methods_are_async(store: ConversationStore):
    for name in ("get", "append", "exists"):
        assert inspect.iscoroutinefunction(getattr(store, name))


@pytest.mark.asyncio
async def test_get_returns_empty_list_for_unknown_id(store: ConversationStore):
    assert await store.get("missing") == []


@pytest.mark.asyncio
async def test_exists_false_until_first_append(store: ConversationStore):
    assert await store.exists("conv-1") is False
    await store.append("conv-1", HumanMessage(content="hello"))
    assert await store.exists("conv-1") is True


@pytest.mark.asyncio
async def test_append_initializes_new_conversation_id(store: ConversationStore):
    await store.append("new-id", HumanMessage(content="first"))
    messages = await store.get("new-id")
    assert len(messages) == 1
    assert messages[0].content == "first"


@pytest.mark.asyncio
async def test_get_returns_copy_not_internal_reference(store: ConversationStore):
    await store.append("conv-1", HumanMessage(content="original"))
    snapshot = await store.get("conv-1")
    snapshot.append(AIMessage(content="mutated via copy"))
    assert len(await store.get("conv-1")) == 1


@pytest.mark.asyncio
async def test_conversations_are_isolated_by_id(store: ConversationStore):
    await store.append("a", HumanMessage(content="a-msg"))
    await store.append("b", HumanMessage(content="b-msg"))
    assert len(await store.get("a")) == 1
    assert len(await store.get("b")) == 1
    assert (await store.get("a"))[0].content == "a-msg"


@pytest.mark.asyncio
async def test_concurrent_appends_on_same_id(store: ConversationStore):
    await asyncio.gather(
        store.append("conv-1", HumanMessage(content="one")),
        store.append("conv-1", HumanMessage(content="two")),
        store.append("conv-1", HumanMessage(content="three")),
    )
    assert len(await store.get("conv-1")) == 3
