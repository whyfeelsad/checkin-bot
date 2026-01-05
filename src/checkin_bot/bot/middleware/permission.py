"""权限中间件"""

import logging
from telegram import Update
from telegram.ext import BaseHandler, ContextTypes, DispatcherHandlerStop

from checkin_bot.services.permission import PermissionLevel, PermissionService

logger = logging.getLogger(__name__)


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

        # 检查权限（一次性完成所有检查）
        level = await self.permission_service.check_permission(
            telegram_id, context.application
        )

        logger.info(f"权限中间件: 用户 {telegram_id} 权限级别={level}")

        if level == PermissionLevel.NOT_WHITELISTED:
            # 用户不在白名单中，发送提示消息
            logger.warning(f"权限中间件: 拒绝用户 {telegram_id} 访问（不在白名单中）")

            message = (
                "🚫 *权限限制*\n\n"
                "抱歉，您没有使用此机器人的权限。\n"
                "请先加入指定频道或联系管理员。"
            )

            # 尝试发送拒绝消息
            try:
                if update.effective_message:
                    await update.effective_message.reply_text(
                        message,
                        parse_mode="Markdown"
                    )
                elif update.callback_query:
                    # 如果是 callback query，先回答再发送消息
                    await update.callback_query.answer(text="🚫 没有权限", show_alert=True)
                    await update.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"发送权限拒绝消息失败: {e}")

            raise DispatcherHandlerStop  # 阻止继续处理

        # 检查群组/频道权限（当 Bot 在群组/频道中被调用时）
        if update.effective_chat:
            chat_id = update.effective_chat.id
            chat_type = update.effective_chat.type

            if chat_type in ["group", "supergroup"]:
                if not await self.permission_service.is_whitelisted_group(chat_id):
                    logger.warning(f"权限中间件: 拒绝群组 {chat_id} 访问（群组不在白名单中）")
                    if update.effective_message:
                        await update.effective_message.reply_text(
                            "🚫 此群组未在白名单中，请联系管理员。"
                        )
                    raise DispatcherHandlerStop

            elif chat_type == "channel":
                if not await self.permission_service.is_whitelisted_channel(chat_id):
                    logger.warning(f"权限中间件: 拒绝频道 {chat_id} 访问（频道不在白名单中）")
                    if update.effective_message:
                        await update.effective_message.reply_text(
                            "🚫 此频道未在白名单中，请联系管理员。"
                        )
                    raise DispatcherHandlerStop

        # 权限检查通过，继续由其他 handler 处理
        logger.info(f"权限中间件: 用户 {telegram_id} 权限检查通过")
        return
