"""Bot 应用实例"""

import logging

from telegram.ext import Application, CommandHandler

from checkin_bot.bot.handlers.start import start_handler
from checkin_bot.bot.handlers.account_handlers import (
    add_account_handler,
    my_accounts_handler,
    delete_account_handler,
    update_cookie_handler,
    toggle_mode_handler,
    set_checkin_time_handler,
    set_push_time_handler,
    back_to_menu_handler,
    checkin_now_handler,
    expired_button_handler,
)
from checkin_bot.bot.handlers.checkin import checkin_handler, checkin_status_handler
from checkin_bot.bot.handlers.logs import logs_handler, view_logs_handler
from checkin_bot.bot.handlers.stats import stats_handler
from checkin_bot.bot.handlers.admin import admin_handler
from checkin_bot.bot.handlers.help import help_handler
from checkin_bot.bot.middleware.permission import PermissionMiddleware
from checkin_bot.config.settings import get_settings
from checkin_bot.tasks.scheduler import register_jobs
from checkin_bot.core.database import check_and_init_database

logger = logging.getLogger(__name__)


def create_app() -> Application:
    """创建 Bot 应用实例"""
    settings = get_settings()

    # 创建 Application
    app = Application.builder().token(settings.bot_token).build()

    # 添加权限中间件
    app.add_handler(PermissionMiddleware(), group=-1)

    # 注册命令处理器
    app.add_handler(CommandHandler("start", start_handler))
    # ConversationHandlers 需要先注册，优先级更高
    app.add_handler(delete_account_handler)
    app.add_handler(add_account_handler)
    # 简单的 CallbackQueryHandlers
    app.add_handler(my_accounts_handler)
    app.add_handler(update_cookie_handler)
    app.add_handler(toggle_mode_handler)
    app.add_handler(set_checkin_time_handler)
    app.add_handler(set_push_time_handler)
    app.add_handler(checkin_now_handler)
    app.add_handler(back_to_menu_handler)
    app.add_handler(checkin_handler)
    app.add_handler(checkin_status_handler)
    app.add_handler(logs_handler)
    app.add_handler(view_logs_handler)
    app.add_handler(stats_handler)
    app.add_handler(admin_handler)
    app.add_handler(help_handler)
    # 过期按钮处理器（作为兜底，放在最后）
    app.add_handler(expired_button_handler)

    # 注册错误处理器
    app.add_error_handler(error_handler)

    # post_init 回调：在应用初始化后注册定时任务
    async def post_init(application: Application) -> None:
        # 检查并初始化数据库表
        await check_and_init_database()
        # 注册定时任务
        await register_jobs(application)
        logger.info("所有定时任务已注册")

    app.post_init = post_init

    logger.info("Bot 应用创建成功")

    return app


async def error_handler(update: object, context) -> None:
    """错误处理器"""
    logger.error(f"处理更新时发生异常: {context.error}", exc_info=context.error)
