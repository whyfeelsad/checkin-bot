"""Session data access layer"""

import json
import logging
from datetime import timedelta

from checkin_bot.config.constants import SessionState
from checkin_bot.config.settings import get_settings
from checkin_bot.core.timezone import now
from checkin_bot.models.session import Session
from checkin_bot.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class SessionRepository(BaseRepository):
    """Session Repository"""

    async def create(
        self,
        telegram_id: int,
        state: SessionState,
        data: dict | None = None,
    ) -> Session:
        """Create session"""
        logger.debug(f"Creating session: telegram_id={telegram_id}, state={state}")
        conn = await self._get_connection()
        try:
            current_time = now()
            ttl = timedelta(minutes=get_settings().session_ttl_minutes)

            record = await conn.fetchrow(
                """
                INSERT INTO sessions (telegram_id, state, data, expires_at, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $5)
                RETURNING *
                """,
                telegram_id,
                state,
                json.dumps(data or {}) if data else "{}",
                current_time + ttl,
                current_time,
            )

            session = self._to_model(record)
            logger.debug(f"Session created: id={session.id} (telegram_id={telegram_id})")
            return session
        finally:
            await self._release_connection(conn)

    async def get_by_telegram_id(self, telegram_id: int) -> Session | None:
        """Get session by Telegram ID"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                "SELECT * FROM sessions WHERE telegram_id = $1 ORDER BY created_at DESC LIMIT 1",
                telegram_id,
            )
            if not record:
                return None

            session = self._to_model(record)

            # Check if expired
            if now() > session.expires_at:
                await self.delete(session.id)
                return None

            return session
        finally:
            await self._release_connection(conn)

    async def update_state(
        self,
        session_id: int,
        state: SessionState,
        data: dict | None = None,
    ) -> Session | None:
        """Update session state"""
        conn = await self._get_connection()
        try:
            updates = ["state = $1", "updated_at = $2"]
            params = [state, now()]
            param_count = 3

            if data is not None:
                updates.append(f"data = ${param_count}")
                params.append(json.dumps(data))
                param_count += 1

            params.append(session_id)

            record = await conn.fetchrow(
                f"UPDATE sessions SET {', '.join(updates)} WHERE id = ${param_count} RETURNING *",
                *params,
            )

            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def update_data(self, session_id: int, data: dict) -> Session | None:
        """Update session data"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                """
                UPDATE sessions
                SET data = $1, updated_at = $2
                WHERE id = $3
                RETURNING *
                """,
                json.dumps(data),
                now(),
                session_id,
            )

            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def delete(self, session_id: int) -> bool:
        """Delete session"""
        conn = await self._get_connection()
        try:
            result = await conn.execute(
                "DELETE FROM sessions WHERE id = $1",
                session_id,
            )
            return result == "DELETE 1"
        finally:
            await self._release_connection(conn)

    async def delete_by_telegram_id(self, telegram_id: int) -> bool:
        """Delete all sessions for a user"""
        conn = await self._get_connection()
        try:
            result = await conn.execute(
                "DELETE FROM sessions WHERE telegram_id = $1",
                telegram_id,
            )
            return "DELETE" in result
        finally:
            await self._release_connection(conn)

    async def clean_expired(self) -> int:
        """Clean expired sessions"""
        conn = await self._get_connection()
        try:
            result = await conn.execute(
                "DELETE FROM sessions WHERE expires_at < NOW()",
            )
            # Parse "DELETE n" return value
            count = int(result.split()[-1]) if result else 0
            if count > 0:
                logger.info(f"Cleaned {count} expired sessions")
            return count
        finally:
            await self._release_connection(conn)

    @staticmethod
    def _to_model(record) -> Session:
        """Convert database record to model"""
        # Parse JSONB data to dict
        data = record["data"]
        if isinstance(data, str):
            data = json.loads(data)

        return Session(
            id=record["id"],
            telegram_id=record["telegram_id"],
            state=SessionState(record["state"]),
            data=data,
            expires_at=record["expires_at"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )
