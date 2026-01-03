"""缓存清理任务"""

import logging

from telegram.ext import Application

from checkin_bot.core.cache import get_cache

logger = logging.getLogger(__name__)


def register_cache_cleanup(app: Application):
    """
    注册缓存清理任务

    Args:
        app: Bot 应用实例
    """
    cache = get_cache()

    async def cleanup_callback(context):
        """清理回调"""
        try:
            await cache.clear_expired()
            logger.debug("权限缓存已清理")

        except Exception as e:
            logger.error(f"缓存清理错误: {e}")

    # 每 5 分钟执行一次
    app.job_queue.run_repeating(
        cleanup_callback,
        interval=300,  # 300 秒 (5 分钟)
        first=30,  # 30 秒后开始
    )

    logger.info("缓存清理任务已注册")
