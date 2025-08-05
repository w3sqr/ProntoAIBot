#!/usr/bin/env python3
"""
Professional Telegram Productivity Bot
Features: Reminders, Tasks, Habits, Notes, AI Assistant
"""

import asyncio
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes, PreCheckoutQueryHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

# Import configuration and utilities
from config import settings
from utils.logger import setup_logger
from utils.decorators import with_user, error_handler
from utils.keyboards import Keyboards
from database.database import create_tables

# Import features
from features.reminders import ReminderFeature
from features.tasks import TaskFeature
from features.habits import HabitFeature
from features.notes import NoteFeature
from features.ai_assistant import AIAssistant
from features.settings import SettingsFeature
from features.statistics import StatisticsFeature
from features.notifications import NotificationService

# Global bot instance for scheduler access
bot_instance = None
notification_service_instance = None

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health-status' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({"status": "ok"})
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_HEAD(self):
        if self.path == '/health-status' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress logging for cleaner output
        pass

def start_health_server():
    """Start a simple HTTP health server on port 8001"""
    server = HTTPServer(('0.0.0.0', 8001), HealthCheckHandler)
    server.serve_forever()

class ProductivityBot:
    def __init__(self):
        self.logger = setup_logger()
        self.application = None
        self.scheduler = None
        self.notification_service = None
        # Features (initialized in setup)
        self.reminder_feature = None
        self.task_feature = None
        self.habit_feature = None
        self.note_feature = None
        self.ai_assistant = AIAssistant()
        self.settings_feature = SettingsFeature()
        self.statistics_feature = StatisticsFeature()
        self.logger.info("ProductivityBot initialized")
    
    def setup(self):
        """Setup bot application and scheduler"""
        # Create database tables
        create_tables()
        
        # Setup scheduler (in-memory job store with UTC timezone)
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        self.scheduler.start()
        
        # Create application
        self.application = Application.builder().token(settings.bot_token).build()
        
        # Initialize notification service
        self.notification_service = NotificationService(self.application.bot, self.scheduler)
        self.notification_service.main_loop = asyncio.get_event_loop()
        
        # Initialize features with notification service where needed
        self.reminder_feature = ReminderFeature(self.scheduler, self.notification_service)
        self.task_feature = TaskFeature(self.notification_service)
        self.habit_feature = HabitFeature(self.notification_service)
        self.note_feature = NoteFeature(self.notification_service)
        
        # Setup handlers
        self.setup_handlers()
        
        # Set bot commands
        asyncio.get_event_loop().run_until_complete(self.set_bot_commands())
        
        # Setup notification jobs
        asyncio.get_event_loop().run_until_complete(self.notification_service.setup_notifications())
        
        self.logger.info("Bot setup completed")
    
    def setup_handlers(self):
        """Setup all command and callback handlers"""
        
        # Basic commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        
        # Main menu handlers
        self.application.add_handler(MessageHandler(
            filters.Regex("^📝 Reminders$"), self.reminder_feature.show_reminders_menu
        ))
        self.application.add_handler(MessageHandler(
            filters.Regex("^✅ Tasks$"), self.task_feature.show_tasks_menu
        ))
        self.application.add_handler(MessageHandler(
            filters.Regex("^🎯 Habits$"), self.habit_feature.show_habits_menu
        ))
        self.application.add_handler(MessageHandler(
            filters.Regex("^📋 Notes$"), self.note_feature.show_notes_menu
        ))
        self.application.add_handler(MessageHandler(
            filters.Regex("^📊 Statistics$"), self.statistics_feature.show_statistics_menu
        ))
        self.application.add_handler(MessageHandler(
            filters.Regex("^⚙️ Settings$"), self.settings_feature.show_settings_menu
        ))
        self.application.add_handler(MessageHandler(
            filters.Regex("^🤖 AI Assistant$"), self.ai_assistant.show_ai_menu
        ))
        self.application.add_handler(MessageHandler(
            filters.Regex("^ℹ️ Help$"), self.help_command
        ))
        self.application.add_handler(MessageHandler(
            filters.Regex("^💝 Donate$"), self.settings_feature.show_donate_info
        ))
        
        # Reminder conversation handler
        reminder_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.reminder_feature.start_add_reminder, 
                pattern="^reminder_add$"
            )],
            states={
                self.reminder_feature.REMINDER_TITLE: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.reminder_feature.get_reminder_title
                )],
                self.reminder_feature.REMINDER_TIME: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.reminder_feature.get_reminder_time
                )],
                self.reminder_feature.REMINDER_DESCRIPTION: [
                    MessageHandler(filters.Regex('^/skip$'), self.reminder_feature.get_reminder_description),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.reminder_feature.get_reminder_description)
                ],
                self.reminder_feature.REMINDER_EDIT_FIELD: [CallbackQueryHandler(
                    self.reminder_feature.edit_field_choice
                )],
                self.reminder_feature.REMINDER_EDIT_TITLE: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self.reminder_feature.edit_reminder_title
                )],
                self.reminder_feature.REMINDER_EDIT_TIME: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self.reminder_feature.edit_reminder_time
                )],
                self.reminder_feature.REMINDER_EDIT_DESCRIPTION: [
                    MessageHandler(filters.Regex('^/skip$'), self.reminder_feature.edit_reminder_description),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.reminder_feature.edit_reminder_description)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.reminder_feature.cancel_conversation)]
        )
        self.application.add_handler(reminder_conv_handler)
        
        # Edit reminder conversation handler
        edit_reminder_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.reminder_feature.edit_reminder, pattern="^reminder_edit_"
            )],
            states={
                self.reminder_feature.REMINDER_EDIT_FIELD: [CallbackQueryHandler(
                    self.reminder_feature.edit_field_choice
                )],
                self.reminder_feature.REMINDER_EDIT_TITLE: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self.reminder_feature.edit_reminder_title
                )],
                self.reminder_feature.REMINDER_EDIT_TIME: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self.reminder_feature.edit_reminder_time
                )],
                self.reminder_feature.REMINDER_EDIT_DESCRIPTION: [
                    MessageHandler(filters.Regex('^/skip$'), self.reminder_feature.edit_reminder_description),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.reminder_feature.edit_reminder_description)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.reminder_feature.cancel_conversation)]
        )
        self.application.add_handler(edit_reminder_conv_handler)
        
        # Task conversation handler
        task_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.task_feature.start_add_task, 
                pattern="^task_add$"
            )],
            states={
                self.task_feature.TASK_TITLE: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.task_feature.get_task_title
                )],
                self.task_feature.TASK_DESCRIPTION: [
                    MessageHandler(filters.Regex('^/skip$'), self.task_feature.get_task_description),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.task_feature.get_task_description)
                ],
                self.task_feature.TASK_PRIORITY: [CallbackQueryHandler(
                    self.task_feature.get_task_priority, 
                    pattern="^priority_"
                )],
                self.task_feature.TASK_DUE_DATE: [
                    MessageHandler(filters.Regex('^/skip$'), self.task_feature.get_task_due_date),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.task_feature.get_task_due_date)
                ],
                self.task_feature.TASK_PROJECT: [
                    MessageHandler(filters.Regex('^/skip$'), self.task_feature.get_task_project),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.task_feature.get_task_project)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.task_feature.cancel_conversation)]
        )
        self.application.add_handler(task_conv_handler)
        
        # Project editing conversation handler
        project_edit_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.task_feature.edit_project, 
                pattern="^project_edit_"
            )],
            states={
                self.task_feature.EDIT_PROJECT_NAME: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.task_feature.get_new_project_name
                )]
            },
            fallbacks=[CommandHandler("cancel", self.task_feature.cancel_conversation)]
        )
        self.application.add_handler(project_edit_conv_handler)
        
        # Habit conversation handler
        habit_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.habit_feature.start_add_habit, 
                pattern="^habit_add$"
            )],
            states={
                self.habit_feature.HABIT_NAME: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.habit_feature.get_habit_name
                )],
                self.habit_feature.HABIT_DESCRIPTION: [
                    MessageHandler(filters.Regex('^/skip$'), self.habit_feature.get_habit_description),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.habit_feature.get_habit_description)
                ],
                self.habit_feature.HABIT_FREQUENCY: [CallbackQueryHandler(
                    self.habit_feature.get_habit_frequency, 
                    pattern="^freq_"
                )],
                self.habit_feature.HABIT_TARGET: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.habit_feature.get_habit_target
                )],
                self.habit_feature.HABIT_UNIT: [
                    MessageHandler(filters.Regex('^/skip$'), self.habit_feature.get_habit_unit),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.habit_feature.get_habit_unit)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.habit_feature.cancel_conversation)]
        )
        self.application.add_handler(habit_conv_handler)
        # Habit edit conversation handler
        habit_edit_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.habit_feature.edit_habit, 
                pattern="^habit_edit_"
            )],
            states={
                self.habit_feature.EDIT_HABIT_NAME: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.habit_feature.get_new_habit_name
                )]
            },
            fallbacks=[CommandHandler("cancel", self.habit_feature.cancel_conversation)]
        )
        self.application.add_handler(habit_edit_conv_handler)
        
        # Habit log update conversation handler
        habit_log_update_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.habit_feature.custom_update_habit_log, 
                pattern="^custom_update_"
            )],
            states={
                self.habit_feature.CUSTOM_UPDATE_VALUE: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.habit_feature.get_custom_update_value
                )]
            },
            fallbacks=[CommandHandler("cancel", self.habit_feature.cancel_conversation)]
        )
        self.application.add_handler(habit_log_update_conv_handler)
        
        # Habit delete handler
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.delete_habit, pattern="^habit_delete_"
        ))
        
        # Note conversation handler
        note_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.note_feature.start_add_note, 
                pattern="^note_add$"
            )],
            states={
                self.note_feature.NOTE_TITLE: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.note_feature.get_note_title
                )],
                self.note_feature.NOTE_CONTENT: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.note_feature.get_note_content
                )],
                self.note_feature.NOTE_CATEGORY: [
                    MessageHandler(filters.Regex('^/skip$'), self.note_feature.get_note_category),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.note_feature.get_note_category)
                ],
                self.note_feature.NOTE_TAGS: [
                    MessageHandler(filters.Regex('^/skip$'), self.note_feature.get_note_tags),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.note_feature.get_note_tags)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.note_feature.cancel_conversation)]
        )
        self.application.add_handler(note_conv_handler)
        
        # Note search conversation handler
        note_search_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.note_feature.start_search_notes, 
                pattern="^note_search$"
            )],
            states={
                self.note_feature.SEARCH_QUERY: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.note_feature.search_notes
                )]
            },
            fallbacks=[CommandHandler("cancel", self.note_feature.cancel_conversation)]
        )
        self.application.add_handler(note_search_conv_handler)
        
        # Note edit title conversation handler
        note_edit_title_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.note_feature.start_edit_title, 
                pattern="^note_edit_title_"
            )],
            states={
                self.note_feature.EDIT_TITLE: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.note_feature.save_edit_title
                )]
            },
            fallbacks=[CommandHandler("cancel", self.note_feature.cancel_conversation)]
        )
        self.application.add_handler(note_edit_title_conv_handler)
        
        # Note edit content conversation handler
        note_edit_content_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.note_feature.start_edit_content, 
                pattern="^note_edit_content_"
            )],
            states={
                self.note_feature.EDIT_CONTENT: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.note_feature.save_edit_content
                )]
            },
            fallbacks=[CommandHandler("cancel", self.note_feature.cancel_conversation)]
        )
        self.application.add_handler(note_edit_content_conv_handler)
        
        # Note edit category conversation handler
        note_edit_category_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.note_feature.start_edit_category, 
                pattern="^note_edit_category_"
            )],
            states={
                self.note_feature.EDIT_CATEGORY: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.note_feature.save_edit_category
                )]
            },
            fallbacks=[CommandHandler("cancel", self.note_feature.cancel_conversation)]
        )
        self.application.add_handler(note_edit_category_conv_handler)
        
        # Note edit tags conversation handler
        note_edit_tags_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.note_feature.start_edit_tags, 
                pattern="^note_edit_tags_"
            )],
            states={
                self.note_feature.EDIT_TAGS: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.note_feature.save_edit_tags
                )]
            },
            fallbacks=[CommandHandler("cancel", self.note_feature.cancel_conversation)]
        )
        self.application.add_handler(note_edit_tags_conv_handler)
        
        # AI conversation handlers
        ai_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.ai_assistant.start_ai_chat,
                    pattern="^ai_chat$"
                )
            ],
            states={
                self.ai_assistant.AI_QUERY: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self.ai_assistant.handle_ai_query
                )]
            },
            fallbacks=[CommandHandler("cancel", self.ai_assistant.cancel_conversation)]
        )
        self.application.add_handler(ai_conv_handler)
        
        # Settings conversation handlers
        timezone_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.settings_feature.show_timezone_settings, 
                    pattern="^settings_timezone$"
                ),
                CallbackQueryHandler(
                    self.settings_feature.set_timezone, 
                    pattern="^tz_"
                )
            ],
            states={
                self.settings_feature.TIMEZONE_INPUT: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.settings_feature.get_custom_timezone
                )],
                self.settings_feature.UTC_OFFSET_INPUT: [MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    self.settings_feature.get_custom_utc_offset
                )]
            },
            fallbacks=[CommandHandler("cancel", self.settings_feature.cancel_conversation)]
        )
        self.application.add_handler(timezone_conv_handler)
        
        # Setup callback handlers
        self.setup_callback_handlers()
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
        
        self.logger.info("Handlers setup completed")
    
    def setup_callback_handlers(self):
        """Setup callback query handlers"""
        
        # Navigation callbacks
        self.application.add_handler(CallbackQueryHandler(
            self.show_main_menu, pattern="^back_to_main$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.reminder_feature.show_reminders_menu, pattern="^reminders_menu$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.show_tasks_menu, pattern="^tasks_menu$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_settings_menu, pattern="^settings_menu$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.statistics_feature.show_statistics_menu, pattern="^stats_menu$"
        ))
        
        # Reminder callbacks
        self.application.add_handler(CallbackQueryHandler(
            self.reminder_feature.show_reminders_menu, pattern="^reminders_menu$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.reminder_feature.list_reminders, pattern="^reminder_list$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.reminder_feature.edit_reminder, pattern="^reminder_edit_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.reminder_feature.snooze_reminder, pattern="^reminder_snooze_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.reminder_feature.mark_reminder_done, pattern="^reminder_done_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.reminder_feature.delete_reminder, pattern="^reminder_delete_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.reminder_feature.start_add_reminder, pattern="^reminder_add_continue$"
        ))
        
        # Task callbacks
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.show_tasks_menu, pattern="^tasks_menu$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.list_tasks, pattern="^task_list$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.complete_task, pattern="^task_complete_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.show_projects, pattern="^task_projects$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.delete_task, pattern="^task_delete_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.view_project_tasks, pattern="^project_view_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.edit_project, pattern="^project_edit_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.task_feature.delete_project, pattern="^project_delete_"
        ))
        
        # Habit callbacks
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.show_habits_menu, pattern="^habits_menu$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.start_add_habit, pattern="^habit_add$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.get_habit_frequency, pattern="^freq_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.list_habits, pattern="^habit_list$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.log_habit_progress, pattern="^habit_log$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.show_habits_overview_stats, pattern="^habit_stats$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.log_specific_habit, pattern="^log_habit_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.quick_log_habit, pattern="^quick_log_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.show_habit_stats, pattern="^habit_stats_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.edit_habit, pattern="^habit_edit_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.log_specific_habit, pattern="^custom_log_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.update_habit_log, pattern="^update_log_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.quick_update_habit_log, pattern="^quick_update_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.habit_feature.custom_update_habit_log, pattern="^custom_update_"
        ))
        
        # Note callbacks
        self.application.add_handler(CallbackQueryHandler(
            self.note_feature.show_notes_menu, pattern="^notes_menu$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.note_feature.list_notes, pattern="^note_list$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.note_feature.view_note, pattern="^note_view_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.note_feature.edit_note, pattern="^note_edit_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.note_feature.share_note, pattern="^note_share_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.note_feature.pin_note, pattern="^note_pin_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.note_feature.show_pinned_notes, pattern="^note_pinned$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.note_feature.delete_note, pattern="^note_delete_"
        ))
        
        # AI Assistant callbacks
        self.application.add_handler(CallbackQueryHandler(
            self.ai_assistant.show_ai_menu, pattern="^ai_menu$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.ai_assistant.start_ai_chat, pattern="^ai_chat$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.ai_assistant.suggest_tasks, pattern="^ai_suggest_tasks$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.ai_assistant.suggest_habits, pattern="^ai_suggest_habits$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.ai_assistant.summarize_notes, pattern="^ai_summarize_notes$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.ai_assistant.get_productivity_insights, pattern="^ai_insights$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.ai_assistant.cancel_conversation, pattern="^ai_cancel$"
        ))
        
        # Settings callbacks
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_language_settings, pattern="^settings_language$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.set_language, pattern="^lang_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_contact_info, pattern="^settings_contact$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_donate_info, pattern="^settings_donate$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_share_bot, pattern="^settings_share$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_notifications_settings, pattern="^settings_notifications$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.toggle_notification_setting, pattern="^notif_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.copy_bot_link, pattern="^copy_link_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_settings_menu, pattern="^back_to_settings$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_timezone_settings, pattern="^settings_timezone$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.skip_timezone_setting, pattern="^skip_timezone$"
        ))
        # Handle stars menu
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.show_stars_menu, pattern="^donate_stars_menu$"
        ))
        
        # Handle all star donation amounts
        self.application.add_handler(CallbackQueryHandler(
            self.settings_feature.handle_donate_star, pattern="^donate_star_\\d+$"
        ))
        
        # Handle successful payments
        self.application.add_handler(MessageHandler(
            filters.SUCCESSFUL_PAYMENT, self.settings_feature.handle_successful_payment
        ))
        
        # Handle pre-checkout queries (required for Telegram Stars payments)
        self.application.add_handler(PreCheckoutQueryHandler(
            self.settings_feature.handle_pre_checkout_query
        ))
        
        # Statistics callbacks
        self.application.add_handler(CallbackQueryHandler(
            self.statistics_feature.show_overview_stats, pattern="^stats_overview$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.statistics_feature.show_task_stats, pattern="^stats_tasks$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.statistics_feature.show_habit_stats, pattern="^stats_habits$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.statistics_feature.show_reminder_stats, pattern="^stats_reminders$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.statistics_feature.show_note_stats, pattern="^stats_notes$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.statistics_feature.show_weekly_report, pattern="^stats_weekly$"
        ))
        
        # Help menu handler
        self.application.add_handler(CallbackQueryHandler(
            self.help_command, pattern="^help_menu$"
        ))
    
    async def set_bot_commands(self):
        """Set bot commands for the menu"""
        commands = [
            BotCommand("start", "Start the bot and show main menu"),
            BotCommand("menu", "Show main menu"),
            BotCommand("help", "Show help information"),
            BotCommand("cancel", "Cancel current operation")
        ]
        
        await self.application.bot.set_my_commands(commands)
        self.logger.info("Bot commands set successfully")
    
    @with_user
    @error_handler
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with enhanced welcome design"""
        first_name = context.user_data.get('user_first_name', update.effective_user.first_name if update.effective_user else 'there')
        user_timezone = context.user_data.get('user_timezone', 'UTC')
        
        # Check if user has a proper timezone set (not just UTC default)
        timezone_warning = ""
        if user_timezone == 'UTC':
            timezone_warning = (
                "\n\n⚠️ *Timezone Notice:*\n"
                "I detected you're using UTC timezone. For accurate reminders and scheduling, "
                "please set your local timezone in Settings → Timezone Settings.\n"
                "This ensures your reminders arrive at the right time! 🕐"
            )
        
        # Enhanced welcome message with modern design
        welcome_message = (
            f"🎉 *Welcome to Your Personal Productivity Assistant!*\n\n"
            f"Hey **{first_name}**! 👋 I'm here to help you stay organized and productive.\n\n"
            f"✨ **What I can do for you:**\n"
            f"• ⏰ **Smart Reminders** - Never miss important tasks\n"
            f"• 📋 **Task Management** - Organize your to-do lists\n"
            f"• 🎯 **Habit Tracking** - Build positive routines\n"
            f"• 📝 **Smart Notes** - Capture and organize ideas\n"
            f"• 🤖 **AI Assistant** - Get intelligent suggestions\n"
            f"• 📊 **Analytics** - Track your progress\n\n"
            f"🕐 **Your Timezone:** {user_timezone}\n"
            f"🚀 Ready to boost your productivity? Let's get started!{timezone_warning}"
        )
        
        # Create keyboard with timezone settings if needed
        if user_timezone == 'UTC':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Set Timezone", callback_data="settings_timezone")],
                [InlineKeyboardButton("🚀 Start Using Bot", callback_data="back_to_main")]
            ])
        else:
            keyboard = Keyboards.reply_main_menu()
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    @with_user
    @error_handler
    async def help_command(self, update: Update, context):
        """Handle /help command"""
        help_message = (
            "ℹ️ *Productivity Bot Help*\n\n"
            "*Main Features:*\n\n"
            "📝 *Reminders*\n"
            "• Set one-time reminders\n"
            "• Natural language time input\n"
            "• Timezone support\n\n"
            "✅ *Tasks*\n"
            "• Create and manage tasks\n"
            "• Set priorities and due dates\n"
            "• Organize by projects\n\n"
            "🎯 *Habits*\n"
            "• Track daily, weekly, or monthly habits\n"
            "• Monitor streaks and progress\n"
            "• Set custom targets\n\n"
            "📋 *Notes*\n"
            "• Create and organize notes\n"
            "• Search and categorize\n"
            "• Pin important notes\n\n"
            "🤖 *AI Assistant*\n"
            "• Get productivity tips\n"
            "• Smart task suggestions\n"
            "• Habit recommendations\n\n"
            "📊 *Statistics*\n"
            "• Track your progress\n"
            "• Weekly reports\n"
            "• Performance analytics\n\n"
            "*Commands:*\n"
            "/start - Show main menu\n"
            "/help - Show this help\n"
            "/menu - Return to main menu\n"
            "/cancel - Cancel current operation\n\n"
            "Need more help? Contact us through Settings → Contact!"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_message,
                parse_mode='Markdown',
                reply_markup=Keyboards.main_menu()
            )
        else:
            await update.message.reply_text(
                help_message,
                parse_mode='Markdown',
                reply_markup=Keyboards.reply_main_menu()
            )
    
    @with_user
    @error_handler
    async def menu_command(self, update: Update, context):
        """Handle /menu command"""
        await self.show_main_menu(update, context)
    
    @with_user
    @error_handler
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show enhanced main menu with modern design"""
        first_name = context.user_data.get('user_first_name', 'there')
        user_timezone = context.user_data.get('user_timezone', 'UTC')
        
        # Add timezone indicator with better formatting
        timezone_indicator = ""
        if user_timezone != 'UTC':
            timezone_indicator = f"\n🕐 **Timezone:** {user_timezone}"
        else:
            timezone_indicator = "\n⚠️ **Timezone:** UTC (Consider setting your local timezone)"
        
        # Enhanced welcome message with modern design
        menu_message = (
            f"🎉 *Welcome to Your Productivity Hub!*\n\n"
            f"Hey **{first_name}**! 👋 Ready to boost your productivity today?\n\n"
            f"🚀 **Quick Actions:**\n"
            f"• Create reminders, tasks, and habits\n"
            f"• Chat with AI for smart suggestions\n"
            f"• Track your progress and insights\n\n"
            f"💡 **Pro Tip:** Try asking the AI Assistant to create items using natural language!\n"
            f"{timezone_indicator}"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                menu_message,
                parse_mode='Markdown',
                reply_markup=Keyboards.main_menu()
            )
        else:
            await update.message.reply_text(
                menu_message,
                parse_mode='Markdown',
                reply_markup=Keyboards.reply_main_menu()
            )
    
    async def error_handler(self, update: Update, context):
        """Handle errors"""
        error = context.error
        self.logger.error(f"Update {update} caused error {error}")
        
        # Handle specific event loop errors more gracefully
        if "Event loop is closed" in str(error) or "RuntimeError" in str(error):
            self.logger.warning("Event loop error detected - this is usually harmless for reminder interactions")
            return
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again or contact support if the problem persists."
                )
            except Exception as e:
                self.logger.error(f"Failed to send error message: {e}")
    
    def run(self):
        """Run the bot"""
        try:
            self.logger.info("Starting Productivity Bot...")
            if settings.webhook_url:
                # Webhook mode - bot runs on port 8000
                self.application.run_webhook(
                    listen="0.0.0.0",
                    port=8000,
                    webhook_url=settings.webhook_url,
                    secret_token=settings.webhook_secret
                )
            else:
                # Polling mode
                self.application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True
                )
        except Exception as e:
            self.logger.error(f"Error running bot: {e}")
            raise
        finally:
            if self.scheduler:
                self.scheduler.shutdown()
            self.logger.info("Bot stopped")

def main():
    global bot_instance
    
    # Start health server in a separate thread on port 8001
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    bot = ProductivityBot()
    bot.setup()
    bot_instance = bot
    bot.run()

if __name__ == "__main__":
    main()