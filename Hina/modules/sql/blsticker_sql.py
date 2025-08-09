import asyncio
import time
from typing import Dict, Set, List, Tuple, Union

from .db_connection import BASE, async_session, async_engine
from sqlalchemy import Column, Integer, String, UnicodeText, distinct, func
from sqlalchemy.future import select
from sqlalchemy import update, delete


class StickersFilters(BASE):
    __tablename__ = "blacklist_stickers"
    __table_args__ = {'extend_existing': True}
    
    chat_id = Column(String(14), primary_key=True)
    trigger = Column(UnicodeText, primary_key=True, nullable=False)
    created_at = Column(Integer)

    def __init__(self, chat_id, trigger):
        self.chat_id = str(chat_id)
        self.trigger = trigger
        self.created_at = int(time.time())

    def __repr__(self):
        return f"<StickersFilter '{self.trigger}' for {self.chat_id}>"

    def __eq__(self, other):
        return bool(
            isinstance(other, StickersFilters)
            and self.chat_id == other.chat_id
            and self.trigger == other.trigger
        )


class StickerSettings(BASE):
    __tablename__ = "blsticker_settings"
    __table_args__ = {'extend_existing': True}
    
    chat_id = Column(String(14), primary_key=True)
    blacklist_type = Column(Integer, default=1)
    value = Column(UnicodeText, default="0")
    updated_at = Column(Integer)

    def __init__(self, chat_id, blacklist_type=1, value="0"):
        self.chat_id = str(chat_id)
        self.blacklist_type = blacklist_type
        self.value = value
        self.updated_at = int(time.time())

    def __repr__(self):
        return f"<StickerSettings {self.chat_id} type={self.blacklist_type}>"


# Async locks
STICKERS_FILTER_INSERTION_LOCK = asyncio.Lock()
STICKSET_FILTER_INSERTION_LOCK = asyncio.Lock()

# In-memory caches
CHAT_STICKERS: Dict[str, Set[str]] = {}
CHAT_BLSTICK_BLACKLISTS: Dict[str, Dict[str, Union[int, str]]] = {}


async def create_tables():
    """Initialize database tables using engine connection"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)


async def add_to_stickers(chat_id: Union[int, str], trigger: str) -> None:
    """Add a sticker to blacklist"""
    async with STICKERS_FILTER_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Update database
                stickers_filt = StickersFilters(chat_id, trigger)
                await session.merge(stickers_filt)
                
                # Update cache
                if str(chat_id) not in CHAT_STICKERS:
                    CHAT_STICKERS[str(chat_id)] = set()
                CHAT_STICKERS[str(chat_id)].add(trigger)


async def rm_from_stickers(chat_id: Union[int, str], trigger: str) -> bool:
    """Remove a sticker from blacklist"""
    async with STICKERS_FILTER_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Update database
                result = await session.execute(
                    delete(StickersFilters)
                    .where(StickersFilters.chat_id == str(chat_id))
                    .where(StickersFilters.trigger == trigger)
                )
                
                # Update cache
                if str(chat_id) in CHAT_STICKERS and trigger in CHAT_STICKERS[str(chat_id)]:
                    CHAT_STICKERS[str(chat_id)].remove(trigger)
                
                return result.rowcount > 0


async def get_chat_stickers(chat_id: Union[int, str]) -> Set[str]:
    """Get all blacklisted stickers for a chat"""
    return CHAT_STICKERS.get(str(chat_id), set())


async def num_stickers_filters() -> int:
    """Count all sticker filters"""
    async with async_session() as session:
        result = await session.execute(
            select(func.count()).select_from(StickersFilters)
        )
        return result.scalar() or 0


async def num_stickers_chat_filters(chat_id: Union[int, str]) -> int:
    """Count sticker filters in a chat"""
    async with async_session() as session:
        result = await session.execute(
            select(func.count())
            .where(StickersFilters.chat_id == str(chat_id))
        )
        return result.scalar() or 0


async def num_stickers_filter_chats() -> int:
    """Count chats with sticker filters"""
    async with async_session() as session:
        result = await session.execute(
            select(func.count(distinct(StickersFilters.chat_id)))
        )
        return result.scalar() or 0


async def set_blacklist_strength(
    chat_id: Union[int, str], 
    blacklist_type: int, 
    value: str
) -> None:
    """
    Set blacklist strength for a chat
    0 = nothing, 1 = delete, 2 = warn, 3 = mute, 
    4 = kick, 5 = ban, 6 = tban, 7 = tmute
    """
    async with STICKSET_FILTER_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Update database
                setting = await session.get(StickerSettings, str(chat_id))
                if not setting:
                    setting = StickerSettings(
                        chat_id,
                        blacklist_type=int(blacklist_type),
                        value=str(value)
                    )
                else:
                    setting.blacklist_type = int(blacklist_type)
                    setting.value = str(value)
                    setting.updated_at = int(time.time())
                
                session.add(setting)
                
                # Update cache
                CHAT_BLSTICK_BLACKLISTS[str(chat_id)] = {
                    "blacklist_type": int(blacklist_type),
                    "value": str(value)
                }


async def get_blacklist_setting(chat_id: Union[int, str]) -> Tuple[int, str]:
    """Get blacklist settings for a chat"""
    setting = CHAT_BLSTICK_BLACKLISTS.get(str(chat_id))
    if setting:
        return setting["blacklist_type"], setting["value"]
    return 1, "0"  # Default values


async def __load_CHAT_STICKERS() -> None:
    """Load sticker filters into memory"""
    global CHAT_STICKERS
    async with async_session() as session:
        # Get all unique chat_ids
        result = await session.execute(
            select(StickersFilters.chat_id).distinct()
        )
        CHAT_STICKERS = {chat_id: set() for (chat_id,) in result.all()}

        # Get all filters
        result = await session.execute(select(StickersFilters))
        for x in result.scalars():
            CHAT_STICKERS[x.chat_id].add(x.trigger)


async def __load_chat_stickerset_blacklists() -> None:
    """Load sticker settings into memory"""
    global CHAT_BLSTICK_BLACKLISTS
    async with async_session() as session:
        result = await session.execute(select(StickerSettings))
        CHAT_BLSTICK_BLACKLISTS = {
            x.chat_id: {
                "blacklist_type": x.blacklist_type,
                "value": x.value
            }
            for x in result.scalars()
        }


async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    """Migrate chat data to new chat ID"""
    async with STICKERS_FILTER_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Migrate sticker filters
                await session.execute(
                    update(StickersFilters)
                    .where(StickersFilters.chat_id == str(old_chat_id))
                    .values(chat_id=str(new_chat_id))
                )
                
                # Migrate settings
                await session.execute(
                    update(StickerSettings)
                    .where(StickerSettings.chat_id == str(old_chat_id))
                    .values(chat_id=str(new_chat_id))
                )
                
                # Update cache
                if str(old_chat_id) in CHAT_STICKERS:
                    CHAT_STICKERS[str(new_chat_id)] = CHAT_STICKERS.pop(str(old_chat_id))
                if str(old_chat_id) in CHAT_BLSTICK_BLACKLISTS:
                    CHAT_BLSTICK_BLACKLISTS[str(new_chat_id)] = CHAT_BLSTICK_BLACKLISTS.pop(str(old_chat_id))


# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize() -> None:
    """Initialize the sticker blacklist system"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_CHAT_STICKERS()
                await __load_chat_stickerset_blacklists()
                print("Sticker blacklist system initialized")
                _initialized = True
            except Exception as e:
                print(f"Sticker blacklist initialization failed: {e}")
                raise

