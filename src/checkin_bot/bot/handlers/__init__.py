"""Bot 处理器模块"""

from checkin_bot.bot.handlers.start import start_handler
from checkin_bot.bot.handlers.account_handlers import (
    add_account_handler,
    my_accounts_handler,
    delete_account_handler,
)
from checkin_bot.bot.handlers.checkin import checkin_handler, checkin_status_handler
from checkin_bot.bot.handlers.logs import logs_handler
from checkin_bot.bot.handlers.stats import stats_handler
from checkin_bot.bot.handlers.admin import admin_handler
from checkin_bot.bot.handlers.help import help_handler

__all__ = [
    "start_handler",
    "add_account_handler",
    "my_accounts_handler",
    "delete_account_handler",
    "checkin_handler",
    "checkin_status_handler",
    "logs_handler",
    "stats_handler",
    "admin_handler",
    "help_handler",
]
