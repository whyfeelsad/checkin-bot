"""定时签到任务"""

import logging

from telegram.ext import Application

from checkin_bot.services.checkin import CheckinService

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

                # 发送通知
                from checkin_bot.tasks.checkin_job import send_checkin_notifications
                await send_checkin_notifications(results, context)

        except Exception as e:
            logger.error(f"签到任务错误: {e}")

    # 每分钟执行一次
    app.job_queue.run_repeating(
        checkin_job_callback,
        interval=60,  # 60 秒
        first=1,  # 1 秒后开始
    )

    logger.info("签到任务已注册")


async def send_checkin_notifications(results, context):
    """发送签到通知"""
    if not results:
        return

    # 按用户分组
    from collections import defaultdict

    user_results = defaultdict(list)
    for result in results:
        # 这里需要从 account 获取 user_id
        # 暂时跳过通知发送，因为需要额外的数据库查询
        pass
