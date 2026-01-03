"""账号管理服务"""

import logging
import random
from typing import Callable

from checkin_bot.config.constants import (
    AccountStatus,
    CheckinMode,
    FINGERPRINT_OPTIONS,
    SiteType,
    UpdateStatus,
)
from checkin_bot.core.encryption import decrypt_password, encrypt_password
from checkin_bot.repositories.account_repository import AccountRepository
from checkin_bot.repositories.account_update_repository import AccountUpdateRepository
from checkin_bot.repositories.user_repository import UserRepository
from checkin_bot.services.site_auth import SiteAuthService
from checkin_bot.sites.base import SiteAdapter
from checkin_bot.sites.nodeseek import NodeSeekAdapter
from checkin_bot.sites.deepflood import DeepFloodAdapter

logger = logging.getLogger(__name__)


class AccountManager:
    """账号管理服务"""

    def __init__(self):
        self.user_repo = UserRepository()
        self.account_repo = AccountRepository()
        self.update_repo = AccountUpdateRepository()
        self._auth_service = None  # 延迟初始化

    @property
    def auth_service(self) -> SiteAuthService:
        """获取认证服务（延迟初始化）"""
        if self._auth_service is None:
            self._auth_service = SiteAuthService()
        return self._auth_service

    async def add_account(
        self,
        telegram_id: int,
        site: SiteType,
        site_username: str,
        password: str,
        checkin_mode: CheckinMode,
        progress_callback: Callable[[int, int], None] | None = None,
        impersonate: str | None = None,
    ) -> dict:
        """
        添加账号

        Args:
            telegram_id: Telegram 用户 ID
            site: 站点类型
            site_username: 站点用户名
            password: 密码
            checkin_mode: 签到模式
            progress_callback: 进度回调函数
            impersonate: 浏览器指纹（可选，已废弃，保留用于兼容）

        Returns:
            操作结果
        """
        logger.info(f"添加 站点 {site.value} 账号: {site_username} (ID={telegram_id})")

        # 1. 获取或创建用户
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            logger.debug(f"创建新用户: telegram_id={telegram_id}")
            user = await self.user_repo.create(
                telegram_id=telegram_id,
            )

        # 2. 确定使用的指纹
        # 如果传入了 impersonate 参数（重试时），优先使用它；否则如果用户已有有效指纹，使用它；否则随机选择一个
        if impersonate:
            fingerprint = impersonate
            logger.debug(f"使用传入指纹（重试）: {fingerprint}")
        elif user.fingerprint:
            fingerprint = user.fingerprint
            logger.debug(f"使用已有指纹: {fingerprint}")
        else:
            fingerprint = random.choice(FINGERPRINT_OPTIONS)
            logger.debug(f"随机选择指纹: {fingerprint}")

        # 3. 站点登录获取 Cookie
        logger.debug(f"登录站点 {site.value}: 用户 {site_username}")
        cookie = await self.auth_service.login(
            site=site,
            username=site_username,
            password=password,
            progress_callback=progress_callback,
            impersonate=fingerprint,
        )

        if not cookie:
            # 日志已在 auth_service 中记录
            return {
                "success": False,
                "message": "登录失败，请检查账号密码或稍后重试",
            }

        # 4. 登录成功，如果使用了新指纹且与用户原有指纹不同，更新用户的指纹
        if not user.fingerprint or (impersonate and impersonate != user.fingerprint):
            await self.user_repo.update(user.id, fingerprint=fingerprint)
            logger.debug(f"更新用户指纹: {fingerprint}")

        # 5. 加密密码
        encrypted_pass = encrypt_password(password)

        # 6. 创建账号记录
        try:
            logger.debug(f"创建账号记录: 站点 {site.value} 用户 {site_username}")
            account = await self.account_repo.create(
                user_id=user.id,
                site=site,
                site_username=site_username,
                encrypted_pass=encrypted_pass,
                checkin_mode=checkin_mode,
            )

            # 7. 更新 Cookie
            await self.account_repo.update_cookie(account.id, cookie)

            # 8. 获取真实鸡腿数并更新到数据库
            adapters = {
                SiteType.NODESEEK: NodeSeekAdapter(),
                SiteType.DEEPFLOOD: DeepFloodAdapter(),
            }
            adapter = adapters.get(site)
            if adapter:
                try:
                    # 重新获取 account 对象以包含 cookie
                    account = await self.account_repo.get_by_id(account.id)
                    logger.info(f"调用 get_credits: cookie={bool(account.cookie)}")
                    credits = await adapter.get_credits(account)
                    logger.info(f"get_credits 返回: credits={credits}")
                    if credits is not None:
                        await self.account_repo.update_credits(account.id, credits)
                        logger.info(f"获取鸡腿数成功: 站点 {site.value} 用户 {site_username} 鸡腿数={credits}")
                    else:
                        logger.warning(f"获取鸡腿数为 None: 站点 {site.value} 用户 {site_username}")
                except Exception as e:
                    logger.error(f"获取鸡腿数异常: 站点 {site.value} 用户 {site_username} - {e}", exc_info=True)

            logger.info(f"账号添加成功: 站点 {site.value} 用户 {site_username} (ID={account.id})")
            return {
                "success": True,
                "message": "账号添加成功",
                "account": account,
            }

        except Exception as e:
            logger.error(f"添加账号失败: 站点 {site.value} 用户 {site_username} - {e}", exc_info=True)
            return {
                "success": False,
                "message": f"添加账号失败: {str(e)}",
            }

    async def delete_account(self, account_id: int, telegram_id: int) -> dict:
        """
        删除账号

        Args:
            account_id: 账号 ID
            telegram_id: Telegram 用户 ID

        Returns:
            操作结果
        """
        logger.info(f"删除账号: ID={account_id} (Telegram ID={telegram_id})")

        # 获取用户
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            logger.warning(f"用户不存在: Telegram ID={telegram_id}")
            return {
                "success": False,
                "message": "用户不存在",
            }

        account = await self.account_repo.get_by_id(account_id)

        if not account:
            logger.warning(f"账号不存在: ID={account_id}")
            return {
                "success": False,
                "message": "账号不存在",
            }

        if account.user_id != user.id:
            logger.warning(f"用户 {user.id} (Telegram ID={telegram_id}) 尝试删除不属于自己的账号 {account_id} (所有者: {account.user_id})")
            return {
                "success": False,
                "message": "无权删除此账号",
            }

        success = await self.account_repo.delete(account_id)

        if success:
            logger.info(f"账号删除成功: 站点 {account.site.value} 用户 {account.site_username} (ID={account_id})")
            return {
                "success": True,
                "message": "账号删除成功",
            }

        logger.error(f"删除账号失败: ID={account_id}")
        return {
            "success": False,
            "message": "删除账号失败",
        }

    async def update_account_cookie(
        self,
        account_id: int,
        telegram_id: int,
        progress_callback: Callable[[int, int], None] | None = None,
        force: bool = False,
    ) -> dict:
        """
        更新账号 Cookie

        Args:
            account_id: 账号 ID
            telegram_id: Telegram 用户 ID
            progress_callback: 进度回调函数
            force: 是否强制更新（清理旧的更新记录）

        Returns:
            操作结果
        """
        logger.info(f"更新 Cookie: 账号 ID={account_id} (Telegram ID={telegram_id}, force={force})")

        # 获取用户
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            logger.warning(f"用户不存在: Telegram ID={telegram_id}")
            return {
                "success": False,
                "message": "用户不存在",
            }

        account = await self.account_repo.get_by_id(account_id)

        if not account:
            logger.warning(f"账号不存在: ID={account_id}")
            return {
                "success": False,
                "message": "账号不存在",
            }

        if account.user_id != user.id:
            logger.warning(f"用户 {user.id} (Telegram ID={telegram_id}) 尝试修改不属于自己的账号 {account_id} (所有者: {account.user_id})")
            return {
                "success": False,
                "message": "无权更新此账号",
            }

        # 1. 创建或强制创建更新记录
        if force:
            # 强制更新：清理旧的活跃记录，创建新的
            update_record = await self.update_repo.force_create(account_id)
            logger.debug(f"强制创建更新记录: ID={update_record.id} (账号 ID={account_id})")
        else:
            # 正常更新：如果已有活跃记录则拒绝
            is_created, update_record = await self.update_repo.try_create_or_get_active(account_id)
            if not is_created:
                logger.info(f"账号更新正在进行中: ID={account_id}")
                return {
                    "success": False,
                    "message": "已有更新任务正在进行中",
                }
            logger.debug(f"创建更新记录: ID={update_record.id} (账号 ID={account_id})")

        # 3. 解密密码
        password = decrypt_password(account.encrypted_pass)

        # 4. 选择新指纹（每次更新都更换指纹）
        new_fingerprint = random.choice(FINGERPRINT_OPTIONS)
        logger.debug(f"更新 Cookie 使用新指纹: {new_fingerprint}")

        # 5. 重新登录获取新 Cookie
        await self.update_repo.update_status(update_record.id, UpdateStatus.PROCESSING)

        logger.debug(f"重新登录 {account.site.value} 以更新 Cookie")
        new_cookie = await self.auth_service.login(
            site=account.site,
            username=account.site_username,
            password=password,
            progress_callback=progress_callback,
            impersonate=new_fingerprint,  # 使用新指纹
        )

        if new_cookie:
            await self.account_repo.update_cookie(account_id, new_cookie)

            # 更新用户指纹为成功的新指纹
            if not user.fingerprint or user.fingerprint != new_fingerprint:
                await self.user_repo.update(user.id, fingerprint=new_fingerprint)
                logger.debug(f"更新用户指纹: {new_fingerprint}")

            await self.update_repo.update_status(
                update_record.id,
                UpdateStatus.COMPLETED,
            )

            logger.info(f"Cookie 更新成功: 站点 {account.site.value} 用户 {account.site_username}")
            return {
                "success": True,
                "message": "Cookie 更新成功",
            }

        await self.update_repo.update_status(
            update_record.id,
            UpdateStatus.FAILED,
            error_message="登录失败",
        )

        logger.warning(f"Cookie 更新失败: 站点 {account.site.value} 用户 {account.site_username}")
        return {
            "success": False,
            "message": "Cookie 更新失败",
        }

    async def update_checkin_time(
        self,
        account_id: int,
        telegram_id: int,
        checkin_hour: int | None = None,
        push_hour: int | None = None,
    ) -> dict:
        """
        更新签到时间和推送时间

        Args:
            account_id: 账号 ID
            telegram_id: Telegram 用户 ID
            checkin_hour: 签到小时
            push_hour: 推送小时

        Returns:
            操作结果
        """
        logger.info(f"更新签到时间: 账号 ID={account_id} (Telegram ID={telegram_id}), 签到={checkin_hour}点, 推送={push_hour}点")

        # 获取用户
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            logger.warning(f"用户不存在: Telegram ID={telegram_id}")
            return {
                "success": False,
                "message": "用户不存在",
            }

        account = await self.account_repo.get_by_id(account_id)

        if not account:
            logger.warning(f"账号不存在: ID={account_id}")
            return {
                "success": False,
                "message": "账号不存在",
            }

        if account.user_id != user.id:
            logger.warning(f"用户 {user.id} (Telegram ID={telegram_id}) 尝试修改不属于自己的账号 {account_id} (所有者: {account.user_id})")
            return {
                "success": False,
                "message": "无权修改此账号",
            }

        # 如果传入 None，保留原有值
        final_checkin_hour = account.checkin_hour if checkin_hour is None else checkin_hour
        final_push_hour = account.push_hour if push_hour is None else push_hour

        await self.account_repo.update_checkin_time(
            account_id,
            final_checkin_hour,
            final_push_hour,
        )

        logger.info(f"签到时间已更新: 站点 {account.site.value} 用户 {account.site_username}")
        return {
            "success": True,
            "message": "时间设置已更新",
        }

    async def toggle_checkin_mode(
        self,
        account_id: int,
        telegram_id: int,
    ) -> dict:
        """
        切换签到模式

        Args:
            account_id: 账号 ID
            telegram_id: Telegram 用户 ID

        Returns:
            操作结果
        """
        logger.info(f"切换签到模式: 账号 ID={account_id} (Telegram ID={telegram_id})")

        # 获取用户
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            logger.warning(f"用户不存在: Telegram ID={telegram_id}")
            return {
                "success": False,
                "message": "用户不存在",
            }

        account = await self.account_repo.get_by_id(account_id)

        if not account:
            logger.warning(f"账号不存在: ID={account_id}")
            return {
                "success": False,
                "message": "账号不存在",
            }

        if account.user_id != user.id:
            logger.warning(f"用户 {user.id} (Telegram ID={telegram_id}) 尝试修改不属于自己的账号 {account_id} (所有者: {account.user_id})")
            return {
                "success": False,
                "message": "无权修改此账号",
            }

        # 切换模式
        new_mode = (
            CheckinMode.FIXED
            if account.checkin_mode == CheckinMode.RANDOM
            else CheckinMode.RANDOM
        )

        # 更新模式
        await self.account_repo.update_checkin_mode(account_id, new_mode)

        logger.info(f"签到模式已切换为 {new_mode.value}: 站点 {account.site.value} 用户 {account.site_username}")
        return {
            "success": True,
            "message": f"已切换为{new_mode.value}模式",
            "mode": new_mode,
        }

    async def get_user_accounts(self, user_id: int) -> list:
        """获取用户的所有账号"""
        return await self.account_repo.get_by_user(user_id)
