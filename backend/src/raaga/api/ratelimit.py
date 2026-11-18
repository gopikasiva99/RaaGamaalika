"""Tiny in-memory sliding-window rate limiter (per instance) with bounded memory."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque


class RateLimiter:
    def __init__(self, per_min: int, window_s: float = 60.0, max_keys: int = 10_000):
        self.per_min, self.window_s, self.max_keys = per_min, window_s, max_keys
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()  # least recently seen first
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits.pop(key, None) or deque()
            while q and now - q[0] >= self.window_s:
                q.popleft()
            allowed = len(q) < self.per_min
            if allowed:
                q.append(now)
            self._hits[key] = q  # re-insert as most recently seen
            self._evict(now)
            return allowed

    def _evict(self, now: float) -> None:
        # Drop keys whose newest hit is outside the window (oldest-seen first), then,
        # if still over budget, the least recently seen keys.
        while self._hits:
            key, q = next(iter(self._hits.items()))
            if q and now - q[-1] < self.window_s and len(self._hits) <= self.max_keys:
                break
            if q and now - q[-1] < self.window_s and len(self._hits) > self.max_keys:
                self._hits.popitem(last=False)
                continue
            self._hits.popitem(last=False)
