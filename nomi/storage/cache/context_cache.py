from typing import Any, Optional

from nomi.storage.cache.memory_cache import MemoryCache


class ContextCache:
    """Cache for assembled context bundles."""

    def __init__(self, max_size: int = 100) -> None:
        self._cache: MemoryCache[Any] = MemoryCache(max_size=max_size)

    def cache_context(self, query_hash: str, context_bundle: Any) -> None:
        """Cache a context bundle with its query hash as the key."""
        self._cache.set(query_hash, context_bundle)

    def get_cached_context(self, query_hash: str) -> Optional[Any]:
        """Retrieve a cached context bundle by its query hash."""
        return self._cache.get(query_hash)

    def invalidate_context(self, query_hash: str) -> bool:
        """Remove a specific context from the cache."""
        return self._cache.invalidate(query_hash)

    def clear(self) -> None:
        """Clear all cached contexts."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return the number of cached contexts."""
        return len(self._cache)
