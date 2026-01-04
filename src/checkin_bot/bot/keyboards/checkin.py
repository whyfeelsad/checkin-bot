"""签到键盘"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from checkin_bot.config.constants import SiteConfig


def get_checkin_keyboard(accounts: list) -> InlineKeyboardMarkup:
    """
    获取签到键盘

    Args:
        accounts: 账号列表

    Returns:
        签到键盘
    """
    buttons = []

    for account in accounts:
        config = SiteConfig.get(account.site)
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{config['name']} • {account.site_username} • 🍗 x {account.credits}",
                    callback_data=f"checkin_{account.id}",
                )
            ]
        )

    # 批量签到和返回菜单按钮（同一行）
    buttons.append([
        InlineKeyboardButton("📋 批量签到", callback_data="checkin_all"),
        InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu"),
    ])

    return InlineKeyboardMarkup(buttons)


def get_back_to_checkin_list_keyboard() -> InlineKeyboardMarkup:
    """
    获取返回签到列表键盘（签到完成后使用）

    Returns:
        返回签到列表键盘
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 返回上一页", callback_data="checkin")]
    ])
