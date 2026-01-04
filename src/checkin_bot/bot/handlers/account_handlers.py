"""Account management handlers"""

import logging
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.error import BadRequest, TelegramError

from checkin_bot.bot.handlers._helpers import (
    get_user_or_error,
    show_account_list,
    return_to_main_menu,
    is_valid_callback,
    answer_callback_query,
    parse_callback_id,
    parse_time_callback,
)
from checkin_bot.bot.keyboards.account import (
    get_site_selection_keyboard,
    get_mode_selection_keyboard,
    get_account_list_keyboard,
    get_confirm_delete_keyboard,
    get_delete_confirm_message,
    get_time_picker_keyboard,
    get_retry_keyboard,
    get_account_added_keyboard,
)
from checkin_bot.config.constants import CheckinMode, FINGERPRINT_OPTIONS, SessionState, SiteType, SiteConfig
from checkin_bot.repositories.session_repository import SessionRepository
from checkin_bot.repositories.user_repository import UserRepository
from checkin_bot.services.account_manager import AccountManager

logger = logging.getLogger(__name__)

# 对话状态
ADD_ACCOUNT_SITE = 0
ADD_ACCOUNT_CREDENTIALS = 1
ADD_ACCOUNT_MODE = 2
LOGIN_FAILED = 3
DELETE_CONFIRM = 4
ADD_ACCOUNT_CONFIRM_REPLACE = 5

# 最大重试次数
MAX_RETRIES = 3


async def cancel_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """取消操作，返回主菜单"""
    if not is_valid_callback(update):
        return ConversationHandler.END

    await return_to_main_menu(update, context)
    return ConversationHandler.END


async def add_account_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """添加账号回调"""
    if not update.effective_message or not update.callback_query:
        return ConversationHandler.END

    await answer_callback_query(update)

    keyboard = get_site_selection_keyboard()

    await update.effective_message.edit_text(
        "🌐 请选择要添加账号的站点：",
        reply_markup=keyboard,
    )

    return ADD_ACCOUNT_SITE


async def add_account_site(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """选择站点"""
    if not is_valid_callback(update):
        return ConversationHandler.END

    await answer_callback_query(update)

    # 解析站点类型
    site_str = update.callback_query.data.replace("site_", "")
    site = SiteType(site_str)
    site_config = SiteConfig.get(site)

    # 保存到会话
    session_repo = SessionRepository()
    user = await get_user_or_error(update, return_none=True)
    if not user:
        return ConversationHandler.END

    await session_repo.create(
        telegram_id=update.effective_user.id,
        state=SessionState.ADDING_ACCOUNT_CREDENTIALS,
        data={"site": site.value, "prompt_message_id": update.effective_message.message_id},
    )

    await update.effective_message.edit_text(
        f"🌐 正在添加账号：{site_config['name']}\n\n"
        "🔐 请输入您的账号和密码\n"
        "📝 格式：`用户名  密码`\n"
        "💡 示例：`myuser passwd`\n\n"
        "🔒 为保护您的隐私，密码在输入后将自动删除",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 返回菜单", callback_data="cancel")]
        ]),
    )

    return ADD_ACCOUNT_CREDENTIALS


