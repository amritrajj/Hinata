import asyncio
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import Column, String, UnicodeText, Boolean, Integer, distinct, func
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from Hina.modules.helper_funcs.msg_types import Types
from .db_connection import BASE, async_session, async_engine  # Add async_engine import

class CustomFilters(BASE):
    __tablename__ = "cust_filters"
    chat_id = Column(String(14), primary_key=True)
    keyword = Column(UnicodeText, primary_key=True, nullable=False)
    reply = Column(UnicodeText, nullable=False)
    is_sticker = Column(Boolean, nullable=False, default=False)
    is_document = Column(Boolean, nullable=False, default=False)
    is_image = Column(Boolean, nullable=False, default=False)
    is_audio = Column(Boolean, nullable=False, default=False)
    is_voice = Column(Boolean, nullable=False, default=False)
    is_video = Column(Boolean, nullable=False, default=False)
    has_buttons = Column(Boolean, nullable=False, default=False)
    has_markdown = Column(Boolean, nullable=False, default=False)
    reply_text = Column(UnicodeText)
    file_type = Column(Integer, nullable=False, default=1)
    file_id = Column(UnicodeText, default=None)

    def __init__(
        self,
        chat_id,
        keyword,
        reply,
        is_sticker=False,
        is_document=False,
        is_image=False,
        is_audio=False,
        is_voice=False,
        is_video=False,
        has_buttons=False,
        reply_text=None,
        file_type=1,
        file_id=None,
    ):
        self.chat_id = str(chat_id)
        self.keyword = keyword
        self.reply = reply
        self.is_sticker = is_sticker
        self.is_document = is_document
        self.is_image = is_image
        self.is_audio = is_audio
        self.is_voice = is_voice
        self.is_video = is_video
        self.has_buttons = has_buttons
        self.has_markdown = True
        self.reply_text = reply_text
        self.file_type = file_type
        self.file_id = file_id

    def __repr__(self):
        return f"<Permissions for {self.chat_id}>"

    def __eq__(self, other):
        return bool(
            isinstance(other, CustomFilters)
            and self.chat_id == other.chat_id
            and self.keyword == other.keyword
        )


class NewCustomFilters(BASE):
    __tablename__ = "cust_filters_new"
    chat_id = Column(String(14), primary_key=True)
    keyword = Column(UnicodeText, primary_key=True, nullable=False)
    text = Column(UnicodeText)
    file_type = Column(Integer, nullable=False, default=1)
    file_id = Column(UnicodeText, default=None)

    def __init__(self, chat_id, keyword, text, file_type, file_id):
        self.chat_id = str(chat_id)
        self.keyword = keyword
        self.text = text
        self.file_type = file_type
        self.file_id = file_id

    def __repr__(self):
        return f"<Filter for {self.chat_id}>"

    def __eq__(self, other):
        return bool(
            isinstance(other, CustomFilters)
            and self.chat_id == other.chat_id
            and self.keyword == other.keyword
        )


class Buttons(BASE):
    __tablename__ = "cust_filter_urls"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(14), primary_key=True)
    keyword = Column(UnicodeText, primary_key=True)
    name = Column(UnicodeText, nullable=False)
    url = Column(UnicodeText, nullable=False)
    same_line = Column(Boolean, default=False)

    def __init__(self, chat_id, keyword, name, url, same_line=False):
        self.chat_id = str(chat_id)
        self.keyword = keyword
        self.name = name
        self.url = url
        self.same_line = same_line


async def create_tables():
    """Initialize database tables using engine connection"""
    async with async_engine.begin() as conn:
        await conn.run_sync(BASE.metadata.create_all)

# Async locks
CUST_FILT_LOCK = asyncio.Lock()
BUTTON_LOCK = asyncio.Lock()

# In-memory cache
CHAT_FILTERS: Dict[str, List[str]] = {}

# =============== CORE FILTER FUNCTIONS ===============
async def get_all_filters() -> List[CustomFilters]:
    """Get all filters from database"""
    try:
        async with async_session() as session:
            result = await session.execute(select(CustomFilters))
            return result.scalars().all()
    except Exception as e:
        print(f"Error getting all filters: {e}")
        return []

async def add_filter(
    chat_id: str,
    keyword: str,
    reply: str,
    is_sticker=False,
    is_document=False,
    is_image=False,
    is_audio=False,
    is_voice=False,
    is_video=False,
    buttons=None
) -> None:
    """Add a new filter"""
    global CHAT_FILTERS
    if buttons is None:
        buttons = []

    async with CUST_FILT_LOCK:
        async with async_session() as session:
            # Check if filter exists
            result = await session.execute(
                select(CustomFilters)
                .where(CustomFilters.chat_id == str(chat_id))
                .where(CustomFilters.keyword == keyword)
            )
            existing = result.scalars().first()

            if existing:
                # Delete existing buttons first
                async with BUTTON_LOCK:
                    result = await session.execute(
                        select(Buttons)
                        .where(Buttons.chat_id == str(chat_id))
                        .where(Buttons.keyword == keyword)
                    )
                    for btn in result.scalars():
                        await session.delete(btn)
                await session.delete(existing)

            # Create new filter
            new_filter = CustomFilters(
                chat_id=str(chat_id),
                keyword=keyword,
                reply=reply,
                is_sticker=is_sticker,
                is_document=is_document,
                is_image=is_image,
                is_audio=is_audio,
                is_voice=is_voice,
                is_video=is_video,
                has_buttons=bool(buttons)
            )

            # Update cache
            if str(chat_id) not in CHAT_FILTERS:
                CHAT_FILTERS[str(chat_id)] = []
            if keyword not in CHAT_FILTERS[str(chat_id)]:
                CHAT_FILTERS[str(chat_id)].append(keyword)
                CHAT_FILTERS[str(chat_id)].sort(key=lambda x: (-len(x), x))

            session.add(new_filter)

            # Add buttons if any
            for btn_name, btn_url, same_line in buttons:
                await add_note_button_to_db(
                    chat_id, keyword, btn_name, btn_url, same_line)

