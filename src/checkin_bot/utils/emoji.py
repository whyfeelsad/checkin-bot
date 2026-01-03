"""Emoji 工具"""

from checkin_bot.config.constants import HOUR_EMOJI, get_hour_emoji
from checkin_bot.config.constants import SiteConfig


def get_site_emoji(site: str) -> str:
    """
    获取站点 Emoji

    Args:
        site: 站点类型

    Returns:
        站点 Emoji
    """
    from checkin_bot.config.constants import SiteType

    config = SiteConfig.get(SiteType(site))
    return config["emoji"]


def get_hour_emoji_str(hour: int) -> str:
    """
    获取小时 Emoji 字符串

    Args:
        hour: 小时（0-23）

    Returns:
        小时 Emoji
    """
    return get_hour_emoji(hour)
