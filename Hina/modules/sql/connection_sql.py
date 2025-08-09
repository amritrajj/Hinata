import asyncio
import time
from typing import Dict, Optional, Union

from sqlalchemy import Column, String, Boolean, UnicodeText, BigInteger, Integer
from sqlalchemy.future import select
from sqlalchemy import delete

from .db_connection import BASE, async_session, async_engine

# Database models
class ChatAccessConnectionSettings(BASE):
    __tablename__ = "access_connection"
    chat_id = Column(String(14), primary_key=True)
    allow_connect_to_chat = Column(Boolean, default=True)

    def __init__(self, chat_id: Union[str, int], allow_connect_to_chat: bool = True):
        self.chat_id = str(chat_id)
        self.allow_connect_to_chat = bool(allow_connect_to_chat)

class Connection(BASE):
    __tablename__ = "connection"
    user_id = Column(BigInteger, primary_key=True)
    chat_id = Column(String(14))

    def __init__(self, user_id: int, chat_id: Union[str, int]):
        self.user_id = user_id
        self.chat_id = str(chat_id)

class ConnectionHistory(BASE):
    __tablename__ = "connection_history"
    user_id = Column(BigInteger, primary_key=True)
    chat_id = Column(String(14), primary_key=True)
    chat_name = Column(UnicodeText)
    conn_time = Column(Integer)

    def __init__(self, user_id: int, chat_id: Union[str, int], chat_name: str, conn_time: int):
        self.user_id = user_id
        self.chat_id = str(chat_id)
        self.chat_name = str(chat_name)
        self.conn_time = int(conn_time)

# Async locks
CHAT_ACCESS_LOCK = asyncio.Lock()
CONNECTION_INSERTION_LOCK = asyncio.Lock()
CONNECTION_HISTORY_LOCK = asyncio.Lock()

# In-memory cache
HISTORY_CONNECT: Dict[int, Dict[int, Dict[str, str]]] = {}

# Table creation
async def create_tables():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

# Connection management functions
async def allow_connect_to_chat(chat_id: Union[str, int]) -> bool:
    """Check if connecting to chat is allowed"""
    async with async_session() as session:
        result = await session.execute(
            select(ChatAccessConnectionSettings).where(
                ChatAccessConnectionSettings.chat_id == str(chat_id)
            )
        )
        setting = result.scalars().first()
        return setting.allow_connect_to_chat if setting else False

async def set_allow_connect_to_chat(chat_id: Union[int, str], setting: bool) -> None:
    """Set chat connection permission"""
    async with CHAT_ACCESS_LOCK:
        async with async_session() as session:
            async with session.begin():
                chat_id_str = str(chat_id)
                result = await session.execute(
                    select(ChatAccessConnectionSettings).where(
                        ChatAccessConnectionSettings.chat_id == chat_id_str
                    )
                )
                chat_setting = result.scalars().first()
                
                if not chat_setting:
                    chat_setting = ChatAccessConnectionSettings(chat_id_str, setting)
                chat_setting.allow_connect_to_chat = setting
                session.add(chat_setting)

async def connect(user_id: int, chat_id: Union[str, int]) -> bool:
    """Connect user to chat"""
    async with CONNECTION_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Remove existing connection
                result = await session.execute(
                    select(Connection).where(Connection.user_id == user_id)
                )
                existing = result.scalars().first()
                if existing:
                    await session.delete(existing)
                
                # Add new connection
                session.add(Connection(user_id, chat_id))
                return True

async def get_connected_chat(user_id: int) -> Optional[Connection]:
    """Get user's connected chat"""
    async with async_session() as session:
        result = await session.execute(
            select(Connection).where(Connection.user_id == user_id)
        )
        return result.scalars().first()

async def disconnect(user_id: int) -> bool:
    """Disconnect user"""
    async with CONNECTION_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Connection).where(Connection.user_id == user_id)
                )
                conn = result.scalars().first()
                if conn:
                    await session.delete(conn)
                    return True
                return False

async def add_history_conn(user_id: int, chat_id: Union[str, int], chat_name: str) -> None:
    """Add connection to history"""
    global HISTORY_CONNECT
    async with CONNECTION_HISTORY_LOCK:
        async with async_session() as session:
            async with session.begin():
                now = int(time.time())
                user_key = user_id
                
                # Initialize if needed
                if user_key not in HISTORY_CONNECT:
                    HISTORY_CONNECT[user_key] = {}
                
                # Trim old entries
                if len(HISTORY_CONNECT[user_key]) >= 5:
                    oldest = sorted(HISTORY_CONNECT[user_key].keys())[:-4]
                    for ts in oldest:
                        old_chat = HISTORY_CONNECT[user_key].pop(ts)
                        result = await session.execute(
                            select(ConnectionHistory).where(
                                ConnectionHistory.user_id == user_key,
                                ConnectionHistory.chat_id == old_chat["chat_id"]
                            )
                        )
                        old_rec = result.scalars().first()
                        if old_rec:
                            await session.delete(old_rec)
                
                # Remove existing for this chat
                result = await session.execute(
                    select(ConnectionHistory).where(
                        ConnectionHistory.user_id == user_key,
                        ConnectionHistory.chat_id == str(chat_id)
                    )
                )
                existing = result.scalars().first()
                if existing:
                    await session.delete(existing)
                
                # Add new record
                new_rec = ConnectionHistory(user_key, chat_id, chat_name, now)
                session.add(new_rec)
                HISTORY_CONNECT[user_key][now] = {
                    "chat_id": str(chat_id),
                    "chat_name": chat_name
                }

async def get_history_conn(user_id: int) -> Dict[int, Dict[str, str]]:
    """Get connection history"""
    return HISTORY_CONNECT.get(user_id, {})

async def clear_history_conn(user_id: int) -> bool:
    """Clear connection history"""
    global HISTORY_CONNECT
    async with CONNECTION_HISTORY_LOCK:
        async with async_session() as session:
            async with session.begin():
                if user_id in HISTORY_CONNECT:
                    for ts in list(HISTORY_CONNECT[user_id].keys()):
                        chat_id = HISTORY_CONNECT[user_id][ts]["chat_id"]
                        result = await session.execute(
                            select(ConnectionHistory).where(
                                ConnectionHistory.user_id == user_id,
                                ConnectionHistory.chat_id == chat_id
                            )
                        )
                        rec = result.scalars().first()
                        if rec:
                            await session.delete(rec)
                        del HISTORY_CONNECT[user_id][ts]
                    return True
                return False

async def __load_user_history():
    """Load history on startup"""
    global HISTORY_CONNECT
    async with async_session() as session:
        result = await session.execute(select(ConnectionHistory))
        for rec in result.scalars().all():
            HISTORY_CONNECT.setdefault(rec.user_id, {})[rec.conn_time] = {
                "chat_name": rec.chat_name,
                "chat_id": rec.chat_id
            }

# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize connection system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_user_history()
                _initialized = True
            except Exception as e:
                print(f"Connection system initialization failed: {e}")
                raise
