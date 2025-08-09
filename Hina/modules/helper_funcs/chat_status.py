import asyncio
from time import perf_counter
from functools import wraps
from cachetools import TTLCache
from threading import RLock
from typing import Optional, Set, Callable, Awaitable, Any, TypeVar, cast, List

from telegram import Chat, ChatMember, Update
from telegram.constants import ParseMode, ChatMemberStatus, ChatType
from telegram.ext import ContextTypes
from telegram.helpers import mention_html

from Hina.config import (
    DEL_CMDS,
    DEV_USERS,
    DRAGONS,
    SUPPORT_CHAT,
    DEMONS,
    TIGERS,
    WOLVES,
    app,
)
from Hina.modules.helper_funcs.misc import LOGGER

# Type variable for generic function type
F = TypeVar('F', bound=Callable[..., Awaitable[Any]])

# stores admins in memory for 10 min
ADMIN_CACHE = TTLCache(maxsize=512, ttl=60 * 10, timer=perf_counter)
THREAD_LOCK = RLock()

# Telegram's special IDs
ANONYMOUS_ADMINS = {1087968824, 136817688, 777000}

async def refresh_admin_cache(chat_id: int) -> Set[int]:
    """Refresh admin cache for a chat"""
    try:
        admins = await app.bot.get_chat_administrators(chat_id)
        admin_list = {admin.user.id for admin in admins}
        with THREAD_LOCK:
            ADMIN_CACHE[chat_id] = admin_list
        return admin_list
    except Exception as e:
        LOGGER.error(f"Error refreshing admin cache for chat {chat_id}: {e}")
        return set()


def is_whitelist_plus(chat: Chat, user_id: int, member: ChatMember = None) -> bool:
    """Check if user is whitelisted"""
    return user_id in WOLVES or user_id in TIGERS or user_id in DEMONS or user_id in DRAGONS or user_id in DEV_USERS

def is_support_plus(chat: Chat, user_id: int, member: ChatMember = None) -> bool:
    """Check if user is support+"""
    return user_id in DEMONS or user_id in DRAGONS or user_id in DEV_USERS

def is_sudo_plus(chat: Chat, user_id: int, member: ChatMember = None) -> bool:
    """Check if user is sudo+"""
    return user_id in DRAGONS or user_id in DEV_USERS

async def is_user_admin(chat: Chat, user_id: int, member: Optional[ChatMember] = None) -> bool:
    """Check if user is admin"""
    if chat.type == ChatType.PRIVATE:
        return True
    
    if user_id in ANONYMOUS_ADMINS:
        return True
    
    if is_whitelist_plus(chat, user_id):
        return True
    
    if not member:
        try:
            with THREAD_LOCK:
                admin_list = ADMIN_CACHE.get(chat.id, set())
            
            if user_id in admin_list:
                return True
            
            admin_list = await refresh_admin_cache(chat.id)
            return user_id in admin_list
            
        except Exception as e:
            LOGGER.error(f"Error checking admin status: {e}")
            return False
            
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

async def bot_admin(chat: Chat, bot_id: int) -> bool:
    """Check if bot is admin"""
    if chat.type == ChatType.PRIVATE:
        return True
    
    try:
        bot_member = await chat.get_member(bot_id)
        return bot_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception as e:
        LOGGER.error(f"Error checking bot admin status: {e}")
        return False

async def can_delete(chat: Chat, bot_id: int) -> bool:
    """Check if bot can delete messages"""
    try:
        bot_member = await chat.get_member(bot_id)
        return bot_member.can_delete_messages
    except Exception as e:
        LOGGER.error(f"Error checking delete permissions: {e}")
        return False

async def is_user_ban_protected(chat: Chat, user_id: int, member: Optional[ChatMember] = None) -> bool:
    """Check if user is ban protected"""
    if chat.type == ChatType.PRIVATE:
        return True
    
    if user_id in ANONYMOUS_ADMINS:
        return True
    
    if is_whitelist_plus(chat, user_id):
        return True
    
    if not member:
        member = await chat.get_member(user_id)
        
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

async def is_user_in_chat(chat: Chat, user_id: int) -> bool:
    """Check if user is in chat"""
    try:
        member = await chat.get_member(user_id)
        return member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
    except Exception:
        return False

