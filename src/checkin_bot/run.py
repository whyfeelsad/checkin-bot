"""Bot 启动入口（在导入前过滤警告）"""

import logging
import sys
import warnings

# ANSI 颜色代码
class Colors:
    """ANSI 颜色代码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


# 日志级别颜色映射（清爽配色）
LOG_COLORS = {
    logging.DEBUG: "\033[38;5;245m",      # 灰色（柔和）
    logging.INFO: "\033[38;5;79m",        # 青绿色（清爽）
    logging.WARNING: "\033[38;5;221m",    # 柔和橙黄
    logging.ERROR: "\033[38;5;203m",      # 柔和红
    logging.CRITICAL: "\033[1;38;5;203m", # 粗体柔和红
}

# 日志级别名称映射
LOG_LEVEL_NAMES = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO ",
    logging.WARNING: "WARN ",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRIT ",
}


# 必须在导入 telegram 模块之前设置过滤器
warnings.filterwarnings("ignore", message=".*per_message.*")

# 导入配置
from checkin_bot.config.settings import get_settings
from checkin_bot.core.timezone import get_timezone

# 获取配置
settings = get_settings()
TZ = get_timezone()


class ColorFormatter(logging.Formatter):
    """带颜色和对齐的日志格式化器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def formatTime(self, record, datefmt=None):
        """使用配置时区的时间格式化器"""
        import time
        from datetime import datetime

        # 将 UTC 时间戳转换为配置时区
        dt = datetime.fromtimestamp(record.created, tz=TZ)
        # 转换为本地时间结构（去掉时区信息）
        ct = dt.replace(tzinfo=None).timetuple()

        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            t = time.strftime(self.default_time_format, ct)
            s = f"{t[:19]}"  # 只保留到秒
        return s

    def format(self, record):
        """格式化日志记录，添加颜色"""
        # 获取日志级别颜色
        level_color = LOG_COLORS.get(record.levelno, "")
        level_name = LOG_LEVEL_NAMES.get(record.levelno, record.levelname)

        # 格式化消息
        record.levelname = level_name

        # 调用父类格式化
        result = super().format(record)

        # 整条消息应用颜色
        if level_color:
            result = f"{level_color}{result}{Colors.RESET}"

        return result

# 使用配置的日志级别
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# 设置格式化器（带颜色和对齐）
for handler in logging.root.handlers:
    handler.setFormatter(ColorFormatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

# 隐藏冗余的日志（始终设置为 WARNING）
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# 隐藏 DEBUG 级别的库日志（保持输出简洁）
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("telegram.ext").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from checkin_bot.bot.app import create_app


def main():
    """启动 Bot"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("正在启动 Bot...")
    app = create_app()
    logger.info("Bot 应用已创建，开始轮询...")
    app.run_polling()


if __name__ == "__main__":
    main()
