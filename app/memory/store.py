import asyncio
from typing import Dict, List
from langchain_core.messages import BaseMessage

class ConversationStore:
    """
    In-process conversation store keyed by conversation_id.

    HARD CONSTRAINT: This store is process-local.
    - Data does not persist across application restarts.
    - With uvicorn --workers N, each worker has its own store instance.
      A POST to worker 1 followed by a GET to worker 2 returns 404.
    - DEPLOYMENT REQUIREMENT: Run with a single worker (default uvicorn behavior).
    - PRODUCTION REMEDIATION: Replace with Redis (with TTL, e.g. 24h session window).
      The interface is backend-agnostic — get/append/exists are the only methods
      agent_loop depends on. Swapping the backend is a one-class change.

    Thread safety: asyncio.Lock() is correct for the async FastAPI event loop.
    The lock protects against concurrent turns on the same conversation_id.
    """

    def __init__(self):
        self._store: Dict[str, List[BaseMessage]] = {}
        self._lock = asyncio.Lock()

    async def get(self, conversation_id: str) -> List[BaseMessage]:
        async with self._lock:
            return list(self._store.get(conversation_id, []))

    async def append(self, conversation_id: str, message: BaseMessage) -> None:
        async with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = []
            self._store[conversation_id].append(message)

    async def exists(self, conversation_id: str) -> bool:
        async with self._lock:
            return conversation_id in self._store
