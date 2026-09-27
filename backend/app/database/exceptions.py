"""Safe application-level errors for persistence operations."""


class DatabaseError(Exception):
    """Base class for controlled database-layer errors."""


class DatabaseUnavailableError(DatabaseError):
    """Database connection is unavailable or not initialized."""


class DuplicateDataError(DatabaseError):
    """A uniqueness constraint rejected the requested data."""


class InvalidDatabaseOperationError(DatabaseError):
    """An operation could not be completed with the supplied data."""


class DatabaseOperationError(DatabaseError):
    """An unexpected persistence failure occurred."""


class UserNotFoundError(DatabaseError):
    """No user matches the requested identifier or email."""
