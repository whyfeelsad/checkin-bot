"""格式化工具"""

from checkin_bot.config.constants import SiteConfig


def format_account_card(account) -> str:
    """
    格式化账号卡片

    Args:
        account: 账号模型

    Returns:
        格式化的账号卡片字符串
    """
    config = SiteConfig.get(account.site)

    lines = [
        f"{config['emoji']} **{config['name']}**",
        f"👤 用户名: `{account.site_username}`",
        f"💰 鸡腿数: **{account.credits}**",
        f"✅ 签到次数: **{account.checkin_count}**",
        f"🎲 模式: {'随机' if account.checkin_mode.value == 'random' else '固定'}",
    ]

    return "\n".join(lines)


def format_checkin_result(result: dict) -> str:
    """
    格式化签到结果

    Args:
        result: 签到结果字典

    Returns:
        格式化的签到结果字符串
    """
    if result["success"]:
        delta = result.get("credits_delta", 0)
        after = result.get("credits_after", 0)
        message = result.get("message", "")

        # 检查是否为重复签到
        if "已完成签到" in message or "已经签到" in message or "重复" in message:
            return (
                f"🔔 今日已签到，请勿重复操作！\n"
                f"📈 鸡腿变化: +{delta}，当前鸡腿：{after}"
            )

        return (
            f"🎉 签到成功！\n"
            f"📈 鸡腿变化: +{delta}\n"
            f"💰 当前鸡腿: {after}"
        )
    else:
        return f"❌ 签到失败\n{result.get('message', '未知错误')}"


def format_stats_summary(accounts: list) -> str:
    """
    格式化统计摘要

    Args:
        accounts: 账号列表

    Returns:
        格式化的统计摘要字符串
    """
    total = len(accounts)
    total_checkins = sum(acc.checkin_count for acc in accounts)
    total_credits = sum(acc.credits for acc in accounts)

    return (
        f"📊 **数据统计**\n\n"
        f"📝 总账号数: {total}\n"
        f"✅ 总签到次数: {total_checkins}\n"
        f"💰 总鸡腿数: {total_credits}"
    )
