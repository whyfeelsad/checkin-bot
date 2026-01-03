"""Account update tracking data access layer"""

from checkin_bot.config.constants import UpdateStatus
from checkin_bot.core.timezone import now
from checkin_bot.models.account_update import AccountUpdate
from checkin_bot.repositories.base import BaseRepository


class AccountUpdateRepository(BaseRepository):
    """Account update tracking Repository"""

    async def try_create_or_get_active(self, account_id: int) -> tuple[bool, AccountUpdate | None]:
        """
        Try to create update record, or return existing active record

        Uses database-level atomic operations for concurrency safety:
        - If no active record exists, create a new pending record
        - If an active record exists, return the existing record

        Returns:
            (created, record): created=True means newly created, False means already exists
        """
        conn = await self._get_connection()
        try:
            current_time = now()

            # Use WITH clause for atomicity: query active record first, create if none exists
            record = await conn.fetchrow(
                """
                WITH existing AS (
                    SELECT * FROM account_updates
                    WHERE account_id = $1
                    AND status IN ('pending', 'processing')
                    ORDER BY created_at DESC
                    LIMIT 1
                    FOR UPDATE
                ),
                inserted AS (
                    INSERT INTO account_updates (account_id, status, started_at, completed_at, error_message, created_at)
                    SELECT $1, 'pending', NULL, NULL, NULL, $2
                    WHERE NOT EXISTS (SELECT 1 FROM existing)
                    RETURNING *
                )
                SELECT * FROM inserted
                UNION ALL
                SELECT * FROM existing
                LIMIT 1
                """,
                account_id,
                current_time,
            )

            if not record:
                return False, None

            update_model = self._to_model(record)
            # If status is pending and just created (created_at equals current_time), it's new
            is_new = update_model.status == UpdateStatus.PENDING and update_model.created_at == current_time
            return is_new, update_model
        finally:
            await self._release_connection(conn)

    async def create(self, account_id: int) -> AccountUpdate:
        """Create update record"""
        conn = await self._get_connection()
        try:
            current_time = now()
            record = await conn.fetchrow(
                """
                INSERT INTO account_updates (account_id, status, started_at, completed_at, error_message, created_at)
                VALUES ($1, 'pending', NULL, NULL, NULL, $2)
                RETURNING *
                """,
                account_id,
                current_time,
            )
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def force_create(self, account_id: int) -> AccountUpdate:
        """
        Force create update record (clears old active records)

        Used when user manually triggers an update, allowing override of previous update task

        Returns:
            Newly created update record
        """
        conn = await self._get_connection()
        try:
            current_time = now()

            # Clear active records for this account first
            await conn.execute(
                """
                DELETE FROM account_updates
                WHERE account_id = $1
                AND status IN ('pending', 'processing')
                """,
                account_id,
            )

            # Create new record
            record = await conn.fetchrow(
                """
                INSERT INTO account_updates (account_id, status, started_at, completed_at, error_message, created_at)
                VALUES ($1, 'pending', NULL, NULL, NULL, $2)
                RETURNING *
                """,
                account_id,
                now,
            )
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def get_by_id(self, update_id: int) -> AccountUpdate | None:
        """Get update record by ID"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                "SELECT * FROM account_updates WHERE id = $1",
                update_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def get_active_by_account(self, account_id: int) -> AccountUpdate | None:
        """Get active update record for an account (pending or processing)"""
        conn = await self._get_connection()
        try:
            record = await conn.fetchrow(
                """
                SELECT * FROM account_updates
                WHERE account_id = $1
                AND status IN ('pending', 'processing')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                account_id,
            )
            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def update_status(
        self,
        update_id: int,
        status: UpdateStatus,
        error_message: str | None = None,
    ) -> AccountUpdate | None:
        """Update status"""
        conn = await self._get_connection()
        try:
            current_time = now()

            updates = ["status = $1"]
            params = [status]
            param_count = 2

            if status == UpdateStatus.PROCESSING:
                updates.append(f"started_at = ${param_count}")
                params.append(current_time)
                param_count += 1

            if status == UpdateStatus.COMPLETED or status == UpdateStatus.FAILED:
                updates.append(f"completed_at = ${param_count}")
                params.append(current_time)
                param_count += 1

            if error_message is not None:
                updates.append(f"error_message = ${param_count}")
                params.append(error_message)
                param_count += 1

            params.append(update_id)

            record = await conn.fetchrow(
                f"UPDATE account_updates SET {', '.join(updates)} WHERE id = ${param_count} RETURNING *",
                *params,
            )

            if not record:
                return None
            return self._to_model(record)
        finally:
            await self._release_connection(conn)

    async def delete(self, update_id: int) -> bool:
        """Delete update record"""
        conn = await self._get_connection()
        try:
            result = await conn.execute(
                "DELETE FROM account_updates WHERE id = $1",
                update_id,
            )
            return result == "DELETE 1"
        finally:
            await self._release_connection(conn)

    @staticmethod
    def _to_model(record) -> AccountUpdate:
        """Convert database record to model"""
        return AccountUpdate(
            id=record["id"],
            account_id=record["account_id"],
            status=UpdateStatus(record["status"]),
            started_at=record["started_at"],
            completed_at=record["completed_at"],
            error_message=record["error_message"],
            created_at=record["created_at"],
        )