async def add_account_credentials(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """输入账号密码"""
    if not update.effective_message:
        return ConversationHandler.END

    text = update.effective_message.text

    # 解析账号密码
    parts = text.strip().split()
    if len(parts) != 2:
        # 获取会话数据以编辑原消息
        session_repo = SessionRepository()
        session = await session_repo.get_by_telegram_id(update.effective_user.id)

        if session:
            prompt_message_id = session.data.get("prompt_message_id")
            site_str = session.data.get("site")
            if prompt_message_id and site_str:
                site = SiteType(site_str)
                site_config = SiteConfig.get(site)
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_message.chat_id,
                        message_id=prompt_message_id,
                        text=(
                            f"🌐 正在添加账号：{site_config['name']}\n\n"
                            "⚠️ 格式错误，请重新输入\n"
                            "📝 格式：`用户名  密码`\n"
                            "💡 示例：`myuser passwd`\n\n"
                            "🔒 为保护您的隐私，密码在输入后将自动删除"
                        ),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 返回菜单", callback_data="cancel")]
                        ]),
                    )
                except Exception:
                    pass  # 编辑失败，忽略
        return ADD_ACCOUNT_CREDENTIALS

    username, password = parts

    # 获取 chat_id 和消息 ID（在删除消息之前）
    chat_id = update.effective_message.chat_id

    # 删除用户消息保护隐私
    try:
        await update.effective_message.delete()
    except Exception:
        pass

    # 获取会话数据
    session_repo = SessionRepository()
    session = await session_repo.get_by_telegram_id(update.effective_user.id)

    if not session:
        await context.bot.send_message(chat_id, "❌ 会话已过期，请重新开始")
        return ConversationHandler.END

    site_str = session.data.get("site")
    prompt_message_id = session.data.get("prompt_message_id")
    site = SiteType(site_str)

    # 获取重试次数
    retry_count = session.data.get("retry_count", 0)

    # 选择新的指纹（重试时）
    fingerprint = None
    if retry_count > 0:
        fingerprint = random.choice(FINGERPRINT_OPTIONS)

    # 先检查是否已存在相同的账号
    user = await get_user_or_error(update, return_none=True)
    if user:
        account_manager = AccountManager()
        accounts = await account_manager.get_user_accounts(user.id)
        existing_account = next(
            (acc for acc in accounts if acc.site == site and acc.site_username == username),
            None
        )

        if existing_account:
            # 账号已存在，直接编辑原消息显示确认对话框
            site_config = SiteConfig.get(site)

            # 保存账号信息到 user_data，供确认后使用
            if context.user_data is None:
                context.user_data = {}
            context.user_data["pending_account"] = {
                "site": site.value,
                "username": username,
                "password": password,
                "fingerprint": fingerprint,
                "progress_msg_id": prompt_message_id,
                "existing_account_id": existing_account.id,
            }

            # 显示确认对话框
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✔️ 确定", callback_data=f"confirm_replace_yes"),
                    InlineKeyboardButton("✖️ 取消", callback_data=f"confirm_replace_no"),
                ]
            ])

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=prompt_message_id,
                text=(
                    f"⚠️ 检测到已添加过的账号\n\n"
                    f"📍 站点：{site_config['name']}\n"
                    f"👤 用户名：{username}\n\n"
                    f"是否替换此账号？"
                ),
                reply_markup=keyboard,
            )

            return ADD_ACCOUNT_CONFIRM_REPLACE

    # 没有重复账号，编辑之前的消息显示进度
    if prompt_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=prompt_message_id,
                text="⚔️ 与 Cloudflare 的终极对决中\n⏳ 当前进度 ▰▱▱▱▱▱▱▱▱ 0%",
            )
            progress_msg_id = prompt_message_id
        except Exception:
            # 如果编辑失败（消息可能已被删除），发送新消息
            msg = await context.bot.send_message(chat_id, "⚔️ 与 Cloudflare 的终极对决中\n⏳ 当前进度 ▰▱▱▱▱▱▱▱▱ 0%")
            progress_msg_id = msg.message_id
    else:
        msg = await context.bot.send_message(chat_id, "⚔️ 与 Cloudflare 的终极对决中\n⏳ 当前进度 ▰▱▱▱▱▱▱▱▱ 0%")
        progress_msg_id = msg.message_id

    # 定义进度回调
    async def progress_callback(current: int, total: int):
        try:
            percentage = int(100 * current / total)
            filled = max(1, int(10 * current / total))  # 至少显示 1 个 ▰
            bar = "▰" * filled + "▱" * (10 - filled)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg_id,
                text=f"⚔️ 与 Cloudflare 的终极对决中\n⏳ 当前进度 {bar} {percentage}%",
            )
        except BadRequest as e:
            # 忽略消息未修改等不影响进度的错误
            if "not modified" not in str(e).lower():
                logger.debug(f"更新进度消息失败: {e}")
        except TelegramError as e:
            # 记录但不中断流程
            logger.debug(f"更新进度消息异常: {e}")

    # 添加账号（指纹自动处理）
    result = await account_manager.add_account(
        telegram_id=update.effective_user.id,
        site=site,
        site_username=username,
        password=password,
        checkin_mode=CheckinMode.FIXED,  # 默认固定鸡腿模式
        progress_callback=progress_callback,
        impersonate=fingerprint,  # 重试时使用新指纹
    )

    if result["success"]:
        logger.info(f"账号添加成功: 站点 {site.value} 用户 {username} (用户 {update.effective_user.id})")

        # 保存刚添加的账号 ID 到 user_data
        if context.user_data is None:
            context.user_data = {}
        context.user_data["last_added_account_id"] = result["account"].id

        # 选择签到模式
        keyboard = get_mode_selection_keyboard()

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_msg_id,
            text=(
                "账号添加成功！\n\n"
                "📋 请选择获取鸡腿的方案：\n"
                "• 📌 鸡腿 x 5  每日固定获得 5 鸡腿\n"
                "• 🎲 试试手气 每日随机获得 1-15 鸡腿"
            ),
            reply_markup=keyboard,
        )

        return ADD_ACCOUNT_MODE
    else:
        logger.warning(f"添加账号失败: 用户 {update.effective_user.id} - {result['message']}")

        # 检查是否可以重试
        new_retry_count = retry_count + 1
        if new_retry_count < MAX_RETRIES:
            # 保存重试信息到会话
            await session_repo.update_data(
                session.id,
                data={
                    "site": site.value,
                    "prompt_message_id": prompt_message_id,
                    "username": username,
                    "password": password,
                    "retry_count": new_retry_count,
                },
            )

            # 显示重试界面
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg_id,
                text=(
                    "😔 登录失败了\n\n"
                    "可能的原因：\n"
                    "• 账号或密码错误\n"
                    "• 网络连接不稳定\n"
                    "• 验证码解决超时\n\n"
                    "💡 您可以重试，系统会自动更换新的浏览器指纹"
                ),
                reply_markup=get_retry_keyboard(new_retry_count, MAX_RETRIES),
            )

            return LOGIN_FAILED
        else:
            # 已达到最大重试次数
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg_id,
                text=(
                    "😔 登录失败，已达到最大重试次数\n\n"
                    "可能的原因：\n"
                    "• 账号或密码错误\n"
                    "• 网络连接不稳定\n"
                    "• 验证码解决超时\n\n"
                    "💡 建议：\n"
                    "• 检查账号密码是否正确\n"
                    "• 稍后再试"
                ),
                reply_markup=get_site_selection_keyboard(),
            )
            return ConversationHandler.END


