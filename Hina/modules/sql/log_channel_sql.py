import asyncio
from typing import Dict, Optional, Union

from .db_connection import BASE, async_session, async_engine  # Add async_engine import
from sqlalchemy import Column, String, distinct, func
from sqlalchemy.future import select
from sqlalchemy import update, delete


class GroupLogs(BASE):
    __tablename__ = "log_channels"
    chat_id = Column(String(14), primary_key=True)
    log_channel = Column(String(14), nullable=False)

    def __init__(self, chat_id, log_channel):
        self.chat_id = str(chat_id)
        self.log_channel = str(log_channel)

    def __repr__(self):
        return f"<Log channel {self.log_channel} for chat {self.chat_id}>"


# Create tables if not exists - FIXED
async def create_tables():
    async with async_engine.begin() as conn:  # Use engine instead of session
        await conn.run_sync(BASE.metadata.create_all)

# Async lock replaces threading.Lock
LOGS_INSERTION_LOCK = asyncio.Lock()

# In-memory cache
CHANNELS: Dict[str, str] = {}

async def set_chat_log_channel(chat_id: Union[int, str], log_channel: Union[int, str]) -> None:
    async with LOGS_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GroupLogs)
                    .where(GroupLogs.chat_id == str(chat_id))
                )
                res = result.scalars().first()
                
                if res:
                    res.log_channel = str(log_channel)
                else:
                    res = GroupLogs(chat_id, log_channel)
                
                CHANNELS[str(chat_id)] = str(log_channel)
                session.add(res)


async def get_chat_log_channel(chat_id: Union[int, str]) -> Optional[str]:
    return CHANNELS.get(str(chat_id))


async def stop_chat_logging(chat_id: Union[int, str]) -> Optional[str]:
    async with LOGS_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GroupLogs)
                    .where(GroupLogs.chat_id == str(chat_id))
                )
                res = result.scalars().first()
                
                if res:
                    if str(chat_id) in CHANNELS:
                        del CHANNELS[str(chat_id)]
                    
                    log_channel = res.log_channel
                    await session.delete(res)
                    return log_channel
                return None


async def num_logchannels() -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(distinct(GroupLogs.chat_id)))
        )
        return result.scalar() or 0


async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    async with LOGS_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GroupLogs)
                    .where(GroupLogs.chat_id == str(old_chat_id))
                )
                chat = result.scalars().first()
                
                if chat:
                    chat.chat_id = str(new_chat_id)
                    session.add(chat)
                    
                    if str(old_chat_id) in CHANNELS:
                        CHANNELS[str(new_chat_id)] = CHANNELS.pop(str(old_chat_id))




# [Rest of your existing functions remain exactly the same...]

async def __load_log_channels() -> None:
    global CHANNELS
    async with async_session() as session:
        result = await session.execute(select(GroupLogs))
        CHANNELS = {chat.chat_id: chat.log_channel for chat in result.scalars()}

# Initialize only when explicitly called
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize database (call this from your main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            await create_tables()
            await __load_log_channels()
            _initialized = True

