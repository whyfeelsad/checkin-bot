"""User data access layer"""

import asyncpg

from checkin_bot.core.timezone import now
from checkin_bot.models.user import User
from checkin_bot.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """User Repository"""

    async def create(
        self,
        telegram_id: int,
        telegram_username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Create user"""
        conn = await self._get_connection()
        try:
            current_time = now()
            record = await conn.fetchrow(
                """
                INSERT INTO users (telegram_id, telegram_username, first_name, last_name, fingerprint, created_at, updated_at)
                VALUES ($1, $2, $3, $4, NULL, $5, $5)
                RETURNING *
                """,
                telegram_id,
                telegram_username,
                first_name,
                last_name,
                current_time,
            )
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                telegram_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def update(
        self,
        user_id: int,
        telegram_username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        fingerprint: str | None = None,
    ) -> User | None:
        """Update user"""
        updates = []
        params = []
        param_count = 1

        if telegram_username is not None:
            updates.append(f"telegram_username = ${param_count}")
            params.append(telegram_username)
            param_count += 1

        if first_name is not None:
            updates.append(f"first_name = ${param_count}")
            params.append(first_name)
            param_count += 1

        if last_name is not None:
            updates.append(f"last_name = ${param_count}")
            params.append(last_name)
            param_count += 1

        if fingerprint is not None:
            updates.append(f"fingerprint = ${param_count}")
            params.append(fingerprint)
            param_count += 1

        if not updates:
            return await self.get_by_id(user_id)

        updates.append(f"updated_at = ${param_count}")
        params.append(now())
        param_count += 1

        params.append(user_id)

        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_count} RETURNING *",
                *params,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def get_all(self) -> list[User]:
        """Get all users"""
        conn = await self._get_connection()
        try:
            records = await conn.fetch(
                "SELECT * FROM users ORDER BY created_at DESC",
            )
            return [self._to_model(record) for record in records]
        finally:
            await self._release_connection(conn)

    @staticmethod
    def _to_model(record) -> User:
        """Convert database record to model"""
        return User(
            id=record["id"],
            telegram_id=record["telegram_id"],
            telegram_username=record["telegram_username"],
            first_name=record["first_name"],
            last_name=record["last_name"],
            fingerprint=record["fingerprint"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )
