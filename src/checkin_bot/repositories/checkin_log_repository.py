"""签到日志数据访问层"""

from datetime import datetime
from typing import List

from checkin_bot.config.constants import CheckinStatus, SiteType
from checkin_bot.core.timezone import now
from checkin_bot.models.checkin_log import CheckinLog
from checkin_bot.repositories.base import BaseRepository


class CheckinLogRepository(BaseRepository):
    """签到日志 Repository"""

    async def create(
        self,
        account_id: int,
        site: SiteType,
        status: CheckinStatus,
        message: str | None = None,
        credits_delta: int = 0,
        credits_before: int | None = None,
        credits_after: int | None = None,
        error_code: str | None = None,
        executed_at: datetime | None = None,
    ) -> CheckinLog:
        """创建签到日志"""
        conn = await self._get_connection()

        if executed_at is None:
            executed_at = now()

        record = await conn.fetchrow(
            """
            INSERT INTO checkin_logs (
                account_id, site, status, message, credits_delta,
                credits_before, credits_after, error_code, executed_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            account_id,
            site,
            status,
            message,
            credits_delta,
            credits_before,
            credits_after,
            error_code,
            executed_at,
        )

        await self._release_connection(conn)
        return self._to_model(record)

    async def get_by_account(
        self,
        account_id: int,
        limit: int = 50,
    ) -> List[CheckinLog]:
        """获取账号的签到日志"""
        conn = await self._get_connection()
        records = await conn.fetch(
            """
            SELECT * FROM checkin_logs
            WHERE account_id = $1
            ORDER BY executed_at DESC
            LIMIT $2
            """,
            account_id,
            limit,
        )
        await self._release_connection(conn)

        return [self._to_model(record) for record in records]

    async def get_by_user(
        self,
        account_ids: List[int],
        limit: int = 50,
    ) -> List[CheckinLog]:
        """获取用户所有账号的签到日志"""
        if not account_ids:
            return []

        conn = await self._get_connection()
        records = await conn.fetch(
            f"""
            SELECT * FROM checkin_logs
            WHERE account_id = ANY($1)
            ORDER BY executed_at DESC
            LIMIT $2
            """,
            account_ids,
            limit,
        )
        await self._release_connection(conn)

        return [self._to_model(record) for record in records]

    async def get_recent_slots(
        self,
        account_id: int,
        days: int = 4,
    ) -> List[datetime]:
        """获取最近几天的签到时间（用于防重复）"""
        conn = await self._get_connection()
        records = await conn.fetch(
            """
            SELECT executed_at FROM checkin_logs
            WHERE account_id = $1
            AND status = 'success'
            AND executed_at > NOW() - INTERVAL '1 day' * $2
            ORDER BY executed_at DESC
            """,
            account_id,
            days,
        )
        await self._release_connection(conn)

        return [record["executed_at"] for record in records]

    async def get_today_count(self, account_id: int) -> int:
        """获取账号今天的签到次数"""
        conn = await self._get_connection()
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM checkin_logs
            WHERE account_id = $1
            AND DATE(executed_at) = CURRENT_DATE
            """,
            account_id,
        )
        await self._release_connection(conn)

        return count or 0

    async def get_today_success_count(self, account_id: int) -> int:
        """获取账号今天成功的签到次数"""
        conn = await self._get_connection()
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM checkin_logs
            WHERE account_id = $1
            AND status = 'success'
            AND DATE(executed_at) = CURRENT_DATE
            """,
            account_id,
        )
        await self._release_connection(conn)

        return count or 0

    @staticmethod
    def _to_model(record) -> CheckinLog:
        """数据库记录转换为模型"""
        return CheckinLog(
            id=record["id"],
            account_id=record["account_id"],
            site=SiteType(record["site"]),
            status=CheckinStatus(record["status"]),
            message=record["message"],
            credits_delta=record["credits_delta"],
            credits_before=record["credits_before"],
            credits_after=record["credits_after"],
            error_code=record["error_code"],
            executed_at=record["executed_at"],
        )
