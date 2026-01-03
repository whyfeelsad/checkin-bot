"""账号相关键盘"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from checkin_bot.config.constants import CheckinMode, SiteConfig, SiteType
from checkin_bot.config.constants import get_hour_emoji


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """获取返回菜单键盘"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]
    ])


def get_empty_account_keyboard() -> InlineKeyboardMarkup:
    """获取空账号状态键盘（添加账号 + 返回菜单）"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 添加账号", callback_data="add_account"),
            InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu"),
        ]
    ])


def get_site_selection_keyboard() -> InlineKeyboardMarkup:
    """获取站点选择键盘"""
    buttons = [
        [
            InlineKeyboardButton(
                f"{SiteConfig.NODESEEK['emoji']} {SiteConfig.NODESEEK['name']}",
                callback_data=f"site_{SiteType.NODESEEK.value}",
            ),
            InlineKeyboardButton(
                f"{SiteConfig.DEEPFLOOD['emoji']} {SiteConfig.DEEPFLOOD['name']}",
                callback_data=f"site_{SiteType.DEEPFLOOD.value}",
            ),
        ],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cancel")],
    ]

    return InlineKeyboardMarkup(buttons)


def get_mode_selection_keyboard() -> InlineKeyboardMarkup:
    """获取签到模式选择键盘"""
    buttons = [
        [
            InlineKeyboardButton(
                "📌 鸡腿 x 5",
                callback_data=f"mode_{CheckinMode.FIXED.value}",
            ),
            InlineKeyboardButton(
                "🎲 试试手气",
                callback_data=f"mode_{CheckinMode.RANDOM.value}",
            ),
        ],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cancel")],
    ]

    return InlineKeyboardMarkup(buttons)


def get_account_list_keyboard(accounts: list, update_status: dict[int, str] | None = None) -> InlineKeyboardMarkup:
    """
    获取账号列表键盘

    Args:
        accounts: 账号列表
        update_status: 更新状态字典 {account_id: status}，status 可为 'updating' 或 'completed'

    Returns:
        账号列表键盘
    """
    buttons = []

    for account in accounts:
        config = SiteConfig.get(account.site)

        # 第一行：账号信息（点击进入删除确认）
        row_1 = [
            InlineKeyboardButton(
                f"👤 {account.site_username} • 🌐 {config['name']} • 🍗 x {account.credits}",
                callback_data=f"delete_{account.id}",
            )
        ]

        # 第二行：操作按钮
        # 模式切换按钮
        mode_button_text = "📌 固定" if account.checkin_mode == CheckinMode.FIXED else "🎲 随机"
        # 更新按钮状态
        update_button_text = "🍪 更新"
        if update_status and account.id in update_status:
            if update_status[account.id] == "updating":
                update_button_text = "⏳ 更新中"
            elif update_status[account.id] == "completed":
                update_button_text = "✔️ 完成"
            elif update_status[account.id] == "failed":
                update_button_text = "✖️ 失败"

        row_2 = [
            InlineKeyboardButton(
                mode_button_text,
                callback_data=f"toggle_mode_{account.id}",
            ),
            InlineKeyboardButton(
                update_button_text,
                callback_data=f"update_cookie_{account.id}",
            ),
            InlineKeyboardButton(
                f"{get_hour_emoji(account.checkin_hour) if account.checkin_hour else '🕐'} 签到",
                callback_data=f"set_checkin_{account.id}_time",
            ),
            InlineKeyboardButton(
                f"{get_hour_emoji(account.push_hour) if account.push_hour else '🕐'} 推送",
                callback_data=f"set_push_{account.id}_time",
            ),
        ]

        buttons.append(row_1)
        buttons.append(row_2)

    # 返回菜单按钮
    buttons.append([InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")])

    return InlineKeyboardMarkup(buttons)


def get_confirm_delete_keyboard(account_id: int, username: str | None = None, site_name: str | None = None) -> InlineKeyboardMarkup:
    """
    获取确认删除键盘

    Args:
        account_id: 账号 ID
        username: 账号用户名（可选，用于显示详情）
        site_name: 站点名称（可选，用于显示详情）

    Returns:
        确认删除键盘
    """
    buttons = [
        [
            InlineKeyboardButton(
                "✔️ 确定",
                callback_data=f"confirm_delete_{account_id}",
            ),
            InlineKeyboardButton(
                "✖️ 取消",
                callback_data="back_to_my_accounts",
            ),
        ],
    ]

    return InlineKeyboardMarkup(buttons)


def get_delete_confirm_message(username: str, site_name: str) -> str:
    """
    获取删除确认消息

    Args:
        username: 账号用户名
        site_name: 站点名称

    Returns:
        删除确认消息
    """
    return f"""⚠️ 确认移除账号

👤 账号：{username}
🌐 站点：{site_name}

‼️ 此操作不可撤销！"""


def get_time_picker_keyboard(account_id: int, is_checkin: bool = True) -> InlineKeyboardMarkup:
    """
    获取时间选择器键盘

    Args:
        account_id: 账号 ID
        is_checkin: 是否为签到时间（True）或推送时间（False）

    Returns:
        时间选择器键盘
    """
    prefix = "checkin" if is_checkin else "push"
    buttons = []

    # 每行 6 个小时（0-23）
    for row_start in range(0, 24, 6):
        row = []
        for hour in range(row_start, row_start + 6):
            emoji = get_hour_emoji(hour)
            row.append(
                InlineKeyboardButton(
                    f"{emoji}",
                    callback_data=f"set_{prefix}_{account_id}_{hour}",
                )
            )
        buttons.append(row)

    # 取消按钮
    buttons.append([InlineKeyboardButton("🔙 返回菜单", callback_data="cancel")])

    return InlineKeyboardMarkup(buttons)


def get_retry_keyboard(retry_count: int, max_retries: int = 3) -> InlineKeyboardMarkup:
    """
    获取重试键盘

    Args:
        retry_count: 当前重试次数
        max_retries: 最大重试次数

    Returns:
        重试键盘
    """
    remaining = max_retries - retry_count
    buttons = [
        [
            InlineKeyboardButton(
                f"🔄 重试 ({remaining}/{max_retries})",
                callback_data="retry_login",
            ),
            InlineKeyboardButton(
                "🔙 返回菜单",
                callback_data="back_to_menu",
            ),
        ]
    ]

    return InlineKeyboardMarkup(buttons)


def get_account_added_keyboard() -> InlineKeyboardMarkup:
    """
    获取账号添加成功后的键盘

    Returns:
        账号添加成功键盘
    """
    buttons = [
        [
            InlineKeyboardButton(
                "🚀 立即签到",
                callback_data="checkin_now",
            ),
            InlineKeyboardButton(
                "📥 添加账号",
                callback_data="add_account",
            ),
        ],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")],
    ]

    return InlineKeyboardMarkup(buttons)

