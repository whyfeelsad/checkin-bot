"""站点适配器模块"""

from checkin_bot.sites.base import SiteAdapter
from checkin_bot.sites.deepflood import DeepFloodAdapter
from checkin_bot.sites.nodeseek import NodeSeekAdapter

__all__ = [
    "SiteAdapter",
    "NodeSeekAdapter",
    "DeepFloodAdapter",
]
