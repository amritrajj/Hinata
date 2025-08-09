import asyncio
from datetime import datetime
from typing import Dict, Optional
from contextlib import asynccontextmanager
from sqlalchemy import Boolean, Column, BigInteger, UnicodeText, DateTime
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

# Import both BASE and async_engine from db_connection
from .db_connection import BASE, async_session, async_engine

class AFK(BASE):
    __tablename__ = "afk_users"
    user_id = Column(BigInteger, primary_key=True)
    is_afk = Column(Boolean, default=False)
    reason = Column(UnicodeText)
    time = Column(DateTime)

    def __init__(self, user_id: int, reason: str = "", is_afk: bool = True):
        self.user_id = user_id
        self.reason = reason
        self.is_afk = is_afk
        self.time = datetime.now()

    def __repr__(self):
        return f"<AFK {self.user_id} ({self.is_afk})>"

# In-memory cache
AFK_USERS: Dict[int, Dict[str, object]] = {}

# Async lock
AFK_LOCK = asyncio.Lock()

@asynccontextmanager
async def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = async_session()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    finally:
        await session.close()

async def create_tables():
    """Initialize database tables using engine connection"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

async def is_afk(user_id: int) -> bool:
    """Check if user is AFK (uses cache)"""
    return user_id in AFK_USERS

async def check_afk_status(user_id: int) -> Optional[AFK]:
    """Get full AFK status from database"""
    async with async_session() as session:
        result = await session.execute(
            select(AFK)
            .where(AFK.user_id == user_id)
        )
        return result.scalars().first()

async def set_afk(user_id: int, reason: str = "") -> bool:
    """Set user as AFK"""
    async with AFK_LOCK:
        try:
            async with session_scope() as session:
                # Check existing AFK status
                result = await session.execute(
                    select(AFK)
                    .where(AFK.user_id == user_id)
                )
                afk_user = result.scalars().first()

                if not afk_user:
                    afk_user = AFK(user_id, reason, True)
                else:
                    afk_user.is_afk = True
                    afk_user.reason = reason
                    afk_user.time = datetime.now()

                # Update cache
                AFK_USERS[user_id] = {
                    "reason": reason,
                    "time": afk_user.time
                }

                session.add(afk_user)
                return True
        except Exception as e:
            print(f"Error setting AFK: {e}")
            return False

async def rm_afk(user_id: int) -> bool:
    """Remove AFK status"""
    async with AFK_LOCK:
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(AFK)
                    .where(AFK.user_id == user_id)
                )
                afk_user = result.scalars().first()

                if afk_user:
                    if user_id in AFK_USERS:
                        del AFK_USERS[user_id]
                    await session.delete(afk_user)
                    return True
                return False
        except Exception as e:
            print(f"Error removing AFK: {e}")
            return False

async def __load_afk_users():
    """Load AFK users into cache on startup"""
    global AFK_USERS
    try:
        async with async_session() as session:
            result = await session.execute(
                select(AFK)
                .where(AFK.is_afk == True)
            )
            AFK_USERS = {
                user.user_id: {
                    "reason": user.reason,
                    "time": user.time
                }
                for user in result.scalars().all()
            }
    except Exception as e:
        print(f"Error loading AFK users: {e}")

# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize AFK system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_afk_users()
                _initialized = True
            except Exception as e:
                print(f"AFK initialization failed: {e}")
                raise
