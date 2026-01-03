"""时段工具"""

from datetime import datetime, timedelta

from checkin_bot.core.timezone import now as get_now


def calculate_slot(dt: datetime) -> int:
    """
    计算时间段（每小时 5 个时段，每个 12 分钟）

    Args:
        dt: 日期时间

    Returns:
        时间段（0-4）
    """
    return dt.minute // 12


def get_used_slots(
    log_times: list[datetime],
    days: int = 4,
) -> list[tuple[int, int]]:
    """
    获取已使用的时间段

    Args:
        log_times: 签到时间列表
        days: 天数

    Returns:
        已使用的时间段列表 [(hour, slot), ...]
    """
    cutoff = get_now() - timedelta(days=days)

    used = []
    for log_time in log_times:
        if log_time > cutoff:
            hour = log_time.hour
            slot = calculate_slot(log_time)
            used.append((hour, slot))

    return used


def get_available_slots(
    used_slots: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """
    获取可用的时间段

    Args:
        used_slots: 已使用的时间段列表

    Returns:
        可用的时间段列表 [(hour, slot), ...]
    """
    all_slots = []

    # 生成所有可能的时间段（24 小时 * 5 时段）
    for hour in range(24):
        for slot in range(5):
            all_slots.append((hour, slot))

    # 过滤已使用的
    available = [slot for slot in all_slots if slot not in used_slots]

    return available
