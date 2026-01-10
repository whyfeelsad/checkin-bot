"""Check-in service"""

import asyncio
import logging
import random
from datetime import date
from datetime import datetime as dt

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
        # Cache for today's check-in status: {account_id: bool}
        self._today_cache: dict[int, bool] = {}
        self._cache_date: date | None = None

        # 站点适配器映射
        self._adapters = {
            SiteType.NODESEEK: NodeSeekAdapter(),
            SiteType.DEEPFLOOD: DeepFloodAdapter(),
        }

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
                "user_id": None,
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
        if account.id not in self._today_cache:
            self._today_cache[account.id] = await self.log_repo.get_today_success_count(account.id) > 0

        if self._today_cache[account.id]:
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

            # 检查今日是否已有成功日志
            has_today_log = await self.log_repo.get_today_success_count(account.id) > 0
            should_increment = result["success"] and not has_today_log

            # 只在第一次成功签到时记录日志
            if result["success"]:
                if not has_today_log:
                    # 第一次成功签到，记录日志
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
                    logger.info(f"{checkin_type}签到成功: 站点 {account.site.value} 用户 {account.site_username} +{result.get('credits_delta', 0)} 鸡腿")
                else:
                    logger.info(f"{checkin_type}签到成功: 站点 {account.site.value} 用户 {account.site_username} +{result.get('credits_delta', 0)} 鸡腿 (今日已记录)")
            else:
                # 签到失败，记录失败日志
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
                logger.warning(f"{checkin_type}签到失败: 站点 {account.site.value} 用户 {account.site_username} - {result.get('message')}")

            # 更新账号鸡腿数和签到次数（只在第一次成功时增加计数）
            if result["success"] and result.get("credits_after") is not None:
                await self.account_repo.update_credits(
                    account.id,
                    result["credits_after"],
                    checkin_count_increment=1 if should_increment else 0,
                )

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
        slot = current_minute // 12 + 1  # 时段从 1 开始
        current_slot = (current_hour, slot)

        logger.info(f"[自动签到] 定时签到检查 {current_time.strftime('%H:%M')}: 小时={current_hour}, 时段={slot}")

        # 获取需要签到的账号
        accounts = await self.account_repo.get_by_checkin_time(current_hour)

        if not accounts:
            return []

        # 并发执行签到
        results = await self._execute_checkins_concurrently(accounts, current_time)

        logger.info(f"[自动签到] 定时签到完成: 处理了 {len(results)} 个账号")
        return results

    async def _execute_checkins_concurrently(
        self,
        accounts: list,
        current_time: dt,
    ) -> list[dict]:
        """
        并发执行签到

        Args:
            accounts: 账号列表
            current_time: 当前时间

        Returns:
            签到结果列表
        """
        async def checkin_with_catch(account):
            try:
                # 计算可用时段
                available_slots = await self._get_available_slots(account, current_time)

                logger.info(f"[自动签到] 账号 {account.site_username} • {account.site.value} 可用时段: {available_slots}")

                # 防重复检测
                should_checkin = await self._should_checkin(account, current_time)

                if should_checkin:
                    logger.info(f"[自动签到] 正在签到: {account.site_username} • {account.site.value}")
                    return await self._do_checkin(account, is_manual=False)
                else:
                    logger.info(f"[自动签到] 跳过签到: {account.site_username} • {account.site.value} (该时段已签到)")
                    return None
            except Exception as e:
                logger.error(f"[自动签到] 签到错误: 账号 {account.id} ({account.site_username}) - {e}", exc_info=True)
                return None

        # 并发执行所有签到，限制并发数为 5
        tasks = [checkin_with_catch(account) for account in accounts]
        results_list = await asyncio.gather(*tasks, return_exceptions=False)

        # 过滤掉 None 结果
        return [r for r in results_list if r is not None]

    async def _get_available_slots(self, account, current_time: dt) -> list[int]:
        """
        计算当前小时的可用时段

        Returns:
            可用时段列表，如 [1, 2, 4, 5]
        """
        # 获取历史签到时段
        recent_slots = await self.log_repo.get_recent_slots(account.id, days=4)

        # 当前小时的所有时段（1-5）
        all_slots = [1, 2, 3, 4, 5]

        # 找出已签到的时段
        used_slots = set()
        for log_time in recent_slots:
            # 只检查当前小时的记录
            if log_time.hour == current_time.hour:
                log_slot = log_time.minute // 12 + 1  # 时段从 1 开始
                used_slots.add(log_slot)

        # 可用时段 = 所有时段 - 已签到时段
        available_slots = [s for s in all_slots if s not in used_slots]

        return available_slots

    async def _should_checkin(
        self,
        account,
        current_time: dt,
    ) -> bool:
        """
        防重复检测

        检查最近 4 天是否在当前时段已签到（防止重复签到）
        """
        # 检查最近 4 天是否已签到
        recent_slots = await self.log_repo.get_recent_slots(account.id, days=4)

        current_slot = (current_time.hour, current_time.minute // 12 + 1)  # 时段从 1 开始

        for log_time in recent_slots:
            # 数据库返回的 TIMESTAMP 是 naive datetime（本地时区）
            # 因为数据库连接已设置时区，所以直接使用即可
            log_slot = (log_time.hour, log_time.minute // 12 + 1)  # 时段从 1 开始
            if log_slot == current_slot:
                return False

        return True
