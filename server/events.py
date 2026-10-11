"""In-memory event hub: per-run event list and condition variable for SSE streaming and replay."""
import asyncio
import json
from typing import Any


class Stream:
    def __init__(self, replay: bool = False):
        self.events: list[dict[str, Any]] = []
        self.done = False
        self.cond = asyncio.Condition()
        self.replay = replay
        self.rails = None
        self.task = None

    async def publish(self, etype: str, data: dict[str, Any], t: float | None = None):
        async with self.cond:
            self.events.append({"type": etype, "data": data, "t": t, "replay": self.replay})
            self.cond.notify_all()

    async def finish(self):
        async with self.cond:
            self.done = True
            self.cond.notify_all()

    async def iterate(self):
        i = 0
        while True:
            async with self.cond:
                await self.cond.wait_for(lambda: i < len(self.events) or self.done)
                batch = self.events[i:]
                i = len(self.events)
                finished = self.done
            for ev in batch:
                yield {"event": "ev", "data": json.dumps(ev)}
            if finished and i >= len(self.events):
                yield {"event": "end", "data": "{}"}
                return


class Hub:
    def __init__(self):
        self.streams: dict[str, Stream] = {}

    def create(self, run_id: str, replay: bool = False) -> Stream:
        s = Stream(replay)
        self.streams[run_id] = s
        return s

    def get(self, run_id: str) -> Stream | None:
        return self.streams.get(run_id)

    def remove(self, run_id: str) -> None:
        self.streams.pop(run_id, None)

    def clear(self) -> None:
        self.streams.clear()
