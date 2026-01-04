"""Check-in service"""

import logging
import random
from datetime import datetime, timedelta, date

from checkin_bot.config.constants import CheckinMode, CheckinStatus, SiteType
from checkin_bot.core.timezone import now, to_local
from checkin_bot.repositories.account_repository import AccountRepository
from checkin_bot.repositories.checkin_log_repository import CheckinLogRepository
from checkin_bot.sites.base import SiteAdapter
from checkin_bot.sites.nodeseek import NodeSeekAdapter
from checkin_bot.sites.deepflood import DeepFloodAdapter

logger = logging.getLogger(__name__)


class CheckinService:
    """Check-in service"""

    def __init__(self):
        self.account_repo = AccountRepository()
        self.log_repo = CheckinLogRepository()
        # Cache for today's check-in status: {(account_id, date): count}
        self._today_cache: dict[tuple[int, date], int] = {}
        self._cache_date: date | None = None

        # 站点适配器映射
        self._adapters = {
            SiteType.NODESEEK: NodeSeekAdapter(),
            SiteType.DEEPFLOOD: DeepFloodAdapter(),
        }

        # 独立的随机数生成器，避免影响全局状态
        self._slot_random = random.Random()

    def _get_adapter(self, site: SiteType) -> SiteAdapter:
        """获取站点适配器"""
        return self._adapters[site]

    async def manual_checkin(self, account_id: int) -> dict:
        """
        手动签到

        Args:
            account_id: 账号 ID

        Returns:
            签到结果字典
        """
        logger.info(f"手动签到请求: 账号 ID={account_id}")

        account = await self.account_repo.get_by_id(account_id)
        if not account:
            logger.warning(f"签到账号不存在: ID={account_id}")
            return {
                "success": False,
                "message": "账号不存在",
                "status": CheckinStatus.FAILED,
            }

        logger.info(f"开始手动签到: 站点 {account.site.value} 用户 {account.site_username}")
        return await self._do_checkin(account, is_manual=True)

    async def _do_checkin(self, account, is_manual: bool = False) -> dict:
        """
        Execute check-in (internal method)

        Args:
            account: Account object
            is_manual: Whether this is a manual check-in

        Returns:
            Check-in result dictionary
        """
        checkin_type = "Manual" if is_manual else "Auto"
        today = date.today()

        # Clear cache if date has changed
        if self._cache_date != today:
            self._today_cache.clear()
            self._cache_date = today

        # Check today's check-in status with cache
        cache_key = (account.id, today)
        if cache_key not in self._today_cache:
            self._today_cache[cache_key] = await self.log_repo.get_today_success_count(account.id)

        if self._today_cache[cache_key] > 0:
            logger.info(f"{checkin_type}签到跳过: 站点 {account.site.value} 用户 {account.site_username} (今日已签到)")
            # 获取今天成功签到获得的鸡腿数
            today_delta = await self.log_repo.get_today_success_delta(account.id)
            return {
                "success": True,
                "status": CheckinStatus.SUCCESS,
                "message": "今日已签到",
                "credits_delta": today_delta,
                "credits_before": account.credits,
                "credits_after": account.credits,
                "username": account.site_username,
                "site": account.site,
                "user_id": account.user_id,
            }

        adapter = self._get_adapter(account.site)

        try:
            result = await adapter.checkin(account)

            # 记录日志
            await self.log_repo.create(
                account_id=account.id,
                site=account.site,
                status=result["status"],
                message=result.get("message"),
                credits_delta=result.get("credits_delta", 0),
                credits_before=result.get("credits_before"),
                credits_after=result.get("credits_after"),
                error_code=result.get("error_code"),
            )

            # 更新账号鸡腿数
            if result["success"] and result.get("credits_after") is not None:
                await self.account_repo.update_credits(
                    account.id,
                    result["credits_after"],
                    checkin_count_increment=1 if result["success"] else 0,
                )

            if result["success"]:
                logger.info(f"{checkin_type}签到成功: 站点 {account.site.value} 用户 {account.site_username} +{result.get('credits_delta', 0)} 鸡腿")
            else:
                logger.warning(f"{checkin_type}签到失败: 站点 {account.site.value} 用户 {account.site_username} - {result.get('message')}")

            # 添加 user_id 到结果中
            result["user_id"] = account.user_id

            return result

        except Exception as e:
            logger.error(f"{checkin_type}签到异常: 站点 {account.site.value} 用户 {account.site_username} - {e}", exc_info=True)
            return {
                "success": False,
                "message": f"签到异常: {str(e)}",
                "status": CheckinStatus.FAILED,
                "user_id": account.user_id,
            }

    async def scheduled_checkin(self) -> list[dict]:
        """
        定时签到（每分钟调用）

        Returns:
            签到结果列表
        """
        current_time = now()
        current_hour = current_time.hour
        current_minute = current_time.minute

        # 计算时间段（每小时 5 个时段，每个 12 分钟）
        slot = current_minute // 12

        logger.debug(f"定时签到检查 {current_time.strftime('%H:%M')}: 小时={current_hour}, 时段={slot}")

        # 获取需要签到的账号（固定时间或随机时间）
        accounts = await self._get_accounts_to_checkin(current_hour, slot)

        if not accounts:
            logger.debug("无需签到的账号")
            return []

        logger.info(f"找到 {len(accounts)} 个账号需要签到")

        results = []
        for account in accounts:
            try:
                # 防重复检测
                if await self._should_checkin(account, current_time):
                    # 在时段内随机偏移
                    delay = random.randint(0, 60) + random.randint(0, 59)
                    # 实际应该用任务队列延迟执行，这里简化为直接执行
                    logger.debug(f"正在签到: 站点 {account.site.value} 用户 {account.site_username}")
                    result = await self._do_checkin(account, is_manual=False)
                    results.append(result)
                else:
                    logger.debug(f"跳过签到: 站点 {account.site.value} 用户 {account.site_username} (已签到)")

            except Exception as e:
                logger.error(f"定时签到错误: 账号 {account.id} - {e}", exc_info=True)

        logger.info(f"定时签到完成: 处理了 {len(results)} 个账号")
        return results

    async def _get_accounts_to_checkin(
        self,
        hour: int,
        slot: int,
    ) -> list:
        """获取需要签到的账号"""
        # 只获取 checkin_hour 等于当前小时的账号
        return await self.account_repo.get_by_checkin_time(hour)

    def _get_random_slot(self, account) -> int:
        """计算随机签到时段"""
        # 使用账号 ID 作为种子确保一致性
        # 创建独立的随机数生成器实例，避免影响全局状态
        rng = random.Random(account.id)
        slot = rng.randint(0, 4)  # 0-4 共 5 个时段
        return slot

    async def _should_checkin(
        self,
        account,
        current_time: datetime,
    ) -> bool:
        """防重复检测"""
        # 检查最近 4 天是否已签到
        recent_slots = await self.log_repo.get_recent_slots(account.id, days=4)

        current_slot = (current_time.hour, current_time.minute // 12)

        for log_time in recent_slots:
            # 数据库返回的是 UTC 时间，需要转换为本地时区再比较
            local_log_time = to_local(log_time)
            log_slot = (local_log_time.hour, local_log_time.minute // 12)
            if log_slot == current_slot:
                return False

        return True
