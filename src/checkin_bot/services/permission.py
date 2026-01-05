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

    async def check_permission(
        self,
        telegram_id: int,
        application: object | None = None
    ) -> PermissionLevel:
        """
        检查用户权限

        Args:
            telegram_id: Telegram 用户 ID
            application: Telegram Application 对象（可选，用于检查群组成员）

        Returns:
            权限级别
        """
        # 1. 检查管理员（管理员不使用缓存，确保实时检查）
        if telegram_id in self.settings.admin_ids:
            logger.info(f"权限检查 {telegram_id}: 管理员 (ADMIN_IDS)")
            return PermissionLevel.ADMIN

        # 2. 检查是否配置了白名单
        has_whitelist = self.settings.has_whitelist
        logger.info(f"权限检查 {telegram_id}: 配置了白名单={has_whitelist}, 用户白名单={self.settings.whitelist_user_ids}, 群组白名单={self.settings.whitelist_group_ids}, 频道白名单={self.settings.whitelist_channel_ids}")

        if not has_whitelist:
            logger.info(f"权限检查 {telegram_id}: 无白名单配置，允许所有用户")
            return PermissionLevel.NO_CONFIG

        # 3. 检查用户白名单
        if telegram_id in self.settings.whitelist_user_ids:
            logger.info(f"权限检查 {telegram_id}: 用户在白名单中")
            return PermissionLevel.USER

        # 4. 检查群组和频道白名单
        if application and (self.settings.whitelist_group_ids or self.settings.whitelist_channel_ids):
            logger.info(f"权限检查 {telegram_id}: 检查群组/频道白名单...")
            is_in_group = await self.check_user_in_whitelist_groups(telegram_id, application)
            if is_in_group:
                logger.info(f"权限检查 {telegram_id}: 用户在白名单群组/频道中，允许")
                return PermissionLevel.USER
            else:
                logger.info(f"权限检查 {telegram_id}: 用户不在白名单群组/频道中")

        # 默认不允许访问
        logger.warning(f"权限检查 {telegram_id}: 不在白名单中，拒绝访问")
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

    async def check_user_in_whitelist_groups(
        self, telegram_id: int, application
    ) -> bool:
        """
        检查用户是否在白名单群组/频道中

        Args:
            telegram_id: Telegram 用户 ID
            application: Telegram Application 对象（用于调用 API）

        Returns:
            用户是否在白名单群组/频道中
        """
        # 合并群组和频道 ID
        group_ids = self.settings.whitelist_group_ids
        channel_ids = self.settings.whitelist_channel_ids
        all_chat_ids = group_ids + channel_ids

        logger.info(f"检查用户 {telegram_id} 是否在白名单群组/频道中，群组={group_ids}, 频道={channel_ids}")

        if not all_chat_ids:
            logger.info(f"没有配置群组/频道白名单")
            return False

        # 检查用户是否在任何一个白名单群组/频道中
        for chat_id in all_chat_ids:
            try:
                logger.info(f"检查用户 {telegram_id} 是否在群组/频道 {chat_id} 中...")
                member = await application.bot.get_chat_member(
                    chat_id=chat_id,
                    user_id=telegram_id,
                )
                # 如果能获取到成员信息，说明用户在群组中
                logger.info(
                    f"用户 {telegram_id} 在白名单群组/频道 {chat_id} 中: status={member.status}"
                )
                return True
            except Exception as e:
                # 用户不在群组中或 Bot 无权限访问
                logger.warning(f"检查用户 {telegram_id} 在群组/频道 {chat_id} 成员身份失败: {e}")
                continue

        logger.warning(f"用户 {telegram_id} 不在任何白名单群组/频道中")
        return False