async def remove_filter(chat_id: str, keyword: str) -> bool:
    """Remove a filter"""
    global CHAT_FILTERS
    async with CUST_FILT_LOCK:
        async with async_session() as session:
            # Find the filter
            result = await session.execute(
                select(CustomFilters)
                .where(CustomFilters.chat_id == str(chat_id))
                .where(CustomFilters.keyword == keyword)
            )
            target = result.scalars().first()

            if target:
                # Remove from cache
                if str(chat_id) in CHAT_FILTERS and keyword in CHAT_FILTERS[str(chat_id)]:
                    CHAT_FILTERS[str(chat_id)].remove(keyword)

                # Delete associated buttons
                async with BUTTON_LOCK:
                    result = await session.execute(
                        select(Buttons)
                        .where(Buttons.chat_id == str(chat_id))
                        .where(Buttons.keyword == keyword)
                    )
                    for btn in result.scalars():
                        await session.delete(btn)

                # Delete the filter
                await session.delete(target)
                return True
            return False

async def get_chat_filters(chat_id: str) -> List[CustomFilters]:
    """Get all filters for a chat"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(CustomFilters)
                .where(CustomFilters.chat_id == str(chat_id))
                .order_by(func.length(CustomFilters.keyword).desc())
                .order_by(CustomFilters.keyword)
            )
            return result.scalars().all()
    except Exception as e:
        print(f"Error getting chat filters: {e}")
        return []

async def get_filter(chat_id: str, keyword: str) -> Optional[CustomFilters]:
    """Get specific filter"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(CustomFilters)
                .where(CustomFilters.chat_id == str(chat_id))
                .where(CustomFilters.keyword == keyword)
            )
            return result.scalars().first()
    except Exception as e:
        print(f"Error getting filter: {e}")
        return None

async def add_note_button_to_db(
    chat_id: str,
    keyword: str,
    btn_name: str,
    btn_url: str,
    same_line: bool = False
) -> None:
    """Add button to filter"""
    async with BUTTON_LOCK:
        async with async_session() as session:
            new_btn = Buttons(
                chat_id=str(chat_id),
                keyword=keyword,
                name=btn_name,
                url=btn_url,
                same_line=same_line
            )
            session.add(new_btn)

async def get_buttons(chat_id: str, keyword: str) -> List[Buttons]:
    """Get all buttons for a filter"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(Buttons)
                .where(Buttons.chat_id == str(chat_id))
                .where(Buttons.keyword == keyword)
                .order_by(Buttons.id)
            )
            return result.scalars().all()
    except Exception as e:
        print(f"Error getting buttons: {e}")
        return []

# =============== CACHE MANAGEMENT ===============
async def __load_chat_filters() -> None:
    """Load all filters into memory cache"""
    global CHAT_FILTERS
    try:
        async with async_session() as session:
            # Get all distinct chat_ids
            result = await session.execute(
                select(distinct(CustomFilters.chat_id))
            )
            chat_ids = [r[0] for r in result.all()]
            
            # Initialize cache structure
            CHAT_FILTERS = {cid: [] for cid in chat_ids}
            
            # Load all filters
            result = await session.execute(select(CustomFilters))
            for flt in result.scalars().all():
                CHAT_FILTERS[flt.chat_id].append(flt.keyword)
            
            # Sort each chat's filters by length (longest first)
            for chat_id in CHAT_FILTERS:
                CHAT_FILTERS[chat_id].sort(key=lambda x: (-len(x), x))
    except Exception as e:
        print(f"Error loading chat filters: {e}")
        CHAT_FILTERS = {}

# =============== MIGRATION ===============
async def migrate_chat(old_chat_id: str, new_chat_id: str) -> None:
    """Migrate filters to new chat ID"""
    async with CUST_FILT_LOCK:
        async with async_session() as session:
            # Migrate filters
            result = await session.execute(
                select(CustomFilters)
                .where(CustomFilters.chat_id == str(old_chat_id))
            )
            for flt in result.scalars():
                flt.chat_id = str(new_chat_id)
            
            # Migrate buttons
            async with BUTTON_LOCK:
                result = await session.execute(
                    select(Buttons)
                    .where(Buttons.chat_id == str(old_chat_id))
                )
                for btn in result.scalars():
                    btn.chat_id = str(new_chat_id)
            
            # Update cache
            if str(old_chat_id) in CHAT_FILTERS:
                CHAT_FILTERS[str(new_chat_id)] = CHAT_FILTERS.pop(str(old_chat_id))

# =============== STATISTICS ===============
async def num_filters() -> int:
    """Count all filters"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(func.count()).select_from(CustomFilters)
            )
            return result.scalar() or 0
    except Exception as e:
        print(f"Error counting filters: {e}")
        return 0

async def num_chats() -> int:
    """Count chats with filters"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(func.count(distinct(CustomFilters.chat_id)))
            )
            return result.scalar() or 0
    except Exception as e:
        print(f"Error counting chats: {e}")
        return 0

# =============== INITIALIZATION ===============
_initialized = False
_init_lock = asyncio.Lock()

async def initialize():
    """Initialize system"""
    global _initialized
    async with _init_lock:
        if not _initialized:
            try:
                await create_tables()
                await __load_chat_filters()
                _initialized = True
            except Exception as e:
                print(f"Initialization failed: {e}")
                raise
