import asyncio
from typing import Dict, Set, Tuple, Optional
from datetime import datetime

from sqlalchemy import func, distinct, Column, String, UnicodeText, Integer
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager

# Import from db_connection instead of recreating
from .db_connection import BASE, async_session, async_engine  # Add async_engine import

class BlackListFilters(BASE):
    __tablename__ = "blacklist"
    chat_id = Column(String(14), primary_key=True)
    trigger = Column(UnicodeText, primary_key=True, nullable=False)

    def __init__(self, chat_id, trigger):
        self.chat_id = str(chat_id)  # ensure string
        self.trigger = trigger

    def __repr__(self):
        return f"<Blacklist filter '{self.trigger}' for {self.chat_id}>"

    def __eq__(self, other):
        return bool(
            isinstance(other, BlackListFilters)
            and self.chat_id == other.chat_id
            and self.trigger == other.trigger
        )


class BlacklistSettings(BASE):
    __tablename__ = "blacklist_settings"
    chat_id = Column(String(14), primary_key=True)
    blacklist_type = Column(Integer, default=1)
    value = Column(UnicodeText, default="0")

    def __init__(self, chat_id, blacklist_type=1, value="0"):
        self.chat_id = str(chat_id)
        self.blacklist_type = blacklist_type
        self.value = value

    def __repr__(self):
        return f"<{self.chat_id} will execute {self.blacklist_type} for blacklist trigger>"

# In-memory caches
CHAT_BLACKLISTS: Dict[str, Set[str]] = {}
CHAT_SETTINGS_BLACKLISTS: Dict[str, Dict[str, object]] = {}

# Async locks
BLACKLIST_FILTER_INSERTION_LOCK = asyncio.Lock()
BLACKLIST_SETTINGS_INSERTION_LOCK = asyncio.Lock()

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

async def add_to_blacklist(chat_id: str, trigger: str) -> bool:
    """Add a new trigger to chat's blacklist"""
    async with BLACKLIST_FILTER_INSERTION_LOCK:
        try:
            async with session_scope() as session:
                blacklist_filt = BlackListFilters(str(chat_id), trigger)
                session.add(blacklist_filt)
                
                # Update cache
                if chat_id not in CHAT_BLACKLISTS:
                    CHAT_BLACKLISTS[chat_id] = set()
                CHAT_BLACKLISTS[chat_id].add(trigger)
                return True
        except Exception as e:
            print(f"Error adding to blacklist: {e}")
            return False

async def rm_from_blacklist(chat_id: str, trigger: str) -> bool:
    """Remove a trigger from chat's blacklist"""
    async with BLACKLIST_FILTER_INSERTION_LOCK:
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(BlackListFilters)
                    .where(BlackListFilters.chat_id == str(chat_id))
                    .where(BlackListFilters.trigger == trigger)
                )
                blacklist_filt = result.scalars().first()
                
                if blacklist_filt:
                    await session.delete(blacklist_filt)
                    # Update cache
                    if chat_id in CHAT_BLACKLISTS and trigger in CHAT_BLACKLISTS[chat_id]:
                        CHAT_BLACKLISTS[chat_id].remove(trigger)
                    return True
                return False
        except Exception as e:
            print(f"Error removing from blacklist: {e}")
            return False

async def get_chat_blacklist(chat_id: str) -> Set[str]:
    """Get all blacklisted triggers for a chat (uses cache)"""
    return CHAT_BLACKLISTS.get(str(chat_id), set())

async def num_blacklist_filters() -> int:
    """Count all blacklist filters"""
    try:
        async with async_session() as session:
            result = await session.execute(select(func.count()).select_from(BlackListFilters))
            return result.scalar() or 0
    except Exception as e:
        print(f"Error counting blacklist filters: {e}")
        return 0

async def num_blacklist_chat_filters(chat_id: str) -> int:
    """Count blacklist filters for a specific chat"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(func.count())
                .where(BlackListFilters.chat_id == str(chat_id))
            )
            return result.scalar() or 0
    except Exception as e:
        print(f"Error counting chat blacklist filters: {e}")
        return 0

async def num_blacklist_filter_chats() -> int:
    """Count chats with blacklist filters"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(func.count(distinct(BlackListFilters.chat_id)))
            )
            return result.scalar() or 0
    except Exception as e:
        print(f"Error counting blacklist chats: {e}")
        return 0

