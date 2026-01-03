"""签到日志数据模型"""

from dataclasses import dataclass
from datetime import datetime

from checkin_bot.config.constants import CheckinStatus, SiteType


@dataclass
class CheckinLog:
    """签到日志模型"""

    id: int
    account_id: int
    site: SiteType
    status: CheckinStatus
    message: str | None
    credits_delta: int
    credits_before: int | None
    credits_after: int | None
    error_code: str | None
    executed_at: datetime
