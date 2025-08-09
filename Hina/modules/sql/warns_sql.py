import asyncio
import time
from typing import Dict, List, Optional, Tuple, Union

from .db_connection import BASE, async_session, async_engine
from sqlalchemy import Boolean, Column, Integer, String, UnicodeText, distinct, func
from sqlalchemy.future import select
from sqlalchemy.dialects import postgresql
from sqlalchemy import update, delete


class Warns(BASE):
    __tablename__ = "warns"
    __table_args__ = {'extend_existing': True}

    user_id = Column(Integer, primary_key=True)
    chat_id = Column(String(14), primary_key=True)
    num_warns = Column(Integer, default=0)
    reasons = Column(postgresql.ARRAY(UnicodeText))
    last_warned = Column(Integer)

    def __init__(self, user_id, chat_id):
        self.user_id = user_id
        self.chat_id = str(chat_id)
        self.num_warns = 0
        self.reasons = []
        self.last_warned = int(time.time())

    def __repr__(self):
        return f"<{self.num_warns} warns for {self.user_id} in {self.chat_id}>"


class WarnFilters(BASE):
    __tablename__ = "warn_filters"
    __table_args__ = {'extend_existing': True}

    chat_id = Column(String(14), primary_key=True)
    keyword = Column(UnicodeText, primary_key=True, nullable=False)
    reply = Column(UnicodeText, nullable=False)
    created_at = Column(Integer)

    def __init__(self, chat_id, keyword, reply):
        self.chat_id = str(chat_id)
        self.keyword = keyword
        self.reply = reply
        self.created_at = int(time.time())

    def __repr__(self):
        return f"<WarnFilter {self.keyword} in {self.chat_id}>"


class WarnSettings(BASE):
    __tablename__ = "warn_settings"
    __table_args__ = {'extend_existing': True}

    chat_id = Column(String(14), primary_key=True)
    warn_limit = Column(Integer, default=3)
    soft_warn = Column(Boolean, default=False)
    updated_at = Column(Integer)

    def __init__(self, chat_id, warn_limit=3, soft_warn=False):
        self.chat_id = str(chat_id)
        self.warn_limit = warn_limit
        self.soft_warn = soft_warn
        self.updated_at = int(time.time())

    def __repr__(self):
        return f"<WarnSettings {self.chat_id} limit={self.warn_limit}>"


# Async locks
WARN_INSERTION_LOCK = asyncio.Lock()
WARN_FILTER_INSERTION_LOCK = asyncio.Lock()
WARN_SETTINGS_LOCK = asyncio.Lock()

# In-memory cache
WARN_FILTERS: Dict[str, List[str]] = {}


