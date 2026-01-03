"""会话清理任务"""

import logging

from telegram.ext import Application

from checkin_bot.repositories.session_repository import SessionRepository

logger = logging.getLogger(__name__)


def register_session_cleanup(app: Application):
    """
    注册会话清理任务

    Args:
        app: Bot 应用实例
    """
    session_repo = SessionRepository()

    async def cleanup_callback(context):
        """清理回调"""
        try:
            count = await session_repo.clean_expired()
            if count > 0:
                logger.info(f"清理了 {count} 个过期会话")

        except Exception as e:
            logger.error(f"会话清理错误: {e}")

    # 每分钟执行一次
    app.job_queue.run_repeating(
        cleanup_callback,
        interval=60,  # 60 秒
        first=10,  # 10 秒后开始
    )

    logger.info("会话清理任务已注册")
