import pytz
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from database.models import User
import re

class TimeHelper:
    @staticmethod
    def parse_time_input(time_str: str, user_timezone: str = "UTC") -> Optional[datetime]:
        """Parse various time input formats with standardized dd-mm-yyyy at 00:00 format"""
        tz = pytz.timezone(user_timezone)
        now = datetime.now(tz)
        
        # Remove extra spaces and convert to lowercase
        time_str = time_str.strip().lower()
        
        # Patterns for different time formats
        patterns = [
            # Standardized format: "27-06-2025 at 14:30", "27-06-2025 at 2:30 PM"
            (r'^(\d{1,2})-(\d{1,2})-(\d{4})\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm)?$', 'standard'),
            # Absolute time: "14:30", "2:30 pm", "14:30 tomorrow"
            (r'^(\d{1,2}):(\d{2})\s*(am|pm)?\s*(today|tomorrow)?$', 'absolute'),
            # Relative time: "in 30 minutes", "in 2 hours"
            (r'^in\s+(\d+)\s+(minute|minutes|hour|hours|day|days)$', 'relative'),
            # Natural language: "tomorrow at 9am", "next monday at 2pm", "tomorrow at 3pm"
            (r'^(tomorrow|next\s+\w+)\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?$', 'natural'),
            # Natural language without minutes: "tomorrow at 3pm", "next monday at 2pm"
            (r'^(tomorrow|next\s+\w+)\s+at\s+(\d{1,2})\s*(am|pm)$', 'natural'),
            # Date only: "27-06-2025", "tomorrow", "next monday"
            (r'^(\d{1,2})-(\d{1,2})-(\d{4})$', 'date_only'),
            (r'^(tomorrow|next\s+\w+)$', 'date_only_natural'),
        ]
        
        for pattern, type_name in patterns:
            match = re.match(pattern, time_str)
            if match:
                if type_name == 'standard':
                    return TimeHelper._parse_standard_time(match, tz)
                elif type_name == 'absolute':
                    return TimeHelper._parse_absolute_time(match, now)
                elif type_name == 'relative':
                    return TimeHelper._parse_relative_time(match, now)
                elif type_name == 'natural':
                    return TimeHelper._parse_natural_time(match, now)
                elif type_name == 'date_only':
                    return TimeHelper._parse_date_only(match, now)
                elif type_name == 'date_only_natural':
                    return TimeHelper._parse_date_only_natural(match, now)
        
        return None
    
    @staticmethod
    def _parse_standard_time(match, tz) -> datetime:
        """Parse standardized format: dd-mm-yyyy at hh:mm"""
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        period = match.group(6)
        
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        
        return tz.localize(datetime(year, month, day, hour, minute, 0))
    
    @staticmethod
    def _parse_absolute_time(match, now: datetime) -> datetime:
        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3)
        day = match.group(4)
        
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if day == 'tomorrow':
            target_time += timedelta(days=1)
        elif target_time <= now:
            target_time += timedelta(days=1)
        
        return target_time
    
    @staticmethod
    def _parse_relative_time(match, now: datetime) -> datetime:
        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit.startswith('minute'):
            return now + timedelta(minutes=amount)
        elif unit.startswith('hour'):
            return now + timedelta(hours=amount)
        elif unit.startswith('day'):
            return now + timedelta(days=amount)
        
        return now
    
    @staticmethod
    def _parse_natural_time(match, now: datetime) -> datetime:
        """Parse natural language time: tomorrow at 3pm, next monday at 2pm, etc."""
        date_part = match.group(1)  # "tomorrow" or "next monday"
        
        # Handle both patterns: with minutes and without minutes
        if len(match.groups()) >= 4:
            # Pattern with minutes: "tomorrow at 3:30pm"
            hour = int(match.group(2))  # hour
            minute = int(match.group(3)) if match.group(3) else 0  # minute (optional)
            period = match.group(4) if len(match.groups()) > 3 else None  # am/pm (optional)
        else:
            # Pattern without minutes: "tomorrow at 3pm"
            hour = int(match.group(2))  # hour
            minute = 0  # default to 0 minutes
            period = match.group(3) if len(match.groups()) > 2 else None  # am/pm
        
        # Convert 12-hour format to 24-hour format
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        
        # Calculate the target date
        if date_part == 'tomorrow':
            target_date = now + timedelta(days=1)
        elif date_part.startswith('next'):
            # For "next monday", "next tuesday", etc.
            day_name = date_part.split()[1].lower()
            days_ahead = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            if day_name in days_ahead:
                target_weekday = days_ahead[day_name]
                current_weekday = now.weekday()
                days_to_add = (target_weekday - current_weekday) % 7
                if days_to_add == 0:
                    days_to_add = 7  # Next week
                target_date = now + timedelta(days=days_to_add)
            else:
                # Fallback: add 7 days
                target_date = now + timedelta(days=7)
        else:
            # Default to tomorrow
            target_date = now + timedelta(days=1)
        
        # Set the time
        target_datetime = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return target_datetime
    
    @staticmethod
    def _parse_date_only(match, now: datetime) -> datetime:
        """Parse date only format: dd-mm-yyyy"""
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        
        # Set time to 9:00 AM by default
        return now.replace(year=year, month=month, day=day, hour=9, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def _parse_date_only_natural(match, now: datetime) -> datetime:
        """Parse natural date: tomorrow, next monday, etc."""
        date_str = match.group(1)
        
        if date_str == 'tomorrow':
            target_date = now + timedelta(days=1)
        elif date_str.startswith('next'):
            # Simplified: just add 7 days for "next" dates
            target_date = now + timedelta(days=7)
        else:
            target_date = now + timedelta(days=1)
        
        # Set time to 9:00 AM by default
        return target_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def format_datetime(dt: datetime, user_timezone: str = "UTC") -> str:
        """Format datetime for user display"""
        tz = pytz.timezone(user_timezone)
        local_dt = dt.astimezone(tz)
        return local_dt.strftime("%d-%m-%Y at %H:%M")

class TextHelper:
    @staticmethod
    def truncate(text: str, max_length: int = 100) -> str:
        """Truncate text with ellipsis"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape markdown special characters"""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def parse_tags(tags_str: str) -> List[str]:
        """Parse comma-separated tags"""
        if not tags_str:
            return []
        return [tag.strip() for tag in tags_str.split(',') if tag.strip()]
    
    @staticmethod
    def format_tags(tags: List[str]) -> str:
        """Format tags for display"""
        if not tags:
            return ""
        return " ".join([f"#{tag}" for tag in tags])

class ValidationHelper:
    @staticmethod
    def is_valid_timezone(timezone_str: str) -> bool:
        """Check if timezone string is valid"""
        try:
            pytz.timezone(timezone_str)
            return True
        except pytz.exceptions.UnknownTimeZoneError:
            return False
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Basic email validation"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None