async def create_tables():
    """Initialize database tables using engine connection"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)


async def warn_user(user_id: int, chat_id: Union[int, str], reason: Optional[str] = None) -> Tuple[int, List[str]]:
    async with WARN_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                warned_user = await session.get(Warns, (user_id, str(chat_id)))
                if not warned_user:
                    warned_user = Warns(user_id, chat_id)
                    session.add(warned_user)

                warned_user.num_warns += 1
                warned_user.last_warned = int(time.time())
                if reason:
                    warned_user.reasons = [*warned_user.reasons, reason]

                return warned_user.num_warns, warned_user.reasons


async def remove_warn(user_id: int, chat_id: Union[int, str]) -> bool:
    async with WARN_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                warned_user = await session.get(Warns, (user_id, str(chat_id)))
                if warned_user and warned_user.num_warns > 0:
                    warned_user.num_warns -= 1
                    warned_user.reasons = warned_user.reasons[:-1]
                    return True
                return False


async def reset_warns(user_id: int, chat_id: Union[int, str]) -> None:
    async with WARN_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                warned_user = await session.get(Warns, (user_id, str(chat_id)))
                if warned_user:
                    warned_user.num_warns = 0
                    warned_user.reasons = []


async def get_warns(user_id: int, chat_id: Union[int, str]) -> Optional[Tuple[int, List[str]]]:
    async with async_session() as session:
        warned_user = await session.get(Warns, (user_id, str(chat_id)))
        if warned_user:
            return warned_user.num_warns, warned_user.reasons
        return None


async def add_warn_filter(chat_id: Union[int, str], keyword: str, reply: str) -> None:
    async with WARN_FILTER_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Update cache
                if str(chat_id) not in WARN_FILTERS:
                    WARN_FILTERS[str(chat_id)] = []
                
                if keyword not in WARN_FILTERS[str(chat_id)]:
                    WARN_FILTERS[str(chat_id)].append(keyword)
                    WARN_FILTERS[str(chat_id)].sort(key=lambda x: (-len(x), x))

                # Update database
                warn_filt = WarnFilters(chat_id, keyword, reply)
                await session.merge(warn_filt)


async def remove_warn_filter(chat_id: Union[int, str], keyword: str) -> bool:
    async with WARN_FILTER_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Update cache
                if keyword in WARN_FILTERS.get(str(chat_id), []):
                    WARN_FILTERS[str(chat_id)].remove(keyword)

                # Update database
                result = await session.execute(
                    delete(WarnFilters)
                    .where(WarnFilters.chat_id == str(chat_id))
                    .where(WarnFilters.keyword == keyword)
                )
                return result.rowcount > 0


async def get_chat_warn_triggers(chat_id: Union[int, str]) -> List[str]:
    return WARN_FILTERS.get(str(chat_id), [])


async def get_chat_warn_filters(chat_id: Union[int, str]) -> List[WarnFilters]:
    async with async_session() as session:
        result = await session.execute(
            select(WarnFilters)
            .where(WarnFilters.chat_id == str(chat_id))
        )
        return result.scalars().all()


async def get_warn_filter(chat_id: Union[int, str], keyword: str) -> Optional[WarnFilters]:
    async with async_session() as session:
        return await session.get(WarnFilters, (str(chat_id), keyword))


async def set_warn_limit(chat_id: Union[int, str], warn_limit: int) -> None:
    async with WARN_SETTINGS_LOCK:
        async with async_session() as session:
            async with session.begin():
                setting = await session.get(WarnSettings, str(chat_id))
                if not setting:
                    setting = WarnSettings(chat_id, warn_limit=warn_limit)
                else:
                    setting.warn_limit = warn_limit
                    setting.updated_at = int(time.time())
                
                session.add(setting)


async def set_warn_strength(chat_id: Union[int, str], soft_warn: bool) -> None:
    async with WARN_SETTINGS_LOCK:
        async with async_session() as session:
            async with session.begin():
                setting = await session.get(WarnSettings, str(chat_id))
                if not setting:
                    setting = WarnSettings(chat_id, soft_warn=soft_warn)
                else:
                    setting.soft_warn = soft_warn
                    setting.updated_at = int(time.time())
                
                session.add(setting)


async def get_warn_setting(chat_id: Union[int, str]) -> Tuple[int, bool]:
    async with async_session() as session:
        setting = await session.get(WarnSettings, str(chat_id))
        if setting:
            return setting.warn_limit, setting.soft_warn
        return 3, False  # Default values


async def num_warns() -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.coalesce(func.sum(Warns.num_warns), 0))
        )
        return result.scalar() or 0


async def num_warn_chats() -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(distinct(Warns.chat_id)))
        )
        return result.scalar()


async def num_warn_filters() -> int:
    async with async_session() as session:
        result = await session.execute(select(func.count(WarnFilters.keyword)))
        return result.scalar()


async def num_warn_chat_filters(chat_id: Union[int, str]) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(WarnFilters.keyword))
            .where(WarnFilters.chat_id == str(chat_id))
        )
        return result.scalar()


async def num_warn_filter_chats() -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(distinct(WarnFilters.chat_id)))
        )
        return result.scalar()


async def __load_chat_warn_filters() -> None:
    global WARN_FILTERS
    async with async_session() as session:
        # Get all unique chat_ids
        result = await session.execute(
            select(WarnFilters.chat_id).distinct()
        )
        for (chat_id,) in result.all():
            WARN_FILTERS[chat_id] = []

        # Get all filters
        result = await session.execute(select(WarnFilters))
        for x in result.scalars().all():
            WARN_FILTERS[x.chat_id].append(x.keyword)

        # Sort all filters
        WARN_FILTERS = {
            chat_id: sorted(set(keywords), key=lambda x: (-len(x), x))
            for chat_id, keywords in WARN_FILTERS.items()
        }


async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    # Warns migration
    async with WARN_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    update(Warns)
                    .where(Warns.chat_id == str(old_chat_id))
                    .values(chat_id=str(new_chat_id))
                )

    # Warn filters migration
    async with WARN_FILTER_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    update(WarnFilters)
                    .where(WarnFilters.chat_id == str(old_chat_id))
                    .values(chat_id=str(new_chat_id))
                )

                # Update cache
                if str(old_chat_id) in WARN_FILTERS:
                    WARN_FILTERS[str(new_chat_id)] = WARN_FILTERS[str(old_chat_id)]
                    del WARN_FILTERS[str(old_chat_id)]

    # Warn settings migration
    async with WARN_SETTINGS_LOCK:
        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    update(WarnSettings)
                    .where(WarnSettings.chat_id == str(old_chat_id))
                    .values(chat_id=str(new_chat_id))
                )


# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize() -> None:
    """Initialize the warns system"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_chat_warn_filters()
                _initialized = True
            except Exception as e:
                print(f"Warns initialization failed: {e}")
                raise


