from __future__ import annotations
import time
from typing import Any, Dict, Optional, Tuple

class TTLCache:
    """Простой in-memory TTL кэш для MVP."""

    def __init__(self, default_ttl_seconds: int = 900, max_items: int = 5000):
        self.default_ttl = default_ttl_seconds
        self.max_items = max_items
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        if len(self._store) >= self.max_items:
            # простейшая очистка: удалить 10% случайных/первых ключей
            for k in list(self._store.keys())[: max(1, self.max_items // 10)]:
                self._store.pop(k, None)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._store[key] = (time.time() + ttl, value)
