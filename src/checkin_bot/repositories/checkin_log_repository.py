"""Check-in log data access layer"""

from datetime import datetime
from typing import List

from checkin_bot.config.constants import CheckinStatus, SiteType
from checkin_bot.core.timezone import now
from checkin_bot.models.checkin_log import CheckinLog
from checkin_bot.repositories.base import BaseRepository


class CheckinLogRepository(BaseRepository):
    """Check-in log Repository"""

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
        """Create check-in log"""
        conn = await self._get_connection()
        try:
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
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def get_by_account(
        self,
        account_id: int,
        limit: int = 50,
    ) -> List[CheckinLog]:
        """Get check-in logs for an account"""
        conn = await self._get_connection()
        try:
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
            return [self._to_model(record) for record in records]
        finally:
            await self._release_connection(conn)

    async def get_by_user(
        self,
        account_ids: List[int],
        limit: int = 50,
    ) -> List[CheckinLog]:
        """Get check-in logs for user's accounts"""
        if not account_ids:
            return []

        conn = await self._get_connection()
        try:
            records = await conn.fetch(
                """
                SELECT * FROM checkin_logs
                WHERE account_id = ANY($1)
                ORDER BY executed_at DESC
                LIMIT $2
                """,
                account_ids,
                limit,
            )
            return [self._to_model(record) for record in records]
        finally:
            await self._release_connection(conn)

    async def get_recent_slots(
        self,
        account_id: int,
        days: int = 4,
    ) -> List[datetime]:
        """Get recent check-in times (for duplicate prevention)"""
        conn = await self._get_connection()
        try:
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
            return [record["executed_at"] for record in records]
        finally:
            await self._release_connection(conn)

    async def get_today_count(self, account_id: int) -> int:
        """Get today's check-in count for an account"""
        conn = await self._get_connection()
        try:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM checkin_logs
                WHERE account_id = $1
                AND DATE(executed_at) = CURRENT_DATE
                """,
                account_id,
            )
            return count or 0
        finally:
            await self._release_connection(conn)

    async def get_today_success_count(self, account_id: int) -> int:
        """Get today's successful check-in count for an account"""
        conn = await self._get_connection()
        try:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM checkin_logs
                WHERE account_id = $1
                AND status = 'success'
                AND DATE(executed_at) = CURRENT_DATE
                """,
                account_id,
            )
            return count or 0
        finally:
            await self._release_connection(conn)

    async def get_last_success_delta(self, account_id: int) -> int:
        """Get last successful check-in credits_delta for an account"""
        conn = await self._get_connection()
        try:
            delta = await conn.fetchval(
                """
                SELECT credits_delta FROM checkin_logs
                WHERE account_id = $1
                AND status = 'success'
                ORDER BY executed_at DESC
                LIMIT 1
                """,
                account_id,
            )
            return delta or 0
        finally:
            await self._release_connection(conn)

    async def get_today_success_delta(self, account_id: int) -> int:
        """Get today's successful check-in credits_delta for an account"""
        conn = await self._get_connection()
        try:
            delta = await conn.fetchval(
                """
                SELECT credits_delta FROM checkin_logs
                WHERE account_id = $1
                AND status = 'success'
                AND DATE(executed_at) = CURRENT_DATE
                ORDER BY executed_at ASC
                LIMIT 1
                """,
                account_id,
            )
            return delta or 0
        finally:
            await self._release_connection(conn)

    @staticmethod
    def _to_model(record) -> CheckinLog:
        """Convert database record to model"""
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