async def set_blacklist_strength(chat_id: str, blacklist_type: int, value: str) -> bool:
    """Set blacklist enforcement strength for a chat"""
    async with BLACKLIST_SETTINGS_INSERTION_LOCK:
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(BlacklistSettings)
                    .where(BlacklistSettings.chat_id == str(chat_id))
                )
                curr_setting = result.scalars().first()
                
                if not curr_setting:
                    curr_setting = BlacklistSettings(
                        chat_id,
                        blacklist_type=int(blacklist_type),
                        value=value,
                    )
                else:
                    curr_setting.blacklist_type = int(blacklist_type)
                    curr_setting.value = str(value)
                
                # Update cache
                CHAT_SETTINGS_BLACKLISTS[str(chat_id)] = {
                    "blacklist_type": int(blacklist_type),
                    "value": value,
                }
                
                session.add(curr_setting)
                return True
        except Exception as e:
            print(f"Error setting blacklist strength: {e}")
            return False

async def get_blacklist_setting(chat_id: str) -> Tuple[int, str]:
    """Get blacklist settings for a chat (uses cache)"""
    setting = CHAT_SETTINGS_BLACKLISTS.get(str(chat_id))
    if setting:
        return setting["blacklist_type"], setting["value"]
    return 1, "0"  # Default values

async def migrate_chat(old_chat_id: str, new_chat_id: str) -> bool:
    """Migrate blacklist data from old chat to new chat"""
    async with BLACKLIST_FILTER_INSERTION_LOCK:
        try:
            async with session_scope() as session:
                # Migrate filters
                result = await session.execute(
                    select(BlackListFilters)
                    .where(BlackListFilters.chat_id == str(old_chat_id))
                )
                filters = result.scalars().all()
                
                for filt in filters:
                    filt.chat_id = str(new_chat_id)
                
                # Migrate settings
                result = await session.execute(
                    select(BlacklistSettings)
                    .where(BlacklistSettings.chat_id == str(old_chat_id))
                )
                setting = result.scalars().first()
                
                if setting:
                    setting.chat_id = str(new_chat_id)
                
                # Update caches
                if str(old_chat_id) in CHAT_BLACKLISTS:
                    CHAT_BLACKLISTS[str(new_chat_id)] = CHAT_BLACKLISTS.pop(str(old_chat_id))
                
                if str(old_chat_id) in CHAT_SETTINGS_BLACKLISTS:
                    CHAT_SETTINGS_BLACKLISTS[str(new_chat_id)] = CHAT_SETTINGS_BLACKLISTS.pop(str(old_chat_id))
                
                return True
        except Exception as e:
            print(f"Error migrating chat blacklist: {e}")
            return False



# [All other functions remain exactly the same...]

async def __load_chat_blacklists():
    """Load blacklists into cache on startup"""
    global CHAT_BLACKLISTS
    try:
        async with async_session() as session:
            # Get all distinct chat_ids with blacklists
            result = await session.execute(
                select(BlackListFilters.chat_id).distinct()
            )
            chat_ids = [row[0] for row in result.all()]

            # Initialize with empty sets
            CHAT_BLACKLISTS = {chat_id: set() for chat_id in chat_ids}

            # Get all filters
            result = await session.execute(select(BlackListFilters))
            for filt in result.scalars().all():
                CHAT_BLACKLISTS[filt.chat_id].add(filt.trigger)
    except Exception as e:
        print(f"Error loading chat blacklists: {e}")

async def __load_chat_settings_blacklists():
    """Load blacklist settings into cache on startup"""
    global CHAT_SETTINGS_BLACKLISTS
    try:
        async with async_session() as session:
            result = await session.execute(select(BlacklistSettings))
            CHAT_SETTINGS_BLACKLISTS = {
                x.chat_id: {
                    "blacklist_type": x.blacklist_type,
                    "value": x.value
                }
                for x in result.scalars().all()
            }
    except Exception as e:
        print(f"Error loading blacklist settings: {e}")

# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize blacklist system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_chat_blacklists()
                await __load_chat_settings_blacklists()
                _initialized = True
            except Exception as e:
                print(f"Blacklist initialization failed: {e}")
                raise
