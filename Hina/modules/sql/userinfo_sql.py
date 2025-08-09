import asyncio
import time
from typing import Optional, List, Union

from .db_connection import BASE, async_session, async_engine
from sqlalchemy import Column, Integer, UnicodeText
from sqlalchemy.future import select


class UserInfo(BASE):
    __tablename__ = "userinfo"
    __table_args__ = {'extend_existing': True}  # Prevent table redefinition
    
    user_id = Column(Integer, primary_key=True)
    info = Column(UnicodeText)
    last_updated = Column(Integer)  # Unix timestamp

    def __init__(self, user_id, info):
        self.user_id = user_id
        self.info = info
        self.last_updated = int(time.time())

    def __repr__(self):
        return f"<UserInfo {self.user_id}>"


class UserBio(BASE):
    __tablename__ = "userbio"
    __table_args__ = {'extend_existing': True}  # Prevent table redefinition
    
    user_id = Column(Integer, primary_key=True)
    bio = Column(UnicodeText)
    last_updated = Column(Integer)  # Unix timestamp

    def __init__(self, user_id, bio):
        self.user_id = user_id
        self.bio = bio
        self.last_updated = int(time.time())

    def __repr__(self):
        return f"<UserBio {self.user_id}>"


async def create_tables():
    """Initialize database tables using async engine"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)


# Async lock for write operations
INSERTION_LOCK = asyncio.Lock()


async def get_user_me_info(user_id: int) -> Optional[str]:
    """Get user info by user_id"""
    async with async_session() as session:
        result = await session.execute(
            select(UserInfo)
            .where(UserInfo.user_id == user_id)
        )
        userinfo = result.scalars().first()
        return userinfo.info if userinfo else None


async def set_user_me_info(user_id: int, info: str) -> None:
    """Set or update user info"""
    async with INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                userinfo = await session.get(UserInfo, user_id)
                if userinfo:
                    userinfo.info = info
                    userinfo.last_updated = int(time.time())
                else:
                    userinfo = UserInfo(user_id, info)
                session.add(userinfo)


async def get_user_bio(user_id: int) -> Optional[str]:
    """Get user bio by user_id"""
    async with async_session() as session:
        result = await session.execute(
            select(UserBio)
            .where(UserBio.user_id == user_id)
        )
        userbio = result.scalars().first()
        return userbio.bio if userbio else None


async def set_user_bio(user_id: int, bio: str) -> None:
    """Set or update user bio"""
    async with INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                userbio = await session.get(UserBio, user_id)
                if userbio:
                    userbio.bio = bio
                    userbio.last_updated = int(time.time())
                else:
                    userbio = UserBio(user_id, bio)
                session.add(userbio)


async def get_recently_updated_info(limit: int = 10) -> List[UserInfo]:
    """Get list of recently updated user info"""
    async with async_session() as session:
        result = await session.execute(
            select(UserInfo)
            .order_by(UserInfo.last_updated.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def get_recently_updated_bios(limit: int = 10) -> List[UserBio]:
    """Get list of recently updated bios"""
    async with async_session() as session:
        result = await session.execute(
            select(UserBio)
            .order_by(UserBio.last_updated.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    """Migrate chat data (placeholder)"""
    pass


async def init():
    """Initialize the module (must be called from main application)"""
    await create_tables()


# State tracking for initialization
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Safe initialization with state tracking"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await init()
                _initialized = True
            except Exception as e:
                print(f"UserInfo initialization failed: {e}")
                raise
