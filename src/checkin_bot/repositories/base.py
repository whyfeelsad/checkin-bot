"""Repository base class"""

import asyncio
import logging
from abc import ABC, abstractmethod

from checkin_bot.core.database import DatabaseConnection

logger = logging.getLogger(__name__)


class BaseRepository(ABC):
    """Repository base class"""

    # 使用任务本地存储隔离每个任务的连接上下文
    _contexts = {}

    async def _get_connection(self):
        """Get database connection"""
        # 使用当前任务 ID 作为 key，确保并发安全
        task_id = id(asyncio.current_task())

        if task_id not in self._contexts:
            self._contexts[task_id] = DatabaseConnection()

        db_context = self._contexts[task_id]
        conn = await db_context.__aenter__()
        return conn

    async def _release_connection(self, _conn=None):
        """
        Release database connection (with exception safety)

        Args:
            _conn: Unused, kept for backwards compatibility
        """
        task_id = id(asyncio.current_task())

        if task_id in self._contexts:
            try:
                await self._contexts[task_id].__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error releasing database connection: {e}")
            finally:
                del self._contexts[task_id]
