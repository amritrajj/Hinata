from sqlalchemy import Column, Integer, String, UnicodeText
from Hina.config import app
import html

from telegram import Update, Chat, ChatPermissions, MessageEntity
from telegram.constants import ParseMode, ChatType
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.helpers import mention_html

from alphabet_detector import AlphabetDetector

import Hina.modules.sql.locks_sql as sql
from Hina.modules.disable import DisableAbleCommandHandler
from Hina.modules.helper_funcs.chat_status import (
    can_delete,
    is_user_admin,
    user_not_admin,
    is_bot_admin,
    user_admin,
)
from Hina.modules.log_channel import loggable
from Hina.modules.connection import connected
from Hina.modules.sql.approve_sql import is_approved
from Hina.modules.helper_funcs.alternate import send_message, typing_action

ad = AlphabetDetector()

LOCK_TYPES = {
    "audio": filters.AUDIO,
    "voice": filters.VOICE,
    "document": filters.Document.ALL,
    "video": filters.VIDEO,
    "contact": filters.CONTACT,
    "photo": filters.PHOTO,
    "url": filters.Entity(MessageEntity.URL) | filters.CaptionEntity(MessageEntity.URL),
    "bots": filters.StatusUpdate.NEW_CHAT_MEMBERS,
    "forward": filters.FORWARDED,
    "game": filters.GAME,
    "location": filters.LOCATION,
    "egame": filters.Dice.ALL,
    "rtl": "rtl",
    "button": "button",
    "inline": "inline",
}

LOCK_CHAT_RESTRICTION = {
    "all": {
        "can_send_messages": False,
        "can_send_media_messages": False,
        "can_send_polls": False,
        "can_send_other_messages": False,
        "can_add_web_page_previews": False,
        "can_change_info": False,
        "can_invite_users": False,
        "can_pin_messages": False,
    },
    "messages": {"can_send_messages": False},
    "media": {"can_send_media_messages": False},
    "sticker": {"can_send_other_messages": False},
    "gif": {"can_send_other_messages": False},
    "poll": {"can_send_polls": False},
    "other": {"can_send_other_messages": False},
    "previews": {"can_add_web_page_previews": False},
    "info": {"can_change_info": False},
    "invite": {"can_invite_users": False},
    "pin": {"can_pin_messages": False},
}

UNLOCK_CHAT_RESTRICTION = {
    "all": {
        "can_send_messages": True,
        "can_send_media_messages": True,
        "can_send_polls": True,
        "can_send_other_messages": True,
        "can_add_web_page_previews": True,
        "can_invite_users": True,
    },
    "messages": {"can_send_messages": True},
    "media": {"can_send_media_messages": True},
    "sticker": {"can_send_other_messages": True},
    "gif": {"can_send_other_messages": True},
    "poll": {"can_send_polls": True},
    "other": {"can_send_other_messages": True},
    "previews": {"can_add_web_page_previews": True},
    "info": {"can_change_info": True},
    "invite": {"can_invite_users": True},
    "pin": {"can_pin_messages": True},
}

PERM_GROUP = 1
REST_GROUP = 2

async def restr_members(
    bot,
    chat_id,
    members,
    messages=False,
    media=False,
    other=False,
    previews=False,
):
    for mem in members:
        if mem.user in DRAGONS:
            continue
        try:
            await bot.restrict_chat_member(
                chat_id,
                mem.user.id,
                permissions=ChatPermissions(
                    can_send_messages=messages,
                    can_send_media_messages=media,
                    can_send_polls=messages,
                    can_send_other_messages=other,
                    can_add_web_page_previews=previews,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                ),
            )
        except TelegramError:
            pass

async def unrestr_members(
    bot,
    chat_id,
    members,
    messages=True,
    media=True,
    other=True,
    previews=True,
):
    for mem in members:
        try:
            await bot.restrict_chat_member(
                chat_id,
                mem.user.id,
                permissions=ChatPermissions(
                    can_send_messages=messages,
                    can_send_media_messages=media,
                    can_send_polls=messages,
                    can_send_other_messages=other,
                    can_add_web_page_previews=previews,
                    can_change_info=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                ),
            )
        except TelegramError:
            pass

async def locktypes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "\n • ".join(
            ["Locks available: "] + sorted(list(LOCK_TYPES) + list(LOCK_CHAT_RESTRICTION))
        )
    )
