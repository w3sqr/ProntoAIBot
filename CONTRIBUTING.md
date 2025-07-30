# Contributing to ProntoAI Bot

Thank you for your interest in contributing to ProntoAI Bot! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- PostgreSQL
- Redis
- Git

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/thesurfhawk/ProntoAIBot.git
   cd ProntoAIBot
   ```

2. **Install Dependencies**
   ```bash
   ./install.sh
   ```

3. **Set Up Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Set Up Database**
   ```bash
   ./setup_database.sh
   ```

## 🏗️ Project Structure

```
├── bot.py                 # Main bot application
├── config.py             # Configuration management
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── setup.py             # Package setup
├── install.sh           # Installation script
├── setup_database.sh    # Database setup script
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

## 🔧 Development Guidelines

### Code Style
- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions small and focused

### Database Changes
When making database changes:

1. **Create a Migration**
   ```bash
   alembic revision --autogenerate -m "Description of changes"
   ```

2. **Test the Migration**
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade +1
   ```

3. **Update Models**
   - Modify `database/models.py` as needed
   - Ensure all relationships are properly defined

### Adding New Features

1. **Create Feature Module**
   - Add new file in `features/` directory
   - Follow existing module structure
   - Implement proper error handling

2. **Update Main Bot**
   - Add handlers to `bot.py`
   - Import new feature module
   - Add to command handlers

3. **Add Tests**
   - Create test files in `tests/` directory
   - Test both success and error cases
   - Mock external dependencies

### Error Handling
- Use try-catch blocks for external API calls
- Log errors with appropriate levels
- Provide user-friendly error messages
- Never expose sensitive information in errors

## 🧪 Testing

### Running Tests
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=.
```

### Test Guidelines
- Write unit tests for all new functions
- Test edge cases and error conditions
- Mock external dependencies (APIs, databases)
- Maintain test coverage above 80%

## 📝 Documentation

### Code Documentation
- Use docstrings for all public functions
- Include parameter types and return types
- Provide usage examples for complex functions

### User Documentation
- Update README.md for new features
- Add screenshots for UI changes
- Document configuration options

## 🔄 Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow coding guidelines
   - Add tests for new functionality
   - Update documentation

3. **Test Your Changes**
   ```bash
   # Run tests
   pytest
   
   # Test database migrations
   alembic upgrade head
   
   # Test bot functionality
   python bot.py
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format
Use conventional commit format:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `style:` for formatting changes
- `refactor:` for code refactoring
- `test:` for test changes
- `chore:` for maintenance tasks

## 🐛 Bug Reports

When reporting bugs, please include:
- Description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Error logs if applicable

## 💡 Feature Requests

When requesting features, please include:
- Description of the feature
- Use case and benefits
- Implementation suggestions (if any)
- Priority level

## 📞 Support

- Create an issue for bugs or feature requests
- Join our community discussions
- Check existing issues before creating new ones

## 📄 License

By contributing to ProntoAI Bot, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing! 🎉 
