"""账号更新追踪数据模型"""

from dataclasses import dataclass
from datetime import datetime

from checkin_bot.config.constants import UpdateStatus


@dataclass
class AccountUpdate:
    """账号更新追踪模型"""

    id: int
    account_id: int
    status: UpdateStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
