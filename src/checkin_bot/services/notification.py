"""通知服务"""

import logging
from collections import defaultdict

from checkin_bot.config.constants import SiteConfig, SiteType
from checkin_bot.core.timezone import now, format_datetime
from checkin_bot.repositories.account_repository import AccountRepository

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服务"""

    def __init__(self):
        self.account_repo = AccountRepository()

    async def format_checkin_results(
        self,
        results: list[dict],
    ) -> dict[int, str]:
        """
        格式化签到结果为推送消息

        Args:
            results: 签到结果列表

        Returns:
            {user_id: message} 字典
        """
        logger.info(f"格式化 {len(results)} 个账号的签到结果")

        # 按用户分组
        user_results = defaultdict(list)
        for result in results:
            user_results[result["user_id"]].append(result)

        # 为每个用户生成消息
        messages = {}
        for user_id, user_results_list in user_results.items():
            messages[user_id] = self._format_user_message(user_results_list)

        logger.info(f"为 {len(messages)} 个用户生成通知")
        return messages

    def _format_user_message(self, results: list[dict]) -> str:
        """格式化单个用户的消息"""
        if not results:
            return ""

        # 按站点分组
        site_results = defaultdict(list)
        for result in results:
            site_results[result["site"]].append(result)

        lines = ["📊 签到结果", ""]

        for site, site_results_list in site_results.items():
            config = SiteConfig.get(site)
            lines.append(f"{config['emoji']} **{config['name']}**")

            for result in site_results_list:
                status_emoji = "✅" if result["success"] else "❌"
                username = result.get("username", "未知")

                if result["success"]:
                    delta = result.get("credits_delta", 0)
                    after = result.get("credits_after", 0)
                    lines.append(f"{status_emoji} `{username}`: +{delta} (总计: {after})")
                else:
                    error_msg = result.get("message", "未知错误")
                    lines.append(f"{status_emoji} `{username}`: {error_msg}")

            lines.append("")

        lines.append(f"⏰ {format_datetime(now(), '%Y-%m-%d %H:%M')}")

        return "\n".join(lines)

    async def should_send_notification(self) -> bool:
        """
        判断是否应该发送推送（只在整分钟发送）

        Returns:
            是否发送
        """
        current_second = now().second
        return current_second < 5  # 前 5 秒内

    async def get_pending_notifications(
        self,
        user_id: int,
    ) -> list[dict]:
        """
        获取待推送的签到结果

        Args:
            user_id: 用户 ID

        Returns:
            待推送的结果列表
        """
        # 获取用户的所有账号
        accounts = await self.account_repo.get_by_user(user_id)

        # 这里应该从缓存或临时存储获取最近的签到结果
        # 暂时返回空列表，实际应该从消息队列获取
        return []
