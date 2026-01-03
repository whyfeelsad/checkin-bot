"""账号更新追踪数据访问层"""

from checkin_bot.config.constants import UpdateStatus
from checkin_bot.core.timezone import now
from checkin_bot.models.account_update import AccountUpdate
from checkin_bot.repositories.base import BaseRepository


class AccountUpdateRepository(BaseRepository):
    """账号更新追踪 Repository"""

    async def try_create_or_get_active(self, account_id: int) -> tuple[bool, AccountUpdate | None]:
        """
        尝试创建更新记录，或返回现有的活跃记录

        使用数据库层面的原子操作确保并发安全：
        - 如果没有活跃记录，创建新的 pending 记录
        - 如果已有活跃记录，返回现有记录

        Returns:
            (created, record): created=True 表示新创建，False 表示已存在
        """
        conn = await self._get_connection()
        current_time = now()

        # 使用 WITH 语句实现原子性：先查询活跃记录，没有则创建
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

        await self._release_connection(conn)

        if not record:
            return False, None

        update_model = self._to_model(record)
        # 如果状态是 pending 且刚创建（created_at 等于 current_time），则为新创建
        is_new = update_model.status == UpdateStatus.PENDING and update_model.created_at == current_time
        return is_new, update_model

    async def create(self, account_id: int) -> AccountUpdate:
        """创建更新记录"""
        conn = await self._get_connection()
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

        await self._release_connection(conn)
        return self._to_model(record)

    async def force_create(self, account_id: int) -> AccountUpdate:
        """
        强制创建更新记录（清理旧的活跃记录）

        用于用户手动触发更新时，允许覆盖之前的更新任务

        Returns:
            新创建的更新记录
        """
        conn = await self._get_connection()
        current_time = now()

        # 先清理该账号的活跃记录
        await conn.execute(
            """
            DELETE FROM account_updates
            WHERE account_id = $1
            AND status IN ('pending', 'processing')
            """,
            account_id,
        )

        # 创建新记录
        record = await conn.fetchrow(
            """
            INSERT INTO account_updates (account_id, status, started_at, completed_at, error_message, created_at)
            VALUES ($1, 'pending', NULL, NULL, NULL, $2)
            RETURNING *
            """,
            account_id,
            now,
        )

        await self._release_connection(conn)
        return self._to_model(record)

    async def get_by_id(self, update_id: int) -> AccountUpdate | None:
        """根据 ID 获取更新记录"""
        conn = await self._get_connection()
        record = await conn.fetchrow(
            "SELECT * FROM account_updates WHERE id = $1",
            update_id,
        )
        await self._release_connection(conn)

        if not record:
            return None
        return self._to_model(record)

    async def get_active_by_account(self, account_id: int) -> AccountUpdate | None:
        """获取账号的活跃更新记录（pending 或 processing）"""
        conn = await self._get_connection()
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
        await self._release_connection(conn)

        if not record:
            return None
        return self._to_model(record)

    async def update_status(
        self,
        update_id: int,
        status: UpdateStatus,
        error_message: str | None = None,
    ) -> AccountUpdate | None:
        """更新状态"""
        conn = await self._get_connection()
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

        await self._release_connection(conn)

        if not record:
            return None
        return self._to_model(record)

    async def delete(self, update_id: int) -> bool:
        """删除更新记录"""
        conn = await self._get_connection()
        result = await conn.execute(
            "DELETE FROM account_updates WHERE id = $1",
            update_id,
        )
        await self._release_connection(conn)

        return result == "DELETE 1"

    @staticmethod
    def _to_model(record) -> AccountUpdate:
        """数据库记录转换为模型"""
        return AccountUpdate(
            id=record["id"],
            account_id=record["account_id"],
            status=UpdateStatus(record["status"]),
            started_at=record["started_at"],
            completed_at=record["completed_at"],
            error_message=record["error_message"],
            created_at=record["created_at"],
        )
