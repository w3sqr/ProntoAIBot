# Professional Telegram Productivity Bot

A comprehensive Telegram bot for productivity management with reminders, task management, habit tracking, note-taking, and AI assistance.

<a href="https://t.me/ProntoAIBot" target="_blank">
  <img width="50" height="50" alt="Logo" src="https://github.com/user-attachments/assets/7d9f7bf7-06d2-4292-b256-270ddeebbb8c" />
</a>


## 🌟 Features

### 📝 Smart Reminders
- One-time and recurring reminders
- Natural language time input ("tomorrow at 9am", "in 30 minutes")
- Timezone support with automatic detection
- Persistent scheduling (survives bot restarts)
- Snooze and edit functionality

### ✅ Task Management
- Create and organize tasks with priorities
- Project-based organization
- Due date tracking with notifications
- Progress monitoring
- Status management (To Do, In Progress, Completed)

### 🎯 Habit Tracking
- Daily, weekly, and monthly habits
- Streak tracking and statistics
- Custom targets and units
- Progress visualization
- Log updates and custom values

### 📋 Note Taking
- Rich note creation and organization
- Categories and tags
- Search functionality
- Pin important notes
- Full editing capabilities

### 🤖 AI Assistant
- ChatGPT integration for productivity advice
- Natural language command processing
- Smart task suggestions based on your data
- Habit recommendations
- Note summarization
- Personalized insights and analytics

### 📊 Analytics & Statistics
- Comprehensive productivity metrics
- Weekly and monthly reports
- Habit performance tracking
- Task completion rates
- Progress visualization
- Custom date range analysis

### 🌍 Multi-language Support
- English, Spanish, French, German, Russian
- Easy language switching
- Localized date/time formats

### ⚙️ Advanced Settings
- Timezone configuration with custom UTC offsets
- Notification preferences
- Contact and support options
- Bot sharing features
- Donation links

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Redis server
- Telegram Bot Token
- OpenAI API Key (optional, for AI features)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/w3sqr/ProntoAIBot.git
cd ProntoAIBot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Environment Setup**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Database Setup**
```bash
# The bot will automatically create tables on first run
# Make sure PostgreSQL is running and accessible
```

5. **Run the bot**
```bash
python bot.py
```

## 📋 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Telegram Bot Token from @BotFather | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `OPENAI_API_KEY` | OpenAI API key for AI features | No |
| `ADMIN_USER_ID` | Telegram user ID for admin features | No |
| `WEBHOOK_URL` | Webhook URL for production deployment | No |
| `WEBHOOK_SECRET` | Secret token for webhook security | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No |
| `ENVIRONMENT` | Environment (development, production) | No |

### Example .env file
```env
BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:password@localhost:5432/telegram_bot
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=your_openai_api_key_here
ADMIN_USER_ID=123456789
LOG_LEVEL=INFO
ENVIRONMENT=production
```

## 🏗️ Architecture

### Project Structure
```
├── bot.py                 # Main bot application
├── config.py             # Configuration management
├── requirements.txt      # Python dependencies
├── requirements-dev.txt  # Development dependencies
├── alembic.ini          # Database migration configuration
├── database/
│   ├── models.py         # SQLAlchemy models
│   └── database.py       # Database connection and utilities
├── features/
│   ├── reminders.py      # Reminder management
│   ├── tasks.py          # Task management
│   ├── habits.py         # Habit tracking
│   ├── notes.py          # Note taking
│   ├── ai_assistant.py   # AI integration
│   ├── settings.py       # User settings
│   ├── statistics.py     # Analytics and reports
│   └── notifications.py  # Notification system
├── migrations/           # Database migration files
├── utils/
│   ├── decorators.py     # Common decorators
│   ├── helpers.py        # Utility functions
│   ├── keyboards.py      # Telegram keyboards
│   └── logger.py         # Logging configuration
└── logs/                 # Application logs
```

### Key Components

- **Modular Architecture**: Each feature is in its own module for maintainability
- **Database Layer**: SQLAlchemy ORM with PostgreSQL and Alembic migrations
- **Caching Layer**: Redis for session storage and job persistence
- **Scheduler**: APScheduler for reminder notifications
- **AI Integration**: OpenAI GPT for intelligent assistance
- **Error Handling**: Comprehensive error logging and user feedback
- **Timezone Support**: Full timezone awareness with automatic detection

## 🔧 Development

### Recent Improvements

- **Enhanced AI Assistant**: Natural language processing for all productivity features
- **Improved UI/UX**: Modern two-column layouts and better visual hierarchy
- **Timezone Awareness**: Automatic timezone detection and custom UTC offset support
- **Bug Fixes**: Resolved SQLAlchemy session issues and notification system problems
- **Code Cleanup**: Removed debug code and optimized performance
- **Production Ready**: Comprehensive error handling and logging

### Adding New Features

1. Create a new module in the `features/` directory
2. Implement the feature class with appropriate handlers
3. Add handlers to `bot.py`
4. Update database models if needed
5. Add tests and documentation

### Database Migrations

The bot uses Alembic for database migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head
```

### Testing

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests (when implemented)
python -m pytest tests/

# Run with coverage
python -m pytest --cov=. tests/

# Code formatting
black .

# Linting
flake8 .
```

## 🚀 Deployment

### Production Deployment

The bot is now production-ready with:
- Comprehensive error handling
- Proper logging configuration
- Security best practices
- Optimized database queries
- Clean, maintainable code

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "bot.py"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  bot:
    build: .
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:13
    environment:
      - POSTGRES_DB=telegram_bot
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## 📝 Changelog

### Latest Updates
- Enhanced AI Assistant with natural language processing
- Improved UI/UX with modern layouts
- Fixed timezone handling and notification system
- Resolved SQLAlchemy session issues
- Added comprehensive error handling
- Optimized database queries and performance
- Removed debug code and cleaned up codebase

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- 🔗 Website: https://prontoai.xyz
- 📧 Email: hello@prontoai.xyz
- 💬 Telegram: @prontoAI
- 🐛 Issues: GitHub Issues
- 📖 Documentation: Wiki

## 🙏 Acknowledgments

- Telegram Bot API
- python-telegram-bot library
- OpenAI for AI capabilities
- SQLAlchemy and PostgreSQL
- Redis for caching and job storage
- APScheduler for task scheduling

---

Made with ❤️ for productivity enthusiasts
