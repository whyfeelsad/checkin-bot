"""日志键盘"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from checkin_bot.config.constants import SiteConfig


def get_logs_keyboard(accounts: list) -> InlineKeyboardMarkup:
    """
    获取日志键盘

    Args:
        accounts: 账号列表

    Returns:
        日志键盘
    """
    buttons = []

    for account in accounts:
        config = SiteConfig.get(account.site)
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{config['emoji']} {account.site_username}",
                    callback_data=f"view_logs_{account.id}",
                )
            ]
        )

    # 返回菜单按钮
    buttons.append([InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")])

    return InlineKeyboardMarkup(buttons)
