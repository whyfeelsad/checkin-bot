"""站点适配器基类"""

from abc import ABC, abstractmethod

from checkin_bot.config.constants import CheckinStatus, SiteType


class SiteAdapter(ABC):
    """站点适配器基类"""

    @abstractmethod
    async def checkin(self, account) -> dict:
        """
        执行签到

        Args:
            account: 账号模型

        Returns:
            签到结果字典，包含:
            - success (bool): 是否成功
            - status (CheckinStatus): 状态
            - message (str | None): 消息
            - credits_delta (int): 鸡腿变化
            - credits_before (int | None): 签到前鸡腿
            - credits_after (int | None): 签到后鸡腿
            - error_code (str | None): 错误码
            - username (str): 站点用户名
            - site (SiteType): 站点类型
        """
        pass

    @abstractmethod
    async def get_credits(self, account) -> int | None:
        """
        获取鸡腿数

        Args:
            account: 账号模型

        Returns:
            鸡腿数，失败返回 None
        """
        pass
