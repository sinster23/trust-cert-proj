"""Persistence operations exposed to modules such as M1."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from ..exceptions import (
    DatabaseOperationError,
    DatabaseUnavailableError,
    DuplicateDataError,
    InvalidDatabaseOperationError,
    UserNotFoundError,
)
from ..models.user import (
    DEFAULT_ROLE,
    User,
    normalize_email,
    normalize_google_sub,
    normalize_role,
    utc_now,
)


class UserRepository:
    COLLECTION = "users"
    EMAIL_INDEX = "uq_users_normalized_email"
    GOOGLE_SUB_INDEX = "uq_users_google_sub"
    ROLE_INDEX = "ix_users_role"
    MAX_PAGE_SIZE = 100

    def __init__(self, database: Any) -> None:
        self._collection = database[self.COLLECTION]

    async def _create_indexes(self) -> None:
        # Plain (non-unique) index so role filters and counts stay cheap.
        await self._collection.create_index([("role", ASCENDING)], name=self.ROLE_INDEX)
        # Unique index on the stored normalized email.
        await self._collection.create_index(
            [("email", ASCENDING)], unique=True, name=self.EMAIL_INDEX
        )
        # Unique index on Google's stable account id. It is partial (only
        # documents whose google_sub is a string) so that any pre-existing
        # document without the field cannot collide on a missing value.
        await self._collection.create_index(
            [("google_sub", ASCENDING)],
            unique=True,
            name=self.GOOGLE_SUB_INDEX,
            partialFilterExpression={"google_sub": {"$type": "string"}},
        )

    async def ensure_indexes(self) -> None:
        try:
            await self._create_indexes()
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not initialize user constraints") from exc

    async def create_user(self, user: User) -> User:
        if not isinstance(user, User):
            raise InvalidDatabaseOperationError("A validated User is required")
        try:
            await self._create_indexes()
            await self._collection.insert_one(user.to_document())
            return user
        except DuplicateKeyError as exc:
            if self.GOOGLE_SUB_INDEX in str(exc):
                raise DuplicateDataError("A user with this Google account already exists") from exc
            raise DuplicateDataError("A user with this email already exists") from exc
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not save user") from exc

    async def find_by_email(self, email: str) -> User:
        try:
            normalized = normalize_email(email)
        except ValueError as exc:
            raise InvalidDatabaseOperationError("Email is invalid") from exc
        try:
            document = await self._collection.find_one({"email": normalized})
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not retrieve user") from exc
        if document is None:
            raise UserNotFoundError("User was not found")
        return self._decode(document)

    async def find_by_google_sub(self, google_sub: str) -> User:
        try:
            normalized = normalize_google_sub(google_sub)
        except ValueError as exc:
            raise InvalidDatabaseOperationError("Google account identifier is invalid") from exc
        try:
            document = await self._collection.find_one({"google_sub": normalized})
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not retrieve user") from exc
        if document is None:
            raise UserNotFoundError("User was not found")
        return self._decode(document)

    async def find_by_id(self, user_id: UUID | str) -> User:
        try:
            normalized_id = str(user_id if isinstance(user_id, UUID) else UUID(user_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidDatabaseOperationError("User identifier is invalid") from exc
        try:
            document = await self._collection.find_one({"_id": normalized_id})
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not retrieve user") from exc
        if document is None:
            raise UserNotFoundError("User was not found")
        return self._decode(document)

    # ----------------------------------------------------------------- #
    # Roles (used by M2). M4 stores and queries role strings only; which
    # roles exist and who may change them is decided by M2.
    # ----------------------------------------------------------------- #
    @staticmethod
    def _valid_role(role: str) -> str:
        try:
            return normalize_role(role)
        except ValueError as exc:
            raise InvalidDatabaseOperationError("Role is invalid") from exc

    @staticmethod
    def _role_filter(role: str) -> dict[str, Any]:
        # Users stored before roles existed have no "role" field and are STUDENTs.
        if role == DEFAULT_ROLE:
            return {"$or": [{"role": role}, {"role": {"$exists": False}}]}
        return {"role": role}

    async def update_role(self, user_id: UUID | str, role: str) -> User:
        """Atomically set a user's role and bump ``updated_at``; return the user."""
        try:
            normalized_id = str(user_id if isinstance(user_id, UUID) else UUID(user_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidDatabaseOperationError("User identifier is invalid") from exc
        normalized_role = self._valid_role(role)
        try:
            document = await self._collection.find_one_and_update(
                {"_id": normalized_id},
                {"$set": {"role": normalized_role, "updated_at": utc_now()}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not update user role") from exc
        if document is None:
            raise UserNotFoundError("User was not found")
        return self._decode(document)

    async def list_users(
        self, *, role: str | None = None, skip: int = 0, limit: int = 50
    ) -> list[User]:
        """A page of users, oldest first (stable order), optionally by role."""
        for name, value in (("skip", skip), ("limit", limit)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidDatabaseOperationError(f"{name} must be an integer")
        if skip < 0 or not 1 <= limit <= self.MAX_PAGE_SIZE:
            raise InvalidDatabaseOperationError(
                f"skip must be >= 0 and limit between 1 and {self.MAX_PAGE_SIZE}"
            )
        query = {} if role is None else self._role_filter(self._valid_role(role))
        try:
            cursor = (
                self._collection.find(query)
                .sort([("created_at", ASCENDING), ("_id", ASCENDING)])
                .skip(skip)
                .limit(limit)
            )
            documents = await cursor.to_list(length=limit)
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not list users") from exc
        return [self._decode(document) for document in documents]

    async def count_by_role(self, role: str) -> int:
        normalized_role = self._valid_role(role)
        try:
            return await self._collection.count_documents(self._role_filter(normalized_role))
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not count users") from exc

    @staticmethod
    def _decode(document: dict[str, Any]) -> User:
        try:
            return User.from_document(document)
        except (KeyError, TypeError, ValueError) as exc:
            raise DatabaseOperationError("Stored user data is invalid") from exc