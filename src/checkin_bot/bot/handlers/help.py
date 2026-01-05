"""帮助处理器"""

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from checkin_bot.bot.handlers._helpers import answer_callback_query
from checkin_bot.bot.keyboards.account import get_back_to_menu_keyboard


async def help_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """帮助回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    help_text = """📖 使用帮助

🌐 支持站点
• NodeSeek • DeepFlood

🎯 主要功能
• 添加账号 - 多站点多账号
• 自动签到 - 定时签到不遗漏
• 签到日志 - 历史记录查看
• 数据统计 - 鸡腿增长趋势

⚙️ 签到模式
• 🛡️ 稳稳拿 - 每天 5 鸡腿
• 🎲 试试手气 - 随机 1-15 鸡腿

⏰ 定时签到
• 可设置签到时间（0-23 点）
• 可设置推送时间，汇总结果

🔧 账号管理
• 切换模式 - 固定/随机随时换
• 更新 Cookie - 失效一键更新
• 删除账号 - 不需要就删除

🔒 安全保证
• AES-256 加密存储
• 密码消息自动删除
• Cookie 失效自动重验

❓ 常见问题
Q: 如何添加账号？
A: 添加账号 → 选站点 → 输入 `用户名 密码`

Q: 固定/随机模式区别？
A: 固定每天 5 鸡腿，随机 1-15 鸡腿

Q: Cookie 失效怎么办？
A: 账号列表点击「🍪 更新」

💡 小提示
• 可为每个账号设置不同时间"""

    await update.effective_message.edit_text(
        help_text,
        reply_markup=get_back_to_menu_keyboard(),
    )


help_handler = CallbackQueryHandler(help_callback, pattern="^help$")
