"""Cloudflyer 验证码解决器"""

import asyncio
import json
import logging
from typing import Callable

from curl_cffi.requests import AsyncSession

from checkin_bot.config.settings import get_settings

logger = logging.getLogger(__name__)


class CloudflyerSolver:
    """Cloudflyer 验证码解决器"""

    def __init__(self):
        settings = get_settings()
        self.api_url = settings.cloudflyer_api_url
        self.api_key = settings.cloudflyer_api_key
        self.max_retries = settings.captcha_max_retries
        self.retry_interval = settings.captcha_retry_interval
        self.impersonate = settings.impersonate_browser
        self.create_task_url = f"{self.api_url}/createTask"
        self.get_result_url = f"{self.api_url}/getTaskResult"

        logger.debug(f"CloudflyerSolver 已初始化: API URL={self.api_url}")

    async def solve(
        self,
        site_url: str,
        sitekey: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str | None:
        """
        解决 Turnstile 验证码

        Args:
            site_url: 站点 URL
            sitekey: Turnstile sitekey
            progress_callback: 进度回调函数 (current, total)

        Returns:
            验证码 token，失败返回 None
        """
        logger.debug(f"开始解决 Turnstile 验证码: site_url={site_url}, sitekey={sitekey}")

        session = AsyncSession(impersonate=self.impersonate)

        try:
            # 1. 创建任务
            payload = {
                "clientKey": self.api_key,
                "type": "Turnstile",
                "url": site_url,
                "siteKey": sitekey,
            }

            logger.debug(f"创建任务: URL={self.create_task_url}")

            response = await session.post(
                self.create_task_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            logger.debug(f"创建任务响应: status={response.status_code}, body={response.text[:500]}")

            if response.status_code != 200:
                logger.warning(f"创建验证码任务失败: HTTP {response.status_code}")
                return None

            data = response.json()
            task_id = data.get("taskId")

            if not task_id:
                logger.warning("验证码服务响应无效: 缺少 taskId")
                return None

            logger.debug(f"任务创建成功: taskId={task_id}")

            # 2. 轮询获取结果
            result_payload = {
                "clientKey": self.api_key,
                "taskId": task_id,
            }

            for attempt in range(1, self.max_retries + 1):
                try:
                    if progress_callback:
                        result = progress_callback(attempt, self.max_retries)
                        if asyncio.iscoroutine(result):
                            await result

                    logger.debug(f"轮询结果: 尝试 {attempt}/{self.max_retries}")

                    result_response = await session.post(
                        self.get_result_url,
                        json=result_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30,
                    )

                    logger.debug(f"获取结果响应: status={result_response.status_code}, body={result_response.text[:500]}")

                    if result_response.status_code == 200:
                        result_data = result_response.json()

                        # 检查任务是否完成
                        if result_data.get("status") == "completed":
                            logger.debug(f"验证码任务完成")

                            result_obj = result_data.get("result", {})
                            response_obj = result_obj.get("response", {})

                            # 处理嵌套结构
                            if isinstance(response_obj, dict) and "token" in response_obj:
                                token = response_obj["token"]
                            else:
                                token = response_obj

                            if token:
                                logger.debug(f"成功获取 token: {token[:20]}...{token[-10:]}")
                                return token
                            else:
                                logger.warning("验证码服务响应无效: 缺少 token")

                    elif result_response.status_code != 200:
                        logger.debug(f"获取结果失败: status={result_response.status_code}")

                except Exception as e:
                    logger.debug(f"轮询结果时发生异常 (尝试 {attempt}): {e}")

                # 最后一次尝试成功则不等待
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_interval)

            logger.debug(f"验证码解决超时: 已尝试 {self.max_retries} 次")
            return None

        except Exception as e:
            logger.debug(f"验证码解决异常: {e}")
            return None
        finally:
            await session.close()

    async def validate_token(self, token: str) -> bool:
        """
        验证 token 有效性

        Args:
            token: 验证码 token

        Returns:
            是否有效
        """
        # Cloudflyer API 没有 validate 端点，这里返回 True 表示信任 token
        # 实际验证应该在站点登录时进行
        return bool(token)
