"""Start 命令处理器"""

import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from checkin_bot.bot.keyboards.main_menu import get_main_menu_keyboard
from checkin_bot.repositories.user_repository import UserRepository
from checkin_bot.services.permission import PermissionLevel, PermissionService

logger = logging.getLogger(__name__)


async def start_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """处理 /start 命令"""
    if not update.effective_user or not update.effective_message:
        return

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"用户 {username} (ID: {user_id}) 启动了 Bot")

    # 获取或创建用户
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(user_id)

    if not user:
        user = await user_repo.create(
            telegram_id=user_id,
            telegram_username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name,
        )
        logger.info(f"创建新用户: {username} (ID: {user_id})")

    permission_service = PermissionService()
    level = await permission_service.check_permission(user_id)

    # 检查是否为管理员
    is_admin = await permission_service.is_admin(user_id)

    welcome_text = (
        f"👋 欢迎使用签到机器人，{update.effective_user.first_name}！\n\n"
        "📅 自动签到，鸡腿不再错过\n"
        "🔒 密码加密，安心使用\n"
        "🎉 支持多站点、多账号管理"
    )

    keyboard = get_main_menu_keyboard(is_admin)

    await update.effective_message.reply_text(
        welcome_text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
