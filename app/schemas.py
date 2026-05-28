from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    reply: str

class MessageRecord(BaseModel):
    role: str       # "human" | "ai" | "tool" | "system"
    content: str    # Serialized message content (see ROLE_MAP in main.py)

class HistoryResponse(BaseModel):
    conversation_id: str
    messages: list[MessageRecord]

class ErrorResponse(BaseModel):
    error: str
    detail: str
