"""验证工具"""


def validate_credentials(text: str) -> tuple[bool, str, str] | None:
    """
    验证账号密码格式

    Args:
        text: 输入文本

    Returns:
        (valid, username, password) 或 None
    """
    parts = text.strip().split()

    if len(parts) != 2:
        return None

    username, password = parts

    if not username or not password:
        return None

    return True, username, password


def clean_input(text: str) -> str:
    """
    清理输入文本

    Args:
        text: 输入文本

    Returns:
        清理后的文本
    """
    # 去除首尾空格
    text = text.strip()

    # 去除多余空格
    text = " ".join(text.split())

    return text
