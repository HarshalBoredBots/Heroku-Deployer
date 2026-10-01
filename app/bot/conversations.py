"""In-memory FSM for multi-step conversation flows."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

STALE_AFTER_SECONDS = 30 * 60


@dataclass
class ConversationState:
    flow: str
    step: str
    data: dict[str, Any] = field(default_factory=dict)
    last_touched: float = field(default_factory=time.monotonic)


class ConversationManager:
    def __init__(self) -> None:
        self._states: dict[int, ConversationState] = {}
        self._lock = asyncio.Lock()

    async def start(self, user_id: int, flow: str, step: str, **initial_data) -> ConversationState:
        async with self._lock:
            state = ConversationState(flow=flow, step=step, data=dict(initial_data))
            self._states[user_id] = state
            return state

    async def get(self, user_id: int) -> ConversationState | None:
        async with self._lock:
            state = self._states.get(user_id)
            if state is None:
                return None
            if time.monotonic() - state.last_touched > STALE_AFTER_SECONDS:
                del self._states[user_id]
                return None
            state.last_touched = time.monotonic()
            return state

    async def set_step(self, user_id: int, step: str) -> None:
        state = await self.get(user_id)
        if state:
            state.step = step

    async def update_data(self, user_id: int, **kwargs) -> None:
        state = await self.get(user_id)
        if state:
            state.data.update(kwargs)

    async def clear(self, user_id: int) -> None:
        async with self._lock:
            self._states.pop(user_id, None)


conversation_manager = ConversationManager()
