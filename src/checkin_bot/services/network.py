"""网络服务"""

import logging
from typing import Optional, Dict

from curl_cffi.requests import AsyncSession

from checkin_bot.config.settings import get_settings

logger = logging.getLogger(__name__)

IP_API_URL = "https://ipinfo.io/"


class NetworkService:
    """网络服务"""

    def __init__(self):
        self.settings = get_settings()

    async def get_ip_info(self) -> Optional[Dict]:
        """
        获取当前 IP 信息

        如果配置了 SOCKS5 代理，则请求会走代理。

        Returns:
            IP 信息字典，失败返回 None
        """
        # 获取代理配置
        proxy_kwargs = self.settings.curl_proxy or {}

        async with AsyncSession(**proxy_kwargs) as session:
            try:
                logger.info(f"正在获取 IP 信息... (代理: {'是' if proxy_kwargs else '否'})")
                response = await session.get(IP_API_URL, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"IP 信息获取成功: {data.get('ip')}")
                    return data
                else:
                    logger.warning(f"获取 IP 信息失败: HTTP {response.status_code}")
                    return None

            except Exception as e:
                logger.error(f"获取 IP 信息异常: {e}")
                return None

    def format_ip_info(self, ip_data: dict) -> str:
        """
        格式化 IP 信息为可读文本

        Args:
            ip_data: IP API 返回的数据

        Returns:
            格式化后的文本
        """
        # 解析 org 字段获取 ASN 信息
        org = ip_data.get('org', 'N/A')
        # org 格式通常为 "AS45102 Alibaba (US) Technology Co., Ltd."
        # 提取 ASN 号码和组织名称
        asn = 'N/A'
        org_name = org
        if org and org.startswith('AS') and ' ' in org:
            parts = org.split(' ', 1)
            if parts[0].startswith('AS'):
                asn = parts[0]
                org_name = parts[1] if len(parts) > 1 else 'N/A'

        lines = [
            "🌐 网络信息",
            "",
            f"📍 IP 地址: {ip_data.get('ip', 'N/A')}",
            f"🏳️ 国家/地区: {ip_data.get('country', 'N/A')}",
            f"🏙️ 城市: {ip_data.get('city', 'N/A')}",
            f"📍 地区: {ip_data.get('region', 'N/A')}",
            f"🏢 组织/ISP: {org_name}",
            f"📡 ASN: {asn}",
            f"🌍 时区: {ip_data.get('timezone', 'N/A')}",
        ]

        return "\n".join(lines)
