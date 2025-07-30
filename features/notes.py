from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.database import get_db
from database.models import User, Note
from utils.decorators import with_user, error_handler
from utils.helpers import TextHelper
from utils.keyboards import Keyboards
from loguru import logger
from sqlalchemy import or_
from typing import Optional
import pytz
from datetime import datetime

class NoteFeature:
    NOTE_TITLE = 0
    NOTE_CONTENT = 1
    NOTE_CATEGORY = 2
    NOTE_TAGS = 3
    SEARCH_QUERY = 0
    EDIT_TITLE = 4
    EDIT_CONTENT = 5
    EDIT_CATEGORY = 6
    EDIT_TAGS = 7

    def __init__(self, notification_service=None):
        self.notification_service = notification_service

    @with_user
    @error_handler
    async def show_notes_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show notes main menu"""
        text = (
            "📋 *Notes Management*\n\n"
            "Choose an option below:"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.notes_menu()
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=Keyboards.notes_menu()
            )
    
    @with_user
    @error_handler
    async def start_add_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start adding a new note"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "📋 *Add New Note*\n\n"
            "Please enter the note title:",
            parse_mode='Markdown'
        )
        
        return self.NOTE_TITLE
    
    @with_user
    @error_handler
    async def get_note_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get note title from user"""
        title = update.message.text.strip()
        
        if len(title) > 255:
            await update.message.reply_text(
                "❌ Title is too long. Please keep it under 255 characters."
            )
            return self.NOTE_TITLE
        
        context.user_data['note_title'] = title
        
        await update.message.reply_text(
            f"📋 Title: *{TextHelper.escape_markdown(title)}*\n\n"
            "📝 Now, please enter the note content:",
            parse_mode='Markdown'
        )
        
        return self.NOTE_CONTENT
    
    @with_user
    @error_handler
    async def get_note_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get note content from user"""
        content = update.message.text.strip()
        
        if len(content) > 4000:  # Telegram message limit consideration
            await update.message.reply_text(
                "❌ Content is too long. Please keep it under 4000 characters."
            )
            return self.NOTE_CONTENT
        
        user_timezone = context.user_data['user_timezone'] or 'UTC'
        local_tz = pytz.timezone(user_timezone)
        now = datetime.now()
        # Ensure now is localized to user's timezone
        if now.tzinfo is None:
            now = local_tz.localize(now)
        else:
            now = now.astimezone(local_tz)
        
        context.user_data['note_content'] = content
        
        await update.message.reply_text(
            "📁 Enter a category for this note (optional):\n\n"
            "Examples: Work, Personal, Ideas, Shopping\n"
            "Or type `/skip` to continue.",
            parse_mode='Markdown'
        )
        
        return self.NOTE_CATEGORY
    
    @with_user
    @error_handler
    async def get_note_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get note category from user"""
        category = None
        
        if update.message.text.strip().lower() != '/skip':
            category = update.message.text.strip()
            if len(category) > 100:
                await update.message.reply_text(
                    "❌ Category is too long. Please keep it under 100 characters."
                )
                return self.NOTE_CATEGORY
        
        context.user_data['note_category'] = category
        
        await update.message.reply_text(
            "🏷️ Add tags for this note (optional):\n\n"
            "Separate multiple tags with commas.\n"
            "Examples: important, urgent, meeting, idea\n"
            "Or type `/skip` to finish.",
            parse_mode='Markdown'
        )
        
        return self.NOTE_TAGS
    
    @with_user
    @error_handler
    async def get_note_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get note tags from user"""
        tags = None
        
        if update.message.text.strip().lower() != '/skip':
            tags_input = update.message.text.strip()
            if len(tags_input) > 500:
                await update.message.reply_text(
                    "❌ Tags are too long. Please keep them under 500 characters."
                )
                return self.NOTE_TAGS
            tags = tags_input
        
        # Save the note
        user_id = context.user_data['user_id']
        title = context.user_data['note_title']
        content = context.user_data['note_content']
        category = context.user_data.get('note_category')
        
        with get_db() as db:
            note = Note(
                user_id=user_id,
                title=title,
                content=content,
                category=category,
                tags=tags,
                is_pinned=False
            )
            db.add(note)
            db.commit()
            db.refresh(note)
        
        # Format confirmation message
        message = (
            f"✅ *Note Created Successfully!*\n\n"
            f"📋 Title: {TextHelper.escape_markdown(title)}\n"
            f"📝 Content: {TextHelper.escape_markdown(TextHelper.truncate(content, 100))}\n"
        )
        
        if category:
            message += f"📁 Category: {TextHelper.escape_markdown(category)}\n"
        
        if tags:
            formatted_tags = TextHelper.format_tags(TextHelper.parse_tags(tags))
            message += f"🏷️ Tags: {formatted_tags}\n"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=Keyboards.notes_menu()
        )
        
        # Clear conversation data
        for key in ['note_title', 'note_content', 'note_category']:
            context.user_data.pop(key, None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def list_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List user's notes"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            notes = db.query(Note).filter(
                Note.user_id == user_id
            ).order_by(Note.is_pinned.desc(), Note.updated_at.desc()).limit(10).all()
            # Extract all needed fields while session is open
            note_data = []
            for note in notes:
                note_data.append({
                    'id': note.id,
                    'title': note.title,
                    'content': note.content,
                    'category': note.category,
                    'tags': note.tags,
                    'is_pinned': note.is_pinned
                })
        
        if not note_data:
            await query.edit_message_text(
                "📋 *Your Notes*\n\n"
                "You don't have any notes yet.\n"
                "Use the button below to create one!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Note", callback_data="note_add")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
            return
        
        message = "📋 *Your Notes*\n\n"
        keyboard = []
        
        for i, note in enumerate(note_data, 1):
            pin_emoji = "📌 " if note['is_pinned'] else ""
            message += f"{i}. {pin_emoji}*{TextHelper.escape_markdown(note['title'])}*\n"
            if note['category']:
                message += f"   📁 {TextHelper.escape_markdown(note['category'])}\n"
            # Show preview of content
            preview = TextHelper.truncate(note['content'], 50)
            message += f"   📝 {TextHelper.escape_markdown(preview)}\n"
            if note['tags']:
                formatted_tags = TextHelper.format_tags(TextHelper.parse_tags(note['tags']))
                message += f"   🏷️ {formatted_tags}\n"
            message += "\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"👁️ View #{i}", 
                    callback_data=f"note_view_{note['id']}"
                ),
                InlineKeyboardButton(
                    f"✏️ Edit #{i}", 
                    callback_data=f"note_edit_{note['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton("➕ Add New", callback_data="note_add")])
        keyboard.append([InlineKeyboardButton("🔍 Search", callback_data="note_search")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def view_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View a specific note"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await query.edit_message_text("❌ Note not found.")
                return
            
            # Extract note data while session is open
            note_title = note.title
            note_content = note.content
            note_category = note.category
            note_tags = note.tags
            note_is_pinned = note.is_pinned
            note_created_at = note.created_at
            note_updated_at = note.updated_at
            note_id = note.id
        
        pin_emoji = "📌 " if note_is_pinned else ""
        message = f"{pin_emoji}*{TextHelper.escape_markdown(note_title)}*\n\n"
        
        if note_category:
            message += f"📁 Category: {TextHelper.escape_markdown(note_category)}\n"
        
        if note_tags:
            formatted_tags = TextHelper.format_tags(TextHelper.parse_tags(note_tags))
            message += f"🏷️ Tags: {formatted_tags}\n"
        
        message += f"\n📝 *Content:*\n{TextHelper.escape_markdown(note_content)}\n"
        message += f"\n📅 Created: {note_created_at.strftime('%Y-%m-%d %H:%M')}"
        
        if note_updated_at != note_created_at:
            message += f"\n✏️ Updated: {note_updated_at.strftime('%Y-%m-%d %H:%M')}"
        
        keyboard = [
            [
                InlineKeyboardButton("✏️ Edit", callback_data=f"note_edit_{note_id}"),
                InlineKeyboardButton("📌 Pin" if not note_is_pinned else "📌 Unpin", callback_data=f"note_pin_{note_id}")
            ],
            [
                InlineKeyboardButton("🗑️ Delete", callback_data=f"note_delete_{note_id}"),
                InlineKeyboardButton("📤 Share", callback_data=f"note_share_{note_id}")
            ],
            [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def pin_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pin or unpin a note"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await query.edit_message_text("❌ Note not found.")
                return
            
            # Extract note data while session is open
            note_title = note.title
            current_pinned_status = note.is_pinned
            
            # Update the pinned status
            note.is_pinned = not current_pinned_status
            db.commit()
        
        # Use the updated status for the response
        new_pinned_status = not current_pinned_status
        action = "pinned" if new_pinned_status else "unpinned"
        emoji = "📌" if new_pinned_status else "📋"
        
        await query.edit_message_text(
            f"{emoji} *Note {action}!*\n\n"
            f"📋 {TextHelper.escape_markdown(note_title)}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ View Note", callback_data=f"note_view_{note_id}")],
                [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
            ])
        )
    
    @with_user
    @error_handler
    async def start_search_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start note search"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "🔍 *Search Notes*\n\n"
            "Enter keywords to search in titles, content, categories, or tags:",
            parse_mode='Markdown'
        )
        
        return self.SEARCH_QUERY
    
    @with_user
    @error_handler
    async def search_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search notes based on query"""
        search_query = update.message.text.strip().lower()
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            notes = db.query(Note).filter(
                Note.user_id == user_id,
                or_(
                    Note.title.ilike(f'%{search_query}%'),
                    Note.content.ilike(f'%{search_query}%'),
                    Note.category.ilike(f'%{search_query}%'),
                    Note.tags.ilike(f'%{search_query}%')
                )
            ).order_by(Note.is_pinned.desc(), Note.updated_at.desc()).limit(10).all()
            
            # Extract all needed fields while session is open
            note_data = []
            for note in notes:
                note_data.append({
                    'id': note.id,
                    'title': note.title,
                    'content': note.content,
                    'is_pinned': note.is_pinned
                })
        
        if not note_data:
            await update.message.reply_text(
                f"🔍 *Search Results*\n\n"
                f"No notes found for: *{TextHelper.escape_markdown(search_query)}*\n\n"
                f"Try different keywords or create a new note!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Note", callback_data="note_add")],
                    [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
                ])
            )
            return ConversationHandler.END
        
        message = f"🔍 *Search Results for: {TextHelper.escape_markdown(search_query)}*\n\n"
        keyboard = []
        
        for i, note in enumerate(note_data, 1):
            pin_emoji = "📌 " if note['is_pinned'] else ""
            message += f"{i}. {pin_emoji}*{TextHelper.escape_markdown(note['title'])}*\n"
            
            # Show preview of content with search term highlighted
            preview = TextHelper.truncate(note['content'], 50)
            message += f"   📝 {TextHelper.escape_markdown(preview)}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"👁️ View #{i}", 
                    callback_data=f"note_view_{note['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔍 New Search", callback_data="note_search")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")])
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def show_pinned_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pinned notes"""
        query = update.callback_query
        await query.answer()
        
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            notes = db.query(Note).filter(
                Note.user_id == user_id,
                Note.is_pinned == True
            ).order_by(Note.updated_at.desc()).all()
            
            # Extract all needed fields while session is open
            note_data = []
            for note in notes:
                note_data.append({
                    'id': note.id,
                    'title': note.title,
                    'content': note.content
                })
        
        if not note_data:
            await query.edit_message_text(
                "📌 *Pinned Notes*\n\n"
                "You don't have any pinned notes yet.\n"
                "Pin important notes for quick access!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View All Notes", callback_data="note_list")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
            return
        
        message = "📌 *Pinned Notes*\n\n"
        keyboard = []
        
        for i, note in enumerate(note_data, 1):
            message += f"{i}. 📌 *{TextHelper.escape_markdown(note['title'])}*\n"
            
            # Show preview of content
            preview = TextHelper.truncate(note['content'], 50)
            message += f"   📝 {TextHelper.escape_markdown(preview)}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"👁️ View #{i}", 
                    callback_data=f"note_view_{note['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("📋 All Notes", callback_data="note_list")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def edit_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start editing a note"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await query.edit_message_text("❌ Note not found.")
                return
            
            # Extract note data while session is open
            note_title = note.title
            note_content = note.content
            note_category = note.category
            note_tags = note.tags
        
        # Store note data for editing
        context.user_data['editing_note_id'] = note_id
        context.user_data['editing_note_title'] = note_title
        context.user_data['editing_note_content'] = note_content
        context.user_data['editing_note_category'] = note_category
        context.user_data['editing_note_tags'] = note_tags
        
        # Show edit options
        message = (
            f"✏️ *Edit Note*\n\n"
            f"📋 Title: {TextHelper.escape_markdown(note_title)}\n"
            f"📝 Content: {TextHelper.escape_markdown(TextHelper.truncate(note_content, 100))}\n"
        )
        
        if note_category:
            message += f"📁 Category: {TextHelper.escape_markdown(note_category)}\n"
        
        if note_tags:
            formatted_tags = TextHelper.format_tags(TextHelper.parse_tags(note_tags))
            message += f"🏷️ Tags: {formatted_tags}\n"
        
        message += "\n*Choose what you want to edit:*"
        
        keyboard = [
            [InlineKeyboardButton("📋 Edit Title", callback_data=f"note_edit_title_{note_id}")],
            [InlineKeyboardButton("📝 Edit Content", callback_data=f"note_edit_content_{note_id}")],
            [InlineKeyboardButton("📁 Edit Category", callback_data=f"note_edit_category_{note_id}")],
            [InlineKeyboardButton("🏷️ Edit Tags", callback_data=f"note_edit_tags_{note_id}")],
            [InlineKeyboardButton("👁️ View Note", callback_data=f"note_view_{note_id}")],
            [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @with_user
    @error_handler
    async def start_edit_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start editing note title"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        context.user_data['editing_note_id'] = note_id
        
        await query.edit_message_text(
            "📋 *Edit Note Title*\n\n"
            "Please enter the new title:",
            parse_mode='Markdown'
        )
        
        return self.EDIT_TITLE
    
    @with_user
    @error_handler
    async def save_edit_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save edited note title"""
        new_title = update.message.text.strip()
        note_id = context.user_data.get('editing_note_id')
        user_id = context.user_data['user_id']
        
        if len(new_title) > 255:
            await update.message.reply_text(
                "❌ Title is too long. Please keep it under 255 characters."
            )
            return self.EDIT_TITLE
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await update.message.reply_text("❌ Note not found.")
                return ConversationHandler.END
            
            note.title = new_title
            note.updated_at = datetime.utcnow()
            db.commit()
        
        await update.message.reply_text(
            f"✅ *Title Updated!*\n\n"
            f"📋 New title: {TextHelper.escape_markdown(new_title)}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ View Note", callback_data=f"note_view_{note_id}")],
                [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
            ])
        )
        
        # Clear editing data
        context.user_data.pop('editing_note_id', None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def start_edit_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start editing note content"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        context.user_data['editing_note_id'] = note_id
        
        await query.edit_message_text(
            "📝 *Edit Note Content*\n\n"
            "Please enter the new content:",
            parse_mode='Markdown'
        )
        
        return self.EDIT_CONTENT
    
    @with_user
    @error_handler
    async def save_edit_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save edited note content"""
        new_content = update.message.text.strip()
        note_id = context.user_data.get('editing_note_id')
        user_id = context.user_data['user_id']
        
        if len(new_content) > 4000:
            await update.message.reply_text(
                "❌ Content is too long. Please keep it under 4000 characters."
            )
            return self.EDIT_CONTENT
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await update.message.reply_text("❌ Note not found.")
                return ConversationHandler.END
            
            note.content = new_content
            note.updated_at = datetime.utcnow()
            db.commit()
        
        await update.message.reply_text(
            f"✅ *Content Updated!*\n\n"
            f"📝 New content: {TextHelper.escape_markdown(TextHelper.truncate(new_content, 100))}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ View Note", callback_data=f"note_view_{note_id}")],
                [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
            ])
        )
        
        # Clear editing data
        context.user_data.pop('editing_note_id', None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def start_edit_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start editing note category"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        context.user_data['editing_note_id'] = note_id
        
        await query.edit_message_text(
            "📁 *Edit Note Category*\n\n"
            "Please enter the new category:\n"
            "Examples: Work, Personal, Ideas, Shopping\n"
            "Or type `/clear` to remove the category.",
            parse_mode='Markdown'
        )
        
        return self.EDIT_CATEGORY
    
    @with_user
    @error_handler
    async def save_edit_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save edited note category"""
        new_category = update.message.text.strip()
        note_id = context.user_data.get('editing_note_id')
        user_id = context.user_data['user_id']
        
        if new_category.lower() == '/clear':
            new_category = None
        elif len(new_category) > 100:
            await update.message.reply_text(
                "❌ Category is too long. Please keep it under 100 characters."
            )
            return self.EDIT_CATEGORY
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await update.message.reply_text("❌ Note not found.")
                return ConversationHandler.END
            
            note.category = new_category
            note.updated_at = datetime.utcnow()
            db.commit()
        
        action = "removed" if new_category is None else f"updated to: {TextHelper.escape_markdown(new_category)}"
        await update.message.reply_text(
            f"✅ *Category {action}!*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ View Note", callback_data=f"note_view_{note_id}")],
                [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
            ])
        )
        
        # Clear editing data
        context.user_data.pop('editing_note_id', None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def start_edit_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start editing note tags"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        context.user_data['editing_note_id'] = note_id
        
        await query.edit_message_text(
            "🏷️ *Edit Note Tags*\n\n"
            "Please enter the new tags:\n"
            "Separate multiple tags with commas.\n"
            "Examples: important, urgent, meeting, idea\n"
            "Or type `/clear` to remove all tags.",
            parse_mode='Markdown'
        )
        
        return self.EDIT_TAGS
    
    @with_user
    @error_handler
    async def save_edit_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save edited note tags"""
        new_tags = update.message.text.strip()
        note_id = context.user_data.get('editing_note_id')
        user_id = context.user_data['user_id']
        
        if new_tags.lower() == '/clear':
            new_tags = None
        elif len(new_tags) > 500:
            await update.message.reply_text(
                "❌ Tags are too long. Please keep them under 500 characters."
            )
            return self.EDIT_TAGS
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await update.message.reply_text("❌ Note not found.")
                return ConversationHandler.END
            
            note.tags = new_tags
            note.updated_at = datetime.utcnow()
            db.commit()
        
        if new_tags:
            formatted_tags = TextHelper.format_tags(TextHelper.parse_tags(new_tags))
            action = f"updated to: {formatted_tags}"
        else:
            action = "removed"
            
        await update.message.reply_text(
            f"✅ *Tags {action}!*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ View Note", callback_data=f"note_view_{note_id}")],
                [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
            ])
        )
        
        # Clear editing data
        context.user_data.pop('editing_note_id', None)
        
        return ConversationHandler.END
    
    @with_user
    @error_handler
    async def share_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Share a note"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await query.edit_message_text("❌ Note not found.")
                return
            
            # Extract note data while session is open
            note_title = note.title
            note_content = note.content
            note_category = note.category
            note_tags = note.tags
        
        # Create shareable message
        share_message = (
            f"📋 *{TextHelper.escape_markdown(note_title)}*\n\n"
        )
        
        if note_category:
            share_message += f"📁 Category: {TextHelper.escape_markdown(note_category)}\n"
        
        if note_tags:
            formatted_tags = TextHelper.format_tags(TextHelper.parse_tags(note_tags))
            share_message += f"🏷️ Tags: {formatted_tags}\n"
        
        share_message += f"\n📝 *Content:*\n{TextHelper.escape_markdown(note_content)}"
        
        await query.edit_message_text(
            f"📤 *Share Note*\n\n"
            f"📋 {TextHelper.escape_markdown(note_title)}\n\n"
            f"Copy the content below to share:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ View Note", callback_data=f"note_view_{note_id}")],
                [InlineKeyboardButton("🔙 Back to Notes", callback_data="note_list")]
            ])
        )
        
        # Send the actual note content as a separate message for easy copying
        await query.message.reply_text(
            share_message,
            parse_mode='Markdown'
        )
    
    @with_user
    @error_handler
    async def delete_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a note"""
        query = update.callback_query
        await query.answer()
        
        note_id = int(query.data.split('_')[-1])
        user_id = context.user_data['user_id']
        
        with get_db() as db:
            note = db.query(Note).filter(
                Note.id == note_id,
                Note.user_id == user_id
            ).first()
            
            if not note:
                await query.edit_message_text("❌ Note not found.")
                return
            
            # Extract note data while session is open
            note_title = note.title
            
            db.delete(note)
            db.commit()
        
        await query.edit_message_text(
            f"🗑️ *Note Deleted*\n\n"
            f"📋 '{TextHelper.escape_markdown(note_title)}' has been deleted.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Notes", callback_data="note_list")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
            ])
        )
    
    @with_user
    @error_handler
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel note creation or search conversation"""
        await update.message.reply_text(
            "❌ Operation cancelled.",
            reply_markup=Keyboards.notes_menu()
        )
        
        # Clear conversation data
        for key in ['note_title', 'note_content', 'note_category']:
            context.user_data.pop(key, None)
        
        return ConversationHandler.END