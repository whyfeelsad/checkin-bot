"""日志处理器"""

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from checkin_bot.bot.handlers._helpers import answer_callback_query
from checkin_bot.bot.keyboards.account import get_back_to_menu_keyboard
from checkin_bot.config.constants import CheckinStatus, SiteConfig
from checkin_bot.core.timezone import format_datetime
from checkin_bot.repositories.checkin_log_repository import CheckinLogRepository
from checkin_bot.repositories.user_repository import UserRepository
from checkin_bot.services.account_manager import AccountManager

logger = logging.getLogger(__name__)


async def logs_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """签到日志回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    user_id = update.effective_user.id
    logger.debug(f"用户 {user_id} 查看日志")

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
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # 获取所有账号的日志
    log_repo = CheckinLogRepository()
    account_ids = [a.id for a in accounts]
    logs = await log_repo.get_by_user(account_ids, limit=50)

    # 构建日志消息
    lines = ["📋 签到日志\n"]

    if not logs:
        lines.append("暂无签到记录")
    else:
        # 统计数据
        success_logs = sum(1 for log in logs if log.status == CheckinStatus.SUCCESS)
        failed_logs = sum(1 for log in logs if log.status == CheckinStatus.FAILED)
        total_credits = sum(log.credits_delta for log in logs if log.status == CheckinStatus.SUCCESS)

        # 统计摘要（简化）
        lines.append(f"✔ {success_logs} 成功 | ✖ {failed_logs} 失败")
        lines.append(f"今日收益 🍗  x {total_credits}\n")

        # 按账号分组
        account_logs = {}
        for log in logs:
            account_id = log.account_id
            if account_id not in account_logs:
                account = next((a for a in accounts if a.id == account_id), None)
                if account:
                    site_config = SiteConfig.get(account.site)
                    account_logs[account_id] = {
                        "account": account,
                        "site_name": site_config['name'],
                        "logs": []
                    }
            if account_id in account_logs:
                account_logs[account_id]["logs"].append(log)

        # 显示每个账号的日志
        for account_id, data in account_logs.items():
            account = data["account"]
            site_name = data["site_name"]
            account_logs_list = data["logs"]

            lines.append(f"🔖 {site_name} • {account.site_username}")

            for log in account_logs_list:
                # 状态图标
                if log.status == CheckinStatus.SUCCESS:
                    status_icon = "✔"
                elif log.status == CheckinStatus.FAILED:
                    status_icon = "✖"
                else:
                    status_icon = "⚠"

                # 时间格式化
                time_str = format_datetime(log.executed_at, "%m-%d %H:%M")

                # 签到结果
                if log.status == CheckinStatus.SUCCESS:
                    result_str = f"🍗 x {log.credits_delta}"
                else:
                    result_str = log.message or "失败"

                lines.append(f"{status_icon}  {time_str} • {result_str}")

            lines.append("")  # 账号之间空行

    await update.effective_message.edit_text(
        "\n".join(lines),
        reply_markup=get_back_to_menu_keyboard(),
    )


async def view_logs_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """查看单个账号的签到日志"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    # 解析账号 ID
    callback_data = update.callback_query.data
    try:
        account_id = int(callback_data.replace("view_logs_", ""))
    except (ValueError, AttributeError):
        logger.warning(f"无效的 callback_data: {callback_data}")
        return

    user_id = update.effective_user.id
    logger.debug(f"用户 {user_id} 查看账号 {account_id} 的日志")

    # 获取用户
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(user_id)

    if not user:
        logger.warning(f"用户不存在: telegram_id={user_id}")
        await update.effective_message.edit_text("❌ 用户不存在")
        return

    # 获取账号并验证权限
    account_manager = AccountManager()
    accounts = await account_manager.get_user_accounts(user.id)
    account = next((a for a in accounts if a.id == account_id), None)

    if not account:
        logger.warning(f"账号不存在或无权访问: account_id={account_id}")
        await update.effective_message.edit_text("❌ 账号不存在")
        return

    # 获取该账号的日志
    log_repo = CheckinLogRepository()
    logs = await log_repo.get_by_account(account_id, limit=50)

    # 构建日志消息
    site_config = SiteConfig.get(account.site)
    lines = [
        f"📋 签到日志",
        f"",
        f"🔖 {site_config['name']} • {account.site_username}",
    ]

    if not logs:
        lines.extend([
            f"",
            f"🍗 {account.credits} | 🔢 {account.checkin_count} 次",
            f"",
            "暂无签到记录",
        ])
    else:
        # 统计数据
        total_logs = len(logs)
        success_logs = sum(1 for log in logs if log.status == CheckinStatus.SUCCESS)
        failed_logs = sum(1 for log in logs if log.status == CheckinStatus.FAILED)
        total_credits = sum(log.credits_delta for log in logs if log.status == CheckinStatus.SUCCESS)
        success_rate = (success_logs / total_logs * 100) if total_logs > 0 else 0

        # 计算趋势（最近5次与之前对比）
        recent_logs = logs[:5]
        recent_credits = sum(log.credits_delta for log in recent_logs if log.status == CheckinStatus.SUCCESS)
        if len(logs) > 5:
            earlier_logs = logs[5:]
            earlier_credits = sum(log.credits_delta for log in earlier_logs if log.status == CheckinStatus.SUCCESS)
            avg_recent = recent_credits / len(recent_logs)
            avg_earlier = earlier_credits / len(earlier_logs) if earlier_logs else 0
            if avg_recent > avg_earlier:
                trend = "📈 上升"
            elif avg_recent < avg_earlier:
                trend = "📉 下降"
            else:
                trend = "➡️ 持平"
        else:
            trend = "➡️ 数据不足"

        lines.extend([
            f"",
            f"🍗 {account.credits} | 🔢 {account.checkin_count} 次",
            f"",
            f"✔ {success_logs} 成功 | ✖ {failed_logs} 失败",
            f"📈 {success_rate:.0f}% | 🍗  x {total_credits}",
            f"📡 {trend}",
            f"",
            f"最近签到",
        ])

        for log in logs:
            # 状态图标
            if log.status == CheckinStatus.SUCCESS:
                status_icon = "✔"
            elif log.status == CheckinStatus.FAILED:
                status_icon = "✖"
            else:
                status_icon = "⚠"

            # 时间格式化
            time_str = format_datetime(log.executed_at, "%m-%d %H:%M")

            # 签到结果
            if log.status == CheckinStatus.SUCCESS:
                result_str = f"🍗 x {log.credits_delta}"
                if log.credits_before is not None and log.credits_after is not None:
                    result_str += f" ({log.credits_before}→{log.credits_after})"
            else:
                result_str = log.message or "失败"

            lines.append(f"{status_icon}  {time_str} • {result_str}")

    lines.append("")

    await update.effective_message.edit_text(
        "\n".join(lines),
        reply_markup=get_back_to_menu_keyboard(),
    )


logs_handler = CallbackQueryHandler(logs_callback, pattern="^logs$")
view_logs_handler = CallbackQueryHandler(view_logs_callback, pattern="^view_logs_\\d+$")