async def add_account_mode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """选择签到模式"""
    if not update.effective_message or not update.callback_query:
        return ConversationHandler.END

    await answer_callback_query(update)

    # 解析模式
    mode_str = update.callback_query.data.replace("mode_", "")
    mode = CheckinMode(mode_str)

    # 获取用户
    user = await get_user_or_error(update, return_none=True)
    if not user:
        return ConversationHandler.END

    # 获取刚添加的账号
    account_id = context.user_data.get("last_added_account_id") if context.user_data else None
    account_credits = 0

    if account_id:
        account_manager = AccountManager()
        accounts = await account_manager.get_user_accounts(user.id)
        account = next((acc for acc in accounts if acc.id == account_id), None)
        if account:
            account_credits = account.credits

    # 根据模式显示不同的文案
    if mode == CheckinMode.FIXED:
        message = (
            "✨ 设置成功！\n\n"
            "📌 模式：固定鸡腿\n"
            "🎁 每日固定获得 5 鸡腿\n\n"
            f"💰 当前鸡腿数：{account_credits}"
        )
    else:
        message = (
            "✨ 设置成功！\n\n"
            "🎲 模式：试试手气\n"
            "🎁 每日随机获得 1-15 鸡腿\n\n"
            f"💰 当前鸡腿数：{account_credits}"
        )

    await update.effective_message.edit_text(
        message,
        reply_markup=get_account_added_keyboard(),
    )

    # 清除保存的账号 ID
    if context.user_data and "last_added_account_id" in context.user_data:
        del context.user_data["last_added_account_id"]

    return ConversationHandler.END


async def confirm_replace_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """确认替换账号回调"""
    if not update.effective_message or not update.callback_query:
        return ConversationHandler.END

    await answer_callback_query(update)

    # 获取保存的账号信息
    pending = context.user_data.get("pending_account") if context.user_data else None
    if not pending:
        await update.effective_message.edit_text("❌ 会话已过期，请重新添加账号")
        return ConversationHandler.END

    # 解析用户选择
    choice = update.callback_query.data

    if choice == "confirm_replace_no":
        # 用户选择取消，返回主菜单
        await return_to_main_menu(update, context)
        return ConversationHandler.END

    # 用户选择确定，执行替换
    site = SiteType(pending["site"])
    username = pending["username"]
    password = pending["password"]
    fingerprint = pending["fingerprint"]
    progress_msg_id = pending["progress_msg_id"]
    existing_account_id = pending["existing_account_id"]
    retry_count = pending.get("retry_count", 0)

    # 定义进度回调
    async def progress_callback(current: int, total: int):
        try:
            percentage = int(100 * current / total)
            filled = max(1, int(10 * current / total))
            bar = "▰" * filled + "▱" * (10 - filled)
            await context.bot.edit_message_text(
                chat_id=update.effective_message.chat_id,
                message_id=progress_msg_id,
                text=f"⚔️ 替换账号中...\n⏳ 当前进度 {bar} {percentage}%",
            )
        except Exception:
            pass  # 忽略进度更新错误

    # 先删除旧账号
    account_manager = AccountManager()
    await account_manager.delete_account(existing_account_id, update.effective_user.id)

    # 添加新账号
    result = await account_manager.add_account(
        telegram_id=update.effective_user.id,
        site=site,
        site_username=username,
        password=password,
        checkin_mode=CheckinMode.FIXED,
        progress_callback=progress_callback,
        impersonate=fingerprint,
    )

    if result["success"]:
        logger.info(f"账号替换成功: 站点 {site.value} 用户 {username}")

        # 清除保存的账号信息
        if context.user_data and "pending_account" in context.user_data:
            del context.user_data["pending_account"]

        # 保存刚添加的账号 ID
        if context.user_data is None:
            context.user_data = {}
        context.user_data["last_added_account_id"] = result["account"].id

        # 选择签到模式
        keyboard = get_mode_selection_keyboard()

        await context.bot.edit_message_text(
            chat_id=update.effective_message.chat_id,
            message_id=progress_msg_id,
            text=(
                "账号替换成功！\n\n"
                "📋 请选择获取鸡腿的方案：\n"
                "• 📌 鸡腿 x 5  每日固定获得 5 鸡腿\n"
                "• 🎲 试试手气 每日随机获得 1-15 鸡腿"
            ),
            reply_markup=keyboard,
        )

        return ADD_ACCOUNT_MODE
    else:
        logger.warning(f"替换账号失败: {result.get('message', '未知错误')}")

        # 检查是否可以重试
        new_retry_count = retry_count + 1
        if new_retry_count < MAX_RETRIES:
            # 更新重试信息到 user_data
            context.user_data["pending_account"] = {
                **pending,
                "retry_count": new_retry_count,
            }

            # 显示重试界面
            await context.bot.edit_message_text(
                chat_id=update.effective_message.chat_id,
                message_id=progress_msg_id,
                text=(
                    "😔 登录失败了\n\n"
                    "可能的原因：\n"
                    "• 账号或密码错误\n"
                    "• 网络连接不稳定\n"
                    "• 验证码解决超时\n\n"
                    "💡 您可以重试，系统会自动更换新的浏览器指纹"
                ),
                reply_markup=get_retry_keyboard(new_retry_count, MAX_RETRIES),
            )

            return LOGIN_FAILED
        else:
            # 已达到最大重试次数
            # 清除保存的账号信息
            if context.user_data and "pending_account" in context.user_data:
                del context.user_data["pending_account"]

            await context.bot.edit_message_text(
                chat_id=update.effective_message.chat_id,
                message_id=progress_msg_id,
                text=(
                    "😔 登录失败，已达到最大重试次数\n\n"
                    "可能的原因：\n"
                    "• 账号或密码错误\n"
                    "• 网络连接不稳定\n"
                    "• 验证码解决超时\n\n"
                    "💡 建议：\n"
                    "• 检查账号密码是否正确\n"
                    "• 稍后再试"
                ),
                reply_markup=get_site_selection_keyboard(),
            )
            return ConversationHandler.END


