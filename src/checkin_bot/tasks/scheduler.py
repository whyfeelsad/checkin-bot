"""任务调度器"""

import logging

from telegram.ext import Application

from checkin_bot.tasks.checkin_job import register_checkin_job
from checkin_bot.tasks.session_cleanup import register_session_cleanup
from checkin_bot.tasks.cache_cleanup import register_cache_cleanup

logger = logging.getLogger(__name__)


async def register_jobs(app: Application):
    """
    注册所有定时任务

    Args:
        app: Bot 应用实例
    """
    # 注册签到任务（每分钟）
    register_checkin_job(app)

    # 注册会话清理任务（每分钟）
    register_session_cleanup(app)

    # 注册缓存清理任务（每 5 分钟）
    register_cache_cleanup(app)

    logger.info("所有定时任务已注册")
