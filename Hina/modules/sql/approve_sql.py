import asyncio
from typing import List, Optional, Union

from .db_connection import BASE, async_session, async_engine  # Add async_engine import
from sqlalchemy import Column, String, Integer
from sqlalchemy.future import select
from sqlalchemy import delete


class Approvals(BASE):
    __tablename__ = "approval"
    chat_id = Column(String(14), primary_key=True)
    user_id = Column(Integer, primary_key=True)

    def __init__(self, chat_id, user_id):
        self.chat_id = str(chat_id)  # ensure string
        self.user_id = user_id

    def __repr__(self):
        return f"<Approve {self.user_id}>"


# Create tables if not exists - FIXED
async def create_tables():
    """Initialize database tables using engine connection"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

# Async lock replaces threading.Lock
APPROVE_INSERTION_LOCK = asyncio.Lock()

async def approve(chat_id: Union[int, str], user_id: int) -> None:
    async with APPROVE_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                # Check if already approved
                result = await session.execute(
                    select(Approvals)
                    .where(Approvals.chat_id == str(chat_id))
                    .where(Approvals.user_id == user_id)
                )
                if not result.scalars().first():
                    approve_user = Approvals(str(chat_id), user_id)
                    session.add(approve_user)


async def is_approved(chat_id: Union[int, str], user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Approvals)
            .where(Approvals.chat_id == str(chat_id))
            .where(Approvals.user_id == user_id)
        )
        return bool(result.scalars().first())


async def disapprove(chat_id: Union[int, str], user_id: int) -> bool:
    async with APPROVE_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Approvals)
                    .where(Approvals.chat_id == str(chat_id))
                    .where(Approvals.user_id == user_id)
                )
                disapprove_user = result.scalars().first()
                if disapprove_user:
                    await session.delete(disapprove_user)
                    return True
                return False


async def list_approved(chat_id: Union[int, str]) -> List[Approvals]:
    async with async_session() as session:
        result = await session.execute(
            select(Approvals)
            .where(Approvals.chat_id == str(chat_id))
            .order_by(Approvals.user_id.asc())
        )
        return result.scalars().all()


async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    async with APPROVE_INSERTION_LOCK:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Approvals)
                    .where(Approvals.chat_id == str(old_chat_id))
                )
                for approval in result.scalars():
                    approval.chat_id = str(new_chat_id)
                    session.add(approval)



# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize approval system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                _initialized = True
            except Exception as e:
                print(f"Approval system initialization failed: {e}")
                raise
