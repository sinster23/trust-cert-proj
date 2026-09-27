"""Async MongoDB connection lifecycle using PyMongo's async client."""

from __future__ import annotations

import os
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from .exceptions import DatabaseUnavailableError


class DatabaseManager:
    """Own one MongoDB client for an application lifespan."""

    def __init__(self, uri: str | None = None, database_name: str | None = None) -> None:
        self._uri = uri if uri is not None else os.getenv("MONGODB_URI")
        self._database_name = database_name if database_name is not None else os.getenv("MONGODB_DATABASE")
        self._client: AsyncMongoClient[Any] | None = None
        self._database: Any | None = None

    async def connect(self) -> Any:
        if not self._uri or not self._database_name:
            raise DatabaseUnavailableError("MongoDB configuration is missing")
        if self._client is not None:
            return self._database
        try:
            client = AsyncMongoClient(self._uri, serverSelectionTimeoutMS=5000)
            await client.admin.command("ping")
            self._client = client
            self._database = client[self._database_name]
            return self._database
        except PyMongoError as exc:
            if "client" in locals():
                await client.close()
            raise DatabaseUnavailableError("Could not connect to the database") from exc

    def get_database(self) -> Any:
        if self._database is None:
            raise DatabaseUnavailableError("Database has not been connected")
        return self._database

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        self._client = None
        self._database = None


def get_database(manager: DatabaseManager) -> Any:
    """FastAPI dependency target when manager is stored on app.state."""
    return manager.get_database()
