import functools
from telegram import Update
from telegram.ext import ContextTypes
from database.database import get_db
from database.models import User
from loguru import logger
from typing import Callable, Any

def with_user(func: Callable) -> Callable:
    """Decorator to ensure user exists in database and inject user data (not the SQLAlchemy object) into context.user_data. Supports both methods and functions."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Detect if this is a method (self, update, context, ...)
        if len(args) > 0 and hasattr(args[0], '__class__') and not isinstance(args[0], Update):
            self = args[0]
            update = args[1]
            context = args[2]
            rest = args[3:]
        else:
            self = None
            update = args[0]
            context = args[1]
            rest = args[2:]

        if not update.effective_user:
            return
        
        telegram_id = update.effective_user.id
        telegram_user = update.effective_user
        
        with get_db() as db:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                # Create new user with Telegram settings
                user = User(
                    telegram_id=telegram_id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    language_code=telegram_user.language_code or "en",
                    timezone="UTC"  # Default timezone, will be updated below
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"New user created: {telegram_id}")
            
            # Auto-update user settings from Telegram
            updated = False
            
            # Update language if different
            telegram_lang = telegram_user.language_code or "en"
            if user.language_code != telegram_lang:
                user.language_code = telegram_lang
                updated = True
                logger.info(f"Updated language for user {telegram_id}: {user.language_code}")
            
            # Try to detect timezone from user's location or message date
            if update.message and update.message.date:
                # Use the message date to infer timezone
                # This is a simple approach - in a real app you might use more sophisticated detection
                message_time = update.message.date
                # For now, we'll keep UTC as default, but you could implement timezone detection here
                # based on the user's activity patterns or explicit timezone setting
            
            # Update other user info if changed
            if user.username != telegram_user.username:
                user.username = telegram_user.username
                updated = True
            
            if user.first_name != telegram_user.first_name:
                user.first_name = telegram_user.first_name
                updated = True
                
            if user.last_name != telegram_user.last_name:
                user.last_name = telegram_user.last_name
                updated = True
            
            if updated:
                db.commit()
                logger.info(f"Updated user info for {telegram_id}")
            
            # Inject only primitive user data into context
            context.user_data['user_id'] = user.id
            context.user_data['user_telegram_id'] = user.telegram_id
            context.user_data['user_username'] = user.username
            context.user_data['user_first_name'] = user.first_name
            context.user_data['user_last_name'] = user.last_name
            context.user_data['user_language_code'] = user.language_code
            context.user_data['user_timezone'] = user.timezone
            context.user_data['user_status'] = user.status.value if hasattr(user.status, 'value') else user.status
        
        if self:
            return await func(self, update, context, *rest, **kwargs)
        else:
            return await func(update, context, *rest, **kwargs)
    return wrapper

def admin_required(func: Callable) -> Callable:
    """Decorator to restrict access to admin users only"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if len(args) > 0 and hasattr(args[0], '__class__') and not isinstance(args[0], Update):
            self = args[0]
            update = args[1]
            context = args[2]
            rest = args[3:]
        else:
            self = None
            update = args[0]
            context = args[1]
            rest = args[2:]

        if not update.effective_user:
            return
        
        from config import settings
        if update.effective_user.id != settings.admin_user_id:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return
        
        if self:
            return await func(self, update, context, *rest, **kwargs)
        else:
            return await func(update, context, *rest, **kwargs)
    return wrapper

def error_handler(func: Callable) -> Callable:
    """Decorator to handle and log errors gracefully. Supports both methods and functions."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            # Try to send error message to user if update is available
            update = None
            if len(args) > 0 and hasattr(args[0], '__class__') and not isinstance(args[0], Update):
                # method: self, update, ...
                if len(args) > 1 and isinstance(args[1], Update):
                    update = args[1]
            elif len(args) > 0 and isinstance(args[0], Update):
                update = args[0]
            if update and hasattr(update, 'message') and update.message:
                try:
                    await update.message.reply_text("❌ An error occurred. Please try again later.")
                except:
                    pass
            raise
    return wrapper