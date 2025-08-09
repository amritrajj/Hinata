# Note: chat_id's are stored as strings because the int is too large to be stored in a PSQL database.
import asyncio
from typing import List, Optional, Tuple

from Hina.modules.helper_funcs.msg_types import Types
from .db_connection import BASE, async_session, async_engine
from sqlalchemy import Boolean, Column, Integer, String, UnicodeText, distinct, func
from sqlalchemy.future import select
from sqlalchemy import delete


class Notes(BASE):
    __tablename__ = "notes"
    chat_id = Column(String(14), primary_key=True)
    name = Column(UnicodeText, primary_key=True)
    value = Column(UnicodeText, nullable=False)
    file = Column(UnicodeText)
    is_reply = Column(Boolean, default=False)
    has_buttons = Column(Boolean, default=False)
    msgtype = Column(Integer, default=Types.BUTTON_TEXT.value)

    def __init__(self, chat_id, name, value, msgtype, file=None):
        self.chat_id = str(chat_id)
        self.name = name
        self.value = value
        self.msgtype = msgtype
        self.file = file

    def __repr__(self):
        return "<Note %s>" % self.name


class Buttons(BASE):
    __tablename__ = "note_urls"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(14), primary_key=True)
    note_name = Column(UnicodeText, primary_key=True)
    name = Column(UnicodeText, nullable=False)
    url = Column(UnicodeText, nullable=False)
    same_line = Column(Boolean, default=False)

    def __init__(self, chat_id, note_name, name, url, same_line=False):
        self.chat_id = str(chat_id)
        self.note_name = note_name
        self.name = name
        self.url = url
        self.same_line = same_line


async def create_tables():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

NOTES_INSERTION_LOCK = asyncio.Lock()
BUTTONS_INSERTION_LOCK = asyncio.Lock()


async def add_note_to_db(chat_id, note_name, note_data, msgtype, buttons=None, file=None):
    if not buttons:
        buttons = []

    async with NOTES_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Check existing note
                result = await session.execute(
                    select(Notes)
                    .where(Notes.chat_id == str(chat_id))
                    .where(Notes.name == note_name)
                )
                prev = result.scalars().first()
                
                if prev:
                    async with BUTTONS_INSERTION_LOCK:
                        # Delete existing buttons
                        result = await session.execute(
                            select(Buttons)
                            .where(Buttons.chat_id == str(chat_id))
                            .where(Buttons.note_name == note_name)
                        )
                        for btn in result.scalars():
                            await session.delete(btn)
                    await session.delete(prev)
                
                # Add new note
                note = Notes(
                    str(chat_id),
                    note_name,
                    note_data or "",
                    msgtype=msgtype.value,
                    file=file,
                )
                session.add(note)

    # Add buttons
    for b_name, url, same_line in buttons:
        await add_note_button_to_db(chat_id, note_name, b_name, url, same_line)


async def get_note(chat_id, note_name):
    async with async_session() as session:
        result = await session.execute(
            select(Notes)
            .where(func.lower(Notes.name) == note_name.lower())
            .where(Notes.chat_id == str(chat_id))
        )
        return result.scalars().first()


async def rm_note(chat_id, note_name):
    async with NOTES_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Notes)
                    .where(func.lower(Notes.name) == note_name.lower())
                    .where(Notes.chat_id == str(chat_id))
                )
                note = result.scalars().first()
                
                if note:
                    async with BUTTONS_INSERTION_LOCK:
                        # Delete associated buttons
                        result = await session.execute(
                            select(Buttons)
                            .where(Buttons.chat_id == str(chat_id))
                            .where(Buttons.note_name == note_name)
                        )
                        for btn in result.scalars():
                            await session.delete(btn)
                    
                    await session.delete(note)
                    return True
                return False


async def get_all_chat_notes(chat_id):
    async with async_session() as session:
        result = await session.execute(
            select(Notes)
            .where(Notes.chat_id == str(chat_id))
            .order_by(Notes.name.asc())
        )
        return result.scalars().all()


async def add_note_button_to_db(chat_id, note_name, b_name, url, same_line):
    async with BUTTONS_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                button = Buttons(str(chat_id), note_name, b_name, url, same_line)
                session.add(button)


async def get_buttons(chat_id, note_name):
    async with async_session() as session:
        result = await session.execute(
            select(Buttons)
            .where(Buttons.chat_id == str(chat_id))
            .where(Buttons.note_name == note_name)
            .order_by(Buttons.id)
        )
        return result.scalars().all()


async def num_notes():
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Notes))
        return result.scalar()


async def num_chats():
    async with async_session() as session:
        result = await session.execute(select(func.count(distinct(Notes.chat_id))))
        return result.scalar()


async def migrate_chat(old_chat_id, new_chat_id):
    async with NOTES_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Migrate notes
                result = await session.execute(
                    select(Notes)
                    .where(Notes.chat_id == str(old_chat_id))
                )
                for note in result.scalars():
                    note.chat_id = str(new_chat_id)
                    session.add(note)

                # Migrate buttons
                async with BUTTONS_INSERTION_LOCK:
                    result = await session.execute(
                        select(Buttons)
                        .where(Buttons.chat_id == str(old_chat_id))
                    )
                    for btn in result.scalars():
                        btn.chat_id = str(new_chat_id)
                        session.add(btn)


# Improved initialization
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize notes system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                _initialized = True
            except Exception as e:
                print(f"Notes initialization failed: {e}")
                raise
