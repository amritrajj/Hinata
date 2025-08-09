import asyncio
import time
from typing import Dict, Set, Tuple, Optional, Union

from sqlalchemy import Boolean, Column, Integer, UnicodeText
from sqlalchemy.future import select
from sqlalchemy import update, delete

from .db_connection import BASE, async_session, async_engine

class CleanerBlueTextChatSettings(BASE):
    __tablename__ = "cleaner_bluetext_chat_setting"
    __table_args__ = {'extend_existing': True}
    
    chat_id = Column(UnicodeText, primary_key=True)
    is_enable = Column(Boolean, default=False)
    updated_at = Column(Integer)

    def __init__(self, chat_id, is_enable):
        self.chat_id = str(chat_id)
        self.is_enable = is_enable
        self.updated_at = int(time.time())

    def __repr__(self):
        return f"<CleanerSetting {self.chat_id} ({self.is_enable})>"

class CleanerBlueTextChat(BASE):
    __tablename__ = "cleaner_bluetext_chat_ignore_commands"
    __table_args__ = {'extend_existing': True}
    
    chat_id = Column(UnicodeText, primary_key=True)
    command = Column(UnicodeText, primary_key=True)
    created_at = Column(Integer)

    def __init__(self, chat_id, command):
        self.chat_id = str(chat_id)
        self.command = command.lower()
        self.created_at = int(time.time())

    def __repr__(self):
        return f"<ChatIgnore {self.command} in {self.chat_id}>"

class CleanerBlueTextGlobal(BASE):
    __tablename__ = "cleaner_bluetext_global_ignore_commands"
    __table_args__ = {'extend_existing': True}
    
    command = Column(UnicodeText, primary_key=True)
    created_at = Column(Integer)

    def __init__(self, command):
        self.command = command.lower()
        self.created_at = int(time.time())

    def __repr__(self):
        return f"<GlobalIgnore {self.command}>"

# Async locks
CLEANER_CHAT_SETTINGS_LOCK = asyncio.Lock()
CLEANER_CHAT_LOCK = asyncio.Lock()
CLEANER_GLOBAL_LOCK = asyncio.Lock()

# In-memory caches
CLEANER_CHATS: Dict[str, Dict[str, object]] = {}
GLOBAL_IGNORE_COMMANDS: Set[str] = set()

async def create_tables():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

async def set_cleanbt(chat_id: Union[int, str], is_enable: bool) -> None:
    """Enable/disable cleaner for a chat"""
    async with CLEANER_CHAT_SETTINGS_LOCK:
        async with async_session() as session:
            async with session.begin():
                existing = await session.get(CleanerBlueTextChatSettings, str(chat_id))
                if existing:
                    await session.delete(existing)
                
                new_setting = CleanerBlueTextChatSettings(str(chat_id), is_enable)
                session.add(new_setting)
                
                # Update cache
                if str(chat_id) not in CLEANER_CHATS:
                    CLEANER_CHATS[str(chat_id)] = {"setting": is_enable, "commands": set()}
                CLEANER_CHATS[str(chat_id)]["setting"] = is_enable

async def chat_ignore_command(chat_id: Union[int, str], command: str) -> bool:
    """Add command to chat's ignore list"""
    command = command.lower()
    async with CLEANER_CHAT_LOCK:
        async with async_session() as session:
            async with session.begin():
                existing = await session.get(CleanerBlueTextChat, (str(chat_id), command))
                if not existing:
                    # Update cache
                    if str(chat_id) not in CLEANER_CHATS:
                        CLEANER_CHATS[str(chat_id)] = {"setting": False, "commands": set()}
                    CLEANER_CHATS[str(chat_id)]["commands"].add(command)
                    
                    # Add to database
                    new_ignore = CleanerBlueTextChat(str(chat_id), command)
                    session.add(new_ignore)
                    return True
                return False

async def chat_unignore_command(chat_id: Union[int, str], command: str) -> bool:
    """Remove command from chat's ignore list"""
    command = command.lower()
    async with CLEANER_CHAT_LOCK:
        async with async_session() as session:
            async with session.begin():
                existing = await session.get(CleanerBlueTextChat, (str(chat_id), command))
                if existing:
                    # Update cache
                    if str(chat_id) in CLEANER_CHATS and command in CLEANER_CHATS[str(chat_id)]["commands"]:
                        CLEANER_CHATS[str(chat_id)]["commands"].remove(command)
                    
                    # Remove from database
                    await session.delete(existing)
                    return True
                return False

