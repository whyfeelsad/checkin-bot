"""Check-in Bot 主入口"""

import warnings
from checkin_bot.bot.app import create_app


def main():
    """启动 Bot"""
    # 过滤 PTB UserWarning
    warnings.filterwarnings("ignore", category=UserWarning, module="telegram")

    app = create_app()
    app.run_polling()


if __name__ == "__main__":
    main()