async def checkin_now_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """立即签到回调"""
    if not is_valid_callback(update):
        return

    await answer_callback_query(update)

    user = await get_user_or_error(update, return_none=True)
    if not user:
        return

    # 获取用户的账号列表
    account_manager = AccountManager()
    accounts = await account_manager.get_user_accounts(user.id)

    if not accounts:
        await update.effective_message.edit_text(
            "📝 您还没有添加任何账号",
            reply_markup=get_account_added_keyboard(),
        )
        return

    # 直接调用签到服务进行签到
    from checkin_bot.services.checkin import CheckinService

    # 获取第一个账号进行签到
    first_account = accounts[0]

    checkin_service = CheckinService()
    result = await checkin_service.manual_checkin(first_account.id)

    if result["success"]:
        delta = result.get("credits_delta", 0)
        after = result.get("credits_after", 0)
        logger.info(f"立即签到成功: 账号 {first_account.id} +{delta} 鸡腿, 总计: {after}")

        # 检查是否是今日已签到的情况
        if result.get("message") == "今日已签到":
            # 今日已签到，显示不同的消息
            try:
                await update.effective_message.edit_text(
                    f"🎉 今日已签到！\n"
                    f"📈 鸡腿变化: +{delta}\n"
                    f"💰 当前鸡腿: {after}",
                    reply_markup=get_account_added_keyboard(),
                )
            except Exception as e:
                # 忽略"消息未修改"错误
                if "not modified" not in str(e).lower():
                    logger.warning(f"编辑消息失败: {e}")
        else:
            # 正常签到成功，编辑消息
            try:
                await update.effective_message.edit_text(
                    f"🎉 签到成功！\n"
                    f"📈 鸡腿变化: +{delta}\n"
                    f"💰 当前鸡腿: {after}",
                    reply_markup=get_account_added_keyboard(),
                )
            except Exception as e:
                # 忽略"消息未修改"错误
                if "not modified" not in str(e).lower():
                    logger.warning(f"编辑消息失败: {e}")
    else:
        logger.warning(f"立即签到失败: 账号 {first_account.id} - {result.get('message', '未知错误')}")
        await update.effective_message.edit_text(
            f"❌ 签到失败\n"
            f"{result.get('message', '未知错误')}",
            reply_markup=get_account_added_keyboard(),
        )


async def checkin_all_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """签到所有账号回调"""
    if not is_valid_callback(update):
        return

    await answer_callback_query(update)

    user = await get_user_or_error(update, return_none=True)
    if not user:
        return

    # 获取用户的账号列表
    account_manager = AccountManager()
    accounts = await account_manager.get_user_accounts(user.id)

    if not accounts:
        await update.effective_message.edit_text(
            "📝 您还没有添加任何账号",
            reply_markup=get_account_added_keyboard(),
        )
        return

    from checkin_bot.services.checkin import CheckinService
    from checkin_bot.bot.keyboards.checkin import get_checkin_keyboard, get_back_to_checkin_list_keyboard

    checkin_service = CheckinService()

    # 记录当前页面，用于签到完成后返回
    current_text = update.effective_message.text or ""
    from_checkin_page = "请选择要签到的账号" in current_text

    # 汇总结果
    success_count = 0
    failed_count = 0
    total_delta = 0
    results = []

    # 依次签到每个账号
    for account in accounts:
        site_config = SiteConfig.get(account.site)
        site_name = site_config["name"]

        # 先尝试用现有 cookie 签到
        result = await checkin_service.manual_checkin(account.id)

        # 如果签到失败且错误是 cookie 相关，重新获取 cookie 后再试
        if not result["success"] and result.get("error_code") in ("invalid_cookie", "blocked"):
            logger.info(f"Cookie 失败，重新获取: 账号 {account.id}")
            update_result = await account_manager.update_account_cookie(
                account.id,
                update.effective_user.id,
                progress_callback=None,
                force=True,
            )
            if update_result["success"]:
                # 重新获取账号（cookie 已更新）
                account = await account_manager.account_repo.get_by_id(account.id)
                result = await checkin_service.manual_checkin(account.id)

        # 记录结果
        if result["success"]:
            success_count += 1
            delta = result.get("credits_delta", 0)
            total_delta += delta
            results.append(f"✅ {site_name} ({account.site_username}): +{delta}")
        else:
            failed_count += 1
            results.append(f"❌ {site_name} ({account.site_username}): {result.get('message', '未知错误')}")

    # 构建汇总消息
    summary_lines = [
        "📋 批量签到完成\n",
        f"✅ 成功: {success_count}",
        f"❌ 失败: {failed_count}",
        f"📈 总鸡腿: +{total_delta}\n",
        "───────",
    ]
    summary_lines.extend(results)

    summary = "\n".join(summary_lines)

    # 判断从哪个页面调用，返回相应的键盘
    if from_checkin_page:
        # 从签到页面调用，返回签到列表键盘
        keyboard = get_back_to_checkin_list_keyboard()
    elif "您的账号列表" in current_text:
        # 从账号列表页面调用，返回账号列表键盘
        keyboard = get_account_list_keyboard(accounts)
    else:
        # 从其他页面（如添加账号页面）调用，返回添加账号键盘
        keyboard = get_account_added_keyboard()

    try:
        await update.effective_message.edit_text(
            summary,
            reply_markup=keyboard,
        )
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"编辑消息失败: {e}")


