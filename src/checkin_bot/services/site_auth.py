"""站点认证服务"""

import logging
from collections.abc import Callable

from curl_cffi.requests import AsyncSession

from checkin_bot.captcha.cloudflyer import CloudflyerSolver
from checkin_bot.config.constants import (
    LOGIN_TIMEOUT,
    SiteConfig,
    SiteType,
    get_login_headers,
)
from checkin_bot.config.settings import get_settings

logger = logging.getLogger(__name__)


class SiteAuthService:
    """站点认证服务"""

    def __init__(self):
        self.settings = get_settings()
        self.captcha_solver = CloudflyerSolver()

    async def login(
        self,
        site: SiteType,
        username: str,
        password: str,
        progress_callback: Callable[..., None] | None = None,
        impersonate: str | None = None,
    ) -> str | None:
        """
        站点登录并获取 Cookie

        Args:
            site: 站点类型
            username: 用户名
            password: 密码
            progress_callback: 进度回调函数
            impersonate: 浏览器指纹（可选，默认使用配置值）

        Returns:
            Cookie 字符串，失败返回 None
        """
        config = SiteConfig.get(site)
        fingerprint = impersonate or self.settings.impersonate_browser
        logger.debug(f"使用浏览器指纹: {fingerprint}")

        # 获取代理配置
        proxy_kwargs = self.settings.curl_proxy or {}
        logger.debug(f"代理配置: {proxy_kwargs if proxy_kwargs else '未配置'}")

        # 使用 async with 确保会话正确关闭
        async with AsyncSession(impersonate=fingerprint, **proxy_kwargs) as session:
            try:
                logger.debug(f"开始登录 {site.value}: {username}")

                # 1. 先访问登录页面获取初始 Cookie
                logger.debug(f"获取登录页面: {config['login_url']}")
                await session.get(config["login_url"])

                # 2. 解决 Turnstile 验证码
                turnstile_token = await self.captcha_solver.solve(
                    site_url=config["login_url"],
                    sitekey=config["sitekey"],
                    progress_callback=progress_callback,
                )

                if not turnstile_token:
                    logger.warning(f"验证码解决失败: 站点 {site.value} 用户 {username}")
                    return None

                logger.debug(f"获取 Turnstile 令牌成功: {site.value}")

                # 3. 准备登录数据
                login_data = {
                    "username": username,
                    "password": password,
                    "token": turnstile_token,
                    "source": "turnstile",
                }

                headers = get_login_headers(config["base_url"], config["login_url"])

                logger.debug(f"发送登录请求到: {config['api_base']}{config['login_api']}")

                # 4. 发送登录请求
                response = await session.post(
                    f"{config['api_base']}{config['login_api']}",
                    json=login_data,
                    headers=headers,
                    timeout=LOGIN_TIMEOUT,
                )

                # 安全起见，不记录响应内容（可能包含敏感信息）
                logger.debug(f"登录响应状态: {response.status_code}, 内容长度: {len(response.text) if response.text else 0}")

                # 5. 检查登录结果
                if response.status_code == 200:
                    resp_json = response.json()
                    if resp_json.get("success"):
                        # 从 session cookies 提取
                        cookies = session.cookies.get_dict()
                        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])

                        logger.info(f"登录成功: 站点 {site.value} 用户 {username}")

                        # 登录成功即说明 Cookie 有效，无需额外验证
                        logger.debug(f"Cookie 有效: {site.value}")
                        return cookie_str
                    else:
                        logger.warning(f"登录失败: 站点 {site.value} 用户 {username} - {resp_json.get('message')}")
                else:
                    logger.warning(f"登录失败: 站点 {site.value} 用户 {username} - HTTP {response.status_code}")

            except Exception as e:
                logger.warning(f"登录异常: 站点 {site.value} 用户 {username} - {e}")

        return None

    async def _validate_cookie(
        self,
        site: SiteType,
        cookie: str,
        session: AsyncSession,
    ) -> bool:
        """
        验证 Cookie 有效性

        既然登录已成功，直接认为 Cookie 有效。
        实际验证在后续签到时进行。

        Args:
            site: 站点类型
            cookie: Cookie 字符串
            session: HTTP 会话

        Returns:
            是否有效（直接返回 True）
        """
        return True

    async def refresh_cookie(
        self,
        site: SiteType,
        old_cookie: str,
        username: str,
        password: str,
    ) -> str | None:
        """
        刷新 Cookie

        Args:
            site: 站点类型
            old_cookie: 旧的 Cookie
            username: 用户名
            password: 密码

        Returns:
            新的 Cookie，失败返回 None
        """
        # 直接重新登录获取新 Cookie
        return await self.login(site, username, password)

    async def validate_cookie(
        self,
        site: SiteType,
        cookie: str,
    ) -> bool:
        """
        验证 Cookie 有效性（独立方法）

        Args:
            site: 站点类型
            cookie: Cookie 字符串

        Returns:
            是否有效
        """
        # 获取代理配置
        proxy_kwargs = self.settings.curl_proxy or {}

        async with AsyncSession(impersonate=self.settings.impersonate_browser, **proxy_kwargs) as session:
            result = await self._validate_cookie(site, cookie, session)
        return result
