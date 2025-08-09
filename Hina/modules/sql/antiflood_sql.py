import asyncio
from typing import Dict, Tuple, Optional, Union

from .db_connection import BASE, async_session, async_engine  # Add async_engine import
from sqlalchemy import String, Column, Integer, UnicodeText
from sqlalchemy.future import select
from sqlalchemy import update, delete

DEF_COUNT = 1
DEF_LIMIT = 0
DEF_OBJ = (None, DEF_COUNT, DEF_LIMIT)

class FloodControl(BASE):
    __tablename__ = "antiflood"
    chat_id = Column(String(14), primary_key=True)
    user_id = Column(Integer)
    count = Column(Integer, default=DEF_COUNT)
    limit = Column(Integer, default=DEF_LIMIT)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)

    def __repr__(self):
        return f"<flood control for {self.chat_id}>"

class FloodSettings(BASE):
    __tablename__ = "antiflood_settings"
    chat_id = Column(String(14), primary_key=True)
    flood_type = Column(Integer, default=1)
    value = Column(UnicodeText, default="0")

    def __init__(self, chat_id, flood_type=1, value="0"):
        self.chat_id = str(chat_id)
        self.flood_type = flood_type
        self.value = value

    def __repr__(self):
        return f"<{self.chat_id} will execute {self.flood_type} for flood>"

# Async locks
INSERTION_FLOOD_LOCK = asyncio.Lock()
INSERTION_FLOOD_SETTINGS_LOCK = asyncio.Lock()

# In-memory cache
CHAT_FLOOD: Dict[str, Tuple[Optional[int], int, int]] = {}

async def create_tables():
    """Initialize database tables using engine connection"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

async def set_flood(chat_id: Union[int, str], amount: int) -> None:
    async with INSERTION_FLOOD_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(FloodControl)
                    .where(FloodControl.chat_id == str(chat_id))
                )
                flood = result.scalars().first()
                
                if not flood:
                    flood = FloodControl(str(chat_id))

                flood.user_id = None
                flood.limit = amount
                CHAT_FLOOD[str(chat_id)] = (None, DEF_COUNT, amount)
                session.add(flood)

async def update_flood(chat_id: Union[int, str], user_id: int) -> bool:
    if str(chat_id) not in CHAT_FLOOD:
        return False

    curr_user_id, count, limit = CHAT_FLOOD.get(str(chat_id), DEF_OBJ)

    if limit == 0:  # no antiflood
        return False

    if user_id != curr_user_id or user_id is None:  # other user
        CHAT_FLOOD[str(chat_id)] = (user_id, DEF_COUNT, limit)
        return False

    count += 1
    if count > limit:  # too many msgs, kick
        CHAT_FLOOD[str(chat_id)] = (None, DEF_COUNT, limit)
        return True

    # default -> update
    CHAT_FLOOD[str(chat_id)] = (user_id, count, limit)
    return False

async def get_flood_limit(chat_id: Union[int, str]) -> int:
    return CHAT_FLOOD.get(str(chat_id), DEF_OBJ)[2]

async def set_flood_strength(chat_id: Union[int, str], flood_type: int, value: str) -> None:
    # flood_type:
    # 1 = ban
    # 2 = kick
    # 3 = mute
    # 4 = tban
    # 5 = tmute
    async with INSERTION_FLOOD_SETTINGS_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(FloodSettings)
                    .where(FloodSettings.chat_id == str(chat_id))
                )
                curr_setting = result.scalars().first()
                
                if not curr_setting:
                    curr_setting = FloodSettings(
                        str(chat_id),
                        flood_type=int(flood_type),
                        value=value,
                    )

                curr_setting.flood_type = int(flood_type)
                curr_setting.value = str(value)
                session.add(curr_setting)

async def get_flood_setting(chat_id: Union[int, str]) -> Tuple[int, str]:
    async with async_session() as session:
        result = await session.execute(
            select(FloodSettings)
            .where(FloodSettings.chat_id == str(chat_id))
        )
        setting = result.scalars().first()
        if setting:
            return setting.flood_type, setting.value
        return 1, "0"

async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    async with INSERTION_FLOOD_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Migrate FloodControl
                result = await session.execute(
                    select(FloodControl)
                    .where(FloodControl.chat_id == str(old_chat_id))
                )
                flood = result.scalars().first()
                
                if flood:
                    CHAT_FLOOD[str(new_chat_id)] = CHAT_FLOOD.get(str(old_chat_id), DEF_OBJ)
                    flood.chat_id = str(new_chat_id)
                    session.add(flood)

                # Migrate FloodSettings
                result = await session.execute(
                    select(FloodSettings)
                    .where(FloodSettings.chat_id == str(old_chat_id))
                )
                setting = result.scalars().first()
                
                if setting:
                    setting.chat_id = str(new_chat_id)
                    session.add(setting)


async def __load_flood_settings() -> None:
    global CHAT_FLOOD
    async with async_session() as session:
        result = await session.execute(select(FloodControl))
        CHAT_FLOOD = {
            chat.chat_id: (None, DEF_COUNT, chat.limit)
            for chat in result.scalars()
        }

# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize antiflood system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_flood_settings()
                _initialized = True
            except Exception as e:
                print(f"Antiflood initialization failed: {e}")
                raise
