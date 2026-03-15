from collections import OrderedDict
from typing import Optional, TypeVar, Generic

T = TypeVar("T")


class MemoryCache(Generic[T]):
    """Simple LRU cache for frequently accessed items."""

    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max_size
        self._cache: OrderedDict[str, T] = OrderedDict()

    def get(self, key: str) -> Optional[T]:
        """Get a value from the cache. Moves item to end (most recently used)."""
        if key not in self._cache:
            return None

        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: str, value: T) -> None:
        """Set a value in the cache. Moves item to end (most recently used)."""
        if key in self._cache:
            self._cache.move_to_end(key)

        self._cache[key] = value

        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all items from the cache."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return the number of items in the cache."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        return key in self._cache
