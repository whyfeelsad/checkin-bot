"""权限中间件"""

from telegram import Update
from telegram.ext import BaseHandler, ContextTypes, ApplicationHandlerStop

from checkin_bot.services.permission import PermissionLevel, PermissionService


class PermissionMiddleware(BaseHandler):
    """权限中间件"""

    def __init__(self):
        super().__init__(callback=self.check_permission)
        self.permission_service = PermissionService()

    def check_update(self, update: Update) -> bool:
        """检查是否需要处理此更新"""
        # 所有更新都需要经过权限检查
        return True

    async def check_permission(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """检查权限，通过则继续，失败则抛出 DispatcherHandlerStop"""
        if not update.effective_user:
            return

        telegram_id = update.effective_user.id

        # 检查权限
        level = await self.permission_service.check_permission(telegram_id)

        if level == PermissionLevel.NOT_WHITELISTED:
            # 用户不在用户白名单中，检查是否在白名单群组/频道中
            is_in_group = await self.permission_service.check_user_in_whitelist_groups(
                telegram_id, context.application
            )

            if is_in_group:
                # 用户在白名单群组/频道中，允许使用
                return

            # 用户不在白名单中，发送提示消息
            if update.effective_message:
                await update.effective_message.reply_text(
                    "抱歉，您没有使用此机器人的权限。"
                )
            raise ApplicationHandlerStop  # 阻止继续处理

        # 检查群组/频道权限
        if update.effective_chat:
            chat_id = update.effective_chat.id
            chat_type = update.effective_chat.type

            if chat_type in ["group", "supergroup"]:
                if not await self.permission_service.is_whitelisted_group(chat_id):
                    if update.effective_message:
                        await update.effective_message.reply_text(
                            "此群组未在白名单中。"
                        )
                    raise ApplicationHandlerStop

            elif chat_type == "channel":
                if not await self.permission_service.is_whitelisted_channel(chat_id):
                    if update.effective_message:
                        await update.effective_message.reply_text(
                            "此频道未在白名单中。"
                        )
                    raise ApplicationHandlerStop

        # 权限检查通过，继续由其他 handler 处理
        return
