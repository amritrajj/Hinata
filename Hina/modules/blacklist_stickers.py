from Hina.config import app
import html
from typing import Optional

import Hina.modules.sql.blsticker_sql as sql
from Hina.modules.connection import connected
from Hina.modules.disable import DisableAbleCommandHandler
from Hina.modules.helper_funcs.alternate import send_message
from Hina.modules.helper_funcs.chat_status import user_admin, user_not_admin
from Hina.modules.helper_funcs.misc import split_message
from Hina.modules.helper_funcs.string_handling import extract_time
from Hina.modules.log_channel import loggable
from Hina.modules.warns import warn
from telegram import Chat, ChatPermissions, Update, User
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.helpers import mention_html, mention_markdown

@loggable
async def blackliststicker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    bot = context.bot
    conn = await connected(bot, update, chat, user.id, need_admin=False)
    if conn:
        chat_id = conn
        chat_name = (await bot.getChat(conn)).title
    else:
        if chat.type == "private":
            return ""
        chat_id = chat.id
        chat_name = chat.title

    sticker_list = f"<b>List blacklisted stickers currently in {chat_name}:</b>\n"

    all_stickerlist = sql.get_chat_stickers(chat_id)

    if context.args and context.args[0].lower() == "copy":
        for trigger in all_stickerlist:
            sticker_list += f"<code>{html.escape(trigger)}</code>\n"
    else:
        for trigger in all_stickerlist:
            sticker_list += f" - <code>{html.escape(trigger)}</code>\n"

    split_text = split_message(sticker_list)
    for text in split_text:
        if sticker_list == f"<b>List blacklisted stickers currently in {chat_name}:</b>\n":
            await send_message(
                msg,
                f"There are no blacklist stickers in <b>{html.escape(chat_name)}</b>!",
                parse_mode=ParseMode.HTML,
            )
            return ""
        await send_message(msg, text, parse_mode=ParseMode.HTML)
    return ""