async def retry_login_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """重试登录（支持添加账号和替换账号两种场景）"""
    if not is_valid_callback(update):
        return LOGIN_FAILED

    await answer_callback_query(update)

    chat_id = update.effective_message.chat_id

    # 检查是否是替换账号的重试
    pending = context.user_data.get("pending_account") if context.user_data else None

    if pending and "existing_account_id" in pending:
        # 替换账号重试流程
        site = SiteType(pending["site"])
        username = pending["username"]
        password = pending["password"]
        progress_msg_id = pending["progress_msg_id"]
        existing_account_id = pending["existing_account_id"]
        retry_count = pending.get("retry_count", 0)

        # 选择新的指纹
        fingerprint = random.choice(FINGERPRINT_OPTIONS)

        # 定义进度回调
        async def progress_callback(current: int, total: int):
            try:
                percentage = int(100 * current / total)
                filled = max(1, int(10 * current / total))
                bar = "▰" * filled + "▱" * (10 - filled)
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg_id,
                    text=f"⚔️ 替换账号中...\n⏳ 当前进度 {bar} {percentage}%",
                )
            except Exception:
                pass  # 忽略进度更新错误

        # 先删除旧账号
        account_manager = AccountManager()
        await account_manager.delete_account(existing_account_id, update.effective_user.id)

        # 添加新账号
        result = await account_manager.add_account(
            telegram_id=update.effective_user.id,
            site=site,
            site_username=username,
            password=password,
            checkin_mode=CheckinMode.FIXED,
            progress_callback=progress_callback,
            impersonate=fingerprint,
        )

        if result["success"]:
            logger.info(f"替换账号重试成功: 站点 {site.value} 用户 {username}")

            # 清除保存的账号信息
            if context.user_data and "pending_account" in context.user_data:
                del context.user_data["pending_account"]

            # 保存刚添加的账号 ID
            if context.user_data is None:
                context.user_data = {}
            context.user_data["last_added_account_id"] = result["account"].id

            # 选择签到模式
            keyboard = get_mode_selection_keyboard()

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg_id,
                text=(
                    "账号替换成功！\n\n"
                    "📋 请选择获取鸡腿的方案：\n"
                    "• 📌 鸡腿 x 5  每日固定获得 5 鸡腿\n"
                    "• 🎲 试试手气 每日随机获得 1-15 鸡腿"
                ),
                reply_markup=keyboard,
            )

            return ADD_ACCOUNT_MODE
        else:
            logger.warning(f"替换账号重试失败: {result.get('message', '未知错误')}")

            # 检查是否可以继续重试
            new_retry_count = retry_count + 1
            if new_retry_count < MAX_RETRIES:
                # 更新重试信息到 user_data
                context.user_data["pending_account"] = {
                    **pending,
                    "retry_count": new_retry_count,
                }

                # 显示重试界面
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg_id,
                    text=(
                        "😔 登录失败了\n\n"
                        "可能的原因：\n"
                        "• 账号或密码错误\n"
                        "• 网络连接不稳定\n"
                        "• 验证码解决超时\n\n"
                        "💡 您可以重试，系统会自动更换新的浏览器指纹"
                    ),
                    reply_markup=get_retry_keyboard(new_retry_count, MAX_RETRIES),
                )

                return LOGIN_FAILED
            else:
                # 已达到最大重试次数
                if context.user_data and "pending_account" in context.user_data:
                    del context.user_data["pending_account"]

                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg_id,
                    text=(
                        "😔 登录失败，已达到最大重试次数\n\n"
                        "可能的原因：\n"
                        "• 账号或密码错误\n"
                        "• 网络连接不稳定\n"
                        "• 验证码解决超时\n\n"
                        "💡 建议：\n"
                        "• 检查账号密码是否正确\n"
                        "• 稍后再试"
                    ),
                    reply_markup=get_site_selection_keyboard(),
                )
                return ConversationHandler.END

    # 添加账号重试流程（原有逻辑）
    session_repo = SessionRepository()
    session = await session_repo.get_by_telegram_id(update.effective_user.id)

    if not session:
        await return_to_main_menu(update, context)
        return ConversationHandler.END

    data = session.data
    username = data.get("username")
    password = data.get("password")
    site_str = data.get("site")
    prompt_message_id = data.get("prompt_message_id")
    retry_count = data.get("retry_count", 0)

    if not all([username, password, site_str]):
        await return_to_main_menu(update, context)
        return ConversationHandler.END

    site = SiteType(site_str)

    # 选择新的指纹
    fingerprint = random.choice(FINGERPRINT_OPTIONS)

    # 编辑消息显示进度
    if prompt_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=prompt_message_id,
                text="⚔️ 与 Cloudflare 的终极对决中\n⏳ 当前进度 ▰▱▱▱▱▱▱▱▱ 0%",
            )
            progress_msg_id = prompt_message_id
        except Exception:
            msg = await context.bot.send_message(chat_id, "⚔️ 与 Cloudflare 的终极对决中\n⏳ 当前进度 ▰▱▱▱▱▱▱▱▱ 0%")
            progress_msg_id = msg.message_id
    else:
        msg = await context.bot.send_message(chat_id, "⚔️ 与 Cloudflare 的终极对决中\n⏳ 当前进度 ▰▱▱▱▱▱▱▱▱ 0%")
        progress_msg_id = msg.message_id

    # 定义进度回调
    async def progress_callback(current: int, total: int):
        try:
            percentage = int(100 * current / total)
            filled = max(1, int(10 * current / total))  # 至少显示 1 个 ▰
            bar = "▰" * filled + "▱" * (10 - filled)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg_id,
                text=f"⚔️ 与 Cloudflare 的终极对决中\n⏳ 当前进度 {bar} {percentage}%",
            )
        except BadRequest as e:
            # 忽略消息未修改等不影响进度的错误
            if "not modified" not in str(e).lower():
                logger.debug(f"更新进度消息失败: {e}")
        except TelegramError as e:
            # 记录但不中断流程
            logger.debug(f"更新进度消息异常: {e}")

    # 重新尝试登录
    account_manager = AccountManager()
    result = await account_manager.add_account(
        telegram_id=update.effective_user.id,
        site=site,
        site_username=username,
        password=password,
        checkin_mode=CheckinMode.FIXED,  # 默认固定鸡腿模式
        progress_callback=progress_callback,
        impersonate=fingerprint,
    )

    if result["success"]:
        logger.info(f"重试成功: 站点 {site.value} 用户 {username} (用户 {update.effective_user.id})")

        keyboard = get_mode_selection_keyboard()

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_msg_id,
            text=(
                "账号添加成功！\n\n"
                "📋 请选择获取鸡腿的方案：\n"
                "• 📌 鸡腿 x 5  每日固定获得 5 鸡腿\n"
                "• 🎲 试试手气 每日随机获得 1-15 鸡腿"
            ),
            reply_markup=keyboard,
        )

        return ADD_ACCOUNT_MODE
    else:
        logger.warning(f"重试失败: 用户 {update.effective_user.id} - {result['message']}")

        # 检查是否可以继续重试
        new_retry_count = retry_count + 1
        if new_retry_count < MAX_RETRIES:
            # 更新重试次数
            await session_repo.update_data(
                session.id,
                data={
                    **data,
                    "retry_count": new_retry_count,
                },
            )

            # 显示重试界面
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg_id,
                text=(
                    "😔 登录失败了\n\n"
                    "可能的原因：\n"
                    "• 账号或密码错误\n"
                    "• 网络连接不稳定\n"
                    "• 验证码解决超时\n\n"
                    "💡 您可以重试，系统会自动更换新的浏览器指纹"
                ),
                reply_markup=get_retry_keyboard(new_retry_count, MAX_RETRIES),
            )

            return LOGIN_FAILED
        else:
            # 已达到最大重试次数
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg_id,
                text=(
                    "😔 登录失败，已达到最大重试次数\n\n"
                    "可能的原因：\n"
                    "• 账号或密码错误\n"
                    "• 网络连接不稳定\n"
                    "• 验证码解决超时\n\n"
                    "💡 建议：\n"
                    "• 检查账号密码是否正确\n"
                    "• 稍后再试"
                ),
                reply_markup=get_site_selection_keyboard(),
            )
            return ConversationHandler.END


