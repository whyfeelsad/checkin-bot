"""用户数据模型"""

from dataclasses import dataclass
from datetime import datetime

from checkin_bot.models.base import BaseEntity


@dataclass
class User(BaseEntity):
    """用户模型"""

    telegram_id: int
    telegram_username: str | None
    first_name: str | None
    last_name: str | None
    fingerprint: str | None  # 有效的浏览器指纹
