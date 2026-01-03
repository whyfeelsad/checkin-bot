"""账号数据模型"""

from dataclasses import dataclass
from datetime import datetime

from checkin_bot.config.constants import AccountStatus, CheckinMode, SiteType
from checkin_bot.models.base import BaseEntity


@dataclass
class Account(BaseEntity):
    """账号模型"""

    user_id: int
    site: SiteType
    site_username: str
    encrypted_pass: str  # base64 编码的加密密码（包含 nonce）
    cookie: str | None
    checkin_mode: CheckinMode
    status: AccountStatus
    credits: int
    checkin_count: int
    checkin_hour: int | None
    push_hour: int | None
