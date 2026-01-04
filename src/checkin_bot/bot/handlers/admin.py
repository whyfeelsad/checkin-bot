"""管理员处理器"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from checkin_bot.bot.handlers._helpers import answer_callback_query, parse_callback_id
from checkin_bot.bot.handlers.account_handlers import (
    show_account_list,
    update_cookie_callback,
    toggle_mode_callback,
    set_checkin_time_callback,
    set_push_time_callback,
    delete_account_callback,
)
from checkin_bot.bot.keyboards.account import get_back_to_menu_keyboard
from checkin_bot.bot.keyboards.checkin import get_checkin_keyboard
from checkin_bot.repositories.user_repository import UserRepository
from checkin_bot.repositories.account_repository import AccountRepository
from checkin_bot.services.permission import PermissionService

logger = logging.getLogger(__name__)


def get_admin_user_list_keyboard(users_with_accounts: list) -> InlineKeyboardMarkup:
    """
    获取管理员用户列表键盘

    Args:
        users_with_accounts: 用户信息列表 [(user, account_count), ...]

    Returns:
        用户列表键盘
    """
    buttons = []

    for user, account_count in users_with_accounts:
        # 显示用户名和账号数量
        username = user.first_name or user.telegram_username or f"用户{user.id}"
        user_info = f"👤 {username} • 🆔 {user.telegram_id} • 📊 {account_count}账号"
        buttons.append([
            InlineKeyboardButton(
                user_info,
                callback_data=f"admin_user_{user.id}",
            )
        ])

    # 返回后台管理按钮
    buttons.append([InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")])

    return InlineKeyboardMarkup(buttons)


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

    # 获取所有用户和账号统计
    user_repo = UserRepository()
    account_repo = AccountRepository()

    users = await user_repo.get_all()
    total_accounts = await account_repo.count_all_active()

    # 统计每个用户的账号数量
    users_with_accounts = []
    for user in users:
        account_count = await account_repo.count_by_user(user.id)
        if account_count > 0:
            users_with_accounts.append((user, account_count))

    # 生成键盘
    keyboard = get_admin_user_list_keyboard(users_with_accounts)

    # 生成统计消息
    text = f"⚙️ 管理后台 • 👥 {len(users_with_accounts)} 用户 • 📦 {total_accounts} 账号"

    await update.effective_message.edit_text(
        text,
        reply_markup=keyboard,
    )


async def admin_view_user_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """管理员查看用户账号回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    user_id = update.effective_user.id

    # 检查管理员权限
    permission_service = PermissionService()
    is_admin = await permission_service.is_admin(user_id)

    if not is_admin:
        await update.effective_message.edit_text(
            "❌ 您没有权限访问此功能",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # 解析目标用户 ID
    target_user_id = parse_callback_id(update.callback_query.data, "admin_user_")
    if target_user_id is None:
        await update.effective_message.edit_text("❌ 无效的请求")
        return

    logger.info(f"管理员 {user_id} 查看用户 {target_user_id} 的账号")

    # 获取目标用户的账号
    account_repo = AccountRepository()
    accounts = await account_repo.get_by_user(target_user_id)

    if not accounts:
        await update.effective_message.edit_text(
            "该用户没有账号",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # 生成账号列表键盘（与用户自己看到的一样）
    from checkin_bot.bot.keyboards.account import get_account_list_keyboard

    keyboard = get_account_list_keyboard(accounts)

    # 获取用户信息
    user_repo = UserRepository()
    target_user = await user_repo.get_by_id(target_user_id)
    username = target_user.first_name or target_user.telegram_username or f"用户{target_user.id}"

    await update.effective_message.edit_text(
        f"👤 {username} 的账号列表（共 {len(accounts)} 个）",
        reply_markup=keyboard,
    )


# Handler instances
admin_handler = CallbackQueryHandler(admin_callback, pattern="^admin$")
admin_view_user_handler = CallbackQueryHandler(admin_view_user_callback, pattern="^admin_user_")
