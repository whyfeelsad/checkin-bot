"""Repository 基类"""

from abc import ABC, abstractmethod

from checkin_bot.core.database import DatabaseConnection


class BaseRepository(ABC):
    """Repository 基类"""

    def __init__(self):
        self._db_context = None

    async def _get_connection(self):
        """获取数据库连接"""
        self._db_context = DatabaseConnection()
        conn = await self._db_context.__aenter__()
        return conn

    async def _release_connection(self, conn):
        """释放数据库连接"""
        if self._db_context:
            await self._db_context.__aexit__(None, None, None)
            self._db_context = None
