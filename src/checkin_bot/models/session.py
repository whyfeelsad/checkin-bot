"""会话数据模型"""

from dataclasses import dataclass
from datetime import datetime

from checkin_bot.config.constants import SessionState
from checkin_bot.models.base import BaseEntity


@dataclass
class Session(BaseEntity):
    """会话模型"""

    telegram_id: int
    state: SessionState
    data: dict
    expires_at: datetime