async def my_accounts_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """我的账号回调"""
    if not is_valid_callback(update):
        return

    await answer_callback_query(update)

    user = await get_user_or_error(update, return_none=True)
    if not user:
        return

    # 清除更新状态（重新进入页面时重置）
    if context.user_data:
        context.user_data.pop("update_status", None)

    await show_account_list(update, user.id)


async def delete_account_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """删除账号回调"""
    logger.info(f"删除账号回调被触发: {update.callback_query.data if update.callback_query else 'None'}")

    if not is_valid_callback(update):
        logger.warning("删除账号回调验证失败")
        return ConversationHandler.END

    await answer_callback_query(update)
    logger.info("回答回调查询成功")

    # 解析账号 ID
    account_id = parse_callback_id(update.callback_query.data, "delete_")
    if account_id is None:
        logger.warning(f"无效的删除回调数据: {update.callback_query.data}")
        return ConversationHandler.END

    user = await get_user_or_error(update)
    if user == ConversationHandler.END:
        return ConversationHandler.END

    # 初始化删除状态
    if "deleting_account_ids" not in context.user_data:
        context.user_data["deleting_account_ids"] = set()

    # 获取账号详情
    account_manager = AccountManager()
    accounts = await account_manager.get_user_accounts(user.id)
    account = next((a for a in accounts if a.id == account_id), None)

    if account:
        # 获取站点配置
        site_config = SiteConfig.get(account.site)
        site_name = site_config["name"]

        # 显示详细确认对话框
        keyboard = get_confirm_delete_keyboard(account_id)
        message = get_delete_confirm_message(account.site_username, site_name)
        try:
            await update.effective_message.edit_text(message, reply_markup=keyboard)
        except BadRequest as e:
            logger.warning(f"显示删除确认对话框失败 (Bad请求): {e}")
            # 回退到简化版本
            try:
                await update.effective_message.edit_text(
                    f"⚠️ 确认移除账号\n\n账号：{account.site_username}\n站点：{site_name}\n\n此操作不可撤销！",
                    reply_markup=keyboard,
                )
            except TelegramError as e2:
                logger.error(f"显示删除确认对话框失败 (Telegram错误): {e2}")
        except TelegramError as e:
            logger.error(f"显示删除确认对话框失败 (未知错误): {e}")
    else:
        await update.effective_message.edit_text("❌ 账号不存在")
        return ConversationHandler.END

    return DELETE_CONFIRM