@user_admin
@loggable
async def add_blackliststicker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    bot = context.bot
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    words = msg.text.split(None, 1)
    conn = await connected(bot, update, chat, user.id)
    
    if conn:
        chat_id = conn
        chat_name = (await bot.getChat(conn)).title
    else:
        if chat.type == "private":
            return ""
        chat_id = chat.id
        chat_name = chat.title

    if len(words) > 1:
        text = words[1].replace("https://t.me/addstickers/", "")
        to_blacklist = list({trigger.strip() for trigger in text.split("\n") if trigger.strip()})

        added = 0
        for trigger in to_blacklist:
            try:
                await bot.getStickerSet(trigger)
                sql.add_to_stickers(chat_id, trigger.lower())
                added += 1
            except BadRequest:
                await send_message(
                    msg,
                    f"Sticker `{trigger}` can not be found!",
                    parse_mode=ParseMode.MARKDOWN,
                )

        if added == 0:
            return ""

        if len(to_blacklist) == 1:
            await send_message(
                msg,
                f"Sticker <code>{html.escape(to_blacklist[0])}</code> added to blacklist stickers in <b>{html.escape(chat_name)}</b>!",
                parse_mode=ParseMode.HTML,
            )
        else:
            await send_message(
                msg,
                f"<code>{added}</code> stickers added to blacklist sticker in <b>{html.escape(chat_name)}</b>!",
                parse_mode=ParseMode.HTML,
            )
    elif msg.reply_to_message and msg.reply_to_message.sticker:
        trigger = msg.reply_to_message.sticker.set_name
        if not trigger:
            await send_message(msg, "Sticker is invalid!")
            return ""

        try:
            await bot.getStickerSet(trigger)
            sql.add_to_stickers(chat_id, trigger.lower())
            await send_message(
                msg,
                f"Sticker <code>{trigger}</code> added to blacklist stickers in <b>{html.escape(chat_name)}</b>!",
                parse_mode=ParseMode.HTML,
            )
        except BadRequest:
            await send_message(
                msg,
                f"Sticker `{trigger}` can not be found!",
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        await send_message(msg, "Tell me what stickers you want to add to the blacklist.")
    return ""

@user_admin
@loggable
async def unblackliststicker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    bot = context.bot
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    words = msg.text.split(None, 1)
    conn = await connected(bot, update, chat, user.id)
    
    if conn:
        chat_id = conn
        chat_name = (await bot.getChat(conn)).title
    else:
        if chat.type == "private":
            return ""
        chat_id = chat.id
        chat_name = chat.title

    if len(words) > 1:
        text = words[1].replace("https://t.me/addstickers/", "")
        to_unblacklist = list({trigger.strip() for trigger in text.split("\n") if trigger.strip()})

        successful = 0
        for trigger in to_unblacklist:
            success = sql.rm_from_stickers(chat_id, trigger.lower())
            if success:
                successful += 1

        if len(to_unblacklist) == 1:
            if successful:
                await send_message(
                    msg,
                    f"Sticker <code>{html.escape(to_unblacklist[0])}</code> deleted from blacklist in <b>{html.escape(chat_name)}</b>!",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await send_message(msg, "This sticker is not on the blacklist...!")
        elif successful == len(to_unblacklist):
            await send_message(
                msg,
                f"Sticker <code>{successful}</code> deleted from blacklist in <b>{html.escape(chat_name)}</b>!",
                parse_mode=ParseMode.HTML,
            )
        elif not successful:
            await send_message(
                msg,
                "None of these stickers exist, so they cannot be removed.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await send_message(
                msg,
                f"Sticker <code>{successful}</code> deleted from blacklist. {len(to_unblacklist) - successful} did not exist, so it's not deleted.",
                parse_mode=ParseMode.HTML,
            )
    elif msg.reply_to_message and msg.reply_to_message.sticker:
        trigger = msg.reply_to_message.sticker.set_name
        if not trigger:
            await send_message(msg, "Sticker is invalid!")
            return ""

        if sql.rm_from_stickers(chat_id, trigger.lower()):
            await send_message(
                msg,
                f"Sticker <code>{trigger}</code> deleted from blacklist in <b>{chat_name}</b>!",
                parse_mode=ParseMode.HTML,
            )
        else:
            await send_message(
                msg,
                f"{trigger} not found on blacklisted stickers...!",
            )
    else:
        await send_message(msg, "Tell me what stickers you want to remove from the blacklist.")
    return ""

@loggable
@user_admin
async def blacklist_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    bot = context.bot
    conn = await connected(bot, update, chat, user.id, need_admin=True)
    
    if conn:
        chat_id = conn
        chat_name = (await bot.getChat(conn)).title
    else:
        if chat.type == "private":
            await send_message(msg, "This command can be used only in groups, not PM")
            return ""
        chat_id = chat.id
        chat_name = chat.title

    if context.args:
        if context.args[0].lower() in ["off", "nothing", "no"]:
            settypeblacklist = "turn off"
            sql.set_blacklist_strength(chat_id, 0, "0")
        elif context.args[0].lower() in ["del", "delete"]:
            settypeblacklist = "left, the message will be deleted"
            sql.set_blacklist_strength(chat_id, 1, "0")
        elif context.args[0].lower() == "warn":
            settypeblacklist = "warned"
            sql.set_blacklist_strength(chat_id, 2, "0")
        elif context.args[0].lower() == "mute":
            settypeblacklist = "muted"
            sql.set_blacklist_strength(chat_id, 3, "0")
        elif context.args[0].lower() == "kick":
            settypeblacklist = "kicked"
            sql.set_blacklist_strength(chat_id, 4, "0")
        elif context.args[0].lower() == "ban":
            settypeblacklist = "banned"
            sql.set_blacklist_strength(chat_id, 5, "0")
        elif context.args[0].lower() == "tban":
            if len(context.args) == 1:
                await send_message(
                    msg,
                    "You need to specify a time for temporary ban! Use like: `/blstickermode tban <time>`\n"
                    "Examples: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return ""
            settypeblacklist = f"temporary banned for {context.args[1]}"
            sql.set_blacklist_strength(chat_id, 6, str(context.args[1]))
        elif context.args[0].lower() == "tmute":
            if len(context.args) == 1:
                await send_message(
                    msg,
                    "You need to specify a time for temporary mute! Use like: `/blstickermode tmute <time>`\n"
                    "Examples: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return ""
            settypeblacklist = f"temporary muted for {context.args[1]}"
            sql.set_blacklist_strength(chat_id, 7, str(context.args[1]))
        else:
            await send_message(
                msg,
                "I only understand off/del/warn/ban/kick/mute/tban/tmute!",
            )
            return ""

        if conn:
            text = f"Blacklist sticker mode changed, users will be `{settypeblacklist}` at *{chat_name}*!"
        else:
            text = f"Blacklist sticker mode changed, users will be `{settypeblacklist}`!"
        await send_message(msg, text, parse_mode=ParseMode.MARKDOWN)
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Changed sticker blacklist mode. users will be {settypeblacklist}."
        )
    else:
        getmode, getvalue = sql.get_blacklist_setting(chat.id)
        if getmode == 0:
            settypeblacklist = "not active"
        elif getmode == 1:
            settypeblacklist = "delete"
        elif getmode == 2:
            settypeblacklist = "warn"
        elif getmode == 3:
            settypeblacklist = "mute"
        elif getmode == 4:
            settypeblacklist = "kick"
        elif getmode == 5:
            settypeblacklist = "ban"
        elif getmode == 6:
            settypeblacklist = f"temporarily banned for {getvalue}"
        elif getmode == 7:
            settypeblacklist = f"temporarily muted for {getvalue}"
        
        if conn:
            text = f"Blacklist sticker mode is currently set to *{settypeblacklist}* in *{chat_name}*."
        else:
            text = f"Blacklist sticker mode is currently set to *{settypeblacklist}*."
        await send_message(msg, text, parse_mode=ParseMode.MARKDOWN)
    return ""

@user_not_admin
async def del_blackliststicker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user
    
    if not message.sticker or not message.sticker.set_name:
        return
    
    getmode, value = sql.get_blacklist_setting(chat.id)
    chat_filters = sql.get_chat_stickers(chat.id)
    
    for trigger in chat_filters:
        if message.sticker.set_name.lower() == trigger.lower():
            try:
                if getmode == 0:
                    return
                elif getmode == 1:
                    await message.delete()
                elif getmode == 2:
                    await message.delete()
                    await warn(
                        user,
                        chat,
                        f"Using sticker '{trigger}' which in blacklist stickers",
                        message,
                        user,
                    )
                    return
                elif getmode == 3:
                    await message.delete()
                    await bot.restrict_chat_member(
                        chat.id,
                        user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                    )
                    await send_message(
                        chat,
                        f"{mention_markdown(user.id, user.first_name)} muted because using '{trigger}' which in blacklist stickers",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return
                elif getmode == 4:
                    await message.delete()
                    res = await chat.unban_member(user.id)
                    if res:
                        await send_message(
                            chat,
                            f"{mention_markdown(user.id, user.first_name)} kicked because using '{trigger}' which in blacklist stickers",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    return
                elif getmode == 5:
                    await message.delete()
                    await chat.ban_member(user.id)
                    await send_message(
                        chat,
                        f"{mention_markdown(user.id, user.first_name)} banned because using '{trigger}' which in blacklist stickers",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return
                elif getmode == 6:
                    await message.delete()
                    bantime = extract_time(message, value)
                    await chat.ban_member(user.id, until_date=bantime)
                    await send_message(
                        chat,
                        f"{mention_markdown(user.id, user.first_name)} banned for {value} because using '{trigger}' which in blacklist stickers",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return
                elif getmode == 7:
                    await message.delete()
                    mutetime = extract_time(message, value)
                    await bot.restrict_chat_member(
                        chat.id,
                        user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                        until_date=mutetime,
                    )
                    await send_message(
                        chat,
                        f"{mention_markdown(user.id, user.first_name)} muted for {value} because using '{trigger}' which in blacklist stickers",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return
            except BadRequest as excp:
                if excp.message != "Message to delete not found":
                    LOGGER.exception("Error while deleting blacklist message.")
            break

def __import_data__(chat_id, data):
    blacklist = data.get("sticker_blacklist", {})
    for trigger in blacklist:
        sql.add_to_stickers(chat_id, trigger)

def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)

def __chat_settings__(chat_id, user_id):
    blacklisted = sql.num_stickers_chat_filters(chat_id)
    return f"There are `{blacklisted}` blacklisted stickers."

def __stats__():
    return f"• {sql.num_stickers_filters()} blacklist stickers, across {sql.num_stickers_filter_chats()} chats."

__mod_name__ = "Stickers Blacklist"

BLACKLIST_STICKER_HANDLER = DisableAbleCommandHandler(
    "blsticker", blackliststicker, admin_ok=True
)
ADDBLACKLIST_STICKER_HANDLER = DisableAbleCommandHandler(
    "addblsticker", add_blackliststicker
)
UNBLACKLIST_STICKER_HANDLER = CommandHandler(
    ["unblsticker", "rmblsticker"], unblackliststicker
)
BLACKLISTMODE_HANDLER = CommandHandler("blstickermode", blacklist_mode)
BLACKLIST_STICKER_DEL_HANDLER = MessageHandler(
    filters.Sticker.ALL & filters.ChatType.GROUPS, 
    del_blackliststicker
)

app.add_handler(BLACKLIST_STICKER_HANDLER)
app.add_handler(ADDBLACKLIST_STICKER_HANDLER)
app.add_handler(UNBLACKLIST_STICKER_HANDLER)
app.add_handler(BLACKLISTMODE_HANDLER)
app.add_handler(BLACKLIST_STICKER_DEL_HANDLER)
