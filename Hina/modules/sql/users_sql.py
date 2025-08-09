import asyncio
from contextlib import asynccontextmanager
import time
from typing import Dict, List, Optional, Set, Union

from .db_connection import BASE, async_session, async_engine
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    UnicodeText,
    UniqueConstraint,
    func,
    select,
    delete,
    update
)
from sqlalchemy.future import select
from sqlalchemy.orm import relationship, selectinload


class Users(BASE):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    username = Column(UnicodeText)

    # New fields (optional but recommended)
    first_name = Column(UnicodeText)
    last_name = Column(UnicodeText)
    last_updated = Column(Integer)

    def __init__(self, user_id, username=None):
        self.user_id = user_id
        self.username = username
        # Initialize new fields
        self.last_updated = int(time.time())

    def __repr__(self):
        return "<User {} ({})>".format(self.username, self.user_id)


class Chats(BASE):
    __tablename__ = "chats"
    chat_id = Column(String(14), primary_key=True)
    chat_name = Column(UnicodeText, nullable=False)

    # New field (optional but recommended)
    chat_type = Column(String(50))

    def __init__(self, chat_id, chat_name):
        self.chat_id = str(chat_id)
        self.chat_name = chat_name

    def __repr__(self):
        return "<Chat {} ({})>".format(self.chat_name, self.chat_id)


class ChatMembers(BASE):
    __tablename__ = "chat_members"
    priv_chat_id = Column(Integer, primary_key=True)
    chat = Column(
        String(14),
        ForeignKey("chats.chat_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    user = Column(
        Integer,
        ForeignKey("users.user_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    __table_args__ = (UniqueConstraint("chat", "user", name="_chat_members_uc"),)

    # New field (optional but recommended)
    joined_date = Column(Integer)

    def __init__(self, chat, user):
        self.chat = chat
        self.user = user
        # Initialize new field
        self.joined_date = int(time.time())

    def __repr__(self):
        return "<Chat user {} ({}) in chat {} ({})>".format(
            self.user.username,
            self.user.user_id,
            self.chat.chat_name,
            self.chat.chat_id,
        )


# Original lock remains unchanged
INSERTION_LOCK = asyncio.Lock()


# Original table creation remains unchanged
# Change the create_tables function to use the engine directly
async def create_tables():
    """Initialize database tables"""
    from .db_connection import async_engine  # Import the engine
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

# Original session scope remains unchanged
@asynccontextmanager
async def session_scope():
    """Provide transactional scope around operations."""
    session = async_session()
    try:
        yield session
        await session.commit()
    except:
        await session.rollback()
        raise
    finally:
        await session.close()


# Original functions remain exactly the same (no changes to signatures or behavior)

async def ensure_bot_in_db(bot):
    async with INSERTION_LOCK:
        async with session_scope() as session:
            bot_user = Users(bot.id, bot.username)
            await session.merge(bot_user)


async def update_user(user_id, username, chat_id=None, chat_name=None):
    async with INSERTION_LOCK:
        async with session_scope() as session:
            # Get or create user
            result = await session.execute(select(Users).where(Users.user_id == user_id))
            user = result.scalars().first()
            if not user:
                user = Users(user_id, username)
                session.add(user)
            else:
                user.username = username
                user.last_updated = int(time.time())  # Update timestamp

            if not chat_id or not chat_name:
                return

            # Get or create chat
            result = await session.execute(select(Chats).where(Chats.chat_id == str(chat_id)))
            chat = result.scalars().first()
            if not chat:
                chat = Chats(str(chat_id), chat_name)
                session.add(chat)

            # Check membership
            result = await session.execute(
                select(ChatMembers)
                .where(ChatMembers.chat == str(chat_id))
                .where(ChatMembers.user == user_id))
            if not result.scalars().first():
                session.add(ChatMembers(str(chat_id), user_id))


async def get_userid_by_name(username):
    async with async_session() as session:
        result = await session.execute(
            select(Users)
            .where(func.lower(Users.username) == username.lower())
        )
        return result.scalars().all()


async def get_name_by_userid(user_id):
    async with async_session() as session:
        result = await session.execute(
            select(Users)
            .where(Users.user_id == int(user_id))
        )
        return result.scalars().first()


async def get_chat_members(chat_id):
    async with async_session() as session:
        result = await session.execute(
            select(ChatMembers)
            .where(ChatMembers.chat == str(chat_id))
        )
        return result.scalars().all()


async def get_all_chats():
    async with async_session() as session:
        result = await session.execute(select(Chats))
        return result.scalars().all()


async def get_all_users():
    async with async_session() as session:
        result = await session.execute(select(Users))
        return result.scalars().all()


async def get_user_num_chats(user_id):
    async with async_session() as session:
        result = await session.execute(
            select(func.count(ChatMembers.priv_chat_id))
            .where(ChatMembers.user == int(user_id))
        )
        return result.scalar()


async def get_user_com_chats(user_id):
    async with async_session() as session:
        result = await session.execute(
            select(ChatMembers)
            .where(ChatMembers.user == int(user_id))
        )
        return [row.chat for row in result.scalars().all()]


async def num_chats():
    async with async_session() as session:
        result = await session.execute(select(func.count(Chats.chat_id)))
        return result.scalar()


async def num_users():
    async with async_session() as session:
        result = await session.execute(select(func.count(Users.user_id)))
        return result.scalar()


async def migrate_chat(old_chat_id, new_chat_id):
    async with INSERTION_LOCK:
        async with session_scope() as session:
            # Update chat
            result = await session.execute(select(Chats).where(Chats.chat_id == str(old_chat_id)))
            chat = result.scalars().first()
            if chat:
                chat.chat_id = str(new_chat_id)

            # Update members
            await session.execute(
                update(ChatMembers)
                .where(ChatMembers.chat == str(old_chat_id))
                .values(chat=str(new_chat_id))
            )


async def del_user(user_id):
    async with INSERTION_LOCK:
        async with session_scope() as session:
            # Delete user
            result = await session.execute(select(Users).where(Users.user_id == user_id))
            user = result.scalars().first()
            if user:
                await session.delete(user)
                return True

            # Delete chat memberships
            await session.execute(
                delete(ChatMembers)
                .where(ChatMembers.user == user_id)
            )
            return False


async def rem_chat(chat_id):
    async with INSERTION_LOCK:
        async with session_scope() as session:
            result = await session.execute(select(Chats).where(Chats.chat_id == str(chat_id)))
            chat = result.scalars().first()
            if chat:
                await session.delete(chat)
                return True
            return False


# New functions (added without removing anything)
async def get_active_users(days: int = 30) -> List[Users]:
    """Get users active in last X days (new addition)"""
    cutoff = int(time.time()) - (days * 86400)
    async with async_session() as session:
        result = await session.execute(
            select(Users)
            .where(Users.last_updated >= cutoff)
            .order_by(Users.last_updated.desc())
        )
        return result.scalars().all()


# At the bottom of users_sql.py, replace the initialization code with:

_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize database"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                _initialized = True
            except Exception as e:
                print(f"Initialization failed: {e}")
                raise

def start_initialization():
    """Handle initialization without causing event loop conflicts"""
    try:
        # Try to get the existing loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule the initialization
            asyncio.create_task(initialize())
        else:
            # If loop exists but isn't running
            loop.run_until_complete(initialize())
    except RuntimeError:
        # No event loop exists, create a new one
        asyncio.run(initialize())

# Don't auto-initialize on import - let the main application handle it
# Remove the start_initialization() call here
