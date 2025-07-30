from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.database import get_db
from database.models import User, Task, TaskStatus, TaskPriority
from utils.decorators import with_user, error_handler
from utils.helpers import TimeHelper, TextHelper
from utils.keyboards import Keyboards
from loguru import logger
from datetime import datetime
from typing import Optional
from sqlalchemy import func, case
import pytz

# Conversation states
class TaskFeature:
    TASK_TITLE = 0
    TASK_DESCRIPTION = 1
    TASK_PRIORITY = 2
    TASK_DUE_DATE = 3
    TASK_PROJECT = 4
    EDIT_PROJECT_NAME = 5

    def __init__(self, notification_service=None):
        self.notification_service = notification_service

    @with_user
    @error_handler
    async def show_tasks_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show tasks main menu"""
        text = (
            "✅ *Tasks Management*\n\n"
            "Choose an option below:"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.tasks_menu()
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.tasks_menu()
            )
    
    @with_user
    @error_handler
    async def start_add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start adding a new task"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "✅ *Add New Task*\n\n"
            "Please enter the task title:",
            parse_mode='Markdown'
        )
        
        return self.TASK_TITLE
    
    @with_user
    @error_handler
    async def get_task_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get task title from user"""
        title = update.message.text.strip()
        
        if len(title) > 255:
            await update.message.reply_text(
                "❌ Title is too long. Please keep it under 255 characters."
            )
            return self.TASK_TITLE
        
        context.user_data['task_title'] = title
        
        await update.message.reply_text(
            f"✅ Title: *{TextHelper.escape_markdown(title)}*\n\n"
            "📝 Please enter a description (optional):\n\n"
            "Send the description or type `/skip` to continue.",
            parse_mode='Markdown'
        )
        
        return self.TASK_DESCRIPTION
    
    @with_user
    @error_handler
    async def get_task_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get task description from user"""
        text = update.message.text.strip() if update.message else None
        if text and text.lower() == '/skip':
            description = None
        else:
            description = text
            if description and len(description) > 1000:
                await update.message.reply_text(
                    "❌ Description is too long. Please keep it under 1000 characters."
                )
                return self.TASK_DESCRIPTION
        
        context.user_data['task_description'] = description
        
        await update.message.reply_text(
            "🎯 *Select Task Priority:*",
            parse_mode='Markdown',
            reply_markup=Keyboards.priority_selection()
        )
        
        return self.TASK_PRIORITY
    
    @with_user
    @error_handler
    async def get_task_priority(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get task priority from user"""
        query = update.callback_query
        await query.answer()
        
        priority_map = {
            'priority_urgent': TaskPriority.URGENT,
            'priority_high': TaskPriority.HIGH,
            'priority_medium': TaskPriority.MEDIUM,
            'priority_low': TaskPriority.LOW
        }
        
        priority = priority_map.get(query.data, TaskPriority.MEDIUM)
        context.user_data['task_priority'] = priority
        
        priority_emoji = {
            TaskPriority.URGENT: "🔴",
            TaskPriority.HIGH: "🟡",
            TaskPriority.MEDIUM: "🟢",
            TaskPriority.LOW: "🔵"
        }
        
        await query.edit_message_text(
            f"🎯 Priority: {priority_emoji[priority]} *{priority.value.title()}*\n\n"
            "📅 Enter due date (optional):\n\n"
            "Please use the format: *dd-mm-yyyy at hh:mm*\n\n"
            "Examples:\n"
            "• `27-06-2025 at 14:30`\n"
            "• `27-06-2025 at 2:30 PM`\n"
            "• `tomorrow at 9am`\n"
            "• `in 3 days`\n\n"
            "Or type `/skip` to continue without due date.",
            parse_mode='Markdown'
        )
        
        return self.TASK_DUE_DATE
    
    @with_user
    @error_handler
    async def get_task_due_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get task due date from user"""
        text = update.message.text.strip() if update.message else None
        if text and text.lower() == '/skip':
            due_date = None
        else:
            due_date = None
            if text:
                user_timezone = context.user_data['user_timezone'] or 'UTC'
                # Parse the date input
                due_date = TimeHelper.parse_time_input(text, user_timezone)
                
                if not due_date:
                    await update.message.reply_text(
                        "❌ I couldn't understand that date format. Please try again or type `/skip`.\n\n"
                        "Please use the format: *dd-mm-yyyy at hh:mm*\n\n"
                        "Examples:\n"
                        "• `27-06-2025 at 14:30`\n"
                        "• `27-06-2025 at 2:30 PM`\n"
                        "• `tomorrow at 9am`\n"
                        "• `in 3 days`",
                        parse_mode='Markdown'
                    )
                    return self.TASK_DUE_DATE
        
        user_timezone = context.user_data['user_timezone'] or 'UTC'
        local_tz = pytz.timezone(user_timezone)
        
        # Ensure due_date is localized to user's timezone
        if due_date and due_date.tzinfo is None:
            due_date = local_tz.localize(due_date)
        elif due_date:
            due_date = due_date.astimezone(local_tz)
        
        context.user_data['task_due_date'] = due_date
        
        await update.message.reply_text(
            "📁 Enter project name (optional):\n\n"
            "This helps organize related tasks together.\n"
            "Type the project name or `/skip` to finish.",
            parse_mode='Markdown'
        )
        
        return self.TASK_PROJECT
    
    @with_user
    @error_handler
    async def get_task_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get task project from user"""
        text = update.message.text.strip() if update.message else None
        if text and text.lower() == '/skip':
            project_name = None
        else:
            project_name = text
            if project_name and len(project_name) > 255:
                await update.message.reply_text(
                    "❌ Project name is too long. Please keep it under 255 characters."
                )
                return self.TASK_PROJECT
        
        # Save the task
        user_id = context.user_data['user_id']
        title = context.user_data['task_title']
        description = context.user_data.get('task_description')
        priority = context.user_data['task_priority']
        due_date = context.user_data.get('task_due_date')
        
        with get_db() as db:
            task = Task(
                user_id=user_id,
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                project_name=project_name
            )
            db.add(task)
            db.commit()
            db.refresh(task)
        
        # Build confirmation message
        priority_emoji = {
            TaskPriority.URGENT: "🔴",
            TaskPriority.HIGH: "🟡",
            TaskPriority.MEDIUM: "🟢",
            TaskPriority.LOW: "🔵"
        }
        
        user_timezone = context.user_data['user_timezone'] or 'UTC'
        
        message = f"✅ *Task Created Successfully!*\n\n"
        message += f"📝 **Title:** {TextHelper.escape_markdown(title)}\n"
        if description:
            message += f"📄 **Description:** {TextHelper.escape_markdown(description)}\n"
        message += f"🎯 **Priority:** {priority_emoji[priority]} {priority.value.title()}\n"
        if due_date:
            formatted_date = TimeHelper.format_datetime(due_date, user_timezone)
            message += f"📅 **Due Date:** {formatted_date}\n"
        if project_name:
            message += f"📁 **Project:** {TextHelper.escape_markdown(project_name)}\n"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=Keyboards.tasks_menu()
        )
        
        # Clear conversation data
        context.user_data.clear()
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def list_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List user's tasks"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        user_timezone = context.user_data['user_timezone']
        
        with get_db() as db:
            tasks = db.query(Task).filter(
                Task.user_id == user_id,
                Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS])
            ).order_by(Task.priority.desc(), Task.created_at).limit(10).all()
            # Extract all needed fields while session is open
            task_data = []
            for task in tasks:
                task_data.append({
                    'id': task.id,
                    'title': task.title,
                    'priority': task.priority,
                    'status': task.status,
                    'project_name': task.project_name,
                    'due_date': task.due_date,
                })
        
        if not task_data:
            await query.edit_message_text(
                "✅ *Your Tasks*\n\n"
                "You don't have any active tasks.\n"
                "Use the button below to create one!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Task", callback_data="task_add")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
            return
        
        message = "✅ *Your Active Tasks*\n\n"
        keyboard = []
        
        priority_emoji = {
            TaskPriority.URGENT: "🔴",
            TaskPriority.HIGH: "🟡",
            TaskPriority.MEDIUM: "🟢",
            TaskPriority.LOW: "🔵"
        }
        
        status_emoji = {
            TaskStatus.TODO: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅"
        }
        
        for i, task in enumerate(task_data, 1):
            message += f"{i}. {priority_emoji[task['priority']]} {status_emoji[task['status']]} *{TextHelper.escape_markdown(task['title'])}*\n"
            
            if task['project_name']:
                message += f"   📁 {TextHelper.escape_markdown(task['project_name'])}\n"
            
            if task['due_date']:
                formatted_date = TimeHelper.format_datetime(task['due_date'], user_timezone)
                message += f"   📅 Due: {formatted_date}\n"
            
            message += "\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Complete #{i}", 
                    callback_data=f"task_complete_{task['id']}"
                ),
                InlineKeyboardButton(
                    f"🗑️ Delete #{i}", 
                    callback_data=f"task_delete_{task['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add New", callback_data="task_add")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def complete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mark task as completed"""
        query = update.callback_query
        await query.answer()
        
        task_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            task = db.query(Task).filter(
                Task.id == task_id,
                Task.user_id == user_id
            ).first()
            
            if not task:
                await query.edit_message_text("❌ Task not found.")
                return
            
            # Extract task title while session is open
            task_title = task.title
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            db.commit()
        
        await query.edit_message_text(
            f"🎉 *Task Completed!*\n\n"
            f"✅ {TextHelper.escape_markdown(task_title)}\n\n"
            f"Great job! Keep up the good work! 💪",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Tasks", callback_data="task_list")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def show_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's projects"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Get projects with task counts
            projects = db.query(Task.project_name, 
                              func.count(Task.id).label('task_count'),
                              func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)).label('completed_count')
                              ).filter(
                Task.user_id == user_id,
                Task.project_name.isnot(None),
                Task.project_name != ''
            ).group_by(Task.project_name).all()
        
        if not projects:
            await query.edit_message_text(
                "📁 *Your Projects*\n\n"
                "You don't have any projects yet.\n"
                "Create tasks with project names to organize them!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Task", callback_data="task_add")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
            return
        
        message = "📁 *Your Projects*\n\n"
        keyboard = []
        
        for project in projects:
            progress = int((project.completed_count / project.task_count) * 100) if project.task_count > 0 else 0
            message += f"📁 *{TextHelper.escape_markdown(project.project_name)}*\n"
            message += f"   📊 {project.completed_count}/{project.task_count} tasks ({progress}%)\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 View {project.project_name}", 
                    callback_data=f"project_view_{project.project_name}"
                ),
                InlineKeyboardButton(
                    f"✏️ Edit", 
                    callback_data=f"project_edit_{project.project_name}"
                ),
                InlineKeyboardButton(
                    f"🗑️ Delete", 
                    callback_data=f"project_delete_{project.project_name}"
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
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel task creation conversation"""
        await update.message.reply_text(
            "❌ Task creation cancelled.",
            reply_markup=Keyboards.tasks_menu()
        )
        
        # Clear conversation data
        for key in ['task_title', 'task_description', 'task_priority', 'task_due_date']:
            context.user_data.pop(key, None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def delete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete an existing task"""
        query = update.callback_query
        await query.answer()
        
        task_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            task = db.query(Task).filter(
                Task.id == task_id,
                Task.user_id == user_id
            ).first()
            
            if not task:
                await query.edit_message_text("❌ Task not found.")
                return
            
            # Extract task title while session is open
            task_title = task.title
            
            # Delete the task
            db.delete(task)
            db.commit()
        
        await query.edit_message_text(
            f"🗑️ *Task Deleted!*\n\n"
            f"✅ {TextHelper.escape_markdown(task_title)}\n\n"
            f"Task has been permanently deleted.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Tasks", callback_data="task_list")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def edit_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit project name"""
        query = update.callback_query
        await query.answer()
        
        old_project_name = query.data.replace('project_edit_', '')
        user_id = context.user_data['user_id']
        
        # Store the old project name for the conversation
        context.user_data['editing_project'] = old_project_name
        
        await query.edit_message_text(
            f"✏️ *Edit Project*\n\n"
            f"Current name: *{TextHelper.escape_markdown(old_project_name)}*\n\n"
            f"Please enter the new project name:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Cancel", callback_data="task_projects")]
            ])
        )
        
        return self.EDIT_PROJECT_NAME
    
    @with_user
    @error_handler
    async def get_new_project_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get new project name from user"""
        new_project_name = update.message.text.strip()
        
        if len(new_project_name) > 255:
            await update.message.reply_text(
                "❌ Project name is too long. Please keep it under 255 characters."
            )
            return self.EDIT_PROJECT_NAME
        
        old_project_name = context.user_data['editing_project']
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Update all tasks with the old project name
            tasks_updated = db.query(Task).filter(
                Task.user_id == user_id,
                Task.project_name == old_project_name
            ).update({
                Task.project_name: new_project_name
            })
            db.commit()
        
        await update.message.reply_text(
            f"✅ *Project Updated!*\n\n"
            f"📁 **Old name:** {TextHelper.escape_markdown(old_project_name)}\n"
            f"📁 **New name:** {TextHelper.escape_markdown(new_project_name)}\n"
            f"📊 **Tasks updated:** {tasks_updated}",
            parse_mode='Markdown',
            reply_markup=Keyboards.tasks_menu()
        )
        
        # Clear conversation data
        context.user_data.pop('editing_project', None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def delete_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete project and all its tasks"""
        query = update.callback_query
        await query.answer()
        
        project_name = query.data.replace('project_delete_', '')
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            # Get tasks count before deletion
            tasks_count = db.query(Task).filter(
                Task.user_id == user_id,
                Task.project_name == project_name
            ).count()
            
            # Delete all tasks in the project
            db.query(Task).filter(
                Task.user_id == user_id,
                Task.project_name == project_name
            ).delete()
            db.commit()
        
        await query.edit_message_text(
            f"🗑️ *Project Deleted!*\n\n"
            f"📁 **Project:** {TextHelper.escape_markdown(project_name)}\n"
            f"📊 **Tasks deleted:** {tasks_count}\n\n"
            f"Project and all its tasks have been permanently deleted.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 View Projects", callback_data="task_projects")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def view_project_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View tasks for a specific project"""
        query = update.callback_query
        await query.answer()
        
        project_name = query.data.replace('project_view_', '')
        user_id = context.user_data['user_id']
        user_timezone = context.user_data['user_timezone']
        
        with get_db() as db:
            tasks = db.query(Task).filter(
                Task.user_id == user_id,
                Task.project_name == project_name
            ).order_by(Task.priority.desc(), Task.created_at).all()
            # Extract all needed fields while session is open
            task_data = []
            for task in tasks:
                task_data.append({
                    'id': task.id,
                    'title': task.title,
                    'priority': task.priority,
                    'status': task.status,
                    'due_date': task.due_date,
                })
        
        if not task_data:
            await query.edit_message_text(
                f"📁 *Project: {TextHelper.escape_markdown(project_name)}*\n\n"
                "No tasks found in this project.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Projects", callback_data="task_projects")],
                    [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
                ])
            )
            return
        
        message = f"📁 *Project: {TextHelper.escape_markdown(project_name)}*\n\n"
        keyboard = []
        
        priority_emoji = {
            TaskPriority.URGENT: "🔴",
            TaskPriority.HIGH: "🟡",
            TaskPriority.MEDIUM: "🟢",
            TaskPriority.LOW: "🔵"
        }
        
        status_emoji = {
            TaskStatus.TODO: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅"
        }
        
        for i, task in enumerate(task_data, 1):
            message += f"{i}. {priority_emoji[task['priority']]} {status_emoji[task['status']]} *{TextHelper.escape_markdown(task['title'])}*\n"
            
            if task['due_date']:
                formatted_date = TimeHelper.format_datetime(task['due_date'], user_timezone)
                message += f"   📅 Due: {formatted_date}\n"
            
            message += "\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Complete #{i}", 
                    callback_data=f"task_complete_{task['id']}"
                ),
                InlineKeyboardButton(
                    f"🗑️ Delete #{i}", 
                    callback_data=f"task_delete_{task['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Projects", callback_data="task_projects")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")])
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )