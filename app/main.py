import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage, BaseMessage

from app.schemas import ChatRequest, ChatResponse, HistoryResponse, MessageRecord, ErrorResponse
from app.memory.store import ConversationStore
from app.agent.loop import agent_loop
from app.agent import tools as agent_tools
from app.config import settings

# ─── Role serialization ─────────────────────────────────────────────────────
# Explicit map — not derived from class name strings.
# Fragility (A9): class name derivation breaks on any upstream LangChain rename.
ROLE_MAP: dict[type, str] = {
    HumanMessage:  "human",
    AIMessage:     "ai",
    ToolMessage:   "tool",
    SystemMessage: "system",
}

def serialize_content(message: BaseMessage) -> str:
    """
    Safe content extraction per message type.
    AIMessage.content is Union[str, List] when tool calls are present.
    ToolMessage.content is always str.
    """
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # List of content blocks — extract text blocks, join.
        text_parts = [
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return " ".join(text_parts) if text_parts else "[tool call — no text content]"
    return str(content)

# ─── Application state ────────────────────────────────────────────────────────
store = ConversationStore()
llm: ChatOpenAI | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: validate config, initialize LLM, bind tools.
    Shutdown: nothing required for demo scope.
    """
    global llm
    # Fail fast if required config is missing.
    # settings.openai_api_key will raise ValidationError at import if absent,
    # but this is an explicit signal during the session.
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Set it in .env or as an environment variable.")

    llm = ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
    )
    # Initialize module-level singletons once — not per request.
    agent_tools.init_singletons(llm)
    yield
    # Shutdown (no teardown needed for in-process store)

app = FastAPI(lifespan=lifespan)

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid.uuid4())
    try:
        reply = await agent_loop(
            conversation_id=conversation_id,
            user_message=request.message,
            store=store,
        )
    except Exception as e:
        # Return 500 with structured error — never expose raw stack traces.
        raise HTTPException(
            status_code=500,
            detail={"error": "Agent execution failed", "detail": str(e)},
        )
    return ChatResponse(conversation_id=conversation_id, reply=reply)


@app.get("/chat/{conversation_id}", response_model=HistoryResponse)
async def get_history(conversation_id: str):
    if not await store.exists(conversation_id):
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
    raw = await store.get(conversation_id)
    messages = [
        MessageRecord(
            role=ROLE_MAP.get(type(m), "unknown"),
            content=serialize_content(m),
        )
        for m in raw
    ]
    return HistoryResponse(conversation_id=conversation_id, messages=messages)
