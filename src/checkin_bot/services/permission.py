"""权限服务"""

import logging
from enum import Enum

from checkin_bot.config.settings import get_settings
from checkin_bot.core.cache import get_cache

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """权限级别"""
    ADMIN = "admin"  # 管理员
    USER = "user"  # 普通用户
    NO_CONFIG = "no_config"  # 无白名单限制
    NOT_WHITELISTED = "not_whitelisted"  # 不在白名单


class PermissionService:
    """权限服务类"""

    def __init__(self):
        self.settings = get_settings()
        self.cache = get_cache()

    async def check_permission(self, telegram_id: int) -> PermissionLevel:
        """
        检查用户权限

        Args:
            telegram_id: Telegram 用户 ID

        Returns:
            权限级别
        """
        # 1. 检查缓存
        cached = await self.cache.get(telegram_id)
        if cached is not None:
            logger.debug(f"权限检查 {telegram_id}: {'允许' if cached else '拒绝'} (缓存)")
            return PermissionLevel.USER if cached else PermissionLevel.NOT_WHITELISTED

        # 2. 检查管理员
        if telegram_id in self.settings.admin_ids:
            await self.cache.set(telegram_id, True)
            logger.debug(f"权限检查 {telegram_id}: 管理员")
            return PermissionLevel.ADMIN

        # 3. 检查是否配置了白名单
        if not self.settings.has_whitelist:
            await self.cache.set(telegram_id, True)
            logger.debug(f"权限检查 {telegram_id}: 无白名单配置，允许")
            return PermissionLevel.NO_CONFIG

        # 4. 检查用户白名单
        if telegram_id in self.settings.whitelist_user_ids:
            await self.cache.set(telegram_id, True)
            logger.debug(f"权限检查 {telegram_id}: 用户在白名单中")
            return PermissionLevel.USER

        # 5. 检查群组和频道白名单
        # 这里需要额外的上下文信息，暂不在缓存中处理
        # 群组和频道检查在中间件中处理

        # 默认不允许访问
        logger.debug(f"权限检查 {telegram_id}: 不在白名单中，拒绝")
        return PermissionLevel.NOT_WHITELISTED

    async def is_admin(self, telegram_id: int) -> bool:
        """检查是否为管理员"""
        return telegram_id in self.settings.admin_ids

    async def is_whitelisted_user(self, telegram_id: int) -> bool:
        """检查用户是否在白名单"""
        # 管理员自动拥有权限
        if await self.is_admin(telegram_id):
            return True

        # 无白名单配置则允许所有
        if not self.settings.has_whitelist:
            return True

        # 检查用户白名单
        return telegram_id in self.settings.whitelist_user_ids

    async def is_whitelisted_group(self, group_id: int) -> bool:
        """检查群组是否在白名单"""
        # 无白名单配置则允许所有
        if not self.settings.has_whitelist:
            return True

        return group_id in self.settings.whitelist_group_ids

    async def is_whitelisted_channel(self, channel_id: int) -> bool:
        """检查频道是否在白名单"""
        # 无白名单配置则允许所有
        if not self.settings.has_whitelist:
            return True

        return channel_id in self.settings.whitelist_channel_ids

    async def revoke_cache(self, telegram_id: int):
        """撤销用户缓存"""
        await self.cache.delete(telegram_id)
