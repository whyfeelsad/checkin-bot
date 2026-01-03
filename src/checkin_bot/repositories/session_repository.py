"""会话数据访问层"""

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
    """会话 Repository"""

    async def create(
        self,
        telegram_id: int,
        state: SessionState,
        data: dict | None = None,
    ) -> Session:
        """创建会话"""
        logger.debug(f"创建会话: telegram_id={telegram_id}, state={state}")
        conn = await self._get_connection()
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

        await self._release_connection(conn)
        session = self._to_model(record)
        logger.debug(f"会话已创建: id={session.id} (telegram_id={telegram_id})")
        return session

    async def get_by_telegram_id(self, telegram_id: int) -> Session | None:
        """根据 Telegram ID 获取会话"""
        conn = await self._get_connection()
        record = await conn.fetchrow(
            "SELECT * FROM sessions WHERE telegram_id = $1 ORDER BY created_at DESC LIMIT 1",
            telegram_id,
        )
        await self._release_connection(conn)

        if not record:
            return None

        session = self._to_model(record)

        # 检查是否过期
        if now() > session.expires_at:
            await self.delete(session.id)
            return None

        return session

    async def update_state(
        self,
        session_id: int,
        state: SessionState,
        data: dict | None = None,
    ) -> Session | None:
        """更新会话状态"""
        conn = await self._get_connection()

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

        await self._release_connection(conn)

        if not record:
            return None
        return self._to_model(record)

    async def update_data(self, session_id: int, data: dict) -> Session | None:
        """更新会话数据"""
        conn = await self._get_connection()
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

        await self._release_connection(conn)

        if not record:
            return None
        return self._to_model(record)

    async def delete(self, session_id: int) -> bool:
        """删除会话"""
        conn = await self._get_connection()
        result = await conn.execute(
            "DELETE FROM sessions WHERE id = $1",
            session_id,
        )
        await self._release_connection(conn)

        return result == "DELETE 1"

    async def delete_by_telegram_id(self, telegram_id: int) -> bool:
        """删除用户的所有会话"""
        conn = await self._get_connection()
        result = await conn.execute(
            "DELETE FROM sessions WHERE telegram_id = $1",
            telegram_id,
        )
        await self._release_connection(conn)

        return "DELETE" in result

    async def clean_expired(self) -> int:
        """清理过期会话"""
        conn = await self._get_connection()
        result = await conn.execute(
            "DELETE FROM sessions WHERE expires_at < NOW()",
        )
        await self._release_connection(conn)

        # 解析 "DELETE n" 返回值
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(f"清理了 {count} 个过期会话")
        return count

    @staticmethod
    def _to_model(record) -> Session:
        """数据库记录转换为模型"""
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
