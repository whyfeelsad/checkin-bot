"""Bot handler decorators"""

import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from checkin_bot.bot.handlers._helpers import get_user_or_error
from checkin_bot.services.permission import PermissionService

logger = logging.getLogger(__name__)


def require_user(return_none: bool = False):
    """
    Decorator: Validate user exists before running handler

    Args:
        return_none: If True, return None when user doesn't exist;
                     if False, return ConversationHandler.END

    Example:
        @require_user(return_none=True)
        async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # User is guaranteed to exist here
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = await get_user_or_error(update, return_none=return_none)
            if not user:
                return ConversationHandler.END if not return_none else None
            # Inject user into kwargs
            return await func(update, context, user=user, *args, **kwargs)
        return wrapper
    return decorator


def require_admin(func):
    """
    Decorator: Validate admin permission before running handler

    Example:
        @require_admin
        async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Admin permission is guaranteed here
            pass
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        permission_service = PermissionService()
        is_admin = await permission_service.is_admin(user_id)

        if not is_admin:
            logger.warning(f"User {user_id} attempted to access admin feature without permission")
            if update.effective_message:
                await update.effective_message.edit_text("❌ You don't have permission to access this feature")
            return ConversationHandler.END

        return await func(update, context, *args, **kwargs)
    return wrapper