async def user_not_admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is not an admin"""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return True
    
    return not await is_user_admin(chat, user.id)

# ==================== DECORATORS ==================== #

def dev_plus(func: F) -> F:
    @wraps(func)
    async def is_dev_plus_func(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        
        if user and user.id in DEV_USERS:
            return await func(update, context, *args, **kwargs)
            
        if not user:
            return
            
        if DEL_CMDS and " " not in update.effective_message.text:
            try:
                await update.effective_message.delete()
            except Exception:
                pass
        else:
            await update.effective_message.reply_text(
                "This is a developer restricted command. You do not have permissions to run this."
            )
            
    return cast(F, is_dev_plus_func)

def sudo_plus(func: F) -> F:
    @wraps(func)
    async def is_sudo_plus_func(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        
        if user and is_sudo_plus(chat, user.id):
            return await func(update, context, *args, **kwargs)
            
        if not user:
            return
            
        if DEL_CMDS and " " not in update.effective_message.text:
            try:
                await update.effective_message.delete()
            except Exception:
                pass
        else:
            await update.effective_message.reply_text(
                "Who dis non-admin telling me what to do? You want a punch?"
            )
            
    return cast(F, is_sudo_plus_func)

def support_plus(func: F) -> F:
    @wraps(func)
    async def is_support_plus_func(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        
        if user and is_support_plus(chat, user.id):
            return await func(update, context, *args, **kwargs)
            
        if DEL_CMDS and " " not in update.effective_message.text:
            try:
                await update.effective_message.delete()
            except Exception:
                pass
        else:
            await update.effective_message.reply_text(
                "You need support+ rights to use this command!"
            )
            
    return cast(F, is_support_plus_func)

def whitelist_plus(func: F) -> F:
    @wraps(func)
    async def is_whitelist_plus_func(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        
        if user and is_whitelist_plus(chat, user.id):
            return await func(update, context, *args, **kwargs)
        else:
            await update.effective_message.reply_text(
                f"You don't have access to use this.\nVisit @{SUPPORT_CHAT}",
            )
            
    return cast(F, is_whitelist_plus_func)

def user_admin(func: F) -> F:
    @wraps(func)
    async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        
        if user and await is_user_admin(chat, user.id):
            return await func(update, context, *args, **kwargs)
            
        if not user:
            return
            
        if DEL_CMDS and " " not in update.effective_message.text:
            try:
                await update.effective_message.delete()
            except Exception:
                pass
        else:
            await update.effective_message.reply_text(
                "Who dis non-admin telling me what to do? You want a punch?"
            )
            
    return cast(F, is_admin)

def user_admin_no_reply(func: F) -> F:
    @wraps(func)
    async def is_not_admin_no_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        
        if user and await is_user_admin(chat, user.id):
            return await func(update, context, *args, **kwargs)
            
        if not user:
            return
            
        if DEL_CMDS and " " not in update.effective_message.text:
            try:
                await update.effective_message.delete()
            except Exception:
                pass
                
    return cast(F, is_not_admin_no_reply)

def user_not_admin(func: F) -> F:
    @wraps(func)
    async def is_not_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        
        if user and not await is_user_admin(chat, user.id):
            return await func(update, context, *args, **kwargs)
        elif not user:
            pass
            
    return cast(F, is_not_admin)

def bot_admin_decorator(func: F) -> F:
    @wraps(func)
    async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        bot = context.bot
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            not_admin = "I'm not admin! - REEEEEE"
        else:
            not_admin = f"I'm not admin in <b>{update_chat_title}</b>! - REEEEEE"

        if await bot_admin(chat, bot.id):
            return await func(update, context, *args, **kwargs)
        else:
            await update.effective_message.reply_text(not_admin, parse_mode=ParseMode.HTML)
            
    return cast(F, is_admin)

def bot_can_delete(func: F) -> F:
    @wraps(func)
    async def delete_rights(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        bot = context.bot
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            cant_delete = "I can't delete messages here!\nMake sure I'm admin and can delete other user's messages."
        else:
            cant_delete = f"I can't delete messages in <b>{update_chat_title}</b>!\nMake sure I'm admin and can delete other user's messages there."

        if await can_delete(chat, bot.id):
            return await func(update, context, *args, **kwargs)
        else:
            await update.effective_message.reply_text(cant_delete, parse_mode=ParseMode.HTML)
            
    return cast(F, delete_rights)

def can_pin(func: F) -> F:
    @wraps(func)
    async def pin_rights(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        bot = context.bot
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            cant_pin = "I can't pin messages here!\nMake sure I'm admin and can pin messages."
        else:
            cant_pin = f"I can't pin messages in <b>{update_chat_title}</b>!\nMake sure I'm admin and can pin messages there."

        try:
            bot_member = await chat.get_member(bot.id)
            if bot_member.can_pin_messages:
                return await func(update, context, *args, **kwargs)
            await update.effective_message.reply_text(cant_pin, parse_mode=ParseMode.HTML)
        except Exception as e:
            LOGGER.error(f"Error checking pin permissions: {e}")
            await update.effective_message.reply_text("Error checking pin permissions!")
            
    return cast(F, pin_rights)

def can_promote(func: F) -> F:
    @wraps(func)
    async def promote_rights(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        bot = context.bot
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            cant_promote = "I can't promote/demote people here!\nMake sure I'm admin and can appoint new admins."
        else:
            cant_promote = (
                f"I can't promote/demote people in <b>{update_chat_title}</b>!\n"
                f"Make sure I'm admin there and can appoint new admins."
            )

        try:
            bot_member = await chat.get_member(bot.id)
            if bot_member.can_promote_members:
                return await func(update, context, *args, **kwargs)
            await update.effective_message.reply_text(cant_promote, parse_mode=ParseMode.HTML)
        except Exception as e:
            LOGGER.error(f"Error checking promote permissions: {e}")
            await update.effective_message.reply_text("Error checking promote permissions!")
            
    return cast(F, promote_rights)

def can_restrict(func: F) -> F:
    @wraps(func)
    async def restrict_rights(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        bot = context.bot
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            cant_restrict = "I can't restrict people here!\nMake sure I'm admin and can restrict users."
        else:
            cant_restrict = f"I can't restrict people in <b>{update_chat_title}</b>!\nMake sure I'm admin there and can restrict users."

        try:
            bot_member = await chat.get_member(bot.id)
            if bot_member.can_restrict_members:
                return await func(update, context, *args, **kwargs)
            await update.effective_message.reply_text(cant_restrict, parse_mode=ParseMode.HTML)
        except Exception as e:
            LOGGER.error(f"Error checking restrict permissions: {e}")
            await update.effective_message.reply_text("Error checking restrict permissions!")
            
    return cast(F, restrict_rights)

def user_can_ban(func: F) -> F:
    @wraps(func)
    async def user_is_banhammer(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        
        if not user:
            return
            
        try:
            member = await chat.get_member(user.id)
            if (member.can_restrict_members or 
                member.status == ChatMemberStatus.OWNER or
                user.id in DRAGONS or
                user.id in ANONYMOUS_ADMINS):
                return await func(update, context, *args, **kwargs)
                
            await update.effective_message.reply_text(
                "Sorry son, but you're not worthy to wield the banhammer.",
            )
        except Exception as e:
            LOGGER.error(f"Error checking ban permissions: {e}")
            await update.effective_message.reply_text("Error checking your permissions!")
            
    return cast(F, user_is_banhammer)

def connection_status(func: F) -> F:
    @wraps(func)
    async def connected_status(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from Hina.modules.connection import connected
        
        conn = await connected(
            context.bot,
            update,
            update.effective_chat,
            update.effective_user.id,
            need_admin=False,
        )
        
        if isinstance(conn, dict):
            chat = await app.bot.get_chat(conn['chat_id'])
            update.__setattr__("_effective_chat", chat)
            return await func(update, context, *args, **kwargs)
            
        if update.effective_message.chat.type == ChatType.PRIVATE:
            await update.effective_message.reply_text(
                "Send /connect in a group that you and I have in common first.",
            )
            return

        return await func(update, context, *args, **kwargs)
        
    return cast(F, connected_status)
