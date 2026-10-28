from collections import OrderedDict
import threading
from typing import Any

from app.contracts.domain import TaskContext
from app.features.activities.schemas import StudyPackage, SupportMode


class StudyPackageCache:
    """Thread-safe bounded in-memory LRU cache for rich StudyPackage instances."""

    def __init__(self, maxsize: int = 64):
        self.maxsize = maxsize
        self._cache: OrderedDict[str, StudyPackage] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def make_key(self, context_hash: str, mode: SupportMode) -> str:
        return f"{context_hash}:{mode.value}"

    def get(self, context: TaskContext, context_hash: str, mode: SupportMode) -> StudyPackage | None:
        key = self.make_key(context_hash, mode)
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            package = self._cache[key]

            # Re-verify authorization: ensure cached resources still match authorized resources
            allowed_resource_ids = {r.resource_id for r in context.resources}
            if any(s.resource_id not in allowed_resource_ids for s in package.sources):
                # Unauthorized or stale resources; invalidate entry
                del self._cache[key]
                self.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self.hits += 1

            # Return a copy with origin marked as 'cache'
            dump = package.model_dump()
            dump["provenance"]["origin"] = "cache"
            return StudyPackage.model_validate(dump)

    def put(self, context_hash: str, mode: SupportMode, package: StudyPackage) -> None:
        # Never cache failed or invalid packages
        if package.provenance.origin == "template" and "fallback" in package.provenance.validation_status:
            return

        key = self.make_key(context_hash, mode)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = package
            if len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)
                self.evictions += 1

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
            }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
