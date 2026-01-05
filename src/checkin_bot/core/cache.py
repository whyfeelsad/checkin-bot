"""权限缓存模块（内存 + TTL）"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from checkin_bot.config.settings import get_settings
from checkin_bot.core.timezone import now


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    expires_at: datetime


class PermissionCache:
    """权限缓存类"""

    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存的权限值"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if now() > entry.expires_at:
                del self._cache[key]
                return None
            return entry.value

    async def set(self, key: str, value: Any, ex: int | None = None):
        """
        设置缓存的权限值

        Args:
            key: 缓存键
            value: 缓存值
            ex: 过期时间（秒），如果为 None 则使用默认 TTL
        """
        async with self._lock:
            if ex is None:
                settings = get_settings()
                ttl = timedelta(minutes=settings.permission_cache_ttl_minutes)
            else:
                ttl = timedelta(seconds=ex)
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=now() + ttl,
            )

    async def delete(self, key: str):
        """删除缓存条目"""
        async with self._lock:
            self._cache.pop(key, None)

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
