# Hina/modules/sql/db_connection.py
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncAttrs
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
from Hina.config import DB_URI
import logging

logger = logging.getLogger(__name__)

def get_async_db_uri(db_uri: str) -> str:
    """Convert regular postgres URI to asyncpg format"""
    if db_uri.startswith("postgresql://"):
        return db_uri.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_uri.startswith("postgres://"):  # Handle common alternative
        return db_uri.replace("postgres://", "postgresql+asyncpg://", 1)
    return db_uri  # Assume it's already correct

async_engine = create_async_engine(
    get_async_db_uri(DB_URI),
    echo=True,  # Enable for debugging
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    pool_timeout=30,
    pool_recycle=3600,
    connect_args={
        "server_settings": {
            "application_name": "HinaBot",
            "statement_timeout": "30000",
            "idle_in_transaction_session_timeout": "30000"
        }
    }
)

async_session = sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
    autoflush=False,
    future=True
)

BASE = declarative_base(cls=AsyncAttrs)

async def check_connection() -> bool:
    """Proper connection check with SQLAlchemy 2.0+ syntax"""
    try:
        async with async_engine.connect() as conn:
            # Use text() for raw SQL and execute() instead of execute_raw()
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database connection check failed: {e}", exc_info=True)
        return False

@asynccontextmanager
async def session_scope():
    """Transactional scope with better error handling"""
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Session rollback due to error: {e}", exc_info=True)
        raise
    finally:
        await session.close()

async def initialize_db():
    """Initialize tables with proper error handling"""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(BASE.metadata.create_all)
            logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}", exc_info=True)
        raise
