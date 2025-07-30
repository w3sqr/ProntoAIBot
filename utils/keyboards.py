from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Optional

class Keyboards:
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Enhanced main menu keyboard with modern design"""
        keyboard = [
            [
                InlineKeyboardButton("⏰ Reminders", callback_data="reminders_menu"), 
                InlineKeyboardButton("📋 Tasks", callback_data="tasks_menu")
            ],
            [
                InlineKeyboardButton("🎯 Habits", callback_data="habits_menu"), 
                InlineKeyboardButton("📝 Notes", callback_data="notes_menu")
            ],
            [
                InlineKeyboardButton("📊 Analytics", callback_data="stats_menu"), 
                InlineKeyboardButton("🤖 AI Assistant", callback_data="ai_menu")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu"), 
                InlineKeyboardButton("💝 Donate", callback_data="settings_donate")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def settings_menu() -> InlineKeyboardMarkup:
        """Enhanced settings menu with two-column layout, Help as alternative to Donate"""
        keyboard = [
            [
                InlineKeyboardButton("🌍 Language", callback_data="settings_language"),
                InlineKeyboardButton("🕐 Timezone", callback_data="settings_timezone")
            ],
            [
                InlineKeyboardButton("🔔 Notifications", callback_data="settings_notifications"),
                InlineKeyboardButton("📞 Contact", callback_data="settings_contact")
            ],
            [
                InlineKeyboardButton("💝 Donate", callback_data="settings_donate"),
                InlineKeyboardButton("❓ Help", callback_data="help_menu")
            ],
            [InlineKeyboardButton("📤 Share Bot", callback_data="settings_share")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def reminders_menu() -> InlineKeyboardMarkup:
        """Enhanced reminders management menu"""
        keyboard = [
            [
                InlineKeyboardButton("➕ Add Reminder", callback_data="reminder_add"), 
                InlineKeyboardButton("📋 View All", callback_data="reminder_list")
            ],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def tasks_menu() -> InlineKeyboardMarkup:
        """Enhanced tasks management menu"""
        keyboard = [
            [
                InlineKeyboardButton("➕ Add Task", callback_data="task_add"), 
                InlineKeyboardButton("📋 View All", callback_data="task_list")
            ],
            [
                InlineKeyboardButton("📁 Projects", callback_data="task_projects")
            ],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def habits_menu() -> InlineKeyboardMarkup:
        """Enhanced habits management menu"""
        keyboard = [
            [
                InlineKeyboardButton("➕ Add Habit", callback_data="habit_add"), 
                InlineKeyboardButton("📋 View All", callback_data="habit_list")
            ],
            [
                InlineKeyboardButton("✅ Log Progress", callback_data="habit_log"), 
                InlineKeyboardButton("📊 Statistics", callback_data="habit_stats")
            ],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def notes_menu() -> InlineKeyboardMarkup:
        """Enhanced notes management menu"""
        keyboard = [
            [
                InlineKeyboardButton("➕ Add Note", callback_data="note_add"), 
                InlineKeyboardButton("📋 View All", callback_data="note_list")
            ],
            [
                InlineKeyboardButton("🔍 Search", callback_data="note_search"), 
                InlineKeyboardButton("📌 Pinned", callback_data="note_pinned")
            ],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirmation(action: str, item_id: int) -> InlineKeyboardMarkup:
        """Confirmation keyboard for actions"""
        keyboard = [
            [InlineKeyboardButton("✅ Yes", callback_data=f"confirm_{action}_{item_id}")],
            [InlineKeyboardButton("❌ No", callback_data=f"cancel_{action}_{item_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def priority_selection() -> InlineKeyboardMarkup:
        """Priority selection keyboard"""
        keyboard = [
            [InlineKeyboardButton("🔴 Urgent", callback_data="priority_urgent")],
            [InlineKeyboardButton("🟡 High", callback_data="priority_high")],
            [InlineKeyboardButton("🟢 Medium", callback_data="priority_medium")],
            [InlineKeyboardButton("🔵 Low", callback_data="priority_low")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def language_selection() -> InlineKeyboardMarkup:
        """Language selection keyboard"""
        keyboard = [
            [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
            [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
            [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_settings")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def statistics_menu() -> InlineKeyboardMarkup:
        """Enhanced statistics menu with two-column layout"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Overview", callback_data="stats_overview"),
                InlineKeyboardButton("✅ Tasks", callback_data="stats_tasks")
            ],
            [
                InlineKeyboardButton("🎯 Habits", callback_data="stats_habits"),
                InlineKeyboardButton("📝 Reminders", callback_data="stats_reminders")
            ],
            [
                InlineKeyboardButton("📋 Notes", callback_data="stats_notes"),
                InlineKeyboardButton("📈 Weekly Report", callback_data="stats_weekly")
            ],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def reply_main_menu() -> ReplyKeyboardMarkup:
        """Persistent reply keyboard main menu (bottom bar)"""
        keyboard = [
            [KeyboardButton("📝 Reminders"), KeyboardButton("✅ Tasks")],
            [KeyboardButton("🎯 Habits"), KeyboardButton("📋 Notes")],
            [KeyboardButton("📊 Statistics"), KeyboardButton("⚙️ Settings")],
            [KeyboardButton("🤖 AI Assistant"), KeyboardButton("💝 Donate")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def ai_menu() -> InlineKeyboardMarkup:
        """Enhanced AI Assistant menu with Natural Chat in single column and rest in two columns"""
        keyboard = [
            [InlineKeyboardButton("💬 Natural Chat", callback_data="ai_chat")],
            [
                InlineKeyboardButton("✅ Smart Tasks", callback_data="ai_suggest_tasks"), 
                InlineKeyboardButton("🎯 Habit Ideas", callback_data="ai_suggest_habits")
            ],
            [
                InlineKeyboardButton("📝 Note Summary", callback_data="ai_summarize_notes"), 
                InlineKeyboardButton("📊 Insights", callback_data="ai_insights")
            ],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def reminder_completed(reminder_id: int) -> InlineKeyboardMarkup:
        """Keyboard for completed reminder notification"""
        keyboard = [
            [InlineKeyboardButton("✅ Mark as Done", callback_data=f"reminder_done_{reminder_id}")],
            [InlineKeyboardButton("🔄 Snooze 15min", callback_data=f"reminder_snooze_{reminder_id}")],
            [InlineKeyboardButton("📝 View Reminders", callback_data="reminder_list")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def habit_reminder() -> InlineKeyboardMarkup:
        """Keyboard for habit reminder notification"""
        keyboard = [
            [InlineKeyboardButton("✅ Log Progress", callback_data="habit_log")],
            [InlineKeyboardButton("📋 View Habits", callback_data="habit_list")],
            [InlineKeyboardButton("🔕 Dismiss", callback_data="habit_dismiss")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def task_deadline_reminder() -> InlineKeyboardMarkup:
        """Keyboard for task deadline reminder notification"""
        keyboard = [
            [InlineKeyboardButton("📋 View Tasks", callback_data="task_list")],
            [InlineKeyboardButton("✅ Mark Complete", callback_data="task_complete")],
            [InlineKeyboardButton("🔕 Dismiss", callback_data="task_dismiss")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def weekly_summary() -> InlineKeyboardMarkup:
        """Keyboard for weekly summary notification"""
        keyboard = [
            [InlineKeyboardButton("📊 View Statistics", callback_data="stats_overview")],
            [InlineKeyboardButton("📈 Weekly Report", callback_data="stats_weekly")],
            [InlineKeyboardButton("🔕 Dismiss", callback_data="summary_dismiss")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def notification_settings() -> InlineKeyboardMarkup:
        """Notification settings keyboard"""
        keyboard = [
            [InlineKeyboardButton("🔔 Reminder Notifications", callback_data="notif_reminders")],
            [InlineKeyboardButton("🎯 Habit Reminders", callback_data="notif_habits")],
            [InlineKeyboardButton("⏰ Task Deadlines", callback_data="notif_tasks")],
            [InlineKeyboardButton("📊 Weekly Summaries", callback_data="notif_summaries")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_settings")]
        ]
        return InlineKeyboardMarkup(keyboard)