@user_admin
@loggable
@typing_action
async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user

    if (
        await can_delete(chat, context.bot.id)
        or update.effective_message.chat.type == ChatType.PRIVATE
    ):
        if len(args) >= 1:
            ltype = args[0].lower()
            if ltype in LOCK_TYPES:
                # Connection check
                conn = await connected(context.bot, update, chat, user.id, need_admin=True)
                if conn:
                    chat = await context.bot.get_chat(conn)
                    chat_id = conn
                    chat_name = chat.title
                    text = f"Locked {ltype} for non-admins in {chat_name}!"
                else:
                    if update.effective_message.chat.type == ChatType.PRIVATE:
                        await send_message(
                            update.effective_message,
                            "This command is meant to use in group not in PM",
                        )
                        return ""
                    chat = update.effective_chat
                    chat_id = update.effective_chat.id
                    chat_name = update.effective_message.chat.title
                    text = f"Locked {ltype} for non-admins!"
                sql.update_lock(chat.id, ltype, locked=True)
                await send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)

                return (
                    "<b>{}:</b>"
                    "\n#LOCK"
                    "\n<b>Admin:</b> {}"
                    "\nLocked <code>{}</code>.".format(
                        html.escape(chat.title),
                        mention_html(user.id, user.first_name),
                        ltype,
                    )
                )

            elif ltype in LOCK_CHAT_RESTRICTION:
                # Connection check
                conn = await connected(context.bot, update, chat, user.id, need_admin=True)
                if conn:
                    chat = await context.bot.get_chat(conn)
                    chat_id = conn
                    chat_name = chat.title
                    text = f"Locked {ltype} for all non-admins in {chat_name}!"
                else:
                    if update.effective_message.chat.type == ChatType.PRIVATE:
                        await send_message(
                            update.effective_message,
                            "This command is meant to use in group not in PM",
                        )
                        return ""
                    chat = update.effective_chat
                    chat_id = update.effective_chat.id
                    chat_name = update.effective_message.chat.title
                    text = f"Locked {ltype} for all non-admins!"

                current_permission = (await context.bot.get_chat(chat_id)).permissions
                await context.bot.set_chat_permissions(
                    chat_id=chat_id,
                    permissions=get_permission_list(
                        current_permission,
                        LOCK_CHAT_RESTRICTION[ltype.lower()],
                    ),
                )

                await send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
                return (
                    "<b>{}:</b>"
                    "\n#Permission_LOCK"
                    "\n<b>Admin:</b> {}"
                    "\nLocked <code>{}</code>.".format(
                        html.escape(chat.title),
                        mention_html(user.id, user.first_name),
                        ltype,
                    )
                )

            else:
                await send_message(
                    update.effective_message,
                    "What are you trying to lock...? Try /locktypes for the list of lockables",
                )
        else:
            await send_message(update.effective_message, "What are you trying to lock...?")

    else:
        await send_message(
            update.effective_message,
            "I am not administrator or haven't got enough rights.",
        )

    return ""

@user_admin
@loggable
@typing_action
async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    if await is_user_admin(chat, message.from_user.id):
        if len(args) >= 1:
            ltype = args[0].lower()
            if ltype in LOCK_TYPES:
                # Connection check
                conn = await connected(context.bot, update, chat, user.id, need_admin=True)
                if conn:
                    chat = await context.bot.get_chat(conn)
                    chat_id = conn
                    chat_name = chat.title
                    text = f"Unlocked {ltype} for everyone in {chat_name}!"
                else:
                    if update.effective_message.chat.type == ChatType.PRIVATE:
                        await send_message(
                            update.effective_message,
                            "This command is meant to use in group not in PM",
                        )
                        return ""
                    chat = update.effective_chat
                    chat_id = update.effective_chat.id
                    chat_name = update.effective_message.chat.title
                    text = f"Unlocked {ltype} for everyone!"
                sql.update_lock(chat.id, ltype, locked=False)
                await send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
                return (
                    "<b>{}:</b>"
                    "\n#UNLOCK"
                    "\n<b>Admin:</b> {}"
                    "\nUnlocked <code>{}</code>.".format(
                        html.escape(chat.title),
                        mention_html(user.id, user.first_name),
                        ltype,
                    )
                )

            elif ltype in UNLOCK_CHAT_RESTRICTION:
                # Connection check
                conn = await connected(context.bot, update, chat, user.id, need_admin=True)
                if conn:
                    chat = await context.bot.get_chat(conn)
                    chat_id = conn
                    chat_name = chat.title
                    text = f"Unlocked {ltype} for everyone in {chat_name}!"
                else:
                    if update.effective_message.chat.type == ChatType.PRIVATE:
                        await send_message(
                            update.effective_message,
                            "This command is meant to use in group not in PM",
                        )
                        return ""
                    chat = update.effective_chat
                    chat_id = update.effective_chat.id
                    chat_name = update.effective_message.chat.title
                    text = f"Unlocked {ltype} for everyone!"

                can_change_info = (await chat.get_member(context.bot.id)).can_change_info
                if not can_change_info:
                    await send_message(
                        update.effective_message,
                        "I don't have permission to change group info.",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return

                current_permission = (await context.bot.get_chat(chat_id)).permissions
                await context.bot.set_chat_permissions(
                    chat_id=chat_id,
                    permissions=get_permission_list(
                        current_permission,
                        UNLOCK_CHAT_RESTRICTION[ltype.lower()],
                    ),
                )

                await send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)

                return (
                    "<b>{}:</b>"
                    "\n#UNLOCK"
                    "\n<b>Admin:</b> {}"
                    "\nUnlocked <code>{}</code>.".format(
                        html.escape(chat.title),
                        mention_html(user.id, user.first_name),
                        ltype,
                    )
                )
            else:
                await send_message(
                    update.effective_message,
                    "What are you trying to unlock...? Try /locktypes for the list of lockables.",
                )

        else:
            await send_message(update.effective_message, "What are you trying to unlock...?")

    return ""

