"""权限中间件"""

import logging
from telegram import Update
from telegram.ext import BaseHandler, ContextTypes, ApplicationHandlerStop

from checkin_bot.services.permission import PermissionLevel, PermissionService

logger = logging.getLogger(__name__)


class PermissionMiddleware(BaseHandler):
    """权限中间件 - 对所有更新进行权限检查"""

    def __init__(self):
        # BaseHandler 需要一个 callback 参数
        super().__init__(callback=self._check_permission)
        self.permission_service = PermissionService()

    def check_update(self, update: Update) -> bool:
        """
        检查是否应该处理此更新

        对于权限中间件，我们需要检查所有更新，所以总是返回 True
        """
        # 只要有有效的用户就检查权限
        return update.effective_user is not None

    async def _check_permission(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        权限检查方法

        Args:
            update: Telegram 更新对象
            context: Bot 上下文
        """
        if not update.effective_user:
            return

        telegram_id = update.effective_user.id
        application = context.application

        # 诊断：记录 application 的详细信息
        logger.debug(
            f"权限中间件诊断: "
            f"application类型={type(application).__name__}, "
            f"有bot属性={hasattr(application, 'bot')}, "
            f"bot类型={type(application.bot).__name__ if hasattr(application, 'bot') else 'N/A'}"
        )

        # 检查权限（一次性完成所有检查）
        level = await self.permission_service.check_permission(
            telegram_id, application
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
                    await application.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"发送权限拒绝消息失败: {e}")

            raise ApplicationHandlerStop  # 阻止继续处理

        # 权限检查通过，继续由其他 handler 处理
        logger.info(f"权限中间件: 用户 {telegram_id} 权限检查通过")
        return
