"""主菜单键盘"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    获取主菜单键盘

    Args:
        is_admin: 是否为管理员

    Returns:
        主菜单键盘
    """
    buttons = []

    # 管理员在顶部显示后台管理按钮
    if is_admin:
        buttons.append([
            InlineKeyboardButton("🛡 后台管理", callback_data="admin"),
        ])

    # 第一行：添加账号、我的账号
    buttons.append([
        InlineKeyboardButton("📥 添加账号", callback_data="add_account"),
        InlineKeyboardButton("💳 我的账号", callback_data="my_accounts"),
    ])
    # 第二行：立即签到、签到日志
    buttons.append([
        InlineKeyboardButton("🚀 立即签到", callback_data="checkin"),
        InlineKeyboardButton("📖 签到日志", callback_data="logs"),
    ])
    # 第三行：数据统计、查看帮助
    buttons.append([
        InlineKeyboardButton("📈 数据统计", callback_data="stats"),
        InlineKeyboardButton("💡 查看帮助", callback_data="help"),
    ])

    return InlineKeyboardMarkup(buttons)
