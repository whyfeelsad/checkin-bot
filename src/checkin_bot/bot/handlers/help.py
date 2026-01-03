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

🌐 支持站点：
• NodeSeek - nodeseek.com
• DeepFlood - deepflood.net

🎯 主要功能：
• 添加账号 - 支持多站点、多账号管理
• 自动签到 - 每日定时自动签到，积分不再错过
• 手动签到 - 随时手动触发签到
• 签到日志 - 查看历史签到记录与详情
• 数据统计 - 查看账号鸡腿数增长趋势

⚙️ 签到模式：
• 📌 固定鸡腿 - 每日固定获得 5 鸡腿
• 🎲 试试手气 - 每日随机获得 1-15 鸡腿

⏰ 定时签到：
• 可设置签到时间（0-23 点）
• 随机模式在设定小时内随机时段签到
• 可设置推送时间，汇总当日签到结果

🔧 账号管理：
• 切换模式 - 固定/随机模式随时切换
• 更新 Cookie - Cookie 失效时一键更新
• 删除账号 - 不再需要的账号可删除

🔒 安全说明：
• 密码使用 AES-256-GCM 加密存储
• 账号密码消息输入后自动删除
• Cookie 失效自动重新验证

❓ 常见问题：
Q: 如何添加账号？
A: 点击「添加账号」→ 选择站点 → 输入 `用户名 密码`

Q: 签到时间是什么意思？
A: 设置在每天几点进行自动签到（0-23 点可选）

Q: 推送时间是什么意思？
A: 设置在几点接收当日签到结果汇总

Q: 固定模式和随机模式有什么区别？
A: 固定模式每日获得 5 鸡腿，随机模式获得 1-15 鸡腿

Q: Cookie 失效怎么办？
A: 在账号列表点击「🍪 更新」按钮即可

Q: 如何删除账号？
A: 在账号列表点击第一行账号信息按钮确认即可

💡 使用提示：
• 建议使用随机模式，收益更高
• 可为每个账号设置不同的签到时间
• 同一账号重复添加会提示替换"""

    await update.effective_message.edit_text(
        help_text,
        reply_markup=get_back_to_menu_keyboard(),
    )


help_handler = CallbackQueryHandler(help_callback, pattern="^help$")
