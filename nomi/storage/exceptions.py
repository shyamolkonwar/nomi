class StorageError(Exception):
    """Raised when a storage operation fails."""

    pass


class CacheError(Exception):
    """Raised when a cache operation fails."""

    pass


class SchemaError(Exception):
    """Raised when a schema operation fails."""

    pass
