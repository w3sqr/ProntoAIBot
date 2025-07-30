from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from database.database import get_db
from database.models import User
from utils.decorators import with_user, error_handler
from utils.helpers import ValidationHelper
from utils.keyboards import Keyboards
from utils.logger import logger
import pytz
from typing import Optional
import re
from config import settings

# Conversation states
class SettingsFeature:
    TIMEZONE_INPUT = 0
    LANGUAGE_SELECT = 1
    UTC_OFFSET_INPUT = 2

    @with_user
    @error_handler
    async def show_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings main menu"""
        user_language = context.user_data.get('user_language_code', 'en')
        user_timezone = context.user_data.get('user_timezone', 'UTC')
        
        text = (
            "⚙️ *Settings*\n\n"
            f"🌍 Language: *{user_language.upper()}* (auto-synced from Telegram)\n"
            f"🕐 Timezone: *{user_timezone}* (auto-detected)\n\n"
            "Customize your bot experience:"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.settings_menu()
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.settings_menu()
            )
    
    @with_user
    @error_handler
    async def show_language_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show language selection"""
        query = update.callback_query
        await query.answer()
        
        user_language_code = context.user_data.get('user_language_code', 'en')
        current_lang = user_language_code or 'en'
        
        await query.edit_message_text(
            f"🌍 *Language Settings*\n\n"
            f"Current language: *{current_lang.upper()}*\n\n"
            f"ℹ️ Your language is automatically synced from your Telegram settings.\n"
            f"To change it, update your Telegram language in the Telegram app.\n\n"
            f"Available languages:",
            parse_mode='Markdown',
            reply_markup=Keyboards.language_selection()
        )
    
    @with_user
    @error_handler
    async def set_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set user language"""
        query = update.callback_query
        await query.answer()
        
        language_code = query.data.split('_')[1]
        user_id = context.user_data['user_id']
        
        language_names = {
            'en': 'English 🇺🇸',
            'es': 'Español 🇪🇸',
            'fr': 'Français 🇫🇷',
            'de': 'Deutsch 🇩🇪',
            'ru': 'Русский 🇷🇺'
        }
        
        with get_db() as db:
            db_user = db.query(User).filter(User.id == user_id).first()
            if db_user:
                db_user.language_code = language_code
                db.commit()
                # Update context with new language
                context.user_data['user_language_code'] = language_code
        
        language_name = language_names.get(language_code, language_code.upper())
        
        await query.edit_message_text(
            f"✅ *Language Updated*\n\n"
            f"Language set to: *{language_name}*\n\n"
            f"ℹ️ Note: Your language will be automatically synced from Telegram in future sessions.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_telegram_settings_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help for changing Telegram settings"""
        query = update.callback_query
        await query.answer()
        
        help_text = (
            "📱 *How to Change Telegram Settings*\n\n"
            "🌍 *Language:*\n"
            "1. Open Telegram app\n"
            "2. Go to Settings → Language\n"
            "3. Select your preferred language\n"
            "4. Restart Telegram\n\n"
            "🕐 *Timezone:*\n"
            "1. Open Telegram app\n"
            "2. Go to Settings → Data and Storage\n"
            "3. Your timezone is automatically detected\n"
            "4. Or change your device timezone\n\n"
            "ℹ️ The bot will automatically sync these settings on your next interaction."
        )
        
        await query.edit_message_text(
            help_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_timezone_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show timezone settings"""
        query = update.callback_query
        await query.answer()
        
        user_timezone = context.user_data.get('user_timezone', 'UTC')
        
        text = (
            "🕐 *Timezone Settings*\n\n"
            f"Current timezone: *{user_timezone}*\n\n"
            "Choose your timezone:"
        )
        
        keyboard = [
            [InlineKeyboardButton("🌍 UTC (Universal Time)", callback_data="tz_UTC")],
            [InlineKeyboardButton("🇺🇸 UTC-5 (Eastern US)", callback_data="tz_America/New_York")],
            [InlineKeyboardButton("🇺🇸 UTC-8 (Pacific US)", callback_data="tz_America/Los_Angeles")],
            [InlineKeyboardButton("🇬🇧 UTC+0 (London)", callback_data="tz_Europe/London")],
            [InlineKeyboardButton("🇩🇪 UTC+1 (Berlin)", callback_data="tz_Europe/Berlin")],
            [InlineKeyboardButton("🇷🇺 UTC+3 (Moscow)", callback_data="tz_Europe/Moscow")],
            [InlineKeyboardButton("🇮🇳 UTC+5:30 (Mumbai)", callback_data="tz_Asia/Kolkata")],
            [InlineKeyboardButton("🇨🇳 UTC+8 (Beijing)", callback_data="tz_Asia/Shanghai")],
            [InlineKeyboardButton("🇯🇵 UTC+9 (Tokyo)", callback_data="tz_Asia/Tokyo")],
            [InlineKeyboardButton("🇦🇺 UTC+10 (Sydney)", callback_data="tz_Australia/Sydney")],
            [InlineKeyboardButton("🕐 Custom UTC Offset", callback_data="tz_custom_utc")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_settings")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def set_timezone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set user timezone"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "tz_custom":
            await query.edit_message_text(
                "🌍 *Custom Timezone*\n\n"
                "Please enter your timezone (e.g., America/New_York, Europe/London):\n\n"
                "You can find your timezone at: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
                parse_mode='Markdown'
            )
            return self.TIMEZONE_INPUT
        
        if query.data == "tz_custom_utc":
            logger.info("tz_custom_utc selected, setting UTC_OFFSET_INPUT state")
            await query.edit_message_text(
                "🕐 *Custom UTC Offset*\n\n"
                "Please enter your UTC offset in the format: UTC:+2 or UTC:-5\n\n"
                "Examples:\n"
                "• `UTC:+2` (2 hours ahead of UTC)\n"
                "• `UTC:-5` (5 hours behind UTC)\n"
                "• `UTC:+5:30` (5 hours 30 minutes ahead of UTC)",
                parse_mode='Markdown'
            )
            return self.UTC_OFFSET_INPUT
        
        timezone = query.data.split('_', 1)[1]
        user_id = context.user_data['user_id']
        
        # Validate timezone
        if not ValidationHelper.is_valid_timezone(timezone):
            await query.edit_message_text(
                "❌ Invalid timezone. Please try again.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="settings_timezone")]
                ])
            )
            return
        
        with get_db() as db:
            db_user = db.query(User).filter(User.id == user_id).first()
            if db_user:
                db_user.timezone = timezone
                db.commit()
                # Update context with new timezone
                context.user_data['user_timezone'] = timezone
        
        await query.edit_message_text(
            f"✅ *Timezone Updated*\n\n"
            f"Timezone set to: *{timezone}*\n\n"
            f"All your reminders and schedules will now use this timezone.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def get_custom_timezone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get custom timezone from user input"""
        timezone = update.message.text.strip()
        user_id = context.user_data['user_id']
        
        # Validate timezone
        if not ValidationHelper.is_valid_timezone(timezone):
            await update.message.reply_text(
                "❌ Invalid timezone. Please enter a valid timezone (e.g., America/New_York, Europe/London).\n\n"
                "You can find your timezone at: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
            )
            return self.TIMEZONE_INPUT
        
        with get_db() as db:
            db_user = db.query(User).filter(User.id == user_id).first()
            if db_user:
                db_user.timezone = timezone
                db.commit()
                # Update context with new timezone
                context.user_data['user_timezone'] = timezone
        
        await update.message.reply_text(
            f"✅ *Timezone Updated*\n\n"
            f"Timezone set to: *{timezone}*\n\n"
            f"All your reminders and schedules will now use this timezone.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        )
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def show_contact_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show contact information"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "📞 *Contact Information*\n\n"
            "Need help or have suggestions?\n\n"
           # "📧 Email: support@productivitybot.com\n"
            "💬 Telegram: @ProntoAI\n"
           # "🌐 Website: https://productivitybot.com\n"
            "📱 GitHub: https://github.com/thesurfhawk/prontoaibot\n\n"
            "We'd love to hear from you!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_donate_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        donate_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Give me Stars", callback_data="donate_stars_menu")],
            [InlineKeyboardButton("☕ Buy me a Coffee", url="https://coff.ee/thesurfhawk")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
        ])
        # If triggered by inline button
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                "💝 *Support Our Bot*\n\n"
                "Help us keep this bot free and improve it!\n\n"
                "Your support helps us:\n"
                "• Keep the bot running 24/7\n"
                "• Add new features\n"
                "• Improve AI capabilities\n"
                "• Provide better support\n\n"
                "Choose how you'd like to support us:\n\n"
                "Thank you for your support! 🙏",
                parse_mode='Markdown',
                reply_markup=donate_keyboard
            )
        # If triggered by reply keyboard or text message
        elif update.message:
            await update.message.reply_text(
                "💝 *Support Our Bot*\n\n"
                "Help us keep this bot free and improve it!\n\n"
                "Your support helps us:\n"
                "• Keep the bot running 24/7\n"
                "• Add new features\n"
                "• Improve AI capabilities\n"
                "• Provide better support\n\n"
                "Choose how you'd like to support us:\n\n"
                "Thank you for your support! 🙏",
                parse_mode='Markdown',
                reply_markup=donate_keyboard
            )
    
    @with_user
    @error_handler
    async def show_share_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot sharing options"""
        query = update.callback_query
        await query.answer()
        
        bot_username = context.bot.username
        share_text = (
            "🤖 Check out this amazing Productivity Bot!\n\n"
            #"It helps me manage:\n"
            #"📝 Reminders & Notifications\n"
            #"✅ Tasks & Projects\n"
            #"🎯 Habits & Goals\n"
            #"📋 Notes & Ideas\n"
            #"🤖 AI Assistant\n\n"
            f"Try it now: @{bot_username}"
        )
        
        share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}&text={share_text}"
        
        await query.edit_message_text(
            "📤 *Share This Bot*\n\n"
            "Help others discover this productivity bot!\n\n"
            "Share with friends and family to help them:\n"
            "• Stay organized\n"
            "• Build better habits\n"
            "• Increase productivity\n"
            "• Achieve their goals\n\n"
            "Click the button below to share:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share Bot", url=share_url)],
                [InlineKeyboardButton("📋 Copy Bot Link", callback_data=f"copy_link_{bot_username}")],
                [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")]
            ])
        )
    
    @with_user
    @error_handler
    async def copy_bot_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot link for copying"""
        query = update.callback_query
        await query.answer()
        
        bot_username = context.bot.username
        bot_link = f"https://t.me/{bot_username}"
        
        await query.edit_message_text(
            f"📋 *Bot Link*\n\n"
            f"Copy this link to share:\n\n"
            f"`{bot_link}`\n\n"
            f"Tap and hold to copy the link above.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Share", callback_data="settings_share")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_notifications_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show notification settings"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            db_user = db.query(User).filter(User.id == user_id).first()
            if not db_user:
                return
            
            # Get current notification settings
            reminder_notif = "✅ Enabled" if db_user.reminder_notifications else "❌ Disabled"
            habit_notif = "✅ Enabled" if db_user.habit_reminders else "❌ Disabled"
            task_notif = "✅ Enabled" if db_user.task_deadlines else "❌ Disabled"
            summary_notif = "✅ Enabled" if db_user.weekly_summaries else "❌ Disabled"
        
        text = (
            "🔔 *Notification Settings*\n\n"
            f"🔔 Reminder notifications: {reminder_notif}\n"
            f"🎯 Habit reminders: {habit_notif} (daily at 9:00 AM)\n"
            f"⏰ Task deadlines: {task_notif}\n"
            f"📊 Weekly summaries: {summary_notif}\n\n"
            "Tap on any setting to toggle it:"
        )
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=Keyboards.notification_settings()
        )
    
    @with_user
    @error_handler
    async def toggle_notification_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle notification setting"""
        query = update.callback_query
        await query.answer()
        
        setting = query.data.split('_', 1)[1]  # notif_reminders -> reminders
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            db_user = db.query(User).filter(User.id == user_id).first()
            if not db_user:
                return
            
            # Toggle the setting
            if setting == "reminders":
                db_user.reminder_notifications = not db_user.reminder_notifications
                status = "enabled" if db_user.reminder_notifications else "disabled"
            elif setting == "habits":
                db_user.habit_reminders = not db_user.habit_reminders
                status = "enabled" if db_user.habit_reminders else "disabled"
            elif setting == "tasks":
                db_user.task_deadlines = not db_user.task_deadlines
                status = "enabled" if db_user.task_deadlines else "disabled"
            elif setting == "summaries":
                db_user.weekly_summaries = not db_user.weekly_summaries
                status = "enabled" if db_user.weekly_summaries else "disabled"
            else:
                return
            
            db.commit()
        
        # Show updated settings
        await self.show_notifications_settings(update, context)
    
    @with_user
    @error_handler
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel settings conversation"""
        await update.message.reply_text(
            "❌ Settings update cancelled.",
            reply_markup=Keyboards.settings_menu()
        )
        
        return ConversationHandler.END

    @with_user
    @error_handler
    async def get_custom_utc_offset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get custom UTC offset from user input"""
        logger.info(f"get_custom_utc_offset called with text: {update.message.text if update.message else 'NO MESSAGE'}")
        logger.info(f"Current conversation state: {context.user_data.get('conversation_state', 'NO STATE')}")
        
        utc_offset = update.message.text.strip()
        user_id = context.user_data['user_id']
        
        # Validate UTC offset format (UTC:+2, UTC:-5, UTC:+5:30)
        utc_pattern = r'^UTC:([+-])(\d{1,2})(?::(\d{2}))?$'
        match = re.match(utc_pattern, utc_offset)
        
        if not match:
            await update.message.reply_text(
                "❌ Invalid UTC offset format. Please use the format: UTC:+2 or UTC:-5\n\n"
                "Examples:\n"
                "• `UTC:+2` (2 hours ahead of UTC)\n"
                "• `UTC:-5` (5 hours behind UTC)\n"
                "• `UTC:+5:30` (5 hours 30 minutes ahead of UTC)"
            )
            return self.UTC_OFFSET_INPUT
        
        # Convert UTC offset to timezone name
        sign = match.group(1)
        hours = int(match.group(2))
        minutes = int(match.group(3)) if match.group(3) else 0
        
        # Validate minutes
        if minutes not in [0, 30]:
            await update.message.reply_text(
                "❌ Invalid minutes. Only 00 or 30 minutes are supported.\n\n"
                "Examples:\n"
                "• `UTC:+2` (2 hours ahead of UTC)\n"
                "• `UTC:-5` (5 hours behind UTC)\n"
                "• `UTC:+5:30` (5 hours 30 minutes ahead of UTC)"
            )
            return self.UTC_OFFSET_INPUT
        
        # Create timezone name like "Etc/GMT+2" or "Etc/GMT-5"
        # Note: pytz uses opposite sign convention for Etc/GMT
        if minutes == 0:
            if sign == '+':
                tz_name = f"Etc/GMT-{hours}"
            else:
                tz_name = f"Etc/GMT+{hours}"
        else:  # minutes == 30
            if sign == '+':
                tz_name = f"Etc/GMT-{hours}.5"
            else:
                tz_name = f"Etc/GMT+{hours}.5"
        
        # Validate the timezone
        try:
            pytz.timezone(tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            await update.message.reply_text(
                f"❌ Invalid timezone offset. The offset UTC:{sign}{hours}:{minutes:02d} is not supported.\n\n"
                "Please try a different offset."
            )
            return self.UTC_OFFSET_INPUT
        
        with get_db() as db:
            db_user = db.query(User).filter(User.id == user_id).first()
            if db_user:
                db_user.timezone = tz_name
                db.commit()
                # Update context with new timezone
                context.user_data['user_timezone'] = tz_name
        
        await update.message.reply_text(
            f"✅ *UTC Offset Updated*\n\n"
            f"UTC offset set to: *{utc_offset}*\n"
            f"Timezone: *{tz_name}*\n\n"
            f"All your reminders and schedules will now use this timezone.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        )
        
        return ConversationHandler.END

    @with_user
    @error_handler
    async def check_timezone_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if user has proper timezone set and prompt if needed"""
        user_timezone = context.user_data.get('user_timezone', 'UTC')
        
        if user_timezone == 'UTC':
            # User hasn't set a proper timezone, show warning
            warning_message = (
                "⚠️ *Timezone Notice*\n\n"
                "I detected you're using UTC timezone. For accurate reminders and scheduling, "
                "please set your local timezone.\n\n"
                "🕐 *Why this matters:*\n"
                "• Reminders will be sent at the correct local time\n"
                "• Task deadlines will be properly calculated\n"
                "• Habit reminders will match your daily schedule\n"
                "• All time-based features will work accurately\n\n"
                "Would you like to set your timezone now?"
            )
            
            keyboard = [
                [InlineKeyboardButton("⚙️ Set Timezone", callback_data="settings_timezone")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")],
                [InlineKeyboardButton("❌ Skip for now", callback_data="skip_timezone")]
            ]
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    warning_message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    warning_message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            return True
        
        return False
    
    @with_user
    @error_handler
    async def skip_timezone_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user skipping timezone setting"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "ℹ️ *Timezone Setting Skipped*\n\n"
            "You can always set your timezone later in Settings → Timezone Settings.\n\n"
            "⚠️ *Note:* Using UTC may cause reminders to arrive at unexpected times.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")],
                [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]
            ])
        )

    @with_user
    @error_handler
    async def handle_donate_star(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle star donation with multiple package options"""
        query = update.callback_query
        await query.answer()
        
        # Extract star amount from callback data (e.g., "donate_star_50" -> 50)
        star_amount = int(query.data.split('_')[-1])
        
        # For Telegram Stars (digital goods), provider_token should be empty string
        # Only physical goods require a provider token
        provider_token = ""  # Empty string for digital goods (Stars)
        
        # Prepare invoice
        title = f"Support the Bot with {star_amount} Telegram Stars"
        description = f"Donate {star_amount} Telegram Stars to help us keep the bot running!"
        payload = f"donate_star_{star_amount}"
        currency = "XTR"  # Telegram Stars currency code
        prices = [
            {
                "label": f"{star_amount} Telegram Stars",
                "amount": star_amount
            }
        ]
        
        try:
            await context.bot.send_invoice(
                chat_id=query.from_user.id,
                title=title,
                description=description,
                payload=payload,
                provider_token=provider_token,  # Empty string for digital goods
                currency=currency,
                prices=prices,
                start_parameter=f"donate_star_{star_amount}"
            )
        except Exception as e:
            logger.error(f"Error sending invoice: {e}")
            await query.edit_message_text(
                "❌ Error creating payment. Please try again later.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="settings_donate")]
                ])
            )

    @with_user
    @error_handler
    async def handle_pre_checkout_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pre-checkout query for Telegram Stars payments"""
        pre_checkout_query = update.pre_checkout_query
        
        # Log the pre-checkout query
        user_id = pre_checkout_query.from_user.id
        user_name = pre_checkout_query.from_user.first_name
        payload = pre_checkout_query.invoice_payload
        logger.info(f"Pre-checkout query from user {user_id} ({user_name}) for payload: {payload}")
        
        try:
            # Always approve the pre-checkout query for Stars donations
            # This is required within 10 seconds or the payment will fail
            await context.bot.answer_pre_checkout_query(
                pre_checkout_query_id=pre_checkout_query.id,
                ok=True
            )
            logger.info(f"Pre-checkout query approved for user {user_id}")
        except Exception as e:
            logger.error(f"Error answering pre-checkout query: {e}")
            # If we can't answer, try to answer with error
            try:
                await context.bot.answer_pre_checkout_query(
                    pre_checkout_query_id=pre_checkout_query.id,
                    ok=False,
                    error_message="Payment processing error. Please try again."
                )
            except Exception as error_e:
                logger.error(f"Error sending error response to pre-checkout query: {error_e}")

    @with_user
    @error_handler
    async def handle_successful_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle successful payment completion"""
        # This is called when a user successfully completes a payment
        successful_payment = update.message.successful_payment
        
        if successful_payment:
            # Extract star amount from payload (e.g., "donate_star_50" -> 50)
            payload = successful_payment.invoice_payload
            try:
                star_amount = int(payload.split('_')[-1])
            except (ValueError, IndexError):
                # Fallback: use total amount from payment
                star_amount = successful_payment.total_amount
                logger.warning(f"Could not parse star amount from payload '{payload}', using total amount: {star_amount}")
            
            # Log the successful donation
            user_id = context.user_data.get('user_id')
            user_name = update.message.from_user.first_name
            logger.info(f"Successful donation: {star_amount} stars from user {user_id} ({user_name})")
            logger.info(f"Payment details - Total amount: {successful_payment.total_amount}, Currency: {successful_payment.currency}")
            
            # Thank the user
            thank_you_message = (
                f"🎉 *Thank You for Your Support!*\n\n"
                f"You have successfully donated *{star_amount} Telegram Stars* to our bot!\n\n"
                f"Your generosity helps us:\n"
                f"• Keep the bot running 24/7\n"
                f"• Add new features and improvements\n"
                f"• Provide better AI capabilities\n"
                f"• Support our development team\n\n"
                f"🌟 *Transaction Details:*\n"
                f"• Amount: {star_amount} Stars\n"
                f"• Currency: XTR (Telegram Stars)\n"
                f"• Status: ✅ Completed\n\n"
                f"Thank you for believing in our project! 🙏\n"
                f"Your support means the world to us! 💝"
            )
            
            await update.message.reply_text(
                thank_you_message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")],
                    [InlineKeyboardButton("💝 Donate More", callback_data="settings_donate")]
                ])
            )
            
            # You could also store donation records in your database here
            # with get_db() as db:
            #     donation = Donation(
            #         user_id=user_id,
            #         amount=star_amount,
            #         currency="XTR",
            #         status="completed"
            #     )
            #     db.add(donation)
            #     db.commit()

    @with_user
    @error_handler
    async def show_stars_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the stars donation menu with different amounts"""
        query = update.callback_query
        await query.answer()
        
        stars_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Donate (5) Stars", callback_data="donate_star_5")],
            [InlineKeyboardButton("⭐ Donate (10) Stars", callback_data="donate_star_10")],
            [InlineKeyboardButton("⭐ Donate (50) Stars", callback_data="donate_star_50")],
            [InlineKeyboardButton("⭐ Donate (100) Stars", callback_data="donate_star_100")],
            [InlineKeyboardButton("⭐ Donate (250) Stars", callback_data="donate_star_250")],
            [InlineKeyboardButton("⭐ Donate (500) Stars", callback_data="donate_star_500")],
            [InlineKeyboardButton("🔙 Back to Donate", callback_data="settings_donate")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(
            "⭐ *Donate with Telegram Stars*\n\n"
            "Choose how many Stars you'd like to donate:\n\n"
            "Your Stars help us keep the bot running and add new features!\n\n"
            "Thank you for your generosity! 🙏",
            parse_mode='Markdown',
            reply_markup=stars_keyboard
        )