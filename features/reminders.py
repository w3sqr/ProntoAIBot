from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.database import get_db
from database.models import User, Reminder, ReminderStatus
from utils.decorators import with_user, error_handler
from utils.helpers import TimeHelper, TextHelper
from utils.keyboards import Keyboards
from loguru import logger
from datetime import datetime, timedelta
from typing import Optional
import pytz

# Conversation states
class ReminderFeature:
    REMINDER_TITLE = 0
    REMINDER_TIME = 1
    REMINDER_DESCRIPTION = 2
    REMINDER_EDIT_FIELD = 10
    REMINDER_EDIT_TITLE = 11
    REMINDER_EDIT_TIME = 12
    REMINDER_EDIT_DESCRIPTION = 13
    def __init__(self, scheduler, notification_service=None):
        self.scheduler = scheduler
        self.notification_service = notification_service
    
    @with_user
    @error_handler
    async def show_reminders_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show reminders main menu"""
        text = (
            "📝 *Reminders Management*\n\n"
            "Choose an option below:"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.reminders_menu()
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.reminders_menu()
            )
    
    @with_user
    @error_handler
    async def start_add_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start adding a new reminder"""
        query = update.callback_query
        await query.answer()
        
        # Check timezone setting and warn if needed
        user_timezone = context.user_data.get('user_timezone', 'UTC')
        if user_timezone == 'UTC':
            await query.edit_message_text(
                "⚠️ *Timezone Notice*\n\n"
                "You're currently using UTC timezone. For accurate reminder timing, "
                "consider setting your local timezone in Settings.\n\n"
                "This ensures your reminders arrive at the correct local time! 🕐",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚙️ Set Timezone", callback_data="settings_timezone")],
                    [InlineKeyboardButton("📝 Continue with Reminder", callback_data="reminder_add_continue")],
                    [InlineKeyboardButton("🔙 Back", callback_data="reminders_menu")]
                ])
            )
            return
        
        # Continue with normal reminder creation
        await query.edit_message_text(
            "📝 *Add New Reminder*\n\n"
            "Please enter the reminder title:",
            parse_mode='Markdown'
        )
        
        return self.REMINDER_TITLE
    
    @with_user
    @error_handler
    async def get_reminder_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get reminder title from user"""
        title = update.message.text.strip()
        
        if len(title) > 255:
            await update.message.reply_text(
                "❌ Title is too long. Please keep it under 255 characters."
            )
            return self.REMINDER_TITLE
        
        context.user_data['reminder_title'] = title
        
        await update.message.reply_text(
            f"✅ Title: *{TextHelper.escape_markdown(title)}*\n\n"
            "⏰ Now, when would you like to be reminded?\n\n"
            "Please use the format: *dd-mm-yyyy at hh:mm*\n\n"
            "Examples:\n"
            "• `27-06-2025 at 14:30`\n"
            "• `27-06-2025 at 2:30 PM`\n"
            "• `tomorrow at 9am`\n"
            "• `in 30 minutes`\n"
            "• `in 2 hours`",
            parse_mode='Markdown'
        )
        
        return self.REMINDER_TIME
    
    @with_user
    @error_handler
    async def get_reminder_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get reminder time from user"""
        time_str = update.message.text.strip()
        user_timezone = context.user_data['user_timezone']
        
        # Parse the time input
        remind_at = TimeHelper.parse_time_input(time_str, user_timezone)
        
        if not remind_at:
            await update.message.reply_text(
                "❌ I couldn't understand that time format. Please try again.\n\n"
                "Please use the format: *dd-mm-yyyy at hh:mm*\n\n"
                "Examples:\n"
                "• `27-06-2025 at 14:30`\n"
                "• `27-06-2025 at 2:30 PM`\n"
                "• `tomorrow at 9am`\n"
                "• `in 30 minutes`",
                parse_mode='Markdown'
            )
            return self.REMINDER_TIME
        
        if remind_at <= datetime.now(remind_at.tzinfo):
            await update.message.reply_text(
                "❌ The reminder time must be in the future. Please try again."
            )
            return self.REMINDER_TIME
        
        context.user_data['reminder_time'] = remind_at
        
        formatted_time = TimeHelper.format_datetime(remind_at, user_timezone)
        
        await update.message.reply_text(
            f"⏰ Reminder time: *{formatted_time}*\n\n"
            "📝 Would you like to add a description? (Optional)\n\n"
            "Send the description or type `/skip` to finish.",
            parse_mode='Markdown'
        )
        
        return self.REMINDER_DESCRIPTION
    
    @with_user
    @error_handler
    async def get_reminder_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get reminder description from user"""
        text = update.message.text.strip()
        if text.lower() == '/skip':
            description = None
        else:
            description = text
            if len(description) > 1000:
                await update.message.reply_text(
                    "❌ Description is too long. Please keep it under 1000 characters."
                )
                return self.REMINDER_DESCRIPTION
        
        # Save the reminder
        user_id = context.user_data['user_id']
        user_timezone = context.user_data['user_timezone'] or 'UTC'
        remind_at = context.user_data['reminder_time']
        
        # The remind_at is already properly timezone-aware from TimeHelper.parse_time_input
        # Just ensure it's in the user's timezone for storage
        local_tz = pytz.timezone(user_timezone)
        if remind_at.tzinfo is None:
            remind_at = local_tz.localize(remind_at)
        else:
            remind_at = remind_at.astimezone(local_tz)
        
        # Convert to UTC for scheduling
        remind_at_utc = remind_at.astimezone(pytz.UTC)
        
        with get_db() as db:
            reminder = Reminder(
                user_id=user_id,
                title=context.user_data['reminder_title'],
                description=description,
                remind_at=remind_at,  # store local time for display
                status=ReminderStatus.PENDING
            )
            db.add(reminder)
            db.commit()
            db.refresh(reminder)
            
            # Schedule the reminder using the notification service (in UTC)
            if self.notification_service:
                logger.info(f"Calling schedule_reminder_notification for reminder {reminder.id} at {remind_at_utc}")
                await self.notification_service.schedule_reminder_notification(reminder.id, remind_at_utc)
            else:
                logger.error("notification_service is not available!")
        
        formatted_time = TimeHelper.format_datetime(remind_at, user_timezone)
        message = (
            f"✅ *Reminder Created Successfully!*\n\n"
            f"📝 Title: {TextHelper.escape_markdown(context.user_data['reminder_title'])}\n"
            f"⏰ Time: {formatted_time}\n"
        )
        if description:
            message += f"📄 Description: {TextHelper.escape_markdown(description)}\n"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=Keyboards.reminders_menu()
        )
        
        # Clear conversation data
        context.user_data.pop('reminder_title', None)
        context.user_data.pop('reminder_time', None)
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def list_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List user's reminders"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        user_timezone = context.user_data['user_timezone']
        
        with get_db() as db:
            reminders = db.query(Reminder).filter(
                Reminder.user_id == user_id,
                Reminder.status == ReminderStatus.PENDING
            ).order_by(Reminder.remind_at).limit(10).all()
            # Extract all needed data while session is open
            reminders_data = [
                {
                    'title': r.title,
                    'remind_at': r.remind_at,
                    'id': r.id,
                    'description': r.description
                }
                for r in reminders
            ]
        
        if not reminders_data:
            await query.edit_message_text(
                "📝 *Your Reminders*\n\n"
                "You don't have any active reminders.\n"
                "Use the button below to create one!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Reminder", callback_data="reminder_add")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
            return
        
        message = "📝 *Your Active Reminders*\n\n"
        keyboard = []
        
        for i, reminder in enumerate(reminders_data, 1):
            formatted_time = TimeHelper.format_datetime(reminder['remind_at'], user_timezone)
            message += f"*{i}. {TextHelper.escape_markdown(reminder['title'])}*\n"
            message += f"   ⏰ _{formatted_time}_\n"
            if reminder['description']:
                message += f"   📄 _{TextHelper.escape_markdown(reminder['description'])}_\n"
            message += "──────────────\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"✏️ Edit #{i}", 
                    callback_data=f"reminder_edit_{reminder['id']}"
                ),
                InlineKeyboardButton(
                    f"🗑️ Delete #{i}", 
                    callback_data=f"reminder_delete_{reminder['id']}"
                )
            ])
        
        message = message.rstrip('─\n') + "\n"
        keyboard.append([InlineKeyboardButton("➕ Add New", callback_data="reminder_add")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @staticmethod
    async def send_reminder(telegram_id: int, reminder_id: int):
        """Send reminder notification to user"""
        try:
            from database.database import get_db
            from database.models import Reminder, ReminderStatus, User
            from utils.helpers import TimeHelper, TextHelper
            from loguru import logger
            with get_db() as db:
                reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
                if not reminder or reminder.status != ReminderStatus.PENDING:
                    return
                user = db.query(User).filter(User.id == reminder.user_id).first()
                if not user:
                    return
                message = f"🔔 *Reminder Alert!*\n\n"
                message += f"📝 {TextHelper.escape_markdown(reminder.title)}\n"
                if reminder.description:
                    message += f"\n📄 {TextHelper.escape_markdown(reminder.description)}\n"
                message += f"\n⏰ Scheduled for: {TimeHelper.format_datetime(reminder.remind_at, user.timezone)}"
                # Mark reminder as completed
                reminder.status = ReminderStatus.COMPLETED
                db.commit()
                # Send notification (this would be handled by the bot instance)
                from bot import bot_instance
                if bot_instance:
                    await bot_instance.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode='Markdown'
                    )
        except Exception as e:
            logger.error(f"Error sending reminder {reminder_id}: {e}")
    
    @with_user
    @error_handler
    async def delete_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a reminder"""
        query = update.callback_query
        await query.answer()
        
        reminder_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            reminder = db.query(Reminder).filter(
                Reminder.id == reminder_id,
                Reminder.user_id == user_id
            ).first()
            
            if not reminder:
                await query.edit_message_text("❌ Reminder not found.")
                return
            
            # Extract reminder data while session is open
            reminder_title = reminder.title
            
            # Cancel scheduled job
            if reminder.job_id:
                try:
                    self.scheduler.remove_job(reminder.job_id)
                except:
                    pass  # Job might not exist
            
            # Delete reminder
            db.delete(reminder)
            db.commit()
        
        await query.edit_message_text(
            f"✅ Reminder '*{TextHelper.escape_markdown(reminder_title)}*' has been deleted.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Reminders", callback_data="reminder_list")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel reminder creation conversation"""
        await update.message.reply_text(
            "❌ Reminder creation cancelled.",
            reply_markup=Keyboards.reminders_menu()
        )
        
        # Clear conversation data
        context.user_data.pop('reminder_title', None)
        context.user_data.pop('reminder_time', None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def edit_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start editing a reminder: ask which field to edit"""
        query = update.callback_query
        await query.answer()
        reminder_id = int(query.data.split('_')[-1])
        context.user_data['edit_reminder_id'] = reminder_id
        # Show menu to pick field
        keyboard = [
            [InlineKeyboardButton("✏️ Title", callback_data="edit_field_title")],
            [InlineKeyboardButton("⏰ Time", callback_data="edit_field_time")],
            [InlineKeyboardButton("📄 Description", callback_data="edit_field_description")],
            [InlineKeyboardButton("❌ Cancel", callback_data="edit_field_cancel")],
        ]
        await query.edit_message_text(
            "What do you want to edit?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return self.REMINDER_EDIT_FIELD

    @with_user
    @error_handler
    async def edit_field_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "edit_field_title":
            await query.edit_message_text("Send the new title:")
            return self.REMINDER_EDIT_TITLE
        elif data == "edit_field_time":
            await query.edit_message_text("Send the new time (e.g., 14:30, tomorrow at 9am):")
            return self.REMINDER_EDIT_TIME
        elif data == "edit_field_description":
            await query.edit_message_text("Send the new description (or /skip to clear):")
            return self.REMINDER_EDIT_DESCRIPTION
        else:
            await query.edit_message_text("Edit cancelled.", reply_markup=Keyboards.reminders_menu())
            return ConversationHandler.END

    @with_user
    @error_handler
    async def edit_reminder_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        new_title = update.message.text.strip()
        reminder_id = context.user_data.get('edit_reminder_id')
        with get_db() as db:
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            if not reminder:
                await update.message.reply_text("❌ Reminder not found.")
                return ConversationHandler.END
            reminder.title = new_title
            db.commit()
        await update.message.reply_text("✅ Title updated!", reply_markup=Keyboards.reminders_menu())
        return ConversationHandler.END

    @with_user
    @error_handler
    async def edit_reminder_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        time_str = update.message.text.strip()
        user_timezone = context.user_data['user_timezone']
        remind_at = TimeHelper.parse_time_input(time_str, user_timezone)
        if not remind_at or remind_at <= datetime.now(remind_at.tzinfo):
            await update.message.reply_text("❌ Invalid or past time. Please try again.")
            return self.REMINDER_EDIT_TIME
        
        reminder_id = context.user_data.get('edit_reminder_id')
        user_timezone = context.user_data['user_timezone'] or 'UTC'
        
        # The remind_at is already properly timezone-aware from TimeHelper.parse_time_input
        # Just ensure it's in the user's timezone for storage
        local_tz = pytz.timezone(user_timezone)
        if remind_at.tzinfo is None:
            remind_at = local_tz.localize(remind_at)
        else:
            remind_at = remind_at.astimezone(local_tz)
        
        # Convert to UTC for scheduling
        remind_at_utc = remind_at.astimezone(pytz.UTC)
        
        with get_db() as db:
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            if not reminder:
                await update.message.reply_text("❌ Reminder not found.")
                return ConversationHandler.END
            
            reminder.remind_at = remind_at  # store local time
            db.commit()
            
            # Reschedule the notification
            if self.notification_service:
                logger.info(f"Rescheduling reminder {reminder.id} to {remind_at_utc}")
                await self.notification_service.schedule_reminder_notification(reminder.id, remind_at_utc)
            else:
                logger.error("notification_service is not available!")
        
        formatted_time = TimeHelper.format_datetime(remind_at, user_timezone)
        await update.message.reply_text(
            f"✅ Time updated to: *{formatted_time}*!",
            parse_mode='Markdown',
            reply_markup=Keyboards.reminders_menu()
        )
        return ConversationHandler.END

    @with_user
    @error_handler
    async def edit_reminder_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        desc = update.message.text.strip() if update.message else None
        if desc and desc.lower() == '/skip':
            desc = None
        reminder_id = context.user_data.get('edit_reminder_id')
        with get_db() as db:
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            if not reminder:
                if update.message:
                    await update.message.reply_text("❌ Reminder not found.")
                elif update.callback_query:
                    await update.callback_query.edit_message_text("❌ Reminder not found.")
                return ConversationHandler.END
            reminder.description = desc
            db.commit()
        response_text = "✅ Description updated!"
        if update.message:
            await update.message.reply_text(response_text, reply_markup=Keyboards.reminders_menu())
        elif update.callback_query:
            await update.callback_query.edit_message_text(response_text, reply_markup=Keyboards.reminders_menu())
        return ConversationHandler.END

    @with_user
    @error_handler
    async def mark_reminder_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mark reminder as done from notification"""
        query = update.callback_query
        await query.answer()
        
        reminder_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            reminder = db.query(Reminder).filter(
                Reminder.id == reminder_id,
                Reminder.user_id == user_id
            ).first()
            
            if not reminder:
                try:
                    await query.edit_message_text("❌ Reminder not found.")
                except Exception as e:
                    logger.error(f"Failed to edit message for reminder not found: {e}")
                return
            
            # Extract reminder data while session is open
            reminder_title = reminder.title
            
            reminder.status = ReminderStatus.COMPLETED
            db.commit()
        
        try:
            await query.edit_message_text(
                f"✅ *Reminder Completed!*\n\n"
                f"📝 {TextHelper.escape_markdown(reminder_title)}\n\n"
                f"Great job! Keep up the good work! 💪",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Reminders", callback_data="reminder_list")],
                    [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
                ])
            )
        except Exception as e:
            logger.error(f"Failed to edit message for reminder completion: {e}")
            # Try to send a new message instead
            try:
                await query.message.reply_text(
                    f"✅ *Reminder Completed!*\n\n"
                    f"📝 {TextHelper.escape_markdown(reminder_title)}\n\n"
                    f"Great job! Keep up the good work! 💪",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 View Reminders", callback_data="reminder_list")],
                        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
                    ])
                )
            except Exception as reply_error:
                logger.error(f"Failed to send reply message for reminder completion: {reply_error}")
    
    @with_user
    @error_handler
    async def snooze_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Snooze reminder for 15 minutes"""
        query = update.callback_query
        await query.answer()
        
        reminder_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        user_timezone = context.user_data['user_timezone'] or 'UTC'
        
        with get_db() as db:
            reminder = db.query(Reminder).filter(
                Reminder.id == reminder_id,
                Reminder.user_id == user_id
            ).first()
            
            if not reminder:
                try:
                    await query.edit_message_text("❌ Reminder not found.")
                except Exception as e:
                    logger.error(f"Failed to edit message for reminder not found (snooze): {e}")
                return
            
            # Extract reminder data while session is open
            reminder_title = reminder.title
            
            # Calculate new time (15 minutes from now)
            local_tz = pytz.timezone(user_timezone)
            now = datetime.now(local_tz)
            new_time = now + timedelta(minutes=15)
            
            reminder.remind_at = new_time
            db.commit()
            
            # Reschedule the notification
            if self.notification_service:
                new_time_utc = new_time.astimezone(pytz.UTC)
                logger.info(f"Snoozing reminder {reminder.id} to {new_time_utc}")
                await self.notification_service.schedule_reminder_notification(reminder.id, new_time_utc)
            else:
                logger.error("notification_service is not available!")
        
        formatted_time = TimeHelper.format_datetime(new_time, user_timezone)
        try:
            await query.edit_message_text(
                f"⏰ *Reminder Snoozed!*\n\n"
                f"📝 {TextHelper.escape_markdown(reminder_title)}\n"
                f"⏰ New time: {formatted_time}\n\n"
                f"You'll be reminded again in 15 minutes.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Reminders", callback_data="reminder_list")],
                    [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
                ])
            )
        except Exception as e:
            logger.error(f"Failed to edit message for reminder snooze: {e}")
            # Try to send a new message instead
            try:
                await query.message.reply_text(
                    f"⏰ *Reminder Snoozed!*\n\n"
                    f"📝 {TextHelper.escape_markdown(reminder_title)}\n"
                    f"⏰ New time: {formatted_time}\n\n"
                    f"You'll be reminded again in 15 minutes.",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 View Reminders", callback_data="reminder_list")],
                        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
                    ])
                )
            except Exception as reply_error:
                logger.error(f"Failed to send reply message for reminder snooze: {reply_error}")