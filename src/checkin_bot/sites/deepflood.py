"""DeepFlood 站点适配器"""

import logging

from curl_cffi.requests import AsyncSession, errors

from checkin_bot.config.constants import (
    DEFAULT_HTTP_HEADERS,
    DEFAULT_TIMEOUT,
    CheckinMode,
    CheckinStatus,
    SiteConfig,
    SiteType,
)
from checkin_bot.config.settings import get_settings
from checkin_bot.sites.base import SiteAdapter

logger = logging.getLogger(__name__)


class DeepFloodAdapter(SiteAdapter):
    """DeepFlood 站点适配器"""

    def __init__(self):
        self.settings = get_settings()
        self.config = SiteConfig.get(SiteType.DEEPFLOOD)

    async def checkin(self, account) -> dict:
        """执行签到"""
        logger.debug(f"开始 DeepFlood 签到: 站点 deepflood 用户 {account.site_username}")

        session = AsyncSession(impersonate=self.settings.impersonate_browser)

        try:
            # 1. 获取当前积分（签到前）
            credits_before = await self._fetch_credits(account.cookie, session)
            logger.debug(f"DeepFlood 签到前积分: 站点 deepflood 用户 {account.site_username} 积分={credits_before}")

            # 2. 发送签到请求（需要 random 参数）
            headers = DEFAULT_HTTP_HEADERS.copy()
            headers.update({
                "Cookie": account.cookie,
                "origin": self.config["base_url"],
                "referer": f"{self.config['base_url']}/board",
                "Content-Type": "application/json",
            })

            # DeepFlood 签到 API random 参数根据 checkin_mode 决定
            random_param = "true" if account.checkin_mode == CheckinMode.RANDOM else "false"
            url = f"{self.config['api_base']}{self.config['checkin_api']}?random={random_param}"
            response = await session.post(url, headers=headers, timeout=DEFAULT_TIMEOUT)

            logger.debug(f"DeepFlood 签到响应: status={response.status_code}")

            if response.status_code == 403:
                logger.warning(f"DeepFlood 签到被拦截: 站点 deepflood 用户 {account.site_username} - 403 Forbidden")
                return {
                    "success": False,
                    "status": CheckinStatus.FAILED,
                    "message": "被 Cloudflare 拦截，请更新 Cookie",
                    "credits_delta": 0,
                    "credits_before": credits_before,
                    "credits_after": credits_before,
                    "error_code": "blocked",
                    "username": account.site_username,
                    "site": SiteType.DEEPFLOOD,
                }

            data = response.json()
            msg = data.get("message", "")

            # 判断签到结果（参考 deepflood_sign.py）
            if "鸡腿" in msg or data.get("success"):
                # 签到成功，获取签到后积分
                credits_after = await self._fetch_credits(account.cookie, session)
                credits_delta = (credits_after or 0) - (credits_before or 0)

                logger.info(f"DeepFlood 签到成功: 站点 deepflood 用户 {account.site_username} +{credits_delta} 鸡腿")
                return {
                    "success": True,
                    "status": CheckinStatus.SUCCESS,
                    "message": msg,
                    "credits_delta": credits_delta,
                    "credits_before": credits_before,
                    "credits_after": credits_after,
                    "username": account.site_username,
                    "site": SiteType.DEEPFLOOD,
                }
            elif "已完成签到" in msg:
                logger.info(f"DeepFlood 今日已签到: 站点 deepflood 用户 {account.site_username}")
                # 获取当前积分和今日鸡腿变化
                credits_after, today_delta = await self._fetch_credits_and_delta(account.cookie, session)
                if credits_after is None:
                    credits_after = credits_before
                return {
                    "success": True,
                    "status": CheckinStatus.SUCCESS,
                    "message": msg,
                    "credits_delta": today_delta,
                    "credits_before": credits_before,
                    "credits_after": credits_after,
                    "username": account.site_username,
                    "site": SiteType.DEEPFLOOD,
                }
            elif data.get("status") == 404:
                logger.warning(f"DeepFlood Cookie 无效: 站点 deepflood 用户 {account.site_username} - 404")
                return {
                    "success": False,
                    "status": CheckinStatus.FAILED,
                    "message": "Cookie 无效",
                    "credits_delta": 0,
                    "credits_before": None,
                    "credits_after": None,
                    "error_code": "invalid_cookie",
                    "username": account.site_username,
                    "site": SiteType.DEEPFLOOD,
                }
            else:
                logger.warning(f"DeepFlood 签到失败: 站点 deepflood 用户 {account.site_username} - {msg}")
                return {
                    "success": False,
                    "status": CheckinStatus.FAILED,
                    "message": msg,
                    "credits_delta": 0,
                    "credits_before": credits_before,
                    "credits_after": credits_before,
                    "error_code": "checkin_failed",
                    "username": account.site_username,
                    "site": SiteType.DEEPFLOOD,
                }

        except Exception as e:
            logger.error(f"DeepFlood 签到异常: 站点 deepflood 用户 {account.site_username} - {e}", exc_info=True)
            return {
                "success": False,
                "status": CheckinStatus.FAILED,
                "message": f"签到异常: {str(e)}",
                "credits_delta": 0,
                "credits_before": None,
                "credits_after": None,
                "error_code": "exception",
                "username": account.site_username,
                "site": SiteType.DEEPFLOOD,
            }

        finally:
            await session.close()

    async def get_credits(self, account) -> int | None:
        """获取积分"""
        session = AsyncSession(impersonate=self.settings.impersonate_browser)

        try:
            return await self._fetch_credits(account.cookie, session)

        except (errors.RequestsError, ValueError) as e:
            # 捕获网络请求错误和 JSON 解析错误
            logger.warning(f"获取 {account.site_username} 积分失败: {e}")
            return None

        finally:
            await session.close()

    async def _fetch_credits(
        self,
        cookie: str,
        session: AsyncSession,
    ) -> int | None:
        """获取积分（内部方法）"""
        import asyncio

        headers = DEFAULT_HTTP_HEADERS.copy()
        headers["Cookie"] = cookie
        headers["origin"] = self.config["base_url"]
        headers["referer"] = f"{self.config['base_url']}/board"

        # DeepFlood API: /api/account/credit/page-1 返回历史记录数组
        # 格式: [[amount, balance, description, timestamp], ...]
        # 第一条记录的 balance 就是当前总积分
        url = f"{self.config['api_base']}{self.config['credit_api']}/page-1"

        # 最多重试 3 次
        for attempt in range(3):
            try:
                logger.debug(f"请求 DeepFlood 积分 API (尝试 {attempt + 1}/3): {url}")

                response = await session.get(
                    url,
                    headers=headers,
                    timeout=DEFAULT_TIMEOUT,
                )

                logger.debug(f"DeepFlood API 响应: status={response.status_code}")

                if response.status_code != 200:
                    # 403 可能是 Cloudflare 拦截，重试
                    if response.status_code == 403 and attempt < 2:
                        logger.warning(f"DeepFlood API 返回 403，等待后重试 ({attempt + 1}/3)")
                        await asyncio.sleep(2)
                        continue
                    logger.warning(f"DeepFlood API 请求失败: status={response.status_code}")
                    return None

                try:
                    data = response.json()
                except ValueError:
                    logger.warning(f"DeepFlood API 响应非 JSON 格式: {response.text[:100]}")
                    return None

                logger.debug(f"DeepFlood API JSON: {data}")

                # DeepFlood API 返回格式: {"success": true, "data": [[amount, balance, desc, time], ...]}
                if not data.get("success") or not data.get("data"):
                    logger.warning(f"DeepFlood API 返回失败或无数据: success={data.get('success')}")
                    return None

                records = data["data"]
                if not isinstance(records, list) or len(records) == 0:
                    logger.warning(f"DeepFlood API 记录为空或格式错误: records={records}")
                    return None

                first_record = records[0]
                if not isinstance(first_record, list) or len(first_record) < 2:
                    logger.warning(f"DeepFlood API 记录格式错误: first_record={first_record}")
                    return None

                balance = first_record[1]  # balance 字段在索引 1
                logger.info(f"DeepFlood 获取积分成功: balance={balance}")
                return balance

            except (errors.RequestsError, ValueError) as e:
                # 捕获网络请求错误和 JSON 解析错误
                if attempt < 2:
                    logger.warning(f"获取积分失败，重试 ({attempt + 1}/3): {e}")
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"获取积分失败: {e}")

        return None

    async def _fetch_credits_and_delta(
        self,
        cookie: str,
        session: AsyncSession,
    ) -> tuple[int | None, int]:
        """
        获取积分和今日鸡腿变化（内部方法）

        Returns:
            (balance, today_delta): balance 为当前总积分，today_delta 为今日获得的鸡腿数
        """
        import asyncio
        from datetime import datetime, timedelta
        from checkin_bot.core.timezone import now

        headers = DEFAULT_HTTP_HEADERS.copy()
        headers["Cookie"] = cookie
        headers["origin"] = self.config["base_url"]
        headers["referer"] = f"{self.config['base_url']}/board"

        url = f"{self.config['api_base']}{self.config['credit_api']}/page-1"

        # 最多重试 3 次
        for attempt in range(3):
            try:
                response = await session.get(
                    url,
                    headers=headers,
                    timeout=DEFAULT_TIMEOUT,
                )

                if response.status_code != 200:
                    if response.status_code == 403 and attempt < 2:
                        await asyncio.sleep(2)
                        continue
                    return None, 0

                data = response.json()
                if not data.get("success") or not data.get("data"):
                    return None, 0

                records = data["data"]
                if not isinstance(records, list) or len(records) == 0:
                    return None, 0

                first_record = records[0]
                if not isinstance(first_record, list) or len(first_record) < 4:
                    return None, 0

                balance = first_record[1]
                amount = first_record[0]
                description = first_record[2]

                # 检查第一条记录是否是今天的签到记录
                # 格式: "签到收益5个鸡腿"
                today_delta = 0
                if "签到" in description and "鸡腿" in description:
                    today_delta = amount

                logger.info(f"DeepFlood 获取积分成功: balance={balance}, today_delta={today_delta}")
                return balance, today_delta

            except (errors.RequestsError, ValueError) as e:
                if attempt < 2:
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"获取积分失败: {e}")

        return None, 0