async def global_ignore_command(command: str) -> bool:
    """Add command to global ignore list"""
    command = command.lower()
    async with CLEANER_GLOBAL_LOCK:
        async with async_session() as session:
            async with session.begin():
                existing = await session.get(CleanerBlueTextGlobal, command)
                if not existing:
                    # Update cache
                    GLOBAL_IGNORE_COMMANDS.add(command)
                    
                    # Add to database
                    new_ignore = CleanerBlueTextGlobal(command)
                    session.add(new_ignore)
                    return True
                return False

async def global_unignore_command(command: str) -> bool:
    """Remove command from global ignore list"""
    command = command.lower()
    async with CLEANER_GLOBAL_LOCK:
        async with async_session() as session:
            async with session.begin():
                existing = await session.get(CleanerBlueTextGlobal, command)
                if existing:
                    # Update cache
                    if command in GLOBAL_IGNORE_COMMANDS:
                        GLOBAL_IGNORE_COMMANDS.remove(command)
                    
                    # Remove from database
                    await session.delete(existing)
                    return True
                return False

def is_command_ignored(chat_id: Union[int, str], command: str) -> bool:
    """Check if command is ignored (uses cache)"""
    command = command.lower()
    if command in GLOBAL_IGNORE_COMMANDS:
        return True
    if str(chat_id) in CLEANER_CHATS:
        return command in CLEANER_CHATS[str(chat_id)]["commands"]
    return False

async def is_enabled(chat_id: Union[int, str]) -> bool:
    """Check if cleaner is enabled for chat"""
    if str(chat_id) in CLEANER_CHATS:
        return CLEANER_CHATS[str(chat_id)]["setting"]
    
    async with async_session() as session:
        setting = await session.get(CleanerBlueTextChatSettings, str(chat_id))
        if setting:
            CLEANER_CHATS[str(chat_id)] = {
                "setting": setting.is_enable,
                "commands": set()
            }
            return setting.is_enable
        return False

def get_all_ignored(chat_id: Union[int, str]) -> Tuple[Set[str], Set[str]]:
    """Get all ignored commands (global and local)"""
    local_commands = (
        CLEANER_CHATS.get(str(chat_id), {}).get("commands", set())
        if str(chat_id) in CLEANER_CHATS
        else set()
    )
    return GLOBAL_IGNORE_COMMANDS, local_commands

async def __load_cleaner_data() -> None:
    """Load cleaner data into memory"""
    global GLOBAL_IGNORE_COMMANDS, CLEANER_CHATS
    
    async with async_session() as session:
        # Load global ignores
        result = await session.execute(select(CleanerBlueTextGlobal))
        GLOBAL_IGNORE_COMMANDS = {x.command for x in result.scalars().all()}
        
        # Load chat settings
        result = await session.execute(select(CleanerBlueTextChatSettings))
        CLEANER_CHATS = {
            setting.chat_id: {
                "setting": setting.is_enable,
                "commands": set()
            }
            for setting in result.scalars().all()
        }
        
        # Load chat ignores
        result = await session.execute(select(CleanerBlueTextChat))
        for ignore in result.scalars().all():
            if ignore.chat_id not in CLEANER_CHATS:
                CLEANER_CHATS[ignore.chat_id] = {
                    "setting": False,
                    "commands": set()
                }
            CLEANER_CHATS[ignore.chat_id]["commands"].add(ignore.command)

async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    """Migrate settings to new chat ID"""
    async with CLEANER_CHAT_SETTINGS_LOCK:
        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    update(CleanerBlueTextChatSettings)
                    .where(CleanerBlueTextChatSettings.chat_id == str(old_chat_id))
                    .values(chat_id=str(new_chat_id))
                )
    
    async with CLEANER_CHAT_LOCK:
        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    update(CleanerBlueTextChat)
                    .where(CleanerBlueTextChat.chat_id == str(old_chat_id))
                    .values(chat_id=str(new_chat_id))
                )
    
    # Update cache
    if str(old_chat_id) in CLEANER_CHATS:
        CLEANER_CHATS[str(new_chat_id)] = CLEANER_CHATS.pop(str(old_chat_id))

# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize the cleaner system"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_cleaner_data()
                _initialized = True
            except Exception as e:
                print(f"Cleaner initialization failed: {e}")
                raise
