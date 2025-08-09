import asyncio
from typing import Set, Union, Optional

from .db_connection import BASE, async_session, async_engine
from sqlalchemy import Boolean, Column, Integer, String, UnicodeText
from sqlalchemy.future import select


class GloballyBannedUsers(BASE):
    __tablename__ = "gbans"
    user_id = Column(Integer, primary_key=True)
    name = Column(UnicodeText, nullable=False)
    reason = Column(UnicodeText)

    def __init__(self, user_id, name, reason=None):
        self.user_id = user_id
        self.name = name
        self.reason = reason

    def __repr__(self):
        return f"<GBanned User {self.name} ({self.user_id})>"

    def to_dict(self):
        return {"user_id": self.user_id, "name": self.name, "reason": self.reason}


class GbanSettings(BASE):
    __tablename__ = "gban_settings"
    chat_id = Column(String(14), primary_key=True)
    setting = Column(Boolean, default=True, nullable=False)

    def __init__(self, chat_id, enabled):
        self.chat_id = str(chat_id)
        self.setting = enabled

    def __repr__(self):
        return f"<Gban setting {self.chat_id} ({self.setting})>"


async def create_tables():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)


# Async locks
GBANNED_USERS_LOCK = asyncio.Lock()
GBAN_SETTING_LOCK = asyncio.Lock()

# In-memory cache
GBANNED_LIST: Set[int] = set()
GBANSTAT_LIST: Set[str] = set()


async def gban_user(user_id: int, name: str, reason: str = None) -> None:
    async with GBANNED_USERS_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GloballyBannedUsers).where(GloballyBannedUsers.user_id == user_id)
                )
                user = result.scalars().first()
                
                if not user:
                    user = GloballyBannedUsers(user_id, name, reason)
                else:
                    user.name = name
                    user.reason = reason

                session.add(user)
                await __load_gbanned_userid_list()


async def update_gban_reason(user_id: int, name: str, reason: str = None) -> Optional[str]:
    async with GBANNED_USERS_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GloballyBannedUsers).where(GloballyBannedUsers.user_id == user_id)
                )
                user = result.scalars().first()
                
                if not user:
                    return None
                
                old_reason = user.reason
                user.name = name
                user.reason = reason
                session.add(user)
                return old_reason


async def ungban_user(user_id: int) -> None:
    async with GBANNED_USERS_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GloballyBannedUsers).where(GloballyBannedUsers.user_id == user_id)
                )
                user = result.scalars().first()
                
                if user:
                    await session.delete(user)
                await __load_gbanned_userid_list()


def is_user_gbanned(user_id: int) -> bool:
    return user_id in GBANNED_LIST


async def get_gbanned_user(user_id: int) -> Optional[GloballyBannedUsers]:
    async with async_session() as session:
        result = await session.execute(
            select(GloballyBannedUsers).where(GloballyBannedUsers.user_id == user_id)
        )
        return result.scalars().first()


async def get_gban_list() -> list:
    async with async_session() as session:
        result = await session.execute(select(GloballyBannedUsers))
        return [x.to_dict() for x in result.scalars()]


async def enable_gbans(chat_id: Union[int, str]) -> None:
    async with GBAN_SETTING_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GbanSettings).where(GbanSettings.chat_id == str(chat_id))
                )
                chat = result.scalars().first()
                
                if not chat:
                    chat = GbanSettings(chat_id, True)
                
                chat.setting = True
                session.add(chat)
                if str(chat_id) in GBANSTAT_LIST:
                    GBANSTAT_LIST.remove(str(chat_id))


async def disable_gbans(chat_id: Union[int, str]) -> None:
    async with GBAN_SETTING_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GbanSettings).where(GbanSettings.chat_id == str(chat_id))
                )
                chat = result.scalars().first()
                
                if not chat:
                    chat = GbanSettings(chat_id, False)
                
                chat.setting = False
                session.add(chat)
                GBANSTAT_LIST.add(str(chat_id))


def does_chat_gban(chat_id: Union[int, str]) -> bool:
    return str(chat_id) not in GBANSTAT_LIST


def num_gbanned_users() -> int:
    return len(GBANNED_LIST)


async def __load_gbanned_userid_list() -> None:
    global GBANNED_LIST
    async with async_session() as session:
        result = await session.execute(select(GloballyBannedUsers))
        GBANNED_LIST = {x.user_id for x in result.scalars()}


async def __load_gban_stat_list() -> None:
    global GBANSTAT_LIST
    async with async_session() as session:
        result = await session.execute(select(GbanSettings))
        GBANSTAT_LIST = {x.chat_id for x in result.scalars() if not x.setting}


async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    async with GBAN_SETTING_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GbanSettings).where(GbanSettings.chat_id == str(old_chat_id))
                )
                chat = result.scalars().first()
                
                if chat:
                    chat.chat_id = str(new_chat_id)
                    session.add(chat)


# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize global bans system"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_gbanned_userid_list()
                await __load_gban_stat_list()
                _initialized = True
            except Exception as e:
                print(f"Global bans initialization failed: {e}")
                raise


# For backward compatibility - but should be called explicitly from main app
async def _startup():
    await initialize()


# Start initialization only if not being imported
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_startup())
        else:
            loop.run_until_complete(_startup())
    except RuntimeError:
        asyncio.run(_startup())
