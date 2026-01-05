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
            logger.debug(f"权限检查 {telegram_id}: 管理员 (ADMIN_IDS)")
            return PermissionLevel.ADMIN

        # 2. 检查缓存（非管理员用户使用缓存）
        cache_key = f"permission:{telegram_id}"
        cached_level = await self.cache.get(cache_key)

        if cached_level is not None:
            logger.debug(f"权限检查 {telegram_id}: 使用缓存结果={cached_level}")
            return PermissionLevel(cached_level)

        logger.debug(f"权限检查开始: 用户 {telegram_id}, application={application is not None}")

        # 缓存未命中，进行完整的权限检查
        level = await self._check_permission_internal(telegram_id, application)

        # 将结果存入缓存（管理员不缓存，已经在上面返回了）
        cache_ttl = self.settings.permission_cache_ttl_minutes * 60
        await self.cache.set(cache_key, level.value, ex=cache_ttl)
        logger.debug(f"权限检查 {telegram_id}: 缓存结果={level.value}, TTL={cache_ttl}秒")

        return level

    async def _check_permission_internal(
        self,
        telegram_id: int,
        application: object | None = None
    ) -> PermissionLevel:
        """
        内部权限检查方法（不包含缓存逻辑）

        Args:
            telegram_id: Telegram 用户 ID
            application: Telegram Application 对象（可选，用于检查群组成员）

        Returns:
            权限级别
        """
        # 2. 检查用户状态（被封禁、限制等）
        if application:
            is_allowed, status_reason = await self.check_user_status(telegram_id, application)
            if not is_allowed:
                logger.warning(f"权限检查 {telegram_id}: 用户状态异常 ({status_reason})，拒绝访问")
                return PermissionLevel.NOT_WHITELISTED

        # 3. 检查是否配置了白名单
        has_whitelist = self.settings.has_whitelist
        logger.info(f"权限检查 {telegram_id}: 配置了白名单={has_whitelist}, 用户白名单={self.settings.whitelist_user_ids}, 群组白名单={self.settings.whitelist_group_ids}, 频道白名单={self.settings.whitelist_channel_ids}")

        if not has_whitelist:
            logger.info(f"权限检查 {telegram_id}: 无白名单配置，允许所有用户")
            return PermissionLevel.NO_CONFIG

        # 4. 检查用户白名单
        if telegram_id in self.settings.whitelist_user_ids:
            logger.info(f"权限检查 {telegram_id}: 用户在白名单中")
            return PermissionLevel.USER

        # 5. 检查群组和频道白名单
        has_group_channel = self.settings.whitelist_group_ids or self.settings.whitelist_channel_ids
        logger.info(f"权限检查 {telegram_id}: application={'有' if application else 'None'}, 有群组/频道白名单={has_group_channel}")

        if application and has_group_channel:
            logger.info(f"权限检查 {telegram_id}: 检查群组/频道白名单...")
            is_in_group = await self.check_user_in_whitelist_groups(telegram_id, application)
            if is_in_group:
                logger.info(f"权限检查 {telegram_id}: 用户在白名单群组/频道中，允许")
                return PermissionLevel.USER
            else:
                logger.info(f"权限检查 {telegram_id}: 用户不在白名单群组/频道中")
        elif has_group_channel:
            # 关键问题：有群组/频道白名单配置，但无法检查！
            logger.error(
                f"权限检查 {telegram_id}: ⚠️ 有群组/频道白名单配置，但 application 为 None！"
                f"无法检查用户是否在群组/频道中。"
                f"这可能是由于："
                f"1. python-telegram-bot 版本问题"
                f"2. 中间件注册顺序错误"
                f"3. Bot 未正确初始化"
            )
        else:
            logger.info(f"权限检查 {telegram_id}: 没有配置群组/频道白名单")

        # 默认不允许访问
        logger.warning(f"权限检查 {telegram_id}: 不在白名单中，拒绝访问")
        return PermissionLevel.NOT_WHITELISTED

    async def check_user_status(
        self, telegram_id: int, application
    ) -> tuple[bool, str]:
        """
        检查用户与 bot 的聊天状态

        Args:
            telegram_id: Telegram 用户 ID
            application: Telegram Application 对象

        Returns:
            (is_allowed, reason): is_allowed 表示是否允许访问，reason 为原因说明
        """
        try:
            # 获取用户与 bot 的聊天状态
            chat_member = await application.bot.get_chat_member(
                chat_id=telegram_id,  # 对于私聊，chat_id 就是 user_id
                user_id=telegram_id,
            )

            status = chat_member.status
            logger.info(f"检查用户 {telegram_id} 状态: {status}")

            # 检查状态
            if status == "member":
                # 正常状态，用户可以与 bot 交互
                return True, "正常"
            elif status == "restricted":
                # 被限制的用户
                logger.warning(f"用户 {telegram_id} 状态为 restricted（被限制）")
                return False, "账户受限"
            elif status == "kicked":
                # 被封禁/踢出
                logger.warning(f"用户 {telegram_id} 状态为 kicked（被封禁）")
                return False, "账户被封禁"
            elif status == "left":
                # 用户主动离开或 block 了 bot
                logger.warning(f"用户 {telegram_id} 状态为 left（已离开/阻止）")
                return False, "已离开或阻止机器人"
            else:
                # 未知状态
                logger.warning(f"用户 {telegram_id} 状态为未知值: {status}")
                return False, f"未知状态({status})"

        except Exception as e:
            error_msg = str(e)
            # 检查是否是被封禁的错误
            if "Forbidden" in error_msg or "bot was blocked" in error_msg.lower():
                logger.warning(f"用户 {telegram_id} 封禁了机器人")
                return False, "已阻止机器人"
            elif "user not found" in error_msg.lower():
                logger.warning(f"用户 {telegram_id} 不存在或已删除")
                return False, "用户不存在"
            elif "chat not found" in error_msg.lower():
                logger.warning(f"用户 {telegram_id} 从未与机器人交互过")
                return False, "从未与机器人交互"
            else:
                logger.warning(f"检查用户 {telegram_id} 状态失败: {e}")
                # 对于检查状态的错误，我们默认允许（可能是网络问题）
                return True, "检查失败，默认允许"

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
        """撤销用户权限缓存"""
        cache_key = f"permission:{telegram_id}"
        await self.cache.delete(cache_key)
        logger.info(f"已清除用户 {telegram_id} 的权限缓存")

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
            # 判断是群组还是频道
            chat_type = "群组" if chat_id in group_ids else "频道"

            try:
                logger.info(f"检查用户 {telegram_id} 是否在{chat_type} {chat_id} 中...")
                member = await application.bot.get_chat_member(
                    chat_id=chat_id,
                    user_id=telegram_id,
                )
                # 如果能获取到成员信息，说明用户在群组中
                logger.info(
                    f"用户 {telegram_id} 在白名单{chat_type} {chat_id} 中: status={member.status}"
                )
                return True
            except Exception as e:
                error_msg = str(e).lower()
                # 区分不同类型的错误
                if "user not found" in error_msg or "not found" in error_msg:
                    logger.info(f"用户 {telegram_id} 不在{chat_type} {chat_id} 中")
                elif "forbidden" in error_msg or "not enough rights" in error_msg:
                    logger.error(f"Bot 没有{chat_type} {chat_id} 的权限！请确保 Bot 是{chat_type}管理员")
                elif "bad request" in error_msg or "chat not found" in error_msg:
                    logger.error(f"{chat_type} {chat_id} 不存在或 Bot 未加入")
                else:
                    logger.warning(f"检查用户 {telegram_id} 在{chat_type} {chat_id} 成员身份失败: {e}")
                continue

        logger.warning(f"用户 {telegram_id} 不在任何白名单群组/频道中")
        return False
