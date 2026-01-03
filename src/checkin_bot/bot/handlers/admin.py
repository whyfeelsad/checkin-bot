"""管理员处理器"""

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from checkin_bot.bot.handlers._helpers import answer_callback_query
from checkin_bot.bot.keyboards.account import get_back_to_menu_keyboard
from checkin_bot.services.account_manager import AccountManager
from checkin_bot.services.permission import PermissionService

logger = logging.getLogger(__name__)


async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """后台管理回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    user_id = update.effective_user.id

    # 检查管理员权限
    permission_service = PermissionService()
    is_admin = await permission_service.is_admin(user_id)

    if not is_admin:
        logger.warning(f"用户 {user_id} 尝试在无权限情况下访问后台管理")
        await update.effective_message.edit_text(
            "❌ 您没有权限访问此功能",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    logger.info(f"管理员 {user_id} 访问后台管理")

    # 获取所有账号
    account_manager = AccountManager()
    accounts = await account_manager.account_repo.get_all_active()

    logger.debug(f"后台管理: 显示 {len(accounts)} 个账号")

    # 生成统计消息
    lines = [
        "🔧 后台管理",
        "",
        f"📊 总账号数: {len(accounts)}",
        "",
        "📋 账号列表:",
    ]

    for account in accounts[:20]:  # 最多显示 20 个
        lines.append(
            f"  • ID: {account.id} | "
            f"{account.site.value} | "
            f"{account.site_username} | "
            f"鸡腿: {account.credits}"
        )

    if len(accounts) > 20:
        lines.append(f"  ... 还有 {len(accounts) - 20} 个账号")

    await update.effective_message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_keyboard(),
    )


admin_handler = CallbackQueryHandler(admin_callback, pattern="^admin$")
