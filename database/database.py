from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import contextmanager, asynccontextmanager
from config import settings
from .models import Base
import redis
from loguru import logger

# Sync database setup
engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async database setup (for future use)
async_engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False
)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Redis setup
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db() -> Session:
    """Get database session context manager"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()

@asynccontextmanager
async def get_async_db() -> AsyncSession:
    """Get async database session context manager"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Async database error: {e}")
            raise

def get_redis():
    """Get Redis client"""
    return redis_client