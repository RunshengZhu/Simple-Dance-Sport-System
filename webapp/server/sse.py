#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进程内 SSE 事件总线：每赛事一个订阅列表，同步 fan-out。"""

import asyncio
import json
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._subscribers = defaultdict(set)  # competition_id -> set[asyncio.Queue]

    def subscribe(self, competition_id: int) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=256)
        self._subscribers[competition_id].add(q)
        return q

    def unsubscribe(self, competition_id: int, q: asyncio.Queue):
        self._subscribers[competition_id].discard(q)

    def publish(self, competition_id: int, event_type: str, payload=None):
        data = json.dumps({"type": event_type, "payload": payload or {}}, ensure_ascii=False)
        for q in list(self._subscribers.get(competition_id, ())):
            try:
                q.put_nowait((event_type, data))
            except asyncio.QueueFull:
                pass


bus = EventBus()
