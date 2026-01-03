"""统计处理器"""

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from checkin_bot.bot.handlers._helpers import answer_callback_query
from checkin_bot.bot.keyboards.account import (
    get_back_to_menu_keyboard,
    get_empty_account_keyboard,
)
from checkin_bot.repositories.user_repository import UserRepository
from checkin_bot.services.account_manager import AccountManager

logger = logging.getLogger(__name__)


async def stats_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """数据统计回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    user_id = update.effective_user.id
    logger.debug(f"用户 {user_id} 查看统计")

    # 获取用户
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(user_id)

    if not user:
        logger.warning(f"用户不存在: telegram_id={user_id}")
        await update.effective_message.edit_text("❌ 用户不存在")
        return

    # 获取账号列表
    account_manager = AccountManager()
    accounts = await account_manager.get_user_accounts(user.id)

    if not accounts:
        logger.debug(f"用户 {user_id} 没有账号")
        await update.effective_message.edit_text(
            "📝 您还没有添加任何账号",
            reply_markup=get_empty_account_keyboard(),
        )
        return

    # 统计数据
    total_accounts = len(accounts)
    total_checkins = sum(acc.checkin_count for acc in accounts)
    total_credits = sum(acc.credits for acc in accounts)

    logger.debug(f"用户 {user_id} 统计: {total_accounts} 个账号, {total_checkins} 次签到, {total_credits} 鸡腿")

    # 按站点统计
    from checkin_bot.config.constants import SiteConfig, SiteType

    site_stats = {}
    for account in accounts:
        site_name = SiteConfig.get(account.site)["name"]
        if site_name not in site_stats:
            site_stats[site_name] = {
                "count": 0,
                "credits": 0,
                "checkins": 0,
            }
        site_stats[site_name]["count"] += 1
        site_stats[site_name]["credits"] += account.credits
        site_stats[site_name]["checkins"] += account.checkin_count

    # 生成统计消息
    lines = [
        "📊 数据统计",
        "",
        f"📝 总账号数: {total_accounts}",
        f"✅ 总签到次数: {total_checkins}",
        f"💰 总鸡腿数: {total_credits}",
        "",
        "🌐 站点分布:",
    ]

    for site_name, stats in site_stats.items():
        lines.append(
            f"  • {site_name}: {stats['count']} 个账号, "
            f"{stats['checkins']} 次签到, {stats['credits']} 鸡腿"
        )

    await update.effective_message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_keyboard(),
    )


stats_handler = CallbackQueryHandler(stats_callback, pattern="^stats$")
