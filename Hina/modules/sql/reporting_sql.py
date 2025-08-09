import asyncio
from typing import Union

from .db_connection import BASE, async_session, async_engine
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.future import select


class ReportingUserSettings(BASE):
    __tablename__ = "user_report_settings"
    user_id = Column(Integer, primary_key=True)
    should_report = Column(Boolean, default=True)

    def __init__(self, user_id):
        self.user_id = user_id

    def __repr__(self):
        return f"<User report settings ({self.user_id})>"


class ReportingChatSettings(BASE):
    __tablename__ = "chat_report_settings"
    chat_id = Column(String(14), primary_key=True)
    should_report = Column(Boolean, default=True)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)

    def __repr__(self):
        return f"<Chat report settings ({self.chat_id})>"


# Async locks
CHAT_LOCK = asyncio.Lock()
USER_LOCK = asyncio.Lock()


async def create_tables():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)


async def chat_should_report(chat_id: Union[str, int]) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(ReportingChatSettings)
            .where(ReportingChatSettings.chat_id == str(chat_id))
        )
        chat_setting = result.scalars().first()
        return chat_setting.should_report if chat_setting else False


async def user_should_report(user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(ReportingUserSettings)
            .where(ReportingUserSettings.user_id == user_id)
        )
        user_setting = result.scalars().first()
        return user_setting.should_report if user_setting else True


async def set_chat_setting(chat_id: Union[int, str], setting: bool):
    async with CHAT_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ReportingChatSettings)
                    .where(ReportingChatSettings.chat_id == str(chat_id))
                )
                chat_setting = result.scalars().first()
                
                if not chat_setting:
                    chat_setting = ReportingChatSettings(chat_id)
                
                chat_setting.should_report = setting
                session.add(chat_setting)


async def set_user_setting(user_id: int, setting: bool):
    async with USER_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ReportingUserSettings)
                    .where(ReportingUserSettings.user_id == user_id)
                )
                user_setting = result.scalars().first()
                
                if not user_setting:
                    user_setting = ReportingUserSettings(user_id)
                
                user_setting.should_report = setting
                session.add(user_setting)


async def migrate_chat(old_chat_id, new_chat_id):
    async with CHAT_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ReportingChatSettings)
                    .where(ReportingChatSettings.chat_id == str(old_chat_id))
                )
                chat_notes = result.scalars().all()
                
                for note in chat_notes:
                    note.chat_id = str(new_chat_id)
                session.add_all(chat_notes)


# Improved initialization
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize reporting system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                _initialized = True
            except Exception as e:
                print(f"Reporting system initialization failed: {e}")
                raise
