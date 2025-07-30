from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.database import get_db
from database.models import User, Habit, HabitLog, HabitFrequency
from utils.decorators import with_user, error_handler
from utils.helpers import TextHelper
from utils.keyboards import Keyboards
from loguru import logger
from datetime import datetime, date, timedelta
from sqlalchemy import func
from typing import Optional
import pytz

# Conversation states
class HabitFeature:
    HABIT_NAME = 0
    HABIT_DESCRIPTION = 1
    HABIT_FREQUENCY = 2
    HABIT_TARGET = 3
    HABIT_UNIT = 4
    EDIT_HABIT_NAME = 5
    CUSTOM_UPDATE_VALUE = 6

    def __init__(self, notification_service=None):
        self.notification_service = notification_service

    @with_user
    @error_handler
    async def show_habits_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show habits main menu"""
        text = (
            "🎯 *Habits Management*\n\n"
            "Choose an option below:"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.habits_menu()
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.habits_menu()
            )
    
    @with_user
    @error_handler
    async def start_add_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start adding a new habit"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "🎯 *Add New Habit*\n\n"
            "What habit would you like to track?\n"
            "Please enter the habit name:",
            parse_mode='Markdown'
        )
        
        return self.HABIT_NAME
    
    @with_user
    @error_handler
    async def get_habit_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get habit name from user"""
        name = update.message.text.strip()
        
        if len(name) > 255:
            await update.message.reply_text(
                "❌ Habit name is too long. Please keep it under 255 characters."
            )
            return self.HABIT_NAME
        
        context.user_data['habit_name'] = name
        
        await update.message.reply_text(
            f"🎯 Habit: *{TextHelper.escape_markdown(name)}*\n\n"
            "📝 Please enter a description (optional):\n\n"
            "This can help you remember why this habit is important.\n"
            "Send the description or type `/skip` to continue.",
            parse_mode='Markdown'
        )
        
        return self.HABIT_DESCRIPTION
    
    @with_user
    @error_handler
    async def get_habit_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get habit description from user"""
        text = update.message.text.strip() if update.message else None
        if text and text.lower() == '/skip':
            description = None
        else:
            description = text
            if description and len(description) > 1000:
                await update.message.reply_text(
                    "❌ Description is too long. Please keep it under 1000 characters."
                )
                return self.HABIT_DESCRIPTION
        context.user_data['habit_description'] = description
        keyboard = [
            [InlineKeyboardButton("📅 Daily", callback_data="freq_daily")],
            [InlineKeyboardButton("📆 Weekly", callback_data="freq_weekly")],
            [InlineKeyboardButton("🗓️ Monthly", callback_data="freq_monthly")]
        ]
        await update.message.reply_text(
            "🔄 *Select Habit Frequency:*\n\n"
            "How often do you want to track this habit?",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return self.HABIT_FREQUENCY
    
    @with_user
    @error_handler
    async def get_habit_frequency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get habit frequency from user"""
        query = update.callback_query
        await query.answer()
        
        frequency_map = {
            'freq_daily': HabitFrequency.DAILY,
            'freq_weekly': HabitFrequency.WEEKLY,
            'freq_monthly': HabitFrequency.MONTHLY
        }
        
        frequency = frequency_map.get(query.data, HabitFrequency.DAILY)
        context.user_data['habit_frequency'] = frequency
        
        frequency_emoji = {
            HabitFrequency.DAILY: "📅",
            HabitFrequency.WEEKLY: "📆",
            HabitFrequency.MONTHLY: "🗓️"
        }
        
        await query.edit_message_text(
            f"🔄 Frequency: {frequency_emoji[frequency]} *{frequency.value.title()}*\n\n"
            "🎯 What's your target?\n\n"
            "Enter a number (e.g., 8 for 8 glasses of water, 30 for 30 minutes of exercise):",
            parse_mode='Markdown'
        )
        
        return self.HABIT_TARGET
    
    @with_user
    @error_handler
    async def get_habit_target(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get habit target value from user"""
        try:
            target = int(update.message.text.strip())
            if target <= 0:
                raise ValueError("Target must be positive")
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a valid positive number for your target."
            )
            return self.HABIT_TARGET
        
        context.user_data['habit_target'] = target
        
        await update.message.reply_text(
            f"🎯 Target: *{target}*\n\n"
            "📏 What unit would you like to use?\n\n"
            "Examples: glasses, minutes, times, pages, kilometers\n"
            "Or type `/skip` for no unit.",
            parse_mode='Markdown'
        )
        
        return self.HABIT_UNIT
    
    @with_user
    @error_handler
    async def get_habit_unit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get habit unit from user"""
        text = update.message.text.strip() if update.message else None
        if text and text.lower() == '/skip':
            unit = None
        else:
            unit = text
            if unit and len(unit) > 50:
                await update.message.reply_text(
                    "❌ Unit is too long. Please keep it under 50 characters."
                )
                return self.HABIT_UNIT
        # Save the habit
        user_id = context.user_data['user_id']
        name = context.user_data['habit_name']
        description = context.user_data.get('habit_description')
        frequency = context.user_data['habit_frequency']
        target = context.user_data['habit_target']
        with get_db() as db:
            habit = Habit(
                user_id=user_id,
                name=name,
                description=description,
                frequency=frequency,
                target_value=target,
                unit=unit,
                is_active=True,
                streak_count=0,
                best_streak=0
            )
            db.add(habit)
            db.commit()
            db.refresh(habit)
        
        # Format confirmation message
        frequency_emoji = {
            HabitFrequency.DAILY: "📅",
            HabitFrequency.WEEKLY: "📆",
            HabitFrequency.MONTHLY: "🗓️"
        }
        
        message = (
            f"🎉 *Habit Created Successfully!*\n\n"
            f"🎯 Name: {TextHelper.escape_markdown(name)}\n"
            f"🔄 Frequency: {frequency_emoji[frequency]} {frequency.value.title()}\n"
            f"📊 Target: {target}"
        )
        
        if unit:
            message += f" {unit}"
        
        if description:
            message += f"\n📝 Description: {TextHelper.escape_markdown(description)}"
        
        message += "\n\n🚀 Start tracking your progress today!"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=Keyboards.habits_menu()
        )
        
        # Clear conversation data
        for key in ['habit_name', 'habit_description', 'habit_frequency', 'habit_target']:
            context.user_data.pop(key, None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def list_habits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List user's habits"""
        query = update.callback_query
        await query.answer()
        user_id = context.user_data['user_id']
        with get_db() as db:
            habits = db.query(Habit).filter(
                Habit.user_id == user_id,
                Habit.is_active == True
            ).order_by(Habit.created_at).all()
            # Extract all needed fields while session is open
            habit_data = []
            for habit in habits:
                habit_data.append({
                    'id': habit.id,
                    'name': habit.name,
                    'frequency': habit.frequency,
                    'target_value': habit.target_value,
                    'unit': habit.unit,
                    'streak_count': habit.streak_count,
                    'best_streak': habit.best_streak
                })
        if not habit_data:
            await query.edit_message_text(
                "🎯 *Your Habits*\n\n"
                "You don't have any habits to track yet.\n"
                "Use the button below to create one!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Habit", callback_data="habit_add")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
            return
        message = "🎯 *Your Active Habits*\n\n"
        keyboard = []
        frequency_emoji = {
            HabitFrequency.DAILY: "📅",
            HabitFrequency.WEEKLY: "📆",
            HabitFrequency.MONTHLY: "🗓️"
        }
        for i, habit in enumerate(habit_data, 1):
            message += f"{i}. *{TextHelper.escape_markdown(habit['name'])}*\n"
            message += f"   {frequency_emoji[habit['frequency']]} {habit['frequency'].value.title()}\n"
            message += f"   🎯 Target: {habit['target_value']}"
            if habit['unit']:
                message += f" {habit['unit']}"
            message += f"\n   🔥 Current streak: {habit['streak_count']}\n"
            message += f"   🏆 Best streak: {habit['best_streak']}\n\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Log #{i}", 
                    callback_data=f"log_habit_{habit['id']}"
                ),
                InlineKeyboardButton(
                    f"📊 Stats #{i}", 
                    callback_data=f"habit_stats_{habit['id']}"
                ),
                InlineKeyboardButton(
                    f"✏️ Edit #{i}",
                    callback_data=f"habit_edit_{habit['id']}"
                ),
                InlineKeyboardButton(
                    f"🗑️ Delete #{i}",
                    callback_data=f"habit_delete_{habit['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton("➕ Add New", callback_data="habit_add")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def log_habit_progress(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show habits available for logging"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            habits = db.query(Habit).filter(
                Habit.user_id == user_id,
                Habit.is_active == True
            ).order_by(Habit.name).all()
            
            # Extract all needed fields while session is open
            habit_data = []
            for habit in habits:
                # Check if already logged today
                today = date.today()
                existing_log = db.query(HabitLog).filter(
                    HabitLog.habit_id == habit.id,
                    func.date(HabitLog.date) == today
                ).first()
                
                habit_data.append({
                    'id': habit.id,
                    'name': habit.name,
                    'has_log_today': existing_log is not None
                })
        
        if not habit_data:
            await query.edit_message_text(
                "🎯 *Log Habit Progress*\n\n"
                "You don't have any habits to log yet.\n"
                "Create a habit first!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Habit", callback_data="habit_add")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
            return
        
        message = "✅ *Log Habit Progress*\n\nSelect a habit to log:"
        keyboard = []
        
        for habit in habit_data:
            status = "✅" if habit['has_log_today'] else "⏳"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{status} {habit['name']}", 
                    callback_data=f"log_habit_{habit['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def log_specific_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log progress for a specific habit"""
        query = update.callback_query
        await query.answer()
        
        habit_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            habit = db.query(Habit).filter(
                Habit.id == habit_id,
                Habit.user_id == user_id
            ).first()
            
            if not habit:
                await query.edit_message_text("❌ Habit not found.")
                return
            
            # Check if already logged today
            today = date.today()
            existing_log = db.query(HabitLog).filter(
                HabitLog.habit_id == habit.id,
                func.date(HabitLog.date) == today
            ).first()
            
            if existing_log:
                await query.edit_message_text(
                    f"✅ *Already Logged Today!*\n\n"
                    f"🎯 Habit: {TextHelper.escape_markdown(habit.name)}\n"
                    f"📊 Today's progress: {existing_log.value}/{habit.target_value}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✏️ Update", callback_data=f"update_log_{existing_log.id}")],
                        [InlineKeyboardButton("🔙 Back", callback_data="habit_log")]
                    ])
                )
                return
            
            # Create quick log buttons
            keyboard = []
            
            # Quick values
            quick_values = [1, habit.target_value // 2, habit.target_value] if habit.target_value > 2 else [1, habit.target_value]
            quick_values = list(set(quick_values))  # Remove duplicates
            quick_values.sort()
            
            for value in quick_values:
                unit_text = f" {habit.unit}" if habit.unit else ""
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {value}{unit_text}", 
                        callback_data=f"quick_log_{habit.id}_{value}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("✏️ Custom Value", callback_data=f"custom_log_{habit.id}")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="habit_log")])
            
            unit_text = f" {habit.unit}" if habit.unit else ""
            
            await query.edit_message_text(
                f"📊 *Log Progress*\n\n"
                f"🎯 Habit: {TextHelper.escape_markdown(habit.name)}\n"
                f"🎯 Target: {habit.target_value}{unit_text}\n\n"
                f"How much did you complete today?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    @with_user
    @error_handler
    async def quick_log_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick log habit with predefined value"""
        query = update.callback_query
        await query.answer()
        
        parts = query.data.split('_')
        habit_id = int(parts[2])
        value = int(parts[3])
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            habit = db.query(Habit).filter(
                Habit.id == habit_id,
                Habit.user_id == user_id
            ).first()
            
            if not habit:
                await query.edit_message_text("❌ Habit not found.")
                return
            
            # Extract habit data while session is open
            habit_name = habit.name
            habit_target = habit.target_value
            habit_unit = habit.unit
            habit_streak = habit.streak_count
            
            # Create habit log
            habit_log = HabitLog(
                user_id=user_id,
                habit_id=habit.id,
                date=datetime.now(),
                value=value
            )
            db.add(habit_log)
            
            # Update streak
            self._update_habit_streak(db, habit)
            
            # Get updated streak after update
            new_streak = habit.streak_count
            
            db.commit()
        
        # Determine completion status
        completion_percentage = (value / habit_target) * 100 if habit_target > 0 else 100
        
        if completion_percentage >= 100:
            status_emoji = "🎉"
            status_text = "Target achieved!"
        elif completion_percentage >= 75:
            status_emoji = "🔥"
            status_text = "Great progress!"
        elif completion_percentage >= 50:
            status_emoji = "👍"
            status_text = "Good job!"
        else:
            status_emoji = "💪"
            status_text = "Keep going!"
        
        unit_text = f" {habit_unit}" if habit_unit else ""
        
        await query.edit_message_text(
            f"{status_emoji} *Progress Logged!*\n\n"
            f"🎯 Habit: {TextHelper.escape_markdown(habit_name)}\n"
            f"📊 Today: {value}/{habit_target}{unit_text} ({completion_percentage:.0f}%)\n"
            f"🔥 Current streak: {new_streak}\n\n"
            f"{status_text}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Stats", callback_data=f"habit_stats_{habit_id}")],
                [InlineKeyboardButton("🔙 Back to Habits", callback_data="habit_list")]
            ])
        )
    
    def _update_habit_streak(self, db, habit):
        """Update habit streak based on recent logs"""
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Check if logged today
        today_log = db.query(HabitLog).filter(
            HabitLog.habit_id == habit.id,
            func.date(HabitLog.date) == today
        ).first()
        
        if not today_log:
            return
        
        # Check if target was met today
        if today_log.value >= habit.target_value:
            # Check if logged yesterday
            yesterday_log = db.query(HabitLog).filter(
                HabitLog.habit_id == habit.id,
                func.date(HabitLog.date) == yesterday
            ).first()
            
            if yesterday_log and yesterday_log.value >= habit.target_value:
                # Continue streak
                habit.streak_count += 1
            else:
                # Start new streak
                habit.streak_count = 1
            
            # Update best streak
            if habit.streak_count > habit.best_streak:
                habit.best_streak = habit.streak_count
        else:
            # Target not met, reset streak
            habit.streak_count = 0
    
    @with_user
    @error_handler
    async def show_habit_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show statistics for a specific habit"""
        query = update.callback_query
        await query.answer()
        
        habit_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            habit = db.query(Habit).filter(
                Habit.id == habit_id,
                Habit.user_id == user_id
            ).first()
            
            if not habit:
                await query.edit_message_text("❌ Habit not found.")
                return
            
            # Extract habit data while session is open
            habit_name = habit.name
            habit_target = habit.target_value
            habit_unit = habit.unit
            habit_streak = habit.streak_count
            habit_best_streak = habit.best_streak
            
            # Get statistics
            total_logs = db.query(HabitLog).filter(HabitLog.habit_id == habit.id).count()
            
            # Last 7 days
            week_ago = date.today() - timedelta(days=7)
            recent_logs = db.query(HabitLog).filter(
                HabitLog.habit_id == habit.id,
                func.date(HabitLog.date) >= week_ago
            ).all()
            
            # Calculate completion rate
            days_with_target = sum(1 for log in recent_logs if log.value >= habit_target)
            completion_rate = (days_with_target / 7) * 100 if recent_logs else 0
            
            # Average daily value
            avg_value = sum(log.value for log in recent_logs) / len(recent_logs) if recent_logs else 0
        
        unit_text = f" {habit_unit}" if habit_unit else ""
        
        message = (
            f"📊 *Habit Statistics*\n\n"
            f"🎯 *{TextHelper.escape_markdown(habit_name)}*\n\n"
            f"🔥 Current streak: *{habit_streak} days*\n"
            f"🏆 Best streak: *{habit_best_streak} days*\n"
            f"📈 Total logs: *{total_logs}*\n\n"
            f"📅 *Last 7 Days:*\n"
            f"✅ Completion rate: *{completion_rate:.0f}%*\n"
            f"📊 Average: *{avg_value:.1f}{unit_text}*\n"
            f"🎯 Target: *{habit_target}{unit_text}*"
        )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Log Today", callback_data=f"log_habit_{habit_id}")],
                [InlineKeyboardButton("🔙 Back to Habits", callback_data="habit_list")]
            ])
        )
    
    @with_user
    @error_handler
    async def delete_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a habit"""
        query = update.callback_query
        await query.answer()
        habit_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        with get_db() as db:
            habit = db.query(Habit).filter(
                Habit.id == habit_id,
                Habit.user_id == user_id
            ).first()
            if not habit:
                await query.edit_message_text("❌ Habit not found.")
                return
            habit_name = habit.name
            db.delete(habit)
            db.commit()
        await query.edit_message_text(
            f"🗑️ *Habit Deleted!*\n\n"
            f"🎯 {TextHelper.escape_markdown(habit_name)}\n\n"
            f"Habit has been permanently deleted.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 View Habits", callback_data="habit_list")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def edit_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit a habit name"""
        query = update.callback_query
        await query.answer()
        habit_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        context.user_data['editing_habit_id'] = habit_id
        with get_db() as db:
            habit = db.query(Habit).filter(
                Habit.id == habit_id,
                Habit.user_id == user_id
            ).first()
            if not habit:
                await query.edit_message_text("❌ Habit not found.")
                return
            habit_name = habit.name
        await query.edit_message_text(
            f"✏️ *Edit Habit*\n\n"
            f"Current name: *{TextHelper.escape_markdown(habit_name)}*\n\n"
            f"Please enter the new habit name:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Cancel", callback_data="habit_list")]
            ])
        )
        return self.EDIT_HABIT_NAME
    
    @with_user
    @error_handler
    async def get_new_habit_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get new habit name from user"""
        new_name = update.message.text.strip()
        if len(new_name) > 255:
            await update.message.reply_text(
                "❌ Habit name is too long. Please keep it under 255 characters."
            )
            return self.EDIT_HABIT_NAME
        habit_id = context.user_data['editing_habit_id']
        user_id = context.user_data['user_id']
        with get_db() as db:
            habit = db.query(Habit).filter(
                Habit.id == habit_id,
                Habit.user_id == user_id
            ).first()
            if not habit:
                await update.message.reply_text("❌ Habit not found.")
                return ConversationHandler.END
            habit.name = new_name
            db.commit()
        await update.message.reply_text(
            f"✅ *Habit Updated!*\n\n"
            f"🎯 **New name:** {TextHelper.escape_markdown(new_name)}",
            parse_mode='Markdown',
            reply_markup=Keyboards.habits_menu()
        )
        context.user_data.pop('editing_habit_id', None)
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel habit creation conversation"""
        await update.message.reply_text(
            "❌ Habit creation cancelled.",
            reply_markup=Keyboards.habits_menu()
        )
        # Clear conversation data
        for key in ['habit_name', 'habit_description', 'habit_frequency', 'habit_target', 'editing_habit_id']:
            context.user_data.pop(key, None)
        return ConversationHandler.END

    @with_user
    @error_handler
    async def show_habits_overview_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show overview statistics for all habits"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Get all active habits
            habits = db.query(Habit).filter(
                Habit.user_id == user_id,
                Habit.is_active == True
            ).all()
            
            if not habits:
                await query.edit_message_text(
                    "📊 *Habits Statistics*\n\n"
                    "You don't have any habits yet.\n"
                    "Create your first habit to see statistics!",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ Add Habit", callback_data="habit_add")],
                        [InlineKeyboardButton("🔙 Back", callback_data="habits_menu")]
                    ])
                )
                return
            
            # Calculate overall statistics
            total_habits = len(habits)
            total_logs = db.query(HabitLog).filter(HabitLog.user_id == user_id).count()
            
            # Streak statistics
            total_current_streaks = sum(habit.streak_count for habit in habits)
            total_best_streaks = sum(habit.best_streak for habit in habits)
            avg_current_streak = total_current_streaks / total_habits if total_habits > 0 else 0
            avg_best_streak = total_best_streaks / total_habits if total_habits > 0 else 0
            
            # Today's completion
            today = date.today()
            today_logs = db.query(HabitLog).filter(
                HabitLog.user_id == user_id,
                func.date(HabitLog.date) == today
            ).count()
            
            # Last 7 days activity
            week_ago = date.today() - timedelta(days=7)
            recent_logs = db.query(HabitLog).filter(
                HabitLog.user_id == user_id,
                func.date(HabitLog.date) >= week_ago
            ).count()
            
            # Frequency breakdown
            daily_habits = sum(1 for habit in habits if habit.frequency.value == 'DAILY')
            weekly_habits = sum(1 for habit in habits if habit.frequency.value == 'WEEKLY')
            monthly_habits = sum(1 for habit in habits if habit.frequency.value == 'MONTHLY')
        
        message = (
            f"📊 *Habits Overview*\n\n"
            f"🎯 *Total Habits:* {total_habits}\n"
            f"📈 *Total Logs:* {total_logs}\n"
            f"✅ *Today's Logs:* {today_logs}\n"
            f"📅 *This Week:* {recent_logs} logs\n\n"
            f"🔥 *Streak Statistics:*\n"
            f"• Average Current Streak: {avg_current_streak:.1f} days\n"
            f"• Average Best Streak: {avg_best_streak:.1f} days\n\n"
            f"🔄 *Frequency Breakdown:*\n"
            f"• 📅 Daily: {daily_habits}\n"
            f"• 📆 Weekly: {weekly_habits}\n"
            f"• 🗓️ Monthly: {monthly_habits}\n\n"
            f"Keep up the great work! 💪"
        )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Habits", callback_data="habit_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="habits_menu")]
            ])
        )

    @with_user
    @error_handler
    async def update_habit_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Update an existing habit log"""
        query = update.callback_query
        await query.answer()
        
        log_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Find the log and associated habit
            habit_log = db.query(HabitLog).filter(
                HabitLog.id == log_id,
                HabitLog.user_id == user_id
            ).first()
            
            if not habit_log:
                await query.edit_message_text("❌ Log not found.")
                return
            
            habit = db.query(Habit).filter(
                Habit.id == habit_log.habit_id,
                Habit.user_id == user_id
            ).first()
            
            if not habit:
                await query.edit_message_text("❌ Habit not found.")
                return
            
            # Extract data while session is open
            habit_name = habit.name
            habit_target = habit.target_value
            habit_unit = habit.unit
            current_value = habit_log.value
        
        # Create quick update buttons
        keyboard = []
        
        # Quick values
        quick_values = [1, habit_target // 2, habit_target] if habit_target > 2 else [1, habit_target]
        quick_values = list(set(quick_values))  # Remove duplicates
        quick_values.sort()
        
        for value in quick_values:
            unit_text = f" {habit_unit}" if habit_unit else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ {value}{unit_text}", 
                    callback_data=f"quick_update_{log_id}_{value}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("✏️ Custom Value", callback_data=f"custom_update_{log_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="habit_log")])
        
        unit_text = f" {habit_unit}" if habit_unit else ""
        
        await query.edit_message_text(
            f"✏️ *Update Progress*\n\n"
            f"🎯 Habit: {TextHelper.escape_markdown(habit_name)}\n"
            f"📊 Current: {current_value}/{habit_target}{unit_text}\n"
            f"🎯 Target: {habit_target}{unit_text}\n\n"
            f"What's your updated progress?",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def quick_update_habit_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick update habit log with predefined value"""
        query = update.callback_query
        await query.answer()
        
        parts = query.data.split('_')
        log_id = int(parts[2])
        value = int(parts[3])
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Find the log and associated habit
            habit_log = db.query(HabitLog).filter(
                HabitLog.id == log_id,
                HabitLog.user_id == user_id
            ).first()
            
            if not habit_log:
                await query.edit_message_text("❌ Log not found.")
                return
            
            habit = db.query(Habit).filter(
                Habit.id == habit_log.habit_id,
                Habit.user_id == user_id
            ).first()
            
            if not habit:
                await query.edit_message_text("❌ Habit not found.")
                return
            
            # Extract all needed data while session is open
            habit_name = habit.name
            habit_target = habit.target_value
            habit_unit = habit.unit
            habit_id = habit.id
            
            # Update the log
            habit_log.value = value
            habit_log.updated_at = datetime.now()
            
            # Update streak
            self._update_habit_streak(db, habit)
            
            # Get updated streak after update
            new_streak = habit.streak_count
            
            db.commit()
        
        # Determine completion status
        completion_percentage = (value / habit_target) * 100 if habit_target > 0 else 100
        
        if completion_percentage >= 100:
            status_emoji = "🎉"
            status_text = "Target achieved!"
        elif completion_percentage >= 75:
            status_emoji = "🔥"
            status_text = "Great progress!"
        elif completion_percentage >= 50:
            status_emoji = "👍"
            status_text = "Good job!"
        else:
            status_emoji = "💪"
            status_text = "Keep going!"
        
        unit_text = f" {habit_unit}" if habit_unit else ""
        
        await query.edit_message_text(
            f"{status_emoji} *Progress Updated!*\n\n"
            f"🎯 Habit: {TextHelper.escape_markdown(habit_name)}\n"
            f"📊 Today: {value}/{habit_target}{unit_text} ({completion_percentage:.0f}%)\n"
            f"🔥 Current streak: {new_streak}\n\n"
            f"{status_text}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Stats", callback_data=f"habit_stats_{habit_id}")],
                [InlineKeyboardButton("🔙 Back to Habits", callback_data="habit_list")]
            ])
        )
    
    @with_user
    @error_handler
    async def custom_update_habit_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start custom update conversation for habit log"""
        query = update.callback_query
        await query.answer()
        
        log_id = int(query.data.split('_')[-1])
        context.user_data['updating_log_id'] = log_id
        
        await query.edit_message_text(
            "✏️ *Custom Update*\n\n"
            "Please enter the new value for today's progress:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Cancel", callback_data="habit_log")]
            ])
        )
        
        return self.CUSTOM_UPDATE_VALUE
    
    @with_user
    @error_handler
    async def get_custom_update_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get custom update value from user"""
        try:
            value = int(update.message.text.strip())
            if value < 0:
                await update.message.reply_text("❌ Please enter a positive number.")
                return self.CUSTOM_UPDATE_VALUE
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
            return self.CUSTOM_UPDATE_VALUE
        
        log_id = context.user_data['updating_log_id']
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Find the log and associated habit
            habit_log = db.query(HabitLog).filter(
                HabitLog.id == log_id,
                HabitLog.user_id == user_id
            ).first()
            
            if not habit_log:
                await update.message.reply_text("❌ Log not found.")
                return ConversationHandler.END
            
            habit = db.query(Habit).filter(
                Habit.id == habit_log.habit_id,
                Habit.user_id == user_id
            ).first()
            
            if not habit:
                await update.message.reply_text("❌ Habit not found.")
                return ConversationHandler.END
            
            # Extract data while session is open
            habit_name = habit.name
            habit_target = habit.target_value
            habit_unit = habit.unit
            habit_id = habit.id
            
            # Update the log
            habit_log.value = value
            habit_log.updated_at = datetime.now()
            
            # Update streak
            self._update_habit_streak(db, habit)
            
            # Get updated streak after update
            new_streak = habit.streak_count
            
            db.commit()
        
        # Determine completion status
        completion_percentage = (value / habit_target) * 100 if habit_target > 0 else 100
        
        if completion_percentage >= 100:
            status_emoji = "🎉"
            status_text = "Target achieved!"
        elif completion_percentage >= 75:
            status_emoji = "🔥"
            status_text = "Great progress!"
        elif completion_percentage >= 50:
            status_emoji = "👍"
            status_text = "Good job!"
        else:
            status_emoji = "💪"
            status_text = "Keep going!"
        
        unit_text = f" {habit_unit}" if habit_unit else ""
        
        await update.message.reply_text(
            f"{status_emoji} *Progress Updated!*\n\n"
            f"🎯 Habit: {TextHelper.escape_markdown(habit_name)}\n"
            f"📊 Today: {value}/{habit_target}{unit_text} ({completion_percentage:.0f}%)\n"
            f"🔥 Current streak: {new_streak}\n\n"
            f"{status_text}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Stats", callback_data=f"habit_stats_{habit_id}")],
                [InlineKeyboardButton("🔙 Back to Habits", callback_data="habit_list")]
            ])
        )
        
        context.user_data.pop('updating_log_id', None)
        return ConversationHandler.END