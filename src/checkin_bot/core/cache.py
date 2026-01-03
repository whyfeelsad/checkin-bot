"""权限缓存模块（内存 + TTL）"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from checkin_bot.config.settings import get_settings
from checkin_bot.core.timezone import now


@dataclass
class CacheEntry:
    """缓存条目"""
    value: bool
    expires_at: datetime


class PermissionCache:
    """权限缓存类"""

    def __init__(self):
        self._cache: dict[int, CacheEntry] = {}
        self._lock = asyncio.Lock()

    def _get_ttl(self) -> timedelta:
        """获取缓存 TTL"""
        settings = get_settings()
        return timedelta(minutes=settings.permission_cache_ttl_minutes)

    async def get(self, telegram_id: int) -> Optional[bool]:
        """获取缓存的权限值"""
        async with self._lock:
            entry = self._cache.get(telegram_id)
            if entry is None:
                return None
            if now() > entry.expires_at:
                del self._cache[telegram_id]
                return None
            return entry.value

    async def set(self, telegram_id: int, value: bool):
        """设置缓存的权限值"""
        async with self._lock:
            self._cache[telegram_id] = CacheEntry(
                value=value,
                expires_at=now() + self._get_ttl(),
            )

    async def delete(self, telegram_id: int):
        """删除缓存条目"""
        async with self._lock:
            self._cache.pop(telegram_id, None)

    async def clear_expired(self):
        """清理过期缓存"""
        async with self._lock:
            current = now()
            expired_keys = [
                key for key, entry in self._cache.items()
                if current > entry.expires_at
            ]
            for key in expired_keys:
                del self._cache[key]

    async def clear_all(self):
        """清空所有缓存"""
        async with self._lock:
            self._cache.clear()


# 全局缓存实例
_cache: Optional[PermissionCache] = None


def get_cache() -> PermissionCache:
    """获取权限缓存实例（单例模式）"""
    global _cache
    if _cache is None:
        _cache = PermissionCache()
    return _cache
