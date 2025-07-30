from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.database import get_db
from database.models import User, Task, Habit, Note, Reminder, TaskStatus, ReminderStatus, HabitLog, TaskPriority
from utils.decorators import with_user, error_handler
from utils.helpers import TextHelper
from utils.keyboards import Keyboards
from loguru import logger
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_
import matplotlib.pyplot as plt
import io
import base64

class StatisticsFeature:
    @with_user
    @error_handler
    async def show_statistics_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show statistics main menu"""
        text = (
            "📊 *Statistics*\n\n"
            "Choose an option below:"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.statistics_menu()
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.statistics_menu()
            )
    
    @with_user
    @error_handler
    async def show_overview_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show overview statistics"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Get counts
            total_tasks = db.query(Task).filter(Task.user_id == user_id).count()
            completed_tasks = db.query(Task).filter(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED
            ).count()
            
            active_habits = db.query(Habit).filter(
                Habit.user_id == user_id,
                Habit.is_active == True
            ).count()
            
            total_notes = db.query(Note).filter(Note.user_id == user_id).count()
            
            total_reminders = db.query(Reminder).filter(Reminder.user_id == user_id).count()
            completed_reminders = db.query(Reminder).filter(
                Reminder.user_id == user_id,
                Reminder.status == ReminderStatus.COMPLETED
            ).count()
            
            # Get habit streaks
            best_streak = db.query(func.max(Habit.best_streak)).filter(
                Habit.user_id == user_id
            ).scalar() or 0
            
            current_streaks = db.query(func.sum(Habit.streak_count)).filter(
                Habit.user_id == user_id,
                Habit.is_active == True
            ).scalar() or 0
            
            # This week's activity
            week_start = date.today() - timedelta(days=date.today().weekday())
            
            tasks_this_week = db.query(Task).filter(
                Task.user_id == user_id,
                Task.created_at >= week_start
            ).count()
            
            habits_logged_this_week = db.query(HabitLog).filter(
                HabitLog.user_id == user_id,
                func.date(HabitLog.date) >= week_start
            ).count()
        
        # Calculate completion rates
        task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        reminder_completion_rate = (completed_reminders / total_reminders * 100) if total_reminders > 0 else 0
        
        message = (
            f"📊 *Productivity Overview*\n\n"
            f"📈 *Overall Stats:*\n"
            f"✅ Tasks: {completed_tasks}/{total_tasks} ({task_completion_rate:.0f}%)\n"
            f"🎯 Active Habits: {active_habits}\n"
            f"📝 Reminders: {completed_reminders}/{total_reminders} ({reminder_completion_rate:.0f}%)\n"
            f"📋 Notes: {total_notes}\n\n"
            f"🔥 *Habit Streaks:*\n"
            f"🏆 Best Streak: {best_streak} days\n"
            f"📊 Total Current Streaks: {current_streaks} days\n\n"
            f"📅 *This Week:*\n"
            f"➕ New Tasks: {tasks_this_week}\n"
            f"✅ Habit Logs: {habits_logged_this_week}\n\n"
            f"Keep up the great work! 💪"
        )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📈 Weekly Report", callback_data="stats_weekly")],
                [InlineKeyboardButton("🔙 Back to Stats", callback_data="stats_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_task_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show task statistics"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Task counts by status
            todo_count = db.query(Task).filter(
                Task.user_id == user_id,
                Task.status == TaskStatus.TODO
            ).count()
            
            in_progress_count = db.query(Task).filter(
                Task.user_id == user_id,
                Task.status == TaskStatus.IN_PROGRESS
            ).count()
            
            completed_count = db.query(Task).filter(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED
            ).count()
            
            # Tasks by priority
            urgent_count = db.query(Task).filter(
                Task.user_id == user_id,
                Task.priority == TaskPriority.URGENT
            ).count()
            
            high_count = db.query(Task).filter(
                Task.user_id == user_id,
                Task.priority == TaskPriority.HIGH
            ).count()
            
            medium_count = db.query(Task).filter(
                Task.user_id == user_id,
                Task.priority == TaskPriority.MEDIUM
            ).count()
            
            low_count = db.query(Task).filter(
                Task.user_id == user_id,
                Task.priority == TaskPriority.LOW
            ).count()
            
            # Project stats - get all projects first, then count completed tasks separately
            projects = db.query(Task.project_name).filter(
                Task.user_id == user_id,
                Task.project_name.isnot(None),
                Task.project_name != ''
            ).distinct().limit(5).all()
            
            project_stats = []
            for project in projects:
                project_name = project.project_name
                total_tasks_in_project = db.query(Task).filter(
                    Task.user_id == user_id,
                    Task.project_name == project_name
                ).count()
                completed_tasks_in_project = db.query(Task).filter(
                    Task.user_id == user_id,
                    Task.project_name == project_name,
                    Task.status == TaskStatus.COMPLETED
                ).count()
                project_stats.append({
                    'project_name': project_name,
                    'task_count': total_tasks_in_project,
                    'completed': completed_tasks_in_project
                })
            
            # This month's completed tasks
            month_start = date.today().replace(day=1)
            monthly_completed = db.query(Task).filter(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                func.date(Task.completed_at) >= month_start
            ).count()
        
        total_tasks = todo_count + in_progress_count + completed_count
        completion_rate = (completed_count / total_tasks * 100) if total_tasks > 0 else 0
        
        message = (
            f"✅ *Task Statistics*\n\n"
            f"📊 *Status Breakdown:*\n"
            f"⏳ To Do: {todo_count}\n"
            f"🔄 In Progress: {in_progress_count}\n"
            f"✅ Completed: {completed_count}\n"
            f"📈 Completion Rate: {completion_rate:.0f}%\n\n"
            f"🎯 *Priority Distribution:*\n"
            f"🔴 Urgent: {urgent_count}\n"
            f"🟡 High: {high_count}\n"
            f"🟢 Medium: {medium_count}\n"
            f"🔵 Low: {low_count}\n\n"
            f"📅 *This Month:*\n"
            f"✅ Completed: {monthly_completed} tasks\n"
        )
        
        if project_stats:
            message += f"\n📁 *Top Projects:*\n"
            for project in project_stats:
                progress = int((project['completed'] / project['task_count']) * 100) if project['task_count'] > 0 else 0
                message += f"• {project['project_name']}: {project['completed']}/{project['task_count']} ({progress}%)\n"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ View Tasks", callback_data="task_list")],
                [InlineKeyboardButton("🔙 Back to Stats", callback_data="stats_menu")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_habit_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show habit statistics"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Active habits
            active_habits = db.query(Habit).filter(
                Habit.user_id == user_id,
                Habit.is_active == True
            ).all()
            
            # Habit performance
            total_habits = len(active_habits)
            total_current_streak = sum(habit.streak_count for habit in active_habits)
            best_streak = max((habit.best_streak for habit in active_habits), default=0)
            
            # This week's logs
            week_start = date.today() - timedelta(days=7)
            weekly_logs = db.query(HabitLog).filter(
                HabitLog.user_id == user_id,
                func.date(HabitLog.date) >= week_start
            ).count()
            
            # Habit completion rates (last 30 days)
            month_start = date.today() - timedelta(days=30)
            habit_performance = []
            
            for habit in active_habits:
                logs_count = db.query(HabitLog).filter(
                    HabitLog.habit_id == habit.id,
                    func.date(HabitLog.date) >= month_start,
                    HabitLog.value >= habit.target_value
                ).count()
                
                expected_days = 30 if habit.frequency.value == 'daily' else (4 if habit.frequency.value == 'weekly' else 1)
                completion_rate = (logs_count / expected_days * 100) if expected_days > 0 else 0
                
                habit_performance.append({
                    'name': habit.name,
                    'rate': completion_rate,
                    'streak': habit.streak_count
                })
            
            # Sort by completion rate
            habit_performance.sort(key=lambda x: x['rate'], reverse=True)
        
        message = (
            f"🎯 *Habit Statistics*\n\n"
            f"📊 *Overview:*\n"
            f"🎯 Active Habits: {total_habits}\n"
            f"🔥 Total Current Streaks: {total_current_streak} days\n"
            f"🏆 Best Streak Ever: {best_streak} days\n"
            f"📅 Logs This Week: {weekly_logs}\n\n"
        )
        
        if habit_performance:
            message += f"📈 *30-Day Performance:*\n"
            for i, habit in enumerate(habit_performance[:5], 1):
                message += f"{i}. {habit['name']}: {habit['rate']:.0f}% (🔥{habit['streak']})\n"
        
        if not active_habits:
            message += "No active habits yet. Start building better habits today!"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 View Habits", callback_data="habit_list")],
                [InlineKeyboardButton("➕ Add Habit", callback_data="habit_add")],
                [InlineKeyboardButton("🔙 Back to Stats", callback_data="stats_menu")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_weekly_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show weekly productivity report"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        # Calculate week boundaries
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        with get_db() as db:
            # Tasks this week
            tasks_created = db.query(Task).filter(
                Task.user_id == user_id,
                func.date(Task.created_at) >= week_start,
                func.date(Task.created_at) <= week_end
            ).count()
            
            tasks_completed = db.query(Task).filter(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                func.date(Task.completed_at) >= week_start,
                func.date(Task.completed_at) <= week_end
            ).count()
            
            # Habits this week
            habit_logs = db.query(HabitLog).filter(
                HabitLog.user_id == user_id,
                func.date(HabitLog.date) >= week_start,
                func.date(HabitLog.date) <= week_end
            ).count()
            
            # Active habits
            active_habits = db.query(Habit).filter(
                Habit.user_id == user_id,
                Habit.is_active == True
            ).count()
            
            # Notes this week
            notes_created = db.query(Note).filter(
                Note.user_id == user_id,
                func.date(Note.created_at) >= week_start,
                func.date(Note.created_at) <= week_end
            ).count()
            
            # Reminders this week
            reminders_completed = db.query(Reminder).filter(
                Reminder.user_id == user_id,
                Reminder.status == ReminderStatus.COMPLETED,
                func.date(Reminder.remind_at) >= week_start,
                func.date(Reminder.remind_at) <= week_end
            ).count()
        
        # Calculate habit completion rate
        expected_habit_logs = active_habits * 7  # Daily habits for 7 days
        habit_completion_rate = (habit_logs / expected_habit_logs * 100) if expected_habit_logs > 0 else 0
        
        # Determine performance level
        if habit_completion_rate >= 80:
            performance_emoji = "🔥"
            performance_text = "Excellent!"
        elif habit_completion_rate >= 60:
            performance_emoji = "👍"
            performance_text = "Good job!"
        elif habit_completion_rate >= 40:
            performance_emoji = "💪"
            performance_text = "Keep going!"
        else:
            performance_emoji = "📈"
            performance_text = "Room for improvement"
        
        week_str = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"
        
        message = (
            f"📈 *Weekly Report*\n"
            f"📅 {week_str}\n\n"
            f"✅ *Tasks:*\n"
            f"➕ Created: {tasks_created}\n"
            f"✅ Completed: {tasks_completed}\n\n"
            f"🎯 *Habits:*\n"
            f"📊 Logs: {habit_logs}\n"
            f"📈 Completion: {habit_completion_rate:.0f}%\n"
            f"{performance_emoji} {performance_text}\n\n"
            f"📝 *Other Activity:*\n"
            f"📋 Notes Created: {notes_created}\n"
            f"🔔 Reminders Completed: {reminders_completed}\n\n"
        )
        
        # Add motivational message
        if tasks_completed > 0 or habit_logs > 0:
            message += "🎉 Great work this week! Keep it up!"
        else:
            message += "💪 Ready to make next week more productive?"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Full Stats", callback_data="stats_overview")],
                [InlineKeyboardButton("🎯 Set Goals", callback_data="habit_add")],
                [InlineKeyboardButton("🔙 Back to Stats", callback_data="stats_menu")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_reminder_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show reminder statistics"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            total_reminders = db.query(Reminder).filter(Reminder.user_id == user_id).count()
            completed_reminders = db.query(Reminder).filter(
                Reminder.user_id == user_id,
                Reminder.status == ReminderStatus.COMPLETED
            ).count()
            pending_reminders = db.query(Reminder).filter(
                Reminder.user_id == user_id,
                Reminder.status == ReminderStatus.PENDING
            ).count()
            
            # This month's reminders
            month_start = date.today().replace(day=1)
            monthly_reminders = db.query(Reminder).filter(
                Reminder.user_id == user_id,
                func.date(Reminder.remind_at) >= month_start
            ).count()
        
        completion_rate = (completed_reminders / total_reminders * 100) if total_reminders > 0 else 0
        
        message = (
            f"📝 *Reminder Statistics*\n\n"
            f"📊 *Overview:*\n"
            f"📝 Total Reminders: {total_reminders}\n"
            f"✅ Completed: {completed_reminders}\n"
            f"⏳ Pending: {pending_reminders}\n"
            f"📈 Completion Rate: {completion_rate:.0f}%\n\n"
            f"📅 *This Month:*\n"
            f"🔔 Reminders: {monthly_reminders}\n\n"
        )
        
        if completion_rate >= 80:
            message += "🎉 Excellent reminder management!"
        elif completion_rate >= 60:
            message += "👍 Good job staying on track!"
        else:
            message += "💪 Keep working on your reminder habits!"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 View Reminders", callback_data="reminder_list")],
                [InlineKeyboardButton("➕ Add Reminder", callback_data="reminder_add")],
                [InlineKeyboardButton("🔙 Back to Stats", callback_data="stats_menu")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_note_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show note statistics"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            total_notes = db.query(Note).filter(Note.user_id == user_id).count()
            pinned_notes = db.query(Note).filter(
                Note.user_id == user_id,
                Note.is_pinned == True
            ).count()
            
            # Notes by category
            category_stats = db.query(
                Note.category,
                func.count(Note.id).label('count')
            ).filter(
                Note.user_id == user_id,
                Note.category.isnot(None),
                Note.category != ''
            ).group_by(Note.category).order_by(func.count(Note.id).desc()).limit(5).all()
            
            # This month's notes
            month_start = date.today().replace(day=1)
            monthly_notes = db.query(Note).filter(
                Note.user_id == user_id,
                func.date(Note.created_at) >= month_start
            ).count()
            
            # Average note length
            avg_length = db.query(func.avg(func.length(Note.content))).filter(
                Note.user_id == user_id
            ).scalar() or 0
        
        message = (
            f"📋 *Note Statistics*\n\n"
            f"📊 *Overview:*\n"
            f"📋 Total Notes: {total_notes}\n"
            f"📌 Pinned Notes: {pinned_notes}\n"
            f"📏 Avg Length: {int(avg_length)} characters\n\n"
            f"📅 *This Month:*\n"
            f"➕ New Notes: {monthly_notes}\n"
        )
        
        if category_stats:
            message += f"\n📁 *Top Categories:*\n"
            for category in category_stats:
                message += f"• {category.category}: {category.count} notes\n"
        
        if total_notes == 0:
            message += "\n💡 Start taking notes to track your ideas!"
        elif total_notes < 10:
            message += "\n📝 You're building a good note collection!"
        else:
            message += "\n🎉 Great job organizing your thoughts!"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Notes", callback_data="note_list")],
                [InlineKeyboardButton("➕ Add Note", callback_data="note_add")],
                [InlineKeyboardButton("🔙 Back to Stats", callback_data="stats_menu")]
            ])
        )