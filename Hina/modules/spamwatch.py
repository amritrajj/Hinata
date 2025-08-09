import os
import logging
import asyncio
from typing import Optional, Dict, Set

from telegram import (
    Update,
    MessageEntity,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    Application
)
from telegram.error import BadRequest
from telegram.helpers import mention_html

from Hina.config import DB_URI, LOG_CHANNEL, app

try:
    import spamwatch
    SPAMWATCH_AVAILABLE = True
except ImportError:
    SPAMWATCH_AVAILABLE = False
    logging.warning("SpamWatch module not installed!")

from Hina.modules.helper_funcs.chat_status import user_admin
from Hina.modules.helper_funcs.extraction import extract_user

try:
    from Hina.modules.disable import DisableAbleCommandHandler
except ImportError:
    DisableAbleCommandHandler = CommandHandler

# Database Setup
from sqlalchemy import Column, String, Boolean, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base

BASE = declarative_base()

class SpamWatchSettings(BASE):
    __tablename__ = "chat_spamwatch_settings"
    chat_id = Column(String(14), primary_key=True)
    setting = Column(Boolean, default=True, nullable=False)
    do_log = Column(Boolean, default=True)

    def __init__(self, chat_id, disabled, does_log=True):
        self.chat_id = str(chat_id)
        self.setting = disabled
        self.do_log = bool(does_log)

    def __repr__(self):
        return f"<SpamWatch setting {self.chat_id} ({self.setting})>"

LOGGER = logging.getLogger(__name__)

async def create_tables(async_engine):
    """Initialize database tables"""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(BASE.metadata.create_all)
        LOGGER.info("SpamWatch database tables initialized successfully.")
    except Exception as e:
        LOGGER.error(f"Failed to initialize SpamWatch database tables: {e}", exc_info=True)
        raise

# Initialize SpamWatch Client with the provided token
SPAMWATCH_TOKEN = "6kkCqbMbiwJzPCkAT359mn0Cum1V09XZ83kLCc90wiAxsT7~hxR5dgccCerMWth6"
spamwatch_client: Optional[spamwatch.Client] = None

if SPAMWATCH_TOKEN and SPAMWATCH_AVAILABLE:
    try:
        spamwatch_client = spamwatch.Client(SPAMWATCH_TOKEN)
        LOGGER.info("Connected to SpamWatch.")
    except Exception as e:
        spamwatch_client = None
        LOGGER.error(f"Failed to load SpamWatch client: {e}", exc_info=True)
else:
    LOGGER.warning("SpamWatch is not configured or not available!")

SPAMWATCH_SETTING_LOCK = asyncio.Lock()
SPAMWATCH_DISABLED_CHATS: Set[str] = set()
SPAMWATCH_SETTINGS: Dict[str, bool] = {}

async def load_spamwatch_data(async_engine):
    """Load data from database into memory"""
    global SPAMWATCH_DISABLED_CHATS, SPAMWATCH_SETTINGS
    async with SPAMWATCH_SETTING_LOCK:
        try:
            async with AsyncSession(async_engine) as session:
                result = await session.execute(select(SpamWatchSettings))
                settings = result.scalars().all()
                SPAMWATCH_DISABLED_CHATS = {x.chat_id for x in settings if not x.setting}
                SPAMWATCH_SETTINGS = {x.chat_id: x.do_log for x in settings}
            LOGGER.info(f"Loaded {len(settings)} SpamWatch settings from database.")
        except Exception as e:
            LOGGER.error(f"Error loading SpamWatch data: {e}", exc_info=True)
            raise

async def init_spamwatch(async_engine):
    """Initialize the SpamWatch module"""
    if not spamwatch_client:
        LOGGER.warning("SpamWatch client not available, skipping database initialization.")
        return False
    try:
        await create_tables(async_engine)
        await load_spamwatch_data(async_engine)
        LOGGER.info("SpamWatch initialization successful.")
        return True
    except Exception as e:
        LOGGER.error(f"Failed to fully initialize SpamWatch: {e}", exc_info=True)
        return False