@user_not_admin
async def del_lockables(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user
    if is_approved(chat.id, user.id):
        return
    for lockable, filter in LOCK_TYPES.items():
        if lockable == "rtl":
            if sql.is_locked(chat.id, lockable) and await can_delete(chat, context.bot.id):
                if message.caption:
                    check = ad.detect_alphabet(f"{message.caption}")
                    if "ARABIC" in check:
                        try:
                            await message.delete()
                        except BadRequest as excp:
                            if excp.message == "Message to delete not found":
                                pass
                            else:
                                LOGGER.exception("ERROR in lockables")
                        break
                if message.text:
                    check = ad.detect_alphabet(f"{message.text}")
                    if "ARABIC" in check:
                        try:
                            await message.delete()
                        except BadRequest as excp:
                            if excp.message == "Message to delete not found":
                                pass
                            else:
                                LOGGER.exception("ERROR in lockables")
                        break
            continue
        if lockable == "button":
            if sql.is_locked(chat.id, lockable) and await can_delete(chat, context.bot.id):
                if message.reply_markup and message.reply_markup.inline_keyboard:
                    try:
                        await message.delete()
                    except BadRequest as excp:
                        if excp.message == "Message to delete not found":
                            pass
                        else:
                            LOGGER.exception("ERROR in lockables")
                    break
            continue
        if lockable == "inline":
            if sql.is_locked(chat.id, lockable) and await can_delete(chat, context.bot.id):
                if message and message.via_bot:
                    try:
                        await message.delete()
                    except BadRequest as excp:
                        if excp.message == "Message to delete not found":
                            pass
                        else:
                            LOGGER.exception("ERROR in lockables")
                    break
            continue
        if (
            await filter(update)
            and sql.is_locked(chat.id, lockable)
            and await can_delete(chat, context.bot.id)
        ):
            if lockable == "bots":
                new_members = update.effective_message.new_chat_members
                for new_mem in new_members:
                    if new_mem.is_bot:
                        if not await is_bot_admin(chat, context.bot.id):
                            await send_message(
                                update.effective_message,
                                "I see a bot and I've been told to stop them from joining..."
                                "but I'm not admin!",
                            )
                            return

                        await chat.ban_member(new_mem.id)
                        await send_message(
                            update.effective_message,
                            "Only admins are allowed to add bots in this chat! Get outta here.",
                        )
                        break
            else:
                try:
                    await message.delete()
                except BadRequest as excp:
                    if excp.message == "Message to delete not found":
                        pass
                    else:
                        LOGGER.exception("ERROR in lockables")

                break

def build_lock_message(chat_id):
    locks = sql.get_locks(chat_id)
    res = ""
    locklist = []
    permslist = []
    if locks:
        res += "*" + "These are the current locks in this Chat:" + "*"
        if locks:
            locklist.append(f"sticker = `{locks.sticker}`")
            locklist.append(f"audio = `{locks.audio}`")
            locklist.append(f"voice = `{locks.voice}`")
            locklist.append(f"document = `{locks.document}`")
            locklist.append(f"video = `{locks.video}`")
            locklist.append(f"contact = `{locks.contact}`")
            locklist.append(f"photo = `{locks.photo}`")
            locklist.append(f"gif = `{locks.gif}`")
            locklist.append(f"url = `{locks.url}`")
            locklist.append(f"bots = `{locks.bots}`")
            locklist.append(f"forward = `{locks.forward}`")
            locklist.append(f"game = `{locks.game}`")
            locklist.append(f"location = `{locks.location}`")
            locklist.append(f"rtl = `{locks.rtl}`")
            locklist.append(f"button = `{locks.button}`")
            locklist.append(f"egame = `{locks.egame}`")
            locklist.append(f"inline = `{locks.inline}`")
    permissions = app.bot.get_chat(chat_id).permissions
    permslist.append(f"messages = `{permissions.can_send_messages}`")
    permslist.append(f"media = `{permissions.can_send_media_messages}`")
    permslist.append(f"poll = `{permissions.can_send_polls}`")
    permslist.append(f"other = `{permissions.can_send_other_messages}`")
    permslist.append(f"previews = `{permissions.can_add_web_page_previews}`")
    permslist.append(f"info = `{permissions.can_change_info}`")
    permslist.append(f"invite = `{permissions.can_invite_users}`")
    permslist.append(f"pin = `{permissions.can_pin_messages}`")

    if locklist:
        locklist.sort()
        for x in locklist:
            res += "\n • {}".format(x)
    res += "\n\n*" + "These are the current chat permissions:" + "*"
    for x in permslist:
        res += "\n • {}".format(x)
    return res

@user_admin
@typing_action
async def list_locks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    conn = await connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = await context.bot.get_chat(conn)
        chat_name = chat.title
    else:
        if update.effective_message.chat.type == ChatType.PRIVATE:
            await send_message(
                update.effective_message,
                "This command is meant to use in group not in PM",
            )
            return ""
        chat = update.effective_chat
        chat_name = update.effective_message.chat.title

    res = build_lock_message(chat.id)
    if conn:
        res = res.replace("Locks in", f"*{chat_name}*")

    await send_message(update.effective_message, res, parse_mode=ParseMode.MARKDOWN)

def get_permission_list(current, new):
    permissions = {
        "can_send_messages": None,
        "can_send_media_messages": None,
        "can_send_polls": None,
        "can_send_other_messages": None,
        "can_add_web_page_previews": None,
        "can_change_info": None,
        "can_invite_users": None,
        "can_pin_messages": None,
    }
    permissions.update(current.__dict__)
    permissions.update(new)
    return ChatPermissions(**permissions)

def __import_data__(chat_id, data):
    locks = data.get("locks", {})
    for itemlock in locks:
        if itemlock in LOCK_TYPES:
            sql.update_lock(chat_id, itemlock, locked=True)
        elif itemlock in LOCK_CHAT_RESTRICTION:
            sql.update_restriction(chat_id, itemlock, locked=True)

def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)

