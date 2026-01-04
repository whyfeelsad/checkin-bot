"""确认对话框键盘"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_confirm_keyboard(
    action: str,
    confirm_data: str,
    cancel_data: str = "cancel",
) -> InlineKeyboardMarkup:
    """
    获取确认对话框键盘

    Args:
        action: 操作描述
        confirm_data: 确认按钮的 callback_data
        cancel_data: 取消按钮的 callback_data

    Returns:
        确认对话框键盘
    """
    buttons = [
        [
            InlineKeyboardButton(f"✔ 确认{action}", callback_data=confirm_data),
            InlineKeyboardButton("✖ 取消", callback_data=cancel_data),
        ],
    ]

    return InlineKeyboardMarkup(buttons)
