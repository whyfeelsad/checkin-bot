"""时区处理模块"""

from datetime import datetime
from zoneinfo import ZoneInfo

from checkin_bot.config.settings import get_settings


def get_timezone():
    """获取配置的时区"""
    settings = get_settings()
    return ZoneInfo(settings.timezone)


def now() -> datetime:
    """获取当前时区的当前时间（返回 naive datetime）"""
    # 获取当前时区的当前时间，然后去掉时区信息
    return datetime.now(get_timezone()).replace(tzinfo=None)


def to_local(dt: datetime) -> datetime:
    """将 datetime 转换为本地时区"""
    if dt.tzinfo is None:
        # naive datetime，假设已经是本地时间，直接添加时区信息
        return dt.replace(tzinfo=get_timezone())
    return dt.astimezone(get_timezone())


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化 datetime 为本地时区字符串"""
    local_dt = to_local(dt)
    return local_dt.strftime(fmt)
