"""Bot 处理器辅助函数"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from checkin_bot.bot.keyboards.account import (
    get_account_list_keyboard,
    get_empty_account_keyboard,
)
from checkin_bot.bot.keyboards.main_menu import get_main_menu_keyboard
from checkin_bot.repositories.user_repository import UserRepository
from checkin_bot.services.account_manager import AccountManager
from checkin_bot.services.permission import PermissionService

logger = logging.getLogger(__name__)


async def get_user_or_error(update: Update, return_none: bool = False) -> Any | None:
    """
    获取当前用户，如果不存在则发送错误消息

    Args:
        update: Telegram 更新对象
        return_none: 是否返回 None（用于 ConversationHandler）

    Returns:
        用户对象，如果不存在且 return_none=True 则返回 None
    """
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(update.effective_user.id)

    if not user:
        await update.effective_message.edit_text("❌ 用户不存在")
        if return_none:
            return None
        # 对于 ConversationHandler，返回 ConversationHandler.END
        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    return user


async def show_account_list(
    update: Update,
    user_id: int,
    empty_message: str = "📝 您还没有添加任何账号",
    update_status: dict[int, str] | None = None,
) -> bool:
    """
    显示用户的账号列表

    Args:
        update: Telegram 更新对象
        user_id: 用户 ID
        empty_message: 空列表时的提示消息
        update_status: 更新状态字典 {account_id: status}，status 可为 'updating' 或 'completed'

    Returns:
        是否成功显示（False 表示账号为空）
    """
    account_manager = AccountManager()
    accounts = await account_manager.get_user_accounts(user_id)

    if not accounts:
        await update.effective_message.edit_text(
            empty_message,
            reply_markup=get_empty_account_keyboard(),
        )
        return False

    keyboard = get_account_list_keyboard(accounts, update_status)
    try:
        await update.effective_message.edit_text(
            f"📋 您的账号列表（共 {len(accounts)} 个）",
            reply_markup=keyboard,
        )
    except BadRequest as e:
        # 忽略 "Message is not modified" 错误（消息内容未改变）
        if "not modified" in str(e).lower():
            logger.debug(f"消息内容未改变，跳过编辑: {e}")
        else:
            logger.warning(f"编辑消息失败: {e}")
    return True


async def return_to_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """返回主菜单"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    permission_service = PermissionService()
    is_admin = await permission_service.is_admin(update.effective_user.id)

    keyboard = get_main_menu_keyboard(is_admin)
    username = update.effective_user.first_name or "朋友"

    try:
        await update.effective_message.edit_text(
            f"👋 欢迎回来，{username}!",
            reply_markup=keyboard,
        )
    except BadRequest as e:
        # 忽略 "Message is not modified" 错误（消息内容未改变）
        if "not modified" in str(e).lower():
            logger.debug(f"消息内容未改变，跳过编辑: {e}")
        else:
            logger.warning(f"编辑消息失败: {e}")


def is_valid_callback(update: Update) -> bool:
    """
    检查回调是否有效

    Args:
        update: Telegram 更新对象

    Returns:
        是否有效
    """
    return bool(update.effective_message and update.callback_query)


def parse_callback_id(callback_data: str, prefix: str) -> int | None:
    """
    解析回调数据中的 ID

    Args:
        callback_data: 回调数据字符串
        prefix: 数据前缀

    Returns:
        解析出的 ID，如果解析失败则返回 None

    Example:
        >>> parse_callback_id("delete_123", "delete_")
        123
        >>> parse_callback_id("view_logs_456", "view_logs_")
        456
    """
    try:
        if callback_data.startswith(prefix):
            return int(callback_data[len(prefix):])
        return None
    except (ValueError, TypeError):
        logger.warning(f"解析回调 ID 失败: callback_data={callback_data}, prefix={prefix}")
        return None


def parse_time_callback(callback_data: str, prefix: str) -> tuple[int, str | int] | None:
    """
    解析时间设置回调数据

    Args:
        callback_data: 回调数据字符串（格式：prefix_accountId_time 或 prefix_accountId_hour）
        prefix: 数据前缀

    Returns:
        (account_id, action) 元组，action 为 "time" 或小时数
        如果解析失败则返回 None

    Example:
        >>> parse_time_callback("set_checkin_123_time", "set_checkin_")
        (123, "time")
        >>> parse_time_callback("set_checkin_123_8", "set_checkin_")
        (123, 8)
    """
    try:
        if not callback_data.startswith(prefix):
            return None

        suffix = callback_data[len(prefix):]
        parts = suffix.split("_")

        if len(parts) != 2:
            return None

        account_id = int(parts[0])
        action = parts[1]

        # 如果是 "time"，返回字符串；否则尝试解析为小时
        if action == "time":
            return (account_id, "time")

        hour = int(action)
        return (account_id, hour)

    except (ValueError, TypeError):
        logger.warning(f"解析时间回调失败: callback_data={callback_data}, prefix={prefix}")
        return None


async def answer_callback_query(update: Update):
    """安全地回答回调查询"""
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except BadRequest as e:
            # 忽略查询已过期或已回答的错误
            if "expired" in str(e).lower() or "already answered" in str(e).lower():
                logger.debug(f"回调查询已过期或已回答: {e}")
            else:
                logger.warning(f"回答回调查询失败: {e}")
        except Exception as e:
            # 其他异常也记录但继续执行
            logger.debug(f"回答回调查询异常: {e}")