async def delete_account_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """确认删除账号"""
    if not is_valid_callback(update):
        return DELETE_CONFIRM

    await answer_callback_query(update)

    # 解析账号 ID
    account_id = parse_callback_id(update.callback_query.data, "confirm_delete_")
    if account_id is None:
        logger.warning(f"无效的确认删除回调数据: {update.callback_query.data}")
        return DELETE_CONFIRM

    user = await get_user_or_error(update)
    if user == ConversationHandler.END:
        return ConversationHandler.END

    # 检查是否已在删除中
    deleting_ids = context.user_data.get("deleting_account_ids", set())
    if account_id in deleting_ids:
        # 已在删除中，忽略重复点击
        return DELETE_CONFIRM

    # 标记为删除中
    deleting_ids.add(account_id)
    context.user_data["deleting_account_ids"] = deleting_ids

    # 删除账号
    account_manager = AccountManager()
    result = await account_manager.delete_account(account_id, update.effective_user.id)

    if result["success"]:
        # 删除成功后直接返回账号列表
        await show_account_list(update, user.id)
    else:
        await update.effective_message.edit_text(f"❌ {result['message']}")

    return ConversationHandler.END


async def back_to_my_accounts_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """返回账号列表（结束对话）"""
    if not is_valid_callback(update):
        return ConversationHandler.END

    await answer_callback_query(update)

    user = await get_user_or_error(update, return_none=True)
    if not user:
        return ConversationHandler.END

    await show_account_list(update, user.id)
    return ConversationHandler.END  # 结束对话，允许再次进入删除流程


async def update_cookie_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """更新 Cookie 回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    # 解析账号 ID
    account_id = parse_callback_id(update.callback_query.data, "update_cookie_")
    if account_id is None:
        await update.effective_message.edit_text("❌ 无效的请求")
        return

    # 获取用户
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(update.effective_user.id)

    if not user:
        await update.effective_message.edit_text("❌ 用户不存在")
        return

    # 初始化更新状态字典
    if context.user_data is None:
        context.user_data = {}
    if "update_status" not in context.user_data:
        context.user_data["update_status"] = {}

    # 如果已经是 updating 状态，不重复执行
    if context.user_data["update_status"].get(account_id) == "updating":
        return

    # 设置为更新中状态
    context.user_data["update_status"][account_id] = "updating"

    # 刷新列表显示更新中状态
    await show_account_list(update, user.id, update_status=context.user_data.get("update_status"))

    # 在后台更新 Cookie（不发送进度消息）
    account_manager = AccountManager()
    result = await account_manager.update_account_cookie(
        account_id,
        update.effective_user.id,
        progress_callback=None,  # 不发送进度消息
        force=True,  # 用户手动点击时强制更新
    )

    if result["success"]:
        # 设置为完成状态
        context.user_data["update_status"][account_id] = "completed"
    else:
        # 失败则设置失败状态
        context.user_data["update_status"][account_id] = "failed"

    # 刷新列表显示更新后的状态
    await show_account_list(update, user.id, update_status=context.user_data.get("update_status"))


async def toggle_mode_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """切换签到模式回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    # 解析账号 ID
    account_id = parse_callback_id(update.callback_query.data, "toggle_mode_")
    if account_id is None:
        await update.effective_message.edit_text("❌ 无效的请求")
        return

    # 获取用户
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(update.effective_user.id)

    if not user:
        await update.effective_message.edit_text("❌ 用户不存在")
        return

    # 切换模式（静默执行，不显示中间消息）
    account_manager = AccountManager()
    await account_manager.toggle_checkin_mode(account_id, update.effective_user.id)

    # 直接刷新列表显示更新后的状态
    update_status = context.user_data.get("update_status") if context.user_data else None
    await show_account_list(update, user.id, update_status=update_status)


