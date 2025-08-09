import asyncio
import time
from sqlalchemy import Column, Integer, String, Boolean
from typing import Optional, Union

from .db_connection import BASE, async_session, async_engine
from sqlalchemy.future import select

class Permissions(BASE):
    __tablename__ = "permissions"
    __table_args__ = {'extend_existing': True}
    
    chat_id = Column(String(14), primary_key=True)
    audio = Column(Boolean, default=False)
    voice = Column(Boolean, default=False)
    contact = Column(Boolean, default=False)
    video = Column(Boolean, default=False)
    document = Column(Boolean, default=False)
    photo = Column(Boolean, default=False)
    sticker = Column(Boolean, default=False)
    gif = Column(Boolean, default=False)
    url = Column(Boolean, default=False)
    bots = Column(Boolean, default=False)
    forward = Column(Boolean, default=False)
    game = Column(Boolean, default=False)
    location = Column(Boolean, default=False)
    rtl = Column(Boolean, default=False)
    button = Column(Boolean, default=False)
    egame = Column(Boolean, default=False)
    inline = Column(Boolean, default=False)
    updated_at = Column(Integer)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)
        self.audio = False
        self.voice = False
        self.contact = False
        self.video = False
        self.document = False
        self.photo = False
        self.sticker = False
        self.gif = False
        self.url = False
        self.bots = False
        self.forward = False
        self.game = False
        self.location = False
        self.rtl = False
        self.button = False
        self.egame = False
        self.inline = False
        self.updated_at = int(time.time())

    def __repr__(self):
        return f"<Permissions for {self.chat_id}>"

class Restrictions(BASE):
    __tablename__ = "restrictions"
    __table_args__ = {'extend_existing': True}
    
    chat_id = Column(String(14), primary_key=True)
    messages = Column(Boolean, default=False)
    media = Column(Boolean, default=False)
    other = Column(Boolean, default=False)
    preview = Column(Boolean, default=False)
    updated_at = Column(Integer)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)
        self.messages = False
        self.media = False
        self.other = False
        self.preview = False
        self.updated_at = int(time.time())

    def __repr__(self):
        return f"<Restrictions for {self.chat_id}>"

# Async locks
PERM_LOCK = asyncio.Lock()
RESTR_LOCK = asyncio.Lock()

# In-memory cache
PERMISSIONS_CACHE = {}
RESTRICTIONS_CACHE = {}

