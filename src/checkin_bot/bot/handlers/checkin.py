"""签到处理器"""

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from checkin_bot.bot.handlers._helpers import answer_callback_query, parse_callback_id
from checkin_bot.bot.keyboards.checkin import (
    get_checkin_keyboard,
    get_back_to_checkin_list_keyboard,
)
from checkin_bot.bot.keyboards.account import (
    get_back_to_menu_keyboard,
    get_empty_account_keyboard,
)
from checkin_bot.repositories.user_repository import UserRepository
from checkin_bot.services.checkin import CheckinService

logger = logging.getLogger(__name__)


async def checkin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """立即签到回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    user_id = update.effective_user.id
    logger.info(f"用户 {update.effective_user.username or user_id} 请求手动签到")

    # 获取用户
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(user_id)

    if not user:
        await update.effective_message.edit_text(
            "❌ 用户不存在",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # 获取账号列表
    checkin_service = CheckinService()
    account_manager = checkin_service.account_repo
    accounts = await account_manager.get_by_user(user.id)

    if not accounts:
        await update.effective_message.edit_text(
            "📝 您还没有添加任何账号",
            reply_markup=get_empty_account_keyboard(),
        )
        return

    keyboard = get_checkin_keyboard(accounts)

    await update.effective_message.edit_text(
        "📋 请选择要签到的账号：",
        reply_markup=keyboard,
    )


async def checkin_status_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """签到状态回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    # 解析账号 ID
    account_id = parse_callback_id(update.callback_query.data, "checkin_")
    if account_id is None:
        logger.warning(f"无效的签到回调数据: {update.callback_query.data}")
        await update.effective_message.edit_text(
            "❌ 无效的请求",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # 执行签到
    checkin_service = CheckinService()
    result = await checkin_service.manual_checkin(account_id)

    if result["success"]:
        delta = result.get("credits_delta", 0)
        after = result.get("credits_after", 0)
        message = result.get("message", "")
        logger.info(f"手动签到成功: 账号 {account_id} +{delta} 鸡腿, 总计: {after}")

        # 检查是否为重复签到
        if "今日已签到" in message or "已完成签到" in message or "已经签到" in message or "重复" in message:
            text = (
                f"🔔 今日已签到，请勿重复操作！\n"
                f"📈 鸡腿变化: +{delta}，当前鸡腿：{after}"
            )
        else:
            text = (
                f"🎉 签到成功！\n"
                f"📈 鸡腿变化: +{delta}\n"
                f"💰 当前鸡腿: {after}"
            )

        await update.effective_message.edit_text(
            text,
            reply_markup=get_back_to_checkin_list_keyboard(),
        )
    else:
        logger.warning(f"手动签到失败: 账号 {account_id} - {result.get('message', '未知错误')}")
        await update.effective_message.edit_text(
            f"❌ 签到失败\n"
            f"{result.get('message', '未知错误')}",
            reply_markup=get_back_to_checkin_list_keyboard(),
        )


# Handler instances
checkin_handler = CallbackQueryHandler(checkin_callback, pattern="^checkin$")
checkin_status_handler = CallbackQueryHandler(checkin_status_callback, pattern="^checkin_")
