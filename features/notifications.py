"""
Notification Service for Productivity Bot
Handles all notification types: reminders, habits, tasks, and weekly summaries
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from telegram import Bot
from telegram.ext import ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from database.database import get_db
from database.models import User, Reminder, Task, Habit, HabitLog, TaskStatus, ReminderStatus, UserStatus
from utils.logger import setup_logger
from utils.keyboards import Keyboards

logger = setup_logger()

# Global bot instance for notifications
bot_instance = None

def sync_reminder_job(reminder_id, bot_instance=None):
    import asyncio
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the notification job in the new loop
        loop.run_until_complete(NotificationService._send_reminder_notification_job(reminder_id, bot_instance))
    except Exception as e:
        logger.error(f"Failed to execute reminder job for reminder {reminder_id}: {e}")
    finally:
        # Clean up the loop
        try:
            loop.close()
        except:
            pass

# Module-level job wrappers for APScheduler

def habit_reminder_job_wrapper(user_id):
    from features.notifications import bot_instance
    if bot_instance:
        asyncio.create_task(bot_instance._send_habit_reminder_job(user_id))

def weekly_summary_job_wrapper(user_id):
    from features.notifications import bot_instance
    if bot_instance:
        asyncio.create_task(bot_instance._send_weekly_summary_job(user_id))

def task_deadline_job_wrapper(user_id):
    from features.notifications import bot_instance
    if bot_instance:
        asyncio.create_task(bot_instance._send_task_deadline_job(user_id))

class NotificationService:
    def __init__(self, bot: Bot, scheduler: AsyncIOScheduler):
        self.bot = bot
        self.scheduler = scheduler
        self.logger = logger
        self.main_loop = None  # Will be set at bot startup
        global bot_instance
        bot_instance = self
        
    async def setup_notifications(self):
        """Setup all per-user notification jobs (no global CronTriggers)"""
        try:
            with get_db() as db:
                users = db.query(User).filter(User.status == UserStatus.ACTIVE).all()
                for user in users:
                    # Schedule habit reminder if enabled
                    if user.habit_reminders:
                        await self.schedule_next_habit_reminder(user)
                    # Schedule weekly summary if enabled
                    if user.weekly_summaries:
                        await self.schedule_next_weekly_summary(user)
                    # Schedule task deadline if enabled
                    if user.task_deadlines:
                        await self.schedule_next_task_deadline(user)
            self.logger.info("Per-user notification jobs scheduled successfully")
        except Exception as e:
            self.logger.error(f"Failed to setup per-user notification jobs: {e}")

    async def schedule_next_habit_reminder(self, user):
        """Schedule the next daily habit reminder for a user at 9:00 AM local time (converted to UTC)"""
        try:
            from pytz import timezone, UTC
            now = datetime.now(UTC)
            user_tz = timezone(user.timezone or 'UTC')
            # Fixed time: 9:00 AM local time
            hour, minute = 9, 0
            # Next notification in user's local time
            next_local = now.astimezone(user_tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_local <= now.astimezone(user_tz):
                next_local += timedelta(days=1)
            next_utc = next_local.astimezone(UTC)
            job_id = f"habit_reminder_{user.id}"
            # Remove existing job if any
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
            self.scheduler.add_job(
                habit_reminder_job_wrapper,
                DateTrigger(run_date=next_utc),
                args=[user.id],
                id=job_id,
                replace_existing=True
            )
            self.logger.info(f"Scheduled habit reminder for user {user.id} at {next_utc}")
        except Exception as e:
            self.logger.error(f"Failed to schedule habit reminder for user {user.id}: {e}")

    async def schedule_next_weekly_summary(self, user):
        """Schedule the next weekly summary for a user at 10:00 AM local time on Sunday (converted to UTC)"""
        try:
            from pytz import timezone, UTC
            now = datetime.now(UTC)
            user_tz = timezone(user.timezone or 'UTC')
            # Fixed time: 10:00 AM local time on Sunday
            hour, minute = 10, 0
            # Find next Sunday at 10:00 AM
            current_local = now.astimezone(user_tz)
            days_until_sunday = (6 - current_local.weekday()) % 7
            if days_until_sunday == 0 and current_local.hour >= hour:
                days_until_sunday = 7
            next_sunday = current_local.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_until_sunday)
            next_utc = next_sunday.astimezone(UTC)
            job_id = f"weekly_summary_{user.id}"
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
            self.scheduler.add_job(
                weekly_summary_job_wrapper,
                DateTrigger(run_date=next_utc),
                args=[user.id],
                id=job_id,
                replace_existing=True
            )
            self.logger.info(f"Scheduled weekly summary for user {user.id} at {next_utc}")
        except Exception as e:
            self.logger.error(f"Failed to schedule weekly summary for user {user.id}: {e}")

    async def schedule_next_task_deadline(self, user):
        """Schedule the next daily task deadline notification for a user at 8:00 AM local time (converted to UTC)"""
        try:
            from pytz import timezone, UTC
            now = datetime.now(UTC)
            user_tz = timezone(user.timezone or 'UTC')
            # Fixed time: 8:00 AM local time
            hour, minute = 8, 0
            next_local = now.astimezone(user_tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_local <= now.astimezone(user_tz):
                next_local += timedelta(days=1)
            next_utc = next_local.astimezone(UTC)
            job_id = f"task_deadline_{user.id}"
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
            self.scheduler.add_job(
                task_deadline_job_wrapper,
                DateTrigger(run_date=next_utc),
                args=[user.id],
                id=job_id,
                replace_existing=True
            )
            self.logger.info(f"Scheduled task deadline for user {user.id} at {next_utc}")
        except Exception as e:
            self.logger.error(f"Failed to schedule task deadline for user {user.id}: {e}")

    async def _send_habit_reminder_job(self, user_id):
        """Send daily habit reminder to a user and reschedule next one"""
        try:
            with get_db() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user or not user.habit_reminders:
                    logger.error(f"User not found or reminders disabled for user_id={user_id}")
                    return
                active_habits = db.query(Habit).filter(
                    Habit.user_id == user.id,
                    Habit.is_active == True
                ).all()
                if not active_habits:
                    return
                today = datetime.utcnow().date()
                habits_to_log = []
                for habit in active_habits:
                    today_log = db.query(HabitLog).filter(
                        HabitLog.habit_id == habit.id,
                        HabitLog.date >= today
                    ).first()
                    if not today_log:
                        habits_to_log.append(habit)
                if habits_to_log:
                    message = "🎯 *Daily Habit Check-in*\n\n"
                    message += "Don't forget to log your progress for:\n\n"
                    for habit in habits_to_log:
                        message += f"• {habit.name}\n"
                    message += "\nTap the button below to log your progress!"
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode='Markdown',
                        reply_markup=Keyboards.habit_reminder()
                    )
            await self.schedule_next_habit_reminder(user)
        except Exception as e:
            logger.error(f"Failed to send habit reminder to user {user_id}: {e}")

    async def _send_weekly_summary_job(self, user_id):
        """Send weekly summary to a user and reschedule next one"""
        try:
            with get_db() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user or not user.weekly_summaries:
                    logger.error(f"User not found or summaries disabled for user_id={user_id}")
                    return
                now = datetime.utcnow()
                week_start = now - timedelta(days=now.weekday())
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                completed_tasks = db.query(Task).filter(
                    Task.user_id == user.id,
                    Task.status == TaskStatus.COMPLETED,
                    Task.completed_at >= week_start
                ).count()
                total_tasks = db.query(Task).filter(
                    Task.user_id == user.id,
                    Task.created_at >= week_start
                ).count()
                completed_reminders = db.query(Reminder).filter(
                    Reminder.user_id == user.id,
                    Reminder.status == ReminderStatus.COMPLETED,
                    Reminder.updated_at >= week_start
                ).count()
                total_reminders = db.query(Reminder).filter(
                    Reminder.user_id == user.id,
                    Reminder.created_at >= week_start
                ).count()
                active_habits = db.query(Habit).filter(
                    Habit.user_id == user.id,
                    Habit.is_active == True
                ).all()
                habit_completion = 0
                total_habit_days = 0
                for habit in active_habits:
                    completed_days = db.query(HabitLog).filter(
                        HabitLog.habit_id == habit.id,
                        HabitLog.date >= week_start
                    ).count()
                    habit_completion += completed_days
                    total_habit_days += 7
                habit_rate = (habit_completion / total_habit_days * 100) if total_habit_days > 0 else 0
                message = "📊 *Weekly Productivity Summary*\n\n"
                message += f"📅 Week of {week_start.strftime('%B %d, %Y')}\n\n"
                if total_tasks > 0:
                    task_rate = (completed_tasks / total_tasks * 100)
                    message += f"✅ *Tasks:* {completed_tasks}/{total_tasks} ({task_rate:.1f}%)\n"
                if total_reminders > 0:
                    reminder_rate = (completed_reminders / total_reminders * 100)
                    message += f"🔔 *Reminders:* {completed_reminders}/{total_reminders} ({reminder_rate:.1f}%)\n"
                if total_habit_days > 0:
                    message += f"🎯 *Habits:* {habit_completion}/{total_habit_days} days ({habit_rate:.1f}%)\n"
                message += "\nKeep up the great work! 💪"
                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=Keyboards.weekly_summary()
                )
            await self.schedule_next_weekly_summary(user)
        except Exception as e:
            logger.error(f"Failed to send weekly summary to user {user_id}: {e}")

    async def _send_task_deadline_job(self, user_id):
        """Send daily task deadline notification to a user and reschedule next one"""
        try:
            with get_db() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user or not user.task_deadlines:
                    logger.error(f"User not found or deadlines disabled for user_id={user_id}")
                    return
                now = datetime.utcnow()
                tomorrow = now + timedelta(days=1)
                upcoming_tasks = db.query(Task).filter(
                    Task.user_id == user.id,
                    Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
                    Task.due_date >= now,
                    Task.due_date <= tomorrow
                ).all()
                if upcoming_tasks:
                    message = "⏰ *Upcoming Task Deadlines*\n\n"
                    for task in upcoming_tasks:
                        time_left = task.due_date - now
                        hours_left = int(time_left.total_seconds() / 3600)
                        if hours_left < 1:
                            time_str = "Due now!"
                        elif hours_left < 24:
                            time_str = f"Due in {hours_left} hours"
                        else:
                            days_left = int(hours_left / 24)
                            time_str = f"Due in {days_left} days"
                        priority_emoji = {
                            "low": "🟢",
                            "medium": "🟡", 
                            "high": "🟠",
                            "urgent": "🔴"
                        }.get(task.priority.value, "⚪")
                        message += f"{priority_emoji} *{task.title}*\n"
                        message += f"   {time_str}\n\n"
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode='Markdown',
                        reply_markup=Keyboards.task_deadline_reminder()
                    )
            await self.schedule_next_task_deadline(user)
        except Exception as e:
            logger.error(f"Failed to check task deadlines for user {user_id}: {e}")

    @staticmethod
    async def _send_reminder_notification_job(reminder_id: int, bot_instance):
        """Send a reminder notification (static method for scheduler)"""
        try:
            logger.info(f"Running _send_reminder_notification_job for reminder_id={reminder_id}")
            if not bot_instance:
                logger.error("Bot instance not available for reminder notification")
                return
            with get_db() as db:
                reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
                if not reminder:
                    logger.error(f"Reminder {reminder_id} not found in DB")
                    return
                user = db.query(User).filter(User.id == reminder.user_id).first()
                if not user or not user.reminder_notifications:
                    logger.error(f"User not found or notifications disabled for user_id={reminder.user_id}")
                    return
                
                # Extract reminder data while session is open
                reminder_title = reminder.title
                reminder_description = reminder.description
                reminder_time = reminder.remind_at
                user_telegram_id = user.telegram_id
                
                # Mark reminder as completed
                reminder.status = ReminderStatus.COMPLETED
                db.commit()
                
                # Send notification
                message = f"🔔 *Reminder*\n\n"
                message += f"*{reminder_title}*\n"
                if reminder_description:
                    message += f"{reminder_description}\n\n"
                message += f"⏰ {reminder_time.strftime('%Y-%m-%d %H:%M')}"
                try:
                    # Use the bot instance directly to send the message
                    await bot_instance.send_message(
                        chat_id=user_telegram_id,
                        text=message,
                        parse_mode='Markdown',
                        reply_markup=Keyboards.reminder_completed(reminder_id)
                    )
                    logger.info(f"Sent reminder notification to user {user_telegram_id}")
                except Exception as send_err:
                    logger.error(f"Failed to send Telegram message: {send_err}")
                    # Try to create a new bot instance if the current one is closed
                    try:
                        from config import settings
                        from telegram import Bot
                        new_bot = Bot(token=settings.bot_token)
                        await new_bot.send_message(
                            chat_id=user_telegram_id,
                            text=message,
                            parse_mode='Markdown',
                            reply_markup=Keyboards.reminder_completed(reminder_id)
                        )
                        logger.info(f"Sent reminder notification with new bot instance to user {user_telegram_id}")
                    except Exception as new_bot_err:
                        logger.error(f"Failed to send with new bot instance: {new_bot_err}")
        except Exception as e:
            logger.error(f"Failed to send reminder notification: {e}")

    async def send_custom_notification(self, user_id: int, message: str, reply_markup=None):
        """Send a custom notification to a specific user"""
        try:
            with get_db() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return
                
                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            self.logger.error(f"Failed to send custom notification: {e}")

    async def schedule_reminder_notification(self, reminder_id: int, remind_at: datetime):
        """Schedule a reminder notification (one-off)"""
        try:
            job_id = f"reminder_{reminder_id}"
            logger.info(f"Scheduling reminder job: {job_id} at {remind_at}")
            # Remove existing job if it exists
            try:
                self.scheduler.remove_job(job_id)
            except Exception as e:
                logger.info(f"No existing job to remove for {job_id}: {e}")
            # Schedule new notification using the sync wrapper with bot instance
            self.scheduler.add_job(
                sync_reminder_job,
                DateTrigger(run_date=remind_at),
                args=[reminder_id, self.bot],
                id=job_id,
                replace_existing=True
            )
            logger.info(f"Scheduled reminder notification for reminder {reminder_id} at {remind_at}")
        except Exception as e:
            logger.error(f"Failed to schedule reminder notification: {e}") 