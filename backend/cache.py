"""
Simple in-memory LRU dictionary cache with 5-minute TTL.
Hashes incoming HTML/text payloads and stores scan outputs to prevent redundant processing.
"""

from __future__ import annotations
import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Optional, Dict, Any, Tuple
from backend.schemas.models import ScanReport


class TimedLRUCache:
    """
    In-memory Least-Recently-Used (LRU) dictionary cache with 5-minute TTL (300 seconds).
    Hashes incoming HTML/text strings to index cached results.
    """

    def __init__(self, maxsize: int = 500, default_ttl_seconds: float = 300.0):
        self.maxsize = maxsize
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: OrderedDict[str, Tuple[ScanReport, float, float]] = OrderedDict()
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def hash_content(content: str) -> str:
        """Computes deterministic SHA-256 hash of incoming HTML or text."""
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    def _evict_expired_nolock(self) -> None:
        """Purges expired items from dictionary."""
        now = time.time()
        expired_keys = [
            k for k, (_, cached_time, ttl) in self._cache.items()
            if now - cached_time > ttl
        ]
        for k in expired_keys:
            del self._cache[k]

    def get(self, key: str) -> Optional[ScanReport]:
        """Retrieves cached ScanReport if valid and unexpired. Updates LRU position."""
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            report, cached_time, ttl = self._cache[key]
            now = time.time()
            age = now - cached_time

            if age > ttl:
                del self._cache[key]
                self.misses += 1
                return None

            self._cache.move_to_end(key)
            self.hits += 1

            cached_copy = report.model_copy(deep=True)
            cached_copy.cached = True
            cached_copy.cache_age_seconds = round(age, 2)
            return cached_copy

    def set(self, key: str, value: ScanReport, ttl_seconds: Optional[float] = None) -> None:
        """Stores a ScanReport indexed by key with 5-minute TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        now = time.time()

        with self._lock:
            self._evict_expired_nolock()

            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)

            report_to_store = value.model_copy(deep=True)
            report_to_store.cached = False
            report_to_store.cache_age_seconds = None

            self._cache[key] = (report_to_store, now, ttl)

    def invalidate(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def size(self) -> int:
        with self._lock:
            self._evict_expired_nolock()
            return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total_requests = self.hits + self.misses
            hit_ratio = round(self.hits / total_requests, 4) if total_requests > 0 else 0.0
            return {
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "default_ttl_seconds": self.default_ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio": hit_ratio,
            }


# Global singleton cache instance with 5-minute TTL
scan_cache = TimedLRUCache(maxsize=500, default_ttl_seconds=300.0)
