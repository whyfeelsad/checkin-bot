"""配置管理模块"""

import logging
from typing import List

from pydantic import Field, ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== Bot 配置 ====================
    bot_token: str = Field(..., description="Telegram Bot Token")
    admin_ids_str: str = Field(default="", alias="ADMIN_IDS", description="管理员 ID 列表（逗号分隔）")

    # 白名单配置
    whitelist_user_ids_str: str = Field(default="", alias="WHITELIST_USER_IDS", description="用户白名单（逗号分隔）")
    whitelist_group_ids_str: str = Field(default="", alias="WHITELIST_GROUP_IDS", description="群组白名单（逗号分隔）")
    whitelist_channel_ids_str: str = Field(default="", alias="WHITELIST_CHANNEL_IDS", description="频道白名单（逗号分隔）")

    # ==================== Cloudflyer 验证码配置 ====================
    cloudflyer_api_url: str = Field(..., description="Cloudflyer API 地址")
    cloudflyer_api_key: str = Field(..., description="Cloudflyer API 密钥")
    captcha_max_retries: int = Field(default=20, description="最大重试次数")
    captcha_retry_interval: int = Field(default=3, description="重试间隔（秒）")
    impersonate_browser: str = Field(default="chrome136", description="curl_cffi 模拟浏览器版本")

    # ==================== 数据库配置 ====================
    database_url: str = Field(..., description="PostgreSQL 连接字符串")
    encryption_key: str = Field(..., min_length=32, description="AES-256-GCM 加密密钥（32 字节或 base64 编码）")

    # ==================== 运行时配置 ====================
    timezone: str = Field(default="Asia/Shanghai", description="时区配置")
    session_ttl_minutes: int = Field(default=10, description="会话过期时间（分钟）")
    permission_cache_ttl_minutes: int = Field(default=1, description="权限缓存时间（分钟）")
    default_checkin_hour: int = Field(default=4, description="默认签到小时")
    default_push_hour: int = Field(default=9, description="默认推送小时")

    # ==================== SOCKS5 代理配置 ====================
    socks5_proxy: str = Field(default="", alias="SOCKS5_PROXY", description="SOCKS5 代理地址")
    telegram_use_proxy: bool = Field(default=False, alias="TELEGRAM_USE_PROXY", description="Telegram 是否使用代理")

    # ==================== 日志配置 ====================
    log_level_str: str = Field(default="INFO", alias="LOG_LEVEL", description="日志级别: DEBUG, INFO, WARNING, ERROR")

    @field_validator("log_level_str")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got '{v}'")
        return v_upper

    @property
    def log_level(self) -> int:
        """获取日志级别常量"""
        return getattr(logging, self.log_level_str)

    @property
    def admin_ids(self) -> List[int]:
        """管理员 ID 列表"""
        return self._parse_ids(self.admin_ids_str)

    @property
    def whitelist_user_ids(self) -> List[int]:
        """用户白名单"""
        return self._parse_ids(self.whitelist_user_ids_str)

    @property
    def whitelist_group_ids(self) -> List[int]:
        """群组白名单"""
        return self._parse_ids(self.whitelist_group_ids_str)

    @property
    def whitelist_channel_ids(self) -> List[int]:
        """频道白名单"""
        return self._parse_ids(self.whitelist_channel_ids_str)

    @staticmethod
    def _parse_ids(value: str) -> List[int]:
        """解析 ID 列表"""
        if not value or not value.strip():
            return []
        return [int(x.strip()) for x in value.split(",") if x.strip()]

    @property
    def has_whitelist(self) -> bool:
        """是否配置了白名单"""
        return bool(
            self.whitelist_user_ids
            or self.whitelist_group_ids
            or self.whitelist_channel_ids
        )

    @property
    def curl_proxy(self) -> dict | None:
        """
        获取用于 curl_cffi 的代理配置

        使用 socks5h:// 协议（对应 curl 的 --socks5-hostname），
        让代理服务器进行 DNS 解析。

        Returns:
            代理配置字典，未配置时返回 None
        """
        if not self.socks5_proxy:
            return None

        # 将 socks5:// 转换为 socks5h://（remote DNS resolution）
        proxy_url = self.socks5_proxy
        if proxy_url.startswith("socks5://"):
            proxy_url = proxy_url.replace("socks5://", "socks5h://", 1)

        return {"proxies": {"http": proxy_url, "https": proxy_url}}

    @property
    def telegram_proxy_url(self) -> str | None:
        """
        获取用于 python-telegram-bot 的代理 URL

        Returns:
            代理 URL 字符串，未配置或不使用时返回 None
        """
        if not self.telegram_use_proxy or not self.socks5_proxy:
            return None
        return self.socks5_proxy


# 全局配置实例
_settings: Settings | None = None


def get_settings() -> Settings:
    """获取配置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