async def toggle_spamwatch_log(chat_id: str, async_engine):
    async with SPAMWATCH_SETTING_LOCK:
        async with AsyncSession(async_engine) as session:
            async with session.begin():
                result = await session.execute(
                    select(SpamWatchSettings)
                    .where(SpamWatchSettings.chat_id == str(chat_id))
                )
                chat = result.scalars().first()
                if chat:
                    chat.do_log = not chat.do_log
                    session.add(chat)
                    SPAMWATCH_SETTINGS[str(chat_id)] = chat.do_log

async def enable_spamwatch(chat_id: str, async_engine):
    async with SPAMWATCH_SETTING_LOCK:
        async with AsyncSession(async_engine) as session:
            async with session.begin():
                result = await session.execute(
                    select(SpamWatchSettings)
                    .where(SpamWatchSettings.chat_id == str(chat_id))
                )
                chat = result.scalars().first()
                if not chat:
                    chat = SpamWatchSettings(chat_id, True)
                chat.setting = True
                session.add(chat)
                if str(chat_id) in SPAMWATCH_DISABLED_CHATS:
                    SPAMWATCH_DISABLED_CHATS.remove(str(chat_id))

async def disable_spamwatch(chat_id: str, async_engine):
    async with SPAMWATCH_SETTING_LOCK:
        async with AsyncSession(async_engine) as session:
            async with session.begin():
                result = await session.execute(
                    select(SpamWatchSettings)
                    .where(SpamWatchSettings.chat_id == str(chat_id))
                )
                chat = result.scalars().first()
                if not chat:
                    chat = SpamWatchSettings(chat_id, False)
                chat.setting = False
                session.add(chat)
                SPAMWATCH_DISABLED_CHATS.add(str(chat_id))

def is_spamwatch_enabled(chat_id: str) -> bool:
    return str(chat_id) not in SPAMWATCH_DISABLED_CHATS

def get_spamwatch_log_setting(chat_id: str) -> bool:
    return SPAMWATCH_SETTINGS.get(str(chat_id), True)

async def spamwatch_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check new messages for banned users"""
    if not spamwatch_client or not is_spamwatch_enabled(str(update.effective_chat.id)):
        return
    
    user = update.effective_user
    if not user:
        return
        
    try:
        ban = spamwatch_client.get_ban(user.id)
        if ban:
            await update.effective_chat.ban_member(user.id)
            if get_spamwatch_log_setting(str(update.effective_chat.id)):
                log_msg = (
                    f"#SPAMWATCH_BAN\n"
                    f"• User: {mention_html(user.id, user.first_name)}\n"
                    f"• ID: <code>{user.id}</code>\n"
                    f"• Reason: <code>{ban.reason}</code>\n"
                    f"• Chat: {update.effective_chat.title} (<code>{update.effective_chat.id}</code>)"
                )
                if LOG_CHANNEL:
                    await context.bot.send_message(
                        chat_id=LOG_CHANNEL,
                        text=log_msg,
                        parse_mode=ParseMode.HTML
                    )
    except Exception as e:
        LOGGER.error(f"Error checking SpamWatch ban: {e}", exc_info=True)

async def spamwatch_ban_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check new members for bans"""
    if not spamwatch_client or not is_spamwatch_enabled(str(update.effective_chat.id)):
        return
    
    for user in update.effective_message.new_chat_members:
        try:
            ban = spamwatch_client.get_ban(user.id)
            if ban:
                await update.effective_chat.ban_member(user.id)
                if get_spamwatch_log_setting(str(update.effective_chat.id)):
                    log_msg = (
                        f"#SPAMWATCH_BAN\n"
                        f"• User: {mention_html(user.id, user.first_name)}\n"
                        f"• ID: <code>{user.id}</code>\n"
                        f"• Reason: <code>{ban.reason}</code>\n"
                        f"• Chat: {update.effective_chat.title} (<code>{update.effective_chat.id}</code>)"
                    )
                    if LOG_CHANNEL:
                        await context.bot.send_message(
                            chat_id=LOG_CHANNEL,
                            text=log_msg,
                            parse_mode=ParseMode.HTML
                        )
        except Exception as e:
            LOGGER.error(f"Error checking SpamWatch ban for new member: {e}", exc_info=True)