async def create_tables():
    """Initialize database tables using engine connection"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

async def init_permissions(chat_id: Union[int, str], reset: bool = False) -> Permissions:
    """Initialize permissions for a chat"""
    async with PERM_LOCK:
        async with async_session() as session:
            async with session.begin():
                curr_perm = await session.get(Permissions, str(chat_id))
                if reset and curr_perm:
                    await session.delete(curr_perm)
                    await session.flush()
                
                perm = Permissions(str(chat_id))
                session.add(perm)
                PERMISSIONS_CACHE[str(chat_id)] = perm
                return perm

async def init_restrictions(chat_id: Union[int, str], reset: bool = False) -> Restrictions:
    """Initialize restrictions for a chat"""
    async with RESTR_LOCK:
        async with async_session() as session:
            async with session.begin():
                curr_restr = await session.get(Restrictions, str(chat_id))
                if reset and curr_restr:
                    await session.delete(curr_restr)
                    await session.flush()
                
                restr = Restrictions(str(chat_id))
                session.add(restr)
                RESTRICTIONS_CACHE[str(chat_id)] = restr
                return restr

async def update_lock(chat_id: Union[int, str], lock_type: str, locked: bool) -> None:
    """Update a specific lock setting"""
    async with PERM_LOCK:
        async with async_session() as session:
            async with session.begin():
                curr_perm = await session.get(Permissions, str(chat_id))
                if not curr_perm:
                    curr_perm = await init_permissions(chat_id)

                lock_attrs = {
                    "audio": "audio",
                    "voice": "voice",
                    "contact": "contact",
                    "video": "video",
                    "document": "document",
                    "photo": "photo",
                    "sticker": "sticker",
                    "gif": "gif",
                    "url": "url",
                    "bots": "bots",
                    "forward": "forward",
                    "game": "game",
                    "location": "location",
                    "rtl": "rtl",
                    "button": "button",
                    "egame": "egame",
                    "inline": "inline"
                }

                if lock_type in lock_attrs:
                    setattr(curr_perm, lock_attrs[lock_type], locked)
                    curr_perm.updated_at = int(time.time())
                    PERMISSIONS_CACHE[str(chat_id)] = curr_perm

async def update_restriction(chat_id: Union[int, str], restr_type: str, locked: bool) -> None:
    """Update a specific restriction setting"""
    async with RESTR_LOCK:
        async with async_session() as session:
            async with session.begin():
                curr_restr = await session.get(Restrictions, str(chat_id))
                if not curr_restr:
                    curr_restr = await init_restrictions(chat_id)

                if restr_type == "messages":
                    curr_restr.messages = locked
                elif restr_type == "media":
                    curr_restr.media = locked
                elif restr_type == "other":
                    curr_restr.other = locked
                elif restr_type == "previews":
                    curr_restr.preview = locked
                elif restr_type == "all":
                    curr_restr.messages = locked
                    curr_restr.media = locked
                    curr_restr.other = locked
                    curr_restr.preview = locked

                curr_restr.updated_at = int(time.time())
                RESTRICTIONS_CACHE[str(chat_id)] = curr_restr

async def is_locked(chat_id: Union[int, str], lock_type: str) -> bool:
    """Check if a specific lock is enabled"""
    if str(chat_id) in PERMISSIONS_CACHE:
        curr_perm = PERMISSIONS_CACHE[str(chat_id)]
    else:
        async with async_session() as session:
            curr_perm = await session.get(Permissions, str(chat_id))
            if curr_perm:
                PERMISSIONS_CACHE[str(chat_id)] = curr_perm

    if not curr_perm:
        return False

    lock_status = {
        "sticker": curr_perm.sticker,
        "photo": curr_perm.photo,
        "audio": curr_perm.audio,
        "voice": curr_perm.voice,
        "contact": curr_perm.contact,
        "video": curr_perm.video,
        "document": curr_perm.document,
        "gif": curr_perm.gif,
        "url": curr_perm.url,
        "bots": curr_perm.bots,
        "forward": curr_perm.forward,
        "game": curr_perm.game,
        "location": curr_perm.location,
        "rtl": curr_perm.rtl,
        "button": curr_perm.button,
        "egame": curr_perm.egame,
        "inline": curr_perm.inline
    }

    return lock_status.get(lock_type, False)

async def is_restr_locked(chat_id: Union[int, str], lock_type: str) -> bool:
    """Check if a specific restriction is enabled"""
    if str(chat_id) in RESTRICTIONS_CACHE:
        curr_restr = RESTRICTIONS_CACHE[str(chat_id)]
    else:
        async with async_session() as session:
            curr_restr = await session.get(Restrictions, str(chat_id))
            if curr_restr:
                RESTRICTIONS_CACHE[str(chat_id)] = curr_restr

    if not curr_restr:
        return False

    if lock_type == "messages":
        return curr_restr.messages
    elif lock_type == "media":
        return curr_restr.media
    elif lock_type == "other":
        return curr_restr.other
    elif lock_type == "previews":
        return curr_restr.preview
    elif lock_type == "all":
        return (
            curr_restr.messages
            and curr_restr.media
            and curr_restr.other
            and curr_restr.preview
        )
    return False

async def get_locks(chat_id: Union[int, str]) -> Optional[Permissions]:
    """Get all lock settings for a chat"""
    if str(chat_id) in PERMISSIONS_CACHE:
        return PERMISSIONS_CACHE[str(chat_id)]
    
    async with async_session() as session:
        result = await session.get(Permissions, str(chat_id))
        if result:
            PERMISSIONS_CACHE[str(chat_id)] = result
        return result

async def get_restr(chat_id: Union[int, str]) -> Optional[Restrictions]:
    """Get all restriction settings for a chat"""
    if str(chat_id) in RESTRICTIONS_CACHE:
        return RESTRICTIONS_CACHE[str(chat_id)]
    
    async with async_session() as session:
        result = await session.get(Restrictions, str(chat_id))
        if result:
            RESTRICTIONS_CACHE[str(chat_id)] = result
        return result

async def migrate_chat(old_chat_id: Union[int, str], new_chat_id: Union[int, str]) -> None:
    """Migrate settings to new chat ID"""
    async with PERM_LOCK:
        async with async_session() as session:
            async with session.begin():
                perms = await session.get(Permissions, str(old_chat_id))
                if perms:
                    perms.chat_id = str(new_chat_id)
                    if str(old_chat_id) in PERMISSIONS_CACHE:
                        PERMISSIONS_CACHE[str(new_chat_id)] = PERMISSIONS_CACHE.pop(str(old_chat_id))

    async with RESTR_LOCK:
        async with async_session() as session:
            async with session.begin():
                rest = await session.get(Restrictions, str(old_chat_id))
                if rest:
                    rest.chat_id = str(new_chat_id)
                    if str(old_chat_id) in RESTRICTIONS_CACHE:
                        RESTRICTIONS_CACHE[str(new_chat_id)] = RESTRICTIONS_CACHE.pop(str(old_chat_id))

async def __load_permissions():
    """Load permissions into cache on startup"""
    global PERMISSIONS_CACHE
    async with async_session() as session:
        result = await session.execute(select(Permissions))
        PERMISSIONS_CACHE = {perm.chat_id: perm for perm in result.scalars()}

async def __load_restrictions():
    """Load restrictions into cache on startup"""
    global RESTRICTIONS_CACHE
    async with async_session() as session:
        result = await session.execute(select(Restrictions))
        RESTRICTIONS_CACHE = {restr.chat_id: restr for restr in result.scalars()}

# Improved initialization with state tracking
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize locks system (call this from main application)"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_permissions()
                await __load_restrictions()
                _initialized = True
            except Exception as e:
                print(f"Locks initialization failed: {e}")
                raise
