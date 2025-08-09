import asyncio
from typing import Set, Optional, List

from sqlalchemy import Column, String, UnicodeText, Integer
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from .db_connection import BASE, async_session, session_scope

class BlacklistUsers(BASE):
    __tablename__ = "blacklistusers"
    __table_args__ = {'extend_existing': True}  # Prevent table redefinition issues
    
    user_id = Column(String(14), primary_key=True)
    reason = Column(UnicodeText)
    date_added = Column(Integer)  # Optional: timestamp of when user was blacklisted

    def __init__(self, user_id, reason=None, date_added=None):
        self.user_id = user_id
        self.reason = reason
        self.date_added = date_added

    def __repr__(self):
        return f"<BlacklistedUser {self.user_id}>"

# Removed manual table creation - let initialize_db() handle it
BLACKLIST_LOCK = asyncio.Lock()
BLACKLIST_USERS: Set[int] = set()

async def blacklist_user(user_id: str, reason: Optional[str] = None) -> bool:
    """Blacklist a user with optional reason. Returns True if successful."""
    async with BLACKLIST_LOCK:
        try:
            async with session_scope() as session:
                # Using merge instead of separate select for better performance
                user = BlacklistUsers(
                    user_id=str(user_id),
                    reason=reason,
                    date_added=int(time.time())  # Optional timestamp
                )
                await session.merge(user)
                await session.commit()
                await __load_blacklist_userid_list()
                return True
        except SQLAlchemyError as e:
            print(f"Error blacklisting user {user_id}: {e}")
            await session.rollback()
            return False

async def unblacklist_user(user_id: str) -> bool:
    """Remove user from blacklist. Returns True if successful."""
    async with BLACKLIST_LOCK:
        try:
            async with session_scope() as session:
                result = await session.execute(
                    delete(BlacklistUsers)
                    .where(BlacklistUsers.user_id == str(user_id))
                    .returning(BlacklistUsers.user_id)
                )
                if result.rowcount > 0:
                    await session.commit()
                    await __load_blacklist_userid_list()
                    return True
                return False
        except SQLAlchemyError as e:
            print(f"Error unblacklisting user {user_id}: {e}")
            await session.rollback()
            return False

async def get_blacklist_reason(user_id: str) -> Optional[str]:
    """Get blacklist reason for user. Returns None if user not found."""
    try:
        async with session_scope() as session:
            result = await session.execute(
                select(BlacklistUsers.reason)
                .where(BlacklistUsers.user_id == str(user_id))
            )
            return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        print(f"Error getting blacklist reason for {user_id}: {e}")
        return None

async def get_all_blacklisted() -> List[BlacklistUsers]:
    """Get all blacklisted users with their details"""
    try:
        async with session_scope() as session:
            result = await session.execute(
                select(BlacklistUsers)
                .order_by(BlacklistUsers.date_added.desc())  # Optional sorting
            )
            return result.scalars().all()
    except SQLAlchemyError as e:
        print(f"Error getting all blacklisted users: {e}")
        return []

def is_user_blacklisted(user_id: int) -> bool:
    """Check if user is blacklisted (uses cache)"""
    return user_id in BLACKLIST_USERS

async def __load_blacklist_userid_list() -> None:
    """Load blacklisted user IDs into memory"""
    global BLACKLIST_USERS
    try:
        async with session_scope() as session:
            result = await session.execute(
                select(BlacklistUsers.user_id)
            )
            BLACKLIST_USERS = {int(x[0]) for x in result.all()}
    except SQLAlchemyError as e:
        print(f"Error loading blacklist: {e}")
        BLACKLIST_USERS = set()

async def blacklist_init() -> None:
    """Initialize blacklist system"""
    try:
        await __load_blacklist_userid_list()
        print(f"Loaded {len(BLACKLIST_USERS)} blacklisted users")
    except Exception as e:
        print(f"Blacklist initialization failed: {e}")
        raise

# Improved initialization handling
async def initialize():
    """Initialize the blacklist system"""
    await blacklist_init()

# Start initialization (modern approach)
if __name__ != "__main__":
    # When imported as module - ensure we're in an async context
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(initialize())
    except RuntimeError:
        # No running event loop - store for later initialization
        _pending_init = initialize()
else:
    # For testing when run directly
    async def main():
        await initialize()
        # Test code here

    asyncio.run(main())