async def spamwatch_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if a user is banned in SpamWatch"""
    if not spamwatch_client:
        await update.effective_message.reply_text("SpamWatch is not currently enabled.")
        return
        
    user_id = await extract_user(update, context)
    if not user_id:
        return
        
    try:
        ban = spamwatch_client.get_ban(user_id)
        if ban:
            await update.effective_message.reply_text(
                f"⚠️ User is banned in SpamWatch.\n"
                f"• Reason: {ban.reason}\n"
                f"• Message: {ban.message or 'No message provided'}\n"
                f"• Date: {ban.date}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.effective_message.reply_text("✅ User is not banned in SpamWatch.")
    except Exception as e:
        await update.effective_message.reply_text(f"Error checking SpamWatch: {e}")
        LOGGER.error(f"Error checking SpamWatch ban: {e}", exc_info=True)

@user_admin
async def spamwatch_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle SpamWatch for a chat"""
    chat_id = str(update.effective_chat.id)
    async_engine = context.application.bot_data.get('async_engine')
    if not async_engine:
        await update.effective_message.reply_text("SpamWatch database not initialized.")
        return
        
    if is_spamwatch_enabled(chat_id):
        await disable_spamwatch(chat_id, async_engine)
        await update.effective_message.reply_text("SpamWatch protection disabled for this chat.")
    else:
        await enable_spamwatch(chat_id, async_engine)
        await update.effective_message.reply_text("SpamWatch protection enabled for this chat.")

@user_admin
async def spamwatch_log_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle logging for SpamWatch bans"""
    chat_id = str(update.effective_chat.id)
    async_engine = context.application.bot_data.get('async_engine')
    if not async_engine:
        await update.effective_message.reply_text("SpamWatch database not initialized.")
        return

    await toggle_spamwatch_log(chat_id, async_engine)
    current_setting = get_spamwatch_log_setting(chat_id)
    
    await update.effective_message.reply_text(
        f"SpamWatch ban logging is now {'enabled' if current_setting else 'disabled'} for this chat."
    )

async def setup_module(application: Application):
    """A single function to initialize and set up the module."""
    LOGGER.info("Starting SpamWatch module setup.")
    if not SPAMWATCH_AVAILABLE:
        LOGGER.warning("SpamWatch module is not available. Skipping setup.")
        return False
        
    if not SPAMWATCH_TOKEN:
        LOGGER.warning("SPAMWATCH_TOKEN is not configured. Skipping setup.")
        return False
        
    try:
        async_engine = create_async_engine(DB_URI.replace("postgresql://", "postgresql+asyncpg://"))
        application.bot_data['async_engine'] = async_engine
        
        success = await init_spamwatch(async_engine)
        if success:
            LOGGER.info("SpamWatch initialization successful. Registering handlers.")
            
            app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.UpdateType.EDITED, spamwatch_ban), group=101)
            app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, spamwatch_ban_alert), group=102)
            app.add_handler(DisableAbleCommandHandler("spamwatch", spamwatch_toggle))
            app.add_handler(DisableAbleCommandHandler("swlog", spamwatch_log_toggle))
            app.add_handler(DisableAbleCommandHandler("check", spamwatch_check))
            return True
        else:
            LOGGER.warning("SpamWatch initialization failed.")
    except Exception as e:
        LOGGER.error(f"Error in setup_module: {e}", exc_info=True)
    return False

__help__ = """
[SpamWatch](https://spamwat.ch) is an advanced anti-spam service.

<b>Commands:</b>
 • /spamwatch - Toggle SpamWatch protection in chat
 • /swlog - Toggle ban logging
 • /check [user] - Check if a user is banned
"""

__mod_name__ = "SpamWatch"
__handlers__ = [
    MessageHandler(filters.ChatType.GROUPS & ~filters.UpdateType.EDITED, spamwatch_ban),
    MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, spamwatch_ban_alert),
    DisableAbleCommandHandler("spamwatch", spamwatch_toggle),
    DisableAbleCommandHandler("swlog", spamwatch_log_toggle),
    DisableAbleCommandHandler("check", spamwatch_check)
]
