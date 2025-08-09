import asyncio
from typing import Optional

from .db_connection import BASE, async_session, async_engine  # Add async_engine import
from sqlalchemy import Column, String, UnicodeText, distinct, func
from sqlalchemy.future import select
from sqlalchemy import update


class Rules(BASE):
    __tablename__ = "rules"
    chat_id = Column(String(14), primary_key=True)
    rules = Column(UnicodeText, default="")

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)

    def __repr__(self):
        return f"<Chat {self.chat_id} rules: {self.rules}>"


# Async lock replaces threading.RLock
INSERTION_LOCK = asyncio.Lock()


async def create_tables():
    """Initialize database tables using engine connection"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)


async def set_rules(chat_id: str, rules_text: str) -> None:
    async with INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Rules)
                    .where(Rules.chat_id == str(chat_id))
                )
                rules = result.scalars().first()
                if not rules:
                    rules = Rules(str(chat_id))
                rules.rules = rules_text
                session.add(rules)


async def get_rules(chat_id: str) -> str:
    async with async_session() as session:
        result = await session.execute(
            select(Rules)
            .where(Rules.chat_id == str(chat_id))
        )
        rules = result.scalars().first()
        return rules.rules if rules else ""


async def num_chats() -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(distinct(Rules.chat_id)))
        )
        return result.scalar() or 0


async def migrate_chat(old_chat_id: str, new_chat_id: str) -> None:
    async with INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Rules)
                    .where(Rules.chat_id == str(old_chat_id))
                )
                chat = result.scalars().first()
                if chat:
                    chat.chat_id = str(new_chat_id)
                    session.add(chat)


_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize rules system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                _initialized = True
            except Exception as e:
                print(f"Rules initialization failed: {e}")
                raise
