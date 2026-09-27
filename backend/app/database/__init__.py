"""Database access and persistence boundary for Credence."""

from .connection import DatabaseManager, get_database

__all__ = ["DatabaseManager", "get_database"]
