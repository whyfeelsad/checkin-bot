"""常量定义模块"""

from enum import Enum
from typing import Final


# ==================== HTTP 请求配置 ====================
DEFAULT_HTTP_HEADERS: Final[dict[str, str]] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "sec-ch-ua": '"Not A(Brand";v="99", "Microsoft Edge";v="121", "Chromium";v="121"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
}


def get_login_headers(base_url: str, login_url: str) -> dict[str, str]:
    """
    获取登录请求的 HTTP 头

    Args:
        base_url: 站点基础 URL
        login_url: 登录页面 URL

    Returns:
        HTTP 头字典
    """
    headers = DEFAULT_HTTP_HEADERS.copy()
    headers.update({
        "origin": base_url,
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": login_url,
        "Content-Type": "application/json",
    })
    return headers


# ==================== 请求超时配置 ====================
DEFAULT_TIMEOUT: Final[int] = 15  # 默认超时 15 秒
LOGIN_TIMEOUT: Final[int] = 30  # 登录超时 30 秒


# ==================== 站点配置 ====================
class SiteType(str, Enum):
    """站点类型枚举"""
    NODESEEK = "nodeseek"
    DEEPFLOOD = "deepflood"


class SiteConfig:
    """站点配置"""

    NODESEEK = {
        "name": "NodeSeek",
        "emoji": "💬",
        "base_url": "https://www.nodeseek.com",
        "login_url": "https://www.nodeseek.com/signIn.html",
        "api_base": "https://www.nodeseek.com/api",
        "login_api": "/account/signIn",
        "sitekey": "0x4AAAAAAAaNy7leGjewpVyR",
        "credit_api": "/account/credit",
        "checkin_api": "/attendance",
    }

    DEEPFLOOD = {
        "name": "DeepFlood",
        "emoji": "💬",
        "base_url": "https://www.deepflood.com",
        "login_url": "https://www.deepflood.com/signIn.html",
        "api_base": "https://www.deepflood.com/api",
        "login_api": "/account/signIn",
        "sitekey": "0x4AAAAAAAaNy7leGjewpVyR",
        "credit_api": "/account/credit",
        "checkin_api": "/attendance",
    }

    @classmethod
    def get(cls, site: SiteType) -> dict:
        """获取站点配置"""
        return {
            SiteType.NODESEEK: cls.NODESEEK,
            SiteType.DEEPFLOOD: cls.DEEPFLOOD,
        }[site]


# ==================== 小时 Emoji 映射 ====================
HOUR_EMOJI: Final[dict[str, str]] = {
    "0": "㍘", "1": "㍙", "2": "㍚", "3": "㍛",
    "4": "㍜", "5": "㍝", "6": "㍞", "7": "㍟",
    "8": "㍠", "9": "㍡", "10": "㍢", "11": "㍣",
    "12": "㍤", "13": "㍥", "14": "㍦", "15": "㍧",
    "16": "㍨", "17": "㍩", "18": "㍪", "19": "㍫",
    "20": "㍬", "21": "㍭", "22": "㍮", "23": "㍯",
}


def get_hour_emoji(hour: int) -> str:
    """获取小时对应的 Emoji"""
    return HOUR_EMOJI.get(str(hour), "")


# ==================== 签到模式 ====================
class CheckinMode(str, Enum):
    """签到模式枚举"""
    FIXED = "fixed"  # 固定时间
    RANDOM = "random"  # 随机时间


# ==================== 账号状态 ====================
class AccountStatus(str, Enum):
    """账号状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


# ==================== 签到状态 ====================
class CheckinStatus(str, Enum):
    """签到状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


# ==================== 更新状态 ====================
class UpdateStatus(str, Enum):
    """更新状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== 会话状态 ====================
class SessionState(str, Enum):
    """会话状态枚举"""
    ADDING_ACCOUNT_SITE = "adding_account_site"
    ADDING_ACCOUNT_CREDENTIALS = "adding_account_credentials"
    ADDING_ACCOUNT_CHECKIN_MODE = "adding_account_checkin_mode"
    SETTING_CHECKIN_TIME = "setting_checkin_time"
    SETTING_PUSH_TIME = "setting_push_time"
    CONFIRMING_DELETE = "confirming_delete"


# ==================== 浏览器指纹选项 ====================
FINGERPRINT_OPTIONS: Final[list[str]] = [
    "chrome99",
    "chrome100",
    "chrome101",
    "chrome104",
    "chrome107",
    "chrome110",
    "chrome116",
    "chrome119",
    "chrome120",
    "chrome123",
    "chrome124",
    "chrome131",
    "chrome133a",
    "chrome136",
]