def __chat_settings__(chat_id, user_id):
    return build_lock_message(chat_id)

__help__ = """
Do stickers annoy you? or want to avoid people sharing links? or pictures? \
You're in the right place!
The locks module allows you to lock away some common items in the \
telegram world; the bot will automatically delete them!

 • `/locktypes`*:* Lists all possible locktypes

*Admins only:*
 • `/lock <type>`*:* Lock items of a certain type (not available in private)
 • `/unlock <type>`*:* Unlock items of a certain type (not available in private)
 • `/locks`*:* The current list of locks in this chat.

Locks can be used to restrict a group's users.
eg:
Locking urls will auto-delete all messages with urls, locking stickers will restrict all \
non-admin users from sending stickers, etc.
Locking bots will stop non-admins from adding bots to the chat.

*Note:*
 • Unlocking permission *info* will allow members (non-admins) to change the group information, such as the description or the group name
 • Unlocking permission *pin* will allow members (non-admins) to pinned a message in a group
"""

__mod_name__ = "Locks"

LOCKTYPES_HANDLER = DisableAbleCommandHandler("locktypes", locktypes, block=False)
LOCK_HANDLER = CommandHandler("lock", lock, filters=filters.ChatType.GROUPS, block=False)
UNLOCK_HANDLER = CommandHandler("unlock", unlock, filters=filters.ChatType.GROUPS, block=False)
LOCKED_HANDLER = CommandHandler("locks", list_locks, filters=filters.ChatType.GROUPS, block=False)

app.add_handler(LOCK_HANDLER)
app.add_handler(UNLOCK_HANDLER)
app.add_handler(LOCKTYPES_HANDLER)
app.add_handler(LOCKED_HANDLER)

app.add_handler(
    MessageHandler(filters.ALL & filters.ChatType.GROUPS, del_lockables),
    group=PERM_GROUP,
)
