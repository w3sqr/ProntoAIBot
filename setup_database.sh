#!/bin/bash

# Database Setup Script for ProntoAI Bot
echo "🗄️ Setting up database for ProntoAI Bot..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found. Please run install.sh first or create .env file manually."
    exit 1
fi

# Load environment variables
source .env

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL not set in .env file"
    exit 1
fi

echo "✅ Database URL found"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "🔧 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if PostgreSQL is running (basic check)
echo "🔍 Checking PostgreSQL connection..."
if command -v psql &> /dev/null; then
    # Try to connect to PostgreSQL
    if psql "$DATABASE_URL" -c "SELECT 1;" &> /dev/null; then
        echo "✅ PostgreSQL connection successful"
    else
        echo "⚠️  Warning: Could not connect to PostgreSQL. Please ensure:"
        echo "   - PostgreSQL is running"
        echo "   - Database exists"
        echo "   - User has proper permissions"
        echo "   - DATABASE_URL is correct"
    fi
else
    echo "⚠️  Warning: psql command not found. Please ensure PostgreSQL is installed."
fi

# Run database migrations
echo "🔄 Running database migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✅ Database migrations completed successfully"
else
    echo "❌ Error: Database migrations failed"
    echo "💡 Try running: alembic stamp head"
    exit 1
fi

echo ""
echo "✅ Database setup completed!"
echo "📋 Database is ready for the bot to use." 