async def set_checkin_time_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """设置签到时间回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    # 解析账号 ID 和时间
    result = parse_time_callback(update.callback_query.data, "set_checkin_")
    if result is None:
        await update.effective_message.edit_text("❌ 无效的请求")
        return

    account_id, action = result

    # 如果是 "time"，显示时间选择器
    if action == "time":
        keyboard = get_time_picker_keyboard(account_id, is_checkin=True)
        await update.effective_message.edit_text(
            "⏰ 请选择签到时间",
            reply_markup=keyboard,
        )
        return

    # 否则设置时间
    hour = action

    # 获取用户
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(update.effective_user.id)

    if not user:
        await update.effective_message.edit_text("❌ 用户不存在")
        return

    # 设置签到时间（静默执行，不显示中间消息）
    account_manager = AccountManager()
    await account_manager.update_checkin_time(
        account_id,
        update.effective_user.id,
        checkin_hour=hour,
    )

    # 直接刷新列表显示更新后的状态
    update_status = context.user_data.get("update_status") if context.user_data else None
    await show_account_list(update, user.id, update_status=update_status)


async def set_push_time_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """设置推送时间回调"""
    if not update.effective_message or not update.callback_query:
        return

    await answer_callback_query(update)

    # 解析账号 ID 和时间
    result = parse_time_callback(update.callback_query.data, "set_push_")
    if result is None:
        await update.effective_message.edit_text("❌ 无效的请求")
        return

    account_id, action = result

    # 如果是 "time"，显示时间选择器
    if action == "time":
        keyboard = get_time_picker_keyboard(account_id, is_checkin=False)
        await update.effective_message.edit_text(
            "🔔 请选择推送时间",
            reply_markup=keyboard,
        )
        return

    # 否则设置时间
    hour = action

    # 获取用户
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(update.effective_user.id)

    if not user:
        await update.effective_message.edit_text("❌ 用户不存在")
        return

    # 设置推送时间（静默执行，不显示中间消息）
    account_manager = AccountManager()
    await account_manager.update_checkin_time(
        account_id,
        update.effective_user.id,
        push_hour=hour,
    )

    # 直接刷新列表显示更新后的状态
    update_status = context.user_data.get("update_status") if context.user_data else None
    await show_account_list(update, user.id, update_status=update_status)


# 创建处理器
add_account_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_account_callback, pattern="^add_account$"),
    ],
    states={
        ADD_ACCOUNT_SITE: [
            CallbackQueryHandler(add_account_site, pattern="^site_"),
            CallbackQueryHandler(cancel_callback, pattern="^cancel$"),
        ],
        ADD_ACCOUNT_CREDENTIALS: [
            CallbackQueryHandler(cancel_callback, pattern="^cancel$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_credentials),
        ],
        ADD_ACCOUNT_MODE: [
            CallbackQueryHandler(add_account_mode, pattern="^mode_"),
            CallbackQueryHandler(cancel_callback, pattern="^cancel$"),
        ],
        ADD_ACCOUNT_CONFIRM_REPLACE: [
            CallbackQueryHandler(confirm_replace_callback, pattern="^confirm_replace_"),
        ],
        LOGIN_FAILED: [
            CallbackQueryHandler(retry_login_callback, pattern="^retry_login$"),
            CallbackQueryHandler(cancel_callback, pattern="^back_to_menu$"),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_callback, pattern="^cancel$"),
    ],
    per_message=False,
)

my_accounts_handler = CallbackQueryHandler(
    my_accounts_callback,
    pattern="^my_accounts$",
)

delete_account_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(delete_account_callback, pattern="^delete_\\d+$"),
    ],
    states={
        DELETE_CONFIRM: [
            CallbackQueryHandler(delete_account_confirm, pattern="^confirm_delete_"),
            CallbackQueryHandler(back_to_my_accounts_callback, pattern="^back_to_my_accounts$"),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(back_to_my_accounts_callback, pattern="^back_to_my_accounts$"),
    ],
    per_message=False,
)

update_cookie_handler = CallbackQueryHandler(
    update_cookie_callback,
    pattern="^update_cookie_\\d+$",
)

toggle_mode_handler = CallbackQueryHandler(
    toggle_mode_callback,
    pattern="^toggle_mode_\\d+$",
)

set_checkin_time_handler = CallbackQueryHandler(
    set_checkin_time_callback,
    pattern="^set_checkin_",
)

set_push_time_handler = CallbackQueryHandler(
    set_push_time_callback,
    pattern="^set_push_",
)

# 返回主菜单处理器
back_to_menu_handler = CallbackQueryHandler(
    cancel_callback,
    pattern="^back_to_menu$",
)

# 立即签到处理器
checkin_now_handler = CallbackQueryHandler(
    checkin_now_callback,
    pattern="^checkin_now$",
)

# 签到所有处理器
checkin_all_handler = CallbackQueryHandler(
    checkin_all_callback,
    pattern="^checkin_all$",
)


# 处理过期的按钮点击（对话已结束后的历史消息按钮）
async def expired_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """处理过期的按钮点击"""
    if not update.callback_query:
        return

    await answer_callback_query(update)

    # 检查是否是已知的回调数据
    callback_data = update.callback_query.data

    # 只处理对话相关的按钮，不包括那些有专门 handler 的按钮
    # 这些是只有在 ConversationHandler 活跃时才有效的按钮
    expired_patterns = [
        "^cancel$",           # 取消按钮
        "^site_",             # 站点选择
        "^mode_",             # 模式选择
        "^retry_login$",      # 重试登录
        "^confirm_replace_",  # 确认替换
        "^delete_\\d+$",      # 删除账号
        "^confirm_delete_",   # 确认删除
        "^back_to_my_accounts$",  # 返回账号列表（删除对话中）
    ]

    from re import match as re_match
    is_expired_callback = any(re_match(pattern, callback_data) for pattern in expired_patterns)

    if is_expired_callback:
        try:
            await update.effective_message.edit_text(
                "⚠️ 此操作已过期\n\n"
                "请使用 /start 重新开始",
                reply_markup=None,
            )
        except Exception:
            # 如果编辑失败，发送新消息
            if update.effective_message.chat_id:
                await context.bot.send_message(
                    chat_id=update.effective_message.chat_id,
                    text="⚠️ 此操作已过期\n\n请使用 /start 重新开始",
                )
    else:
        # 不是已知的回调，忽略
        pass


# 过期按钮处理器（只处理对话相关的按钮）
expired_button_handler = CallbackQueryHandler(
    expired_callback_handler,
    pattern="^(cancel|site_(nodeseek|deepflood)|mode_(fixed|random)|retry_login|confirm_replace_(yes|no)|delete_\\d+|confirm_delete_\\d+|back_to_my_accounts)$",
)
