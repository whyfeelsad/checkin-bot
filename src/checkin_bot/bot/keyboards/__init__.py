"""Bot 键盘模块"""

from checkin_bot.bot.keyboards.main_menu import get_main_menu_keyboard
from checkin_bot.bot.keyboards.account import (
    get_site_selection_keyboard,
    get_mode_selection_keyboard,
    get_account_list_keyboard,
    get_confirm_delete_keyboard,
    get_delete_confirm_message,
    get_time_picker_keyboard,
)
from checkin_bot.bot.keyboards.checkin import get_checkin_keyboard
from checkin_bot.bot.keyboards.logs import get_logs_keyboard
from checkin_bot.bot.keyboards.confirm import get_confirm_keyboard

__all__ = [
    "get_main_menu_keyboard",
    "get_site_selection_keyboard",
    "get_mode_selection_keyboard",
    "get_account_list_keyboard",
    "get_confirm_delete_keyboard",
    "get_delete_confirm_message",
    "get_time_picker_keyboard",
    "get_checkin_keyboard",
    "get_logs_keyboard",
    "get_confirm_keyboard",
]
