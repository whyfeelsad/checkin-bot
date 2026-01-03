"""Account data access layer"""

from typing import List

from checkin_bot.config.constants import AccountStatus, CheckinMode, SiteType
from checkin_bot.config.settings import get_settings
from checkin_bot.core.timezone import now
from checkin_bot.models.account import Account
from checkin_bot.repositories.base import BaseRepository


class AccountRepository(BaseRepository):
    """Account Repository"""

    def __init__(self):
        super().__init__()
        self.settings = get_settings()

    async def create(
        self,
        user_id: int,
        site: SiteType,
        site_username: str,
        encrypted_pass: str,
        checkin_mode: CheckinMode,
    ) -> Account:
        """Create account"""
        conn = await self._get_connection()
        try:
            current_time = now()
            record = await conn.fetchrow(
                """
                INSERT INTO accounts (
                    user_id, site, site_username, encrypted_pass,
                    checkin_mode, status, credits, checkin_count,
                    checkin_hour, push_hour, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, 'active', 0, 0, $7, $8, $6, $6)
                RETURNING *
                """,
                user_id,
                site,
                site_username,
                encrypted_pass,
                checkin_mode,
                current_time,
                self.settings.default_checkin_hour,
                self.settings.default_push_hour,
            )
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def get_by_id(self, account_id: int) -> Account | None:
        """Get account by ID"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                "SELECT * FROM accounts WHERE id = $1",
                account_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def get_by_user(self, user_id: int) -> List[Account]:
        """Get all accounts for a user"""
        conn = await self._get_connection()
        try:
            records = await conn.fetch(
                "SELECT * FROM accounts WHERE user_id = $1 ORDER BY created_at DESC",
                user_id,
            )
            return [self._to_model(record) for record in records]
        finally:
            await self._release_connection(conn)

    async def get_by_site(self, user_id: int, site: SiteType) -> List[Account]:
        """Get user accounts for a specific site"""
        conn = await self._get_connection()
        try:
            records = await conn.fetch(
                "SELECT * FROM accounts WHERE user_id = $1 AND site = $2",
                user_id,
                site,
            )
            return [self._to_model(record) for record in records]
        finally:
            await self._release_connection(conn)

    async def update_cookie(
        self,
        account_id: int,
        cookie: str,
    ) -> Account | None:
        """Update account cookie"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                """
                UPDATE accounts
                SET cookie = $1, updated_at = $2
                WHERE id = $3
                RETURNING *
                """,
                cookie,
                now(),
                account_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def update_credits(
        self,
        account_id: int,
        credits: int,
        checkin_count_increment: int = 0,
    ) -> Account | None:
        """Update credits and check-in count"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                """
                UPDATE accounts
                SET credits = $1, checkin_count = checkin_count + $2, updated_at = $3
                WHERE id = $4
                RETURNING *
                """,
                credits,
                checkin_count_increment,
                now(),
                account_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def update_checkin_time(
        self,
        account_id: int,
        checkin_hour: int | None,
        push_hour: int | None,
    ) -> Account | None:
        """Update check-in and push time"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                """
                UPDATE accounts
                SET checkin_hour = $1, push_hour = $2, updated_at = $3
                WHERE id = $4
                RETURNING *
                """,
                checkin_hour,
                push_hour,
                now(),
                account_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def update_status(
        self,
        account_id: int,
        status: AccountStatus,
    ) -> Account | None:
        """Update account status"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                """
                UPDATE accounts
                SET status = $1, updated_at = $2
                WHERE id = $3
                RETURNING *
                """,
                status,
                now(),
                account_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def update_checkin_mode(
        self,
        account_id: int,
        checkin_mode: CheckinMode,
    ) -> Account | None:
        """Update check-in mode"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                """
                UPDATE accounts
                SET checkin_mode = $1, updated_at = $2
                WHERE id = $3
                RETURNING *
                """,
                checkin_mode,
                now(),
                account_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def delete(self, account_id: int) -> bool:
        """Delete account"""
        conn = await self._get_connection()
        try:
            result = await conn.execute(
                "DELETE FROM accounts WHERE id = $1",
                account_id,
            )
            return result == "DELETE 1"
        finally:
            await self._release_connection(conn)

    async def get_all_active(self) -> List[Account]:
        """Get all active accounts"""
        conn = await self._get_connection()
        try:
            records = await conn.fetch(
                "SELECT * FROM accounts WHERE status = 'active' ORDER BY created_at",
            )
            return [self._to_model(record) for record in records]
        finally:
            await self._release_connection(conn)

    async def get_by_checkin_time(self, hour: int) -> List[Account]:
        """Get accounts with specific check-in hour"""
        conn = await self._get_connection()
        try:
            records = await conn.fetch(
                "SELECT * FROM accounts WHERE checkin_hour = $1 AND status = 'active'",
                hour,
            )
            return [self._to_model(record) for record in records]
        finally:
            await self._release_connection(conn)

    @staticmethod
    def _to_model(record) -> Account:
        """Convert database record to model"""
        return Account(
            id=record["id"],
            user_id=record["user_id"],
            site=SiteType(record["site"]),
            site_username=record["site_username"],
            encrypted_pass=record["encrypted_pass"],
            cookie=record["cookie"],
            checkin_mode=CheckinMode(record["checkin_mode"]),
            status=AccountStatus(record["status"]),
            credits=record["credits"],
            checkin_count=record["checkin_count"],
            checkin_hour=record["checkin_hour"],
            push_hour=record["push_hour"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )
