"""In-memory token-bucket rate limiting.

A free public product needs a floor against abuse. This is per-process and
therefore assumes a SINGLE backend replica (see DECISIONS.md) — scale out and
each replica keeps its own buckets. No new dependency, no Redis.
"""

import threading
import time
from typing import Dict, Tuple


class RateLimiter:
    def __init__(self, capacity: int, refill_per_min: int):
        self.capacity = capacity
        self.refill = refill_per_min / 60.0  # tokens per second
        self.enabled = True
        self._tokens: Dict[str, float] = {}
        self._last: Dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if not self.enabled:
            return True
        with self._lock:
            now = time.monotonic()
            tokens = self._tokens.get(key, self.capacity)
            tokens = min(self.capacity, tokens + (now - self._last.get(key, now)) * self.refill)
            self._last[key] = now
            if tokens < 1:
                self._tokens[key] = tokens
                return False
            self._tokens[key] = tokens - 1
            return True

    def check(self, *keys: str) -> bool:
        """Allow only if EVERY key (e.g. per-user AND per-IP) has budget. All
        matching keys are decremented when allowed."""
        if not self.enabled:
            return True
        # Two-pass so a denial on the second key doesn't spend the first.
        with self._lock:
            now = time.monotonic()
            snapshot: list[Tuple[str, float]] = []
            for k in keys:
                t = min(self.capacity, self._tokens.get(k, self.capacity) + (now - self._last.get(k, now)) * self.refill)
                if t < 1:
                    # refresh timers without spending
                    for kk in keys:
                        self._last[kk] = now
                    return False
                snapshot.append((k, t))
            for k, t in snapshot:
                self._tokens[k] = t - 1
                self._last[k] = now
            return True
