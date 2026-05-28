from app.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HistoryResponse,
    MessageRecord,
)


def test_chat_request_conversation_id_optional_defaults_none():
    req = ChatRequest(message="hello")
    assert req.conversation_id is None
    assert ChatRequest.model_fields["conversation_id"].default is None


def test_chat_request_accepts_conversation_id():
    req = ChatRequest(message="hello", conversation_id="abc-123")
    assert req.conversation_id == "abc-123"


def test_chat_response_shape():
    resp = ChatResponse(conversation_id="id-1", reply="hi")
    assert resp.conversation_id == "id-1"
    assert resp.reply == "hi"


def test_message_record_shape():
    record = MessageRecord(role="human", content="hello")
    assert record.role == "human"
    assert record.content == "hello"


def test_history_response_shape():
    resp = HistoryResponse(
        conversation_id="id-1",
        messages=[MessageRecord(role="ai", content="reply")],
    )
    assert resp.conversation_id == "id-1"
    assert len(resp.messages) == 1
    assert resp.messages[0].role == "ai"


def test_error_response_shape():
    err = ErrorResponse(error="internal_error", detail="boom")
    assert err.error == "internal_error"
    assert err.detail == "boom"
