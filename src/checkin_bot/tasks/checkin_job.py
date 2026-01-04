"""定时签到任务"""

import logging
from collections import defaultdict

from telegram.ext import Application

from checkin_bot.core.timezone import now
from checkin_bot.repositories.account_repository import AccountRepository
from checkin_bot.services.checkin import CheckinService
from checkin_bot.services.notification import NotificationService

logger = logging.getLogger(__name__)


def register_checkin_job(app: Application):
    """
    注册签到任务

    Args:
        app: Bot 应用实例
    """
    checkin_service = CheckinService()

    async def checkin_job_callback(context):
        """签到任务回调"""
        try:
            results = await checkin_service.scheduled_checkin()

            if results:
                logger.info(f"完成了 {len(results)} 个定时签到")

        except Exception as e:
            logger.error(f"签到任务错误: {e}")

    # 每分钟执行一次
    app.job_queue.run_repeating(
        checkin_job_callback,
        interval=60,  # 60 秒
        first=1,  # 1 秒后开始
    )

    logger.info("签到任务已注册")


def register_push_job(app: Application):
    """
    注册推送任务

    Args:
        app: Bot 应用实例
    """
    account_repo = AccountRepository()
    notification_service = NotificationService()

    async def push_job_callback(context):
        """推送任务回调"""
        try:
            current_hour = now().hour
            current_minute = now().minute

            # 只在每小时的第 0 分钟执行
            if current_minute != 0:
                return

            logger.info(f"开始检查推送任务: 当前时间 {current_hour}点")

            # 获取需要推送的账号
            accounts = await account_repo.get_by_push_time(current_hour)

            if not accounts:
                logger.debug(f"没有需要推送的账号 (push_hour={current_hour})")
                return

            # 按用户分组
            user_accounts = defaultdict(list)
            for account in accounts:
                user_accounts[account.user_id].append(account)

            logger.info(f"找到 {len(user_accounts)} 个用户需要推送")

            # 为每个用户发送推送
            sent_count = 0
            for user_id, user_account_list in user_accounts.items():
                try:
                    account_ids = [acc.id for acc in user_account_list]
                    message = await notification_service.format_today_logs(
                        user_id, account_ids
                    )

                    if message:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode="Markdown",
                        )
                        sent_count += 1
                        logger.info(f"已发送签到通知给用户 {user_id}")
                    else:
                        logger.debug(f"用户 {user_id} 今日暂无签到记录")

                except Exception as e:
                    logger.error(f"发送签到通知失败 (用户 {user_id}): {e}")

            logger.info(f"推送任务完成: 发送了 {sent_count}/{len(user_accounts)} 个用户")

        except Exception as e:
            logger.error(f"推送任务错误: {e}")

    # 每分钟执行一次
    app.job_queue.run_repeating(
        push_job_callback,
        interval=60,  # 60 秒
        first=10,  # 10 秒后开始（错开签到任务）
    )

    logger.info("推送任务已注册")
