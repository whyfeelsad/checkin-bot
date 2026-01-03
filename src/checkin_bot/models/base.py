"""数据模型基类"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BaseEntity:
    """实体基类"""

    id: int
    created_at: datetime
    updated_at: datetime
