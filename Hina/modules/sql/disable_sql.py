import asyncio
from typing import Dict, Set, Union

from .db_connection import BASE, async_session, async_engine as engine
from sqlalchemy import Column, String, UnicodeText, distinct, func
from sqlalchemy.future import select
from sqlalchemy import delete, update


class Disable(BASE):
    __tablename__ = "disabled_commands"
    chat_id = Column(String(14), primary_key=True)
    command = Column(UnicodeText, primary_key=True)

    def __init__(self, chat_id, command):
        self.chat_id = str(chat_id)
        self.command = command

    def __repr__(self):
        return "Disabled cmd {} in {}".format(self.command, self.chat_id)


# Create tables if not exists
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

# Async lock replaces threading.Lock
DISABLE_INSERTION_LOCK = asyncio.Lock()

# In-memory cache
DISABLED: Dict[str, Set[str]] = {}


async def disable_command(chat_id: Union[int, str], disable: str) -> bool:
    async with DISABLE_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Disable)
                    .where(Disable.chat_id == str(chat_id))
                    .where(Disable.command == disable)
                )
                disabled = result.scalars().first()

                if not disabled:
                    if str(chat_id) not in DISABLED:
                        DISABLED[str(chat_id)] = set()
                    DISABLED[str(chat_id)].add(disable)

                    disabled = Disable(str(chat_id), disable)
                    session.add(disabled)
                    return True
                return False


async def enable_command(chat_id: Union[int, str], enable: str) -> bool:
    async with DISABLE_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Disable)
                    .where(Disable.chat_id == str(chat_id))
                    .where(Disable.command == enable)
                )
                disabled = result.scalars().first()

                if disabled:
                    if enable in DISABLED.get(str(chat_id), set()):
                        DISABLED[str(chat_id)].remove(enable)

                    await session.delete(disabled)
                    return True
                return False


async def is_command_disabled(chat_id: Union[int, str], cmd: str) -> bool:
    cmd = str(cmd).lower()
    return cmd in DISABLED.get(str(chat_id), set())


async def get_all_disabled(chat_id: Union[int, str]) -> Set[str]:
    return DISABLED.get(str(chat_id), set())


async def num_chats() -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(distinct(Disable.chat_id)))
        )
        return result.scalar() or 0


async def num_disabled() -> int:
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Disable))
        return result.scalar() or 0


async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    async with DISABLE_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Disable)
                    .where(Disable.chat_id == str(old_chat_id))
                )
                chats = result.scalars().all()
                
                for chat in chats:
                    chat.chat_id = str(new_chat_id)
                    session.add(chat)

                if str(old_chat_id) in DISABLED:
                    DISABLED[str(new_chat_id)] = DISABLED.pop(str(old_chat_id))


async def __load_disabled_commands() -> None:
    global DISABLED
    async with async_session() as session:
        result = await session.execute(select(Disable))
        for cmd in result.scalars():
            if cmd.chat_id not in DISABLED:
                DISABLED[cmd.chat_id] = set()
            DISABLED[cmd.chat_id].add(cmd.command)


async def init():
    """Initialize application components"""
    await create_tables()
    await __load_disabled_commands()
