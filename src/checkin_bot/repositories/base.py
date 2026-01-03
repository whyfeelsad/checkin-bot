"""Repository base class"""

import logging
from abc import ABC, abstractmethod

from checkin_bot.core.database import DatabaseConnection

logger = logging.getLogger(__name__)


class BaseRepository(ABC):
    """Repository base class"""

    def __init__(self):
        self._db_context = None

    async def _get_connection(self):
        """Get database connection"""
        self._db_context = DatabaseConnection()
        conn = await self._db_context.__aenter__()
        return conn

    async def _release_connection(self, conn):
        """
        Release database connection (with exception safety)
        """
        if self._db_context:
            try:
                await self._db_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error releasing database connection: {e}")
            finally:
                self._db_context = None
