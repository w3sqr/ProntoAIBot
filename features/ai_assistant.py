import openai
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.database import get_db, get_redis
from database.models import User, Task, Habit, Note, Reminder, TaskStatus, TaskPriority, HabitFrequency
from utils.decorators import with_user, error_handler
from utils.helpers import TextHelper, TimeHelper
from config import settings
from loguru import logger
import json
from typing import Optional, Dict, Any
from utils.keyboards import Keyboards
from datetime import datetime, timedelta
import re
import pytz
from features.notifications import NotificationService
import httpx

# Conversation states
class AIAssistant:
    AI_QUERY = 0

    def __init__(self):
        self.openai_api_key = settings.openai_api_key
        self.deepseek_api_key = settings.deepseek_api_key
        
        # Initialize OpenAI client if available
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            self.openai_enabled = True
        else:
            self.openai_client = None
            self.openai_enabled = False
            logger.warning("OpenAI API key not provided.")
        
        # Initialize DeepSeek client if available
        if self.deepseek_api_key:
            self.deepseek_enabled = True
            self.deepseek_base_url = "https://api.deepseek.com/v1"
        else:
            self.deepseek_enabled = False
            logger.warning("DeepSeek API key not provided.")
        
        # Check if at least one AI service is available
        if self.openai_enabled or self.deepseek_enabled:
            self.enabled = True
        else:
            self.enabled = False
            logger.warning("No AI API keys provided. AI features disabled.")
        
        self.redis = get_redis()
    
    @with_user
    @error_handler
    async def show_ai_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show enhanced AI assistant menu"""
        if not self.enabled:
            await update.message.reply_text(
                "🤖 *AI Assistant*\n\n"
                "❌ AI features are currently unavailable.\n"
                "Please contact the administrator.",
                parse_mode='Markdown'
            )
            return
        
        text = (
            "🤖 *AI Assistant*\n\n"
            "I can help you with all your productivity needs!\n\n"
            "💡 *Try saying things like:*\n"
            "• \"Remind me to call mom tomorrow at 3pm\"\n"
            "• \"Create a task to finish the report by Friday\"\n"
            "• \"I want to build a habit of reading 30 minutes daily\"\n"
            "• \"Note: Meeting with John about project X\"\n\n"
            "Choose an option below:"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.ai_menu()
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.ai_menu()
            )
    
    @with_user
    @error_handler
    async def start_ai_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start enhanced AI chat conversation with natural language processing"""
        if not self.enabled:
            return
        
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "🤖 *AI Assistant - Natural Language Mode*\n\n"
            "I can understand natural language commands and help you:\n\n"
            "📝 *Reminders:*\n"
            "• \"Remind me to call mom tomorrow at 3pm\"\n"
            "• \"Set a reminder for the meeting in 2 hours\"\n\n"
            "✅ *Tasks:*\n"
            "• \"Create a task to finish the report by Friday\"\n"
            "• \"Add a high priority task for the presentation\"\n\n"
            "🎯 *Habits:*\n"
            "• \"I want to build a habit of reading 30 minutes daily\"\n"
            "• \"Create a habit to exercise 3 times a week\"\n\n"
            "📋 *Notes:*\n"
            "• \"Note: Meeting with John about project X\"\n"
            "• \"Save this: Important phone number 123-456-7890\"\n\n"
            "💡 *Or just ask me anything about productivity!*\n\n"
            "What would you like me to help you with?",
            parse_mode='Markdown'
        )
        
        return self.AI_QUERY
    
    @with_user
    @error_handler
    async def handle_ai_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle AI query with natural language processing and smart actions"""
        if not self.enabled:
            return ConversationHandler.END
        
        user_query = update.message.text.strip()
        user_id = context.user_data['user_id']
        telegram_id = context.user_data['user_telegram_id']
        
        # Show typing indicator
        await update.message.reply_chat_action("typing")
        
        try:
            # First, try to detect if this is a command to create something
            action_result = await self._detect_and_execute_action(user_query, user_id, context)
            
            if action_result['success']:
                # It was a command, show the result with enhanced formatting
                keyboard = [
                    [InlineKeyboardButton("✨ Ask Another Question", callback_data="ai_chat")],
                    [InlineKeyboardButton("🔙 Back to AI Menu", callback_data="ai_menu")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
                ]
                
                # Enhanced success message formatting
                success_message = (
                    f"🎉 *Action Completed Successfully!*\n\n"
                    f"{action_result['message']}\n\n"
                    f"💡 *What's next?*\n"
                    f"• Ask me to create more items\n"
                    f"• Get productivity insights\n"
                    f"• Manage your items from the main menu"
                )
                
                await update.message.reply_text(
                    success_message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return ConversationHandler.END
            
            # If not a command, treat as a general question
            user_context = await self._get_user_context(user_id)
            
            system_message = (
                "You are a helpful AI assistant for a productivity bot. "
                "You help users with reminders, tasks, habits, and notes. "
                "Be concise, friendly, and practical in your responses. "
                "Focus on productivity and personal development advice. "
                "If the user asks about creating something, guide them to use natural language commands."
            )
            
            if user_context:
                system_message += f"\n\nUser context: {user_context}"
            
            # Call AI API with fallback
            ai_response = await self._call_ai_api_with_fallback(system_message, user_query)
            
            # Store conversation in Redis for context
            await self._store_conversation(telegram_id, user_query, ai_response)
            
            # Enhanced keyboard with better visual hierarchy
            keyboard = [
                [InlineKeyboardButton("💡 Ask Another Question", callback_data="ai_chat")],
                [InlineKeyboardButton("🔙 Back to AI Menu", callback_data="ai_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ]
            
            # Clean up the AI response
            cleaned_response = self._clean_ai_response(ai_response)
            
            await update.message.reply_text(
                f"🤖 *AI Assistant*\n\n💭 **Your Question:**\n_{TextHelper.escape_markdown(user_query)}_\n\n✨ **My Response:**\n{cleaned_response}\n\n💡 *Need more help? Try asking me to create reminders, tasks, habits, or notes using natural language!*",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"AI query error: {e}")
            
            # Enhanced error message
            error_message = (
                "😔 *Oops! Something went wrong*\n\n"
                "I'm having trouble processing your request right now. "
                "This might be due to:\n"
                "• Temporary connection issues\n"
                "• High server load\n"
                "• Network problems\n\n"
                "Please try again in a moment! 🔄"
            )
            
            await update.message.reply_text(
                error_message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data="ai_chat")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
        
        return ConversationHandler.END
    
    async def _detect_and_execute_action(self, user_query: str, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Detect if user query is a command and execute it"""
        query_lower = user_query.lower()
        
        # Check for reminder commands
        if any(word in query_lower for word in ['remind', 'reminder', 'remind me']):
            return await self._create_reminder_from_text(user_query, user_id, context)
        
        # Check for task commands
        if any(word in query_lower for word in ['task', 'create task', 'add task', 'todo']):
            return await self._create_task_from_text(user_query, user_id, context)
        
        # Check for habit commands
        if any(word in query_lower for word in ['habit', 'build habit', 'create habit', 'start habit']):
            return await self._create_habit_from_text(user_query, user_id, context)
        
        # Check for note commands
        if any(word in query_lower for word in ['note', 'save', 'remember']):
            return await self._create_note_from_text(user_query, user_id, context)
        
        return {'success': False, 'message': ''}
    
    async def _create_reminder_from_text(self, text: str, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Create a reminder from natural language text"""
        try:
            # Use AI to extract reminder details with more explicit JSON formatting instructions
            system_message = (
                "You are a reminder extraction assistant. Extract reminder information from the user's text and return ONLY a valid JSON object. "
                "The JSON must contain exactly these fields: title (string), time (string in format 'dd-mm-yyyy at hh:mm' or relative like 'in 2 hours'), "
                "and description (string). If time is not specified, use 'in 1 hour' as default. "
                "IMPORTANT: Return ONLY the JSON object, no additional text, explanations, or markdown formatting. "
                "Example output: {\"title\": \"Call mom\", \"time\": \"tomorrow at 3pm\", \"description\": \"Call mom to check on her\"}"
            )
            
            ai_response = await self._call_ai_api_with_fallback(system_message, text)
            
            # Clean the response to extract JSON
            cleaned_response = self._extract_json_from_response(ai_response)
            
            # Try to parse JSON response
            try:
                reminder_data = json.loads(cleaned_response)
                title = reminder_data.get('title', 'Reminder')
                time_str = reminder_data.get('time', 'in 1 hour')
                description = reminder_data.get('description', '')
                
                # Parse the time
                user_timezone = context.user_data.get('user_timezone', 'UTC')
                remind_at = TimeHelper.parse_time_input(time_str, user_timezone)
                
                if not remind_at:
                    return {'success': False, 'message': 'Could not parse the time. Please try again.'}
                
                # Create the reminder
                with get_db() as db:
                    user = db.query(User).filter(User.id == user_id).first()
                    if not user:
                        return {'success': False, 'message': 'User not found.'}
                    
                    reminder = Reminder(
                        user_id=user_id,
                        title=title,
                        description=description,
                        remind_at=remind_at.astimezone(pytz.UTC),
                        created_at=datetime.utcnow()
                    )
                    db.add(reminder)
                    db.commit()
                    db.refresh(reminder)
                    
                    # Schedule notification using the correct scheduler
                    scheduler = getattr(context.bot, 'scheduler', None)
                    if scheduler is None and hasattr(context.bot, '_application'):
                        scheduler = getattr(context.bot._application, 'scheduler', None)
                    if scheduler is None:
                        from apscheduler.schedulers.asyncio import AsyncIOScheduler
                        scheduler = AsyncIOScheduler()
                    notification_service = NotificationService(context.bot, scheduler)
                    await notification_service.schedule_reminder_notification(reminder.id, remind_at.astimezone(pytz.UTC))
                
                return {
                    'success': True, 
                    'message': (
                        f"🎯 **Reminder Created Successfully!**\n\n"
                        f"📝 **Title:** {title}\n"
                        f"⏰ **Time:** {remind_at.strftime('%d-%m-%Y at %H:%M')}\n"
                        f"📄 **Description:** {description or 'No description'}\n\n"
                        f"✅ Your reminder has been scheduled and will notify you at the specified time!"
                    )
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for reminder: {e}, Response: {cleaned_response}")
                return {'success': False, 'message': 'Could not parse reminder details. Please try again.'}
                
        except Exception as e:
            logger.error(f"Error creating reminder from text: {e}")
            return {'success': False, 'message': 'Error creating reminder. Please try again.'}
    
    async def _create_task_from_text(self, text: str, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Create a task from natural language text"""
        try:
            # Use AI to extract task details with more explicit JSON formatting instructions
            system_message = (
                "You are a task extraction assistant. Extract task information from the user's text and return ONLY a valid JSON object. "
                "The JSON must contain exactly these fields: title (string), description (string), priority (string: low/medium/high/urgent), "
                "deadline (string in format 'dd-mm-yyyy at hh:mm' or relative like 'by Friday', or null), and project_name (string). "
                "If priority is not specified, use 'medium'. If deadline is not specified, use null. "
                "IMPORTANT: Return ONLY the JSON object, no additional text, explanations, or markdown formatting. "
                "Example output: {\"title\": \"Finish report\", \"description\": \"Complete the quarterly report\", \"priority\": \"high\", \"deadline\": \"by Friday\", \"project_name\": \"Work\"}"
            )
            
            ai_response = await self._call_ai_api_with_fallback(system_message, text)
            
            # Clean the response to extract JSON
            cleaned_response = self._extract_json_from_response(ai_response)
            
            try:
                task_data = json.loads(cleaned_response)
                title = task_data.get('title', 'New Task')
                description = task_data.get('description', '')
                priority_str = task_data.get('priority', 'medium').lower()
                deadline_str = task_data.get('deadline')
                project_name = task_data.get('project_name', '')
                
                # Map priority
                priority_map = {
                    'low': TaskPriority.LOW,
                    'medium': TaskPriority.MEDIUM,
                    'high': TaskPriority.HIGH,
                    'urgent': TaskPriority.URGENT
                }
                priority = priority_map.get(priority_str, TaskPriority.MEDIUM)
                
                # Parse deadline if provided
                deadline = None
                if deadline_str:
                    user_timezone = context.user_data.get('user_timezone', 'UTC')
                    deadline = TimeHelper.parse_time_input(deadline_str, user_timezone)
                
                # Create the task
                with get_db() as db:
                    task = Task(
                        user_id=user_id,
                        title=title,
                        description=description,
                        priority=priority,
                        status=TaskStatus.TODO,
                        project_name=project_name,
                        due_date=deadline.astimezone(pytz.UTC) if deadline else None,
                        created_at=datetime.utcnow()
                    )
                    db.add(task)
                    db.commit()
                    db.refresh(task)
                
                deadline_text = f"\n⏰ Due: {deadline.strftime('%d-%m-%Y at %H:%M')}" if deadline else ""
                priority_emoji = {"low": "🔵", "medium": "🟢", "high": "🟡", "urgent": "🔴"}[priority_str]
                
                return {
                    'success': True, 
                    'message': (
                        f"📋 **Task Created Successfully!**\n\n"
                        f"{priority_emoji} **Title:** {title}\n"
                        f"📄 **Description:** {description or 'No description'}\n"
                        f"📁 **Project:** {project_name or 'General'}\n"
                        f"{deadline_text}\n\n"
                        f"✅ Your task has been added to your todo list!"
                    )
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for task: {e}, Response: {cleaned_response}")
                return {'success': False, 'message': 'Could not parse task details. Please try again.'}
                
        except Exception as e:
            logger.error(f"Error creating task from text: {e}")
            return {'success': False, 'message': 'Error creating task. Please try again.'}
    
    async def _create_habit_from_text(self, text: str, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Create a habit from natural language text"""
        try:
            # Use AI to extract habit details with more explicit JSON formatting instructions
            system_message = (
                "You are a habit extraction assistant. Extract habit information from the user's text and return ONLY a valid JSON object. "
                "The JSON must contain exactly these fields: name (string), description (string), frequency (string: daily/weekly/monthly), "
                "target_value (number), and unit (string: minutes/hours/times/etc). "
                "If frequency is not specified, use 'daily'. If target_value is not specified, use 1. "
                "If unit is not specified, use 'times'. "
                "IMPORTANT: Return ONLY the JSON object, no additional text, explanations, or markdown formatting. "
                "Example output: {\"name\": \"Read books\", \"description\": \"Read for 30 minutes daily\", \"frequency\": \"daily\", \"target_value\": 30, \"unit\": \"minutes\"}"
            )
            
            ai_response = await self._call_ai_api_with_fallback(system_message, text)
            
            # Clean the response to extract JSON
            cleaned_response = self._extract_json_from_response(ai_response)
            
            try:
                habit_data = json.loads(cleaned_response)
                name = habit_data.get('name', 'New Habit')
                description = habit_data.get('description', '')
                frequency_str = habit_data.get('frequency', 'daily').lower()
                target_value = habit_data.get('target_value', 1)
                unit = habit_data.get('unit', 'times')
                
                # Map frequency
                frequency_map = {
                    'daily': HabitFrequency.DAILY,
                    'weekly': HabitFrequency.WEEKLY,
                    'monthly': HabitFrequency.MONTHLY
                }
                frequency = frequency_map.get(frequency_str, HabitFrequency.DAILY)
                
                # Create the habit
                with get_db() as db:
                    habit = Habit(
                        user_id=user_id,
                        name=name,
                        description=description,
                        frequency=frequency,
                        target_value=target_value,
                        unit=unit,
                        is_active=True,
                        streak_count=0,
                        created_at=datetime.utcnow()
                    )
                    db.add(habit)
                    db.commit()
                    db.refresh(habit)
                
                frequency_emoji = {"daily": "📅", "weekly": "📆", "monthly": "📊"}[frequency_str]
                
                return {
                    'success': True, 
                    'message': (
                        f"🎯 **Habit Created Successfully!**\n\n"
                        f"{frequency_emoji} **Name:** {name}\n"
                        f"📄 **Description:** {description or 'No description'}\n"
                        f"🎯 **Target:** {target_value} {unit} {frequency_str}\n\n"
                        f"✅ Your habit has been added! Start building this positive routine today!"
                    )
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for habit: {e}, Response: {cleaned_response}")
                return {'success': False, 'message': 'Could not parse habit details. Please try again.'}
                
        except Exception as e:
            logger.error(f"Error creating habit from text: {e}")
            return {'success': False, 'message': 'Error creating habit. Please try again.'}
    
    async def _create_note_from_text(self, text: str, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Create a note from natural language text"""
        try:
            # Use AI to extract note details with more explicit JSON formatting instructions
            system_message = (
                "You are a note extraction assistant. Extract note information from the user's text and return ONLY a valid JSON object. "
                "The JSON must contain exactly these fields: title (string) and content (string). "
                "The title should be a short summary, and content should be the full note text. "
                "IMPORTANT: Return ONLY the JSON object, no additional text, explanations, or markdown formatting. "
                "Example output: {\"title\": \"Meeting notes\", \"content\": \"Important discussion about project timeline\"}"
            )
            
            ai_response = await self._call_ai_api_with_fallback(system_message, text)
            
            # Clean the response to extract JSON
            cleaned_response = self._extract_json_from_response(ai_response)
            
            try:
                note_data = json.loads(cleaned_response)
                title = note_data.get('title', 'New Note')
                content = note_data.get('content', text)
                
                # Create the note
                with get_db() as db:
                    note = Note(
                        user_id=user_id,
                        title=title,
                        content=content,
                        is_pinned=False,
                        created_at=datetime.utcnow()
                    )
                    db.add(note)
                    db.commit()
                    db.refresh(note)
                
                return {
                    'success': True, 
                    'message': (
                        f"📝 **Note Created Successfully!**\n\n"
                        f"📄 **Title:** {title}\n"
                        f"📝 **Content:** {content[:100]}{'...' if len(content) > 100 else ''}\n\n"
                        f"✅ Your note has been saved! You can find it in your notes section."
                    )
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for note: {e}, Response: {cleaned_response}")
                # Fallback: create note with original text
                with get_db() as db:
                    note = Note(
                        user_id=user_id,
                        title="Quick Note",
                        content=text,
                        is_pinned=False,
                        created_at=datetime.utcnow()
                    )
                    db.add(note)
                    db.commit()
                    db.refresh(note)
                
                return {
                    'success': True, 
                    'message': f"✅ Note created!\n\n📝 **Quick Note**\n📄 {text[:100]}{'...' if len(text) > 100 else ''}"
                }
                
        except Exception as e:
            logger.error(f"Error creating note from text: {e}")
            return {'success': False, 'message': 'Error creating note. Please try again.'}
    
    @with_user
    @error_handler
    async def suggest_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Suggest tasks based on user's current tasks and habits"""
        if not self.enabled:
            return
        
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        await query.edit_message_text("🤖 Analyzing your data to suggest tasks...")
        
        try:
            with get_db() as db:
                from database.models import Task, Habit, TaskStatus
                recent_tasks = db.query(Task).filter(
                    Task.user_id == user_id,
                    Task.status.in_([TaskStatus.TODO, TaskStatus.COMPLETED])
                ).order_by(Task.created_at.desc()).limit(10).all()
                active_habits = db.query(Habit).filter(
                    Habit.user_id == user_id,
                    Habit.is_active == True
                ).all()
                # Extract all needed fields while session is open
                tasks_context = []
                for task in recent_tasks:
                    tasks_context.append({
                        "title": task.title,
                        "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                        "priority": task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
                        "project": task.project_name
                    })
                habits_context = []
                for habit in active_habits:
                    habits_context.append({
                        "name": habit.name,
                        "frequency": habit.frequency.value if hasattr(habit.frequency, 'value') else str(habit.frequency),
                        "streak": habit.streak_count
                    })
            
            system_message = (
                "You are a productivity coach. Based on the user's current tasks and habits, "
                "suggest 3-5 new tasks that would help them improve their productivity and achieve their goals. "
                "Be specific and actionable. Use clean, simple formatting with minimal markdown. "
                "Format as a numbered list with clear, concise suggestions."
            )
            
            user_message = (
                f"Current tasks: {tasks_context}\nCurrent habits: {habits_context}"
            )
            
            ai_response = await self._call_ai_api_with_fallback(system_message, user_message)
            
            # Clean up the AI response
            cleaned_response = self._clean_ai_response(ai_response)
            
            await query.edit_message_text(
                f"🤖 *AI Suggestions*\n\n{cleaned_response}",
                parse_mode='Markdown',
                reply_markup=Keyboards.ai_menu()
            )
            
        except Exception as e:
            logger.error(f"AI task suggestion error: {e}")
            await query.edit_message_text(
                "❌ Sorry, I couldn't generate suggestions right now. Please try again later.",
                reply_markup=Keyboards.ai_menu()
            )
    
    @with_user
    @error_handler
    async def get_productivity_insights(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get AI-powered productivity insights and analytics"""
        if not self.enabled:
            return
        
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        await query.edit_message_text("🤖 Analyzing your productivity patterns...")
        
        try:
            with get_db() as db:
                # Get comprehensive user data
                tasks = db.query(Task).filter(Task.user_id == user_id).all()
                habits = db.query(Habit).filter(Habit.user_id == user_id).all()
                notes = db.query(Note).filter(Note.user_id == user_id).all()
                reminders = db.query(Reminder).filter(Reminder.user_id == user_id).all()
                
                # Extract data while session is open
                task_stats = {
                    "total": len(tasks),
                    "completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                    "todo": len([t for t in tasks if t.status == TaskStatus.TODO]),
                    "in_progress": len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS]),
                    "high_priority": len([t for t in tasks if t.priority in [TaskPriority.HIGH, TaskPriority.URGENT]])
                }
                
                habit_stats = {
                    "total": len(habits),
                    "active": len([h for h in habits if h.is_active]),
                    "avg_streak": sum(h.streak_count for h in habits) / len(habits) if habits else 0,
                    "daily_habits": len([h for h in habits if h.frequency == HabitFrequency.DAILY])
                }
                
                recent_tasks = [{"title": t.title, "status": t.status.value, "priority": t.priority.value} 
                               for t in tasks[-5:]]  # Last 5 tasks
                top_habits = sorted(habits, key=lambda h: h.streak_count, reverse=True)[:3]
                habit_data = [{"name": h.name, "streak": h.streak_count, "frequency": h.frequency.value} 
                             for h in top_habits]
            
            system_message = (
                "You are a productivity analyst. Based on the user's data, provide insights about their "
                "productivity patterns, strengths, areas for improvement, and personalized recommendations. "
                "Be encouraging and actionable. Use clean, simple formatting with minimal markdown. "
                "Structure your response with clear sections using simple headers (##) and bullet points. "
                "Avoid excessive formatting symbols like ####, ***, or escaped characters. "
                "Keep it readable and professional."
            )
            
            user_message = (
                f"Task Statistics: {task_stats}\n"
                f"Habit Statistics: {habit_stats}\n"
                f"Recent Tasks: {recent_tasks}\n"
                f"Top Habits: {habit_data}\n"
                f"Total Notes: {len(notes)}\n"
                f"Total Reminders: {len(reminders)}\n\n"
                "Please provide insights and recommendations."
            )
            
            insights = await self._call_ai_api_with_fallback(system_message, user_message)
            
            # Clean up the AI response
            cleaned_insights = self._clean_ai_response(insights)
            
            await query.edit_message_text(
                f"📊 *AI Productivity Insights*\n\n{cleaned_insights}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎯 Get Action Plan", callback_data="ai_action_plan")],
                    [InlineKeyboardButton("📈 Detailed Analytics", callback_data="stats_overview")],
                    [InlineKeyboardButton("🔙 Back to AI Menu", callback_data="ai_menu")]
                ])
            )
            
        except Exception as e:
            logger.error(f"AI insights error: {e}")
            await query.edit_message_text(
                "❌ Sorry, I couldn't generate insights right now. Please try again later.",
                reply_markup=Keyboards.ai_menu()
            )
    
    @with_user
    @error_handler
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel AI conversation"""
        await update.message.reply_text(
            "❌ AI conversation cancelled.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🤖 AI Menu", callback_data="ai_menu")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
            ])
        )
        
        return ConversationHandler.END

    @with_user
    @error_handler
    async def suggest_habits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Suggest habits based on user's goals and current habits"""
        if not self.enabled:
            return
        
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        await query.edit_message_text("🤖 Analyzing your habits to provide recommendations...")
        
        try:
            # Get user's current habits
            with get_db() as db:
                active_habits = db.query(Habit).filter(
                    Habit.user_id == user_id,
                    Habit.is_active == True
                ).all()
                
                # Extract all needed fields while session is open
                habits_context = []
                for habit in active_habits:
                    habits_context.append({
                        "name": habit.name,
                        "frequency": habit.frequency.value,
                        "streak": habit.streak_count,
                        "target": habit.target_value,
                        "unit": habit.unit
                    })
            
            # Call OpenAI for habit suggestions
            system_message = (
                "You are a habit formation expert. Based on the user's current habits, "
                "suggest 3-5 new habits that would complement their existing routine and "
                "help them build a well-rounded lifestyle. Focus on different areas like "
                "health, productivity, learning, and well-being. Be specific about frequency and targets. "
                "Use clean, simple formatting with minimal markdown. Avoid excessive formatting symbols."
            )
            
            user_message = (
                f"Current habits: {json.dumps(habits_context) if habits_context else 'No current habits'}\n"
                "Please suggest new habits that would create a balanced routine."
            )
            
            suggestions = await self._call_ai_api_with_fallback(system_message, user_message)
            
            # Clean up the AI response
            cleaned_suggestions = self._clean_ai_response(suggestions)
            
            await query.edit_message_text(
                f"💡 *AI Habit Recommendations*\n\n{cleaned_suggestions}\n\n"
                f"🎯 Start small and build consistency!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎯 Add Habit", callback_data="habit_add")],
                    [InlineKeyboardButton("🔄 Get New Suggestions", callback_data="ai_suggest_habits")],
                    [InlineKeyboardButton("🔙 Back to AI Menu", callback_data="ai_menu")]
                ])
            )
            
        except Exception as e:
            logger.error(f"AI habit suggestion error: {e}")
            await query.edit_message_text(
                "❌ Sorry, I couldn't generate habit recommendations right now. "
                "Please try again later.",
                reply_markup=Keyboards.ai_menu()
            )
    
    @with_user
    @error_handler
    async def summarize_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Summarize user's recent notes"""
        if not self.enabled:
            return
        
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        await query.edit_message_text("🤖 Analyzing your notes to generate a summary...")
        
        try:
            with get_db() as db:
                notes = db.query(Note).filter(Note.user_id == user_id).order_by(Note.created_at.desc()).limit(10).all()
                # Extract all needed fields while session is open
                note_texts = [note.content for note in notes if note.content]
            if not note_texts:
                await query.edit_message_text(
                    "❌ You don't have any notes to summarize.",
                    reply_markup=Keyboards.ai_menu()
                )
                return
            system_message = (
                "You are a productivity assistant. Summarize the following notes into a concise summary, "
                "highlighting key ideas, action items, and important information."
            )
            user_message = "\n---\n".join(note_texts)
            ai_response = await self._call_ai_api_with_fallback(system_message, user_message)
            
            # Clean up the AI response
            cleaned_response = self._clean_ai_response(ai_response)
            
            await query.edit_message_text(
                f"🤖 *AI Note Summary*\n\n{cleaned_response}",
                parse_mode='Markdown',
                reply_markup=Keyboards.ai_menu()
            )
        except Exception as e:
            logger.error(f"AI note summary error: {e}")
            await query.edit_message_text(
                "❌ Sorry, I couldn't summarize your notes right now. Please try again later.",
                reply_markup=Keyboards.ai_menu()
            )
    
    async def _get_user_context(self, user_id: int) -> str:
        """Get user context for personalized AI responses"""
        try:
            with get_db() as db:
                from database.models import Task, Habit, Note, User, TaskStatus
                db_user = db.query(User).filter(User.id == user_id).first()
                if not db_user:
                    return ""
                # Count user's data
                task_count = db.query(Task).filter(Task.user_id == user_id).count()
                active_task_count = db.query(Task).filter(
                    Task.user_id == user_id,
                    Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS])
                ).count()
                habit_count = db.query(Habit).filter(
                    Habit.user_id == user_id,
                    Habit.is_active == True
                ).count()
                note_count = db.query(Note).filter(Note.user_id == user_id).count()
                context = (
                    f"User has {task_count} total tasks ({active_task_count} active), "
                    f"{habit_count} active habits, and {note_count} notes. "
                    f"Timezone: {db_user.timezone if db_user.timezone else 'UTC'}."
                )
                return context
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return ""
    
    async def _store_conversation(self, telegram_id: int, query: str, response: str):
        """Store conversation in Redis for context"""
        try:
            key = f"ai_conversation:{telegram_id}"
            conversation = {
                "query": query,
                "response": response,
                "timestamp": str(datetime.utcnow())
            }
            
            # Store last 5 conversations
            self.redis.lpush(key, json.dumps(conversation))
            self.redis.ltrim(key, 0, 4)  # Keep only last 5
            self.redis.expire(key, 86400)  # Expire after 24 hours
            
        except Exception as e:
            logger.error(f"Error storing AI conversation: {e}")

    def _extract_json_from_response(self, text: str) -> str:
        """Extract JSON from AI response, handling various formats"""
        if not text:
            return text
        
        # Try to find JSON in the response
        import re
        
        # First, try to parse as valid JSON
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        
        # Look for JSON object pattern with better regex
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        if matches:
            # Try each match to find valid JSON
            for match in matches:
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue
            
            # If no valid JSON found in matches, try a more aggressive approach
            # Look for any text that looks like JSON
            potential_json_pattern = r'\{[^}]*"[^"]*"[^}]*\}'
            potential_matches = re.findall(potential_json_pattern, text, re.DOTALL)
            
            for match in potential_matches:
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue
        
        # Look for JSON in markdown code blocks
        code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        code_matches = re.findall(code_block_pattern, text, re.DOTALL)
        
        if code_matches:
            for match in code_matches:
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue
        
        # If no valid JSON found, try to clean the response and return as is
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        return text
    
    def _clean_ai_response(self, text: str) -> str:
        """Clean up AI response by removing unwanted markdown symbols and escaped characters"""
        if not text:
            return text
        
        # Remove escaped characters
        text = text.replace('\\/', '/').replace('\\*', '*').replace('\\_', '_')
        text = text.replace('\\`', '`').replace('\\[', '[').replace('\\]', ']')
        text = text.replace('\\(', '(').replace('\\)', ')').replace('\\#', '#')
        text = text.replace('\\+', '+').replace('\\-', '-').replace('\\.', '.')
        text = text.replace('\\!', '!').replace('\\|', '|')
        
        # Remove excessive markdown formatting
        text = text.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
        
        # Clean up headers (remove # symbols but keep structure)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove header symbols but keep the text
            if line.strip().startswith('#'):
                # Count # symbols and remove them, keeping the text
                header_text = line.lstrip('#').strip()
                if header_text:
                    cleaned_lines.append(header_text)
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    async def _call_ai_api_with_fallback(self, system_message: str, user_query: str) -> str:
        """Call AI API with fallback: OpenAI first, then DeepSeek if OpenAI fails"""
        
        # Try OpenAI first
        if self.openai_enabled:
            try:
                logger.info("Attempting OpenAI API call...")
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_query}
                    ],
                    max_tokens=1000,  # Increased for better JSON responses
                    temperature=0.3,  # Lower temperature for more consistent JSON
                    response_format={"type": "json_object"}  # Force JSON response
                )
                ai_response = response.choices[0].message.content.strip()
                logger.info("OpenAI API call successful")
                return ai_response
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"OpenAI API call failed: {error_msg}")
                
                # Check if it's a regional restriction error
                if "unsupported_country_region_territory" in error_msg or "403" in error_msg:
                    logger.info("Detected regional restriction, trying DeepSeek fallback...")
                else:
                    logger.info("OpenAI failed for other reason, trying DeepSeek fallback...")
        
        # Fallback to DeepSeek
        if self.deepseek_enabled:
            try:
                logger.info("Attempting DeepSeek API call...")
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.deepseek_base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.deepseek_api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "deepseek-chat",
                            "messages": [
                                {"role": "system", "content": system_message},
                                {"role": "user", "content": user_query}
                            ],
                            "max_tokens": 1000,  # Increased for better JSON responses
                            "temperature": 0.3,  # Lower temperature for more consistent JSON
                            "response_format": {"type": "json_object"}  # Force JSON response
                        },
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        ai_response = data["choices"][0]["message"]["content"].strip()
                        logger.info("DeepSeek API call successful")
                        return ai_response
                    else:
                        logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                        
            except Exception as e:
                logger.error(f"DeepSeek API call failed: {e}")
        
        # If both fail, return a helpful error message
        error_message = (
            "I'm sorry, but I'm currently unable to process your request. "
            "This might be due to:\n"
            "• Temporary service issues\n"
            "• Network connectivity problems\n"
            "• API service limitations\n\n"
            "Please try again later or contact support if the problem persists."
        )
        
        logger.error("Both OpenAI and DeepSeek APIs failed")
        return error_message