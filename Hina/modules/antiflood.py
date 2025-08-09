from Hina.config import app
import html
from typing import Optional, List
import re

from telegram import Message, Chat, Update, User, ChatPermissions
from telegram.constants import ParseMode

from Hina.config import TIGERS, WOLVES, app
from Hina.modules.helper_funcs.chat_status import (
    bot_admin,
    is_user_admin,
    user_admin,
    user_admin_no_reply,
)
from Hina.modules.log_channel import loggable
from Hina.modules.sql import antiflood_sql as sql
from telegram.error import BadRequest
from telegram.ext import filters
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler, MessageHandler, BaseHandler
from telegram.helpers import mention_html
from Hina.modules.helper_funcs.string_handling import extract_time
from Hina.modules.connection import connected
from Hina.modules.helper_funcs.alternate import send_message
from Hina.modules.sql.approve_sql import is_approved

FLOOD_GROUP = 3


@loggable
async def check_flood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user = update.effective_user
    chat = update.effective_chat
    msg = update.effective_message
    if not user:
        return ""

    if await is_user_admin(chat, user.id) or user.id in WOLVES or user.id in TIGERS:
        sql.update_flood(chat.id, None)
        return ""
    if is_approved(chat.id, user.id):
        sql.update_flood(chat.id, None)
        return
    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        getmode, getvalue = sql.get_flood_setting(chat.id)
        if getmode == 1:
            await chat.ban_member(user.id)
            execstrings = "Banned"
            tag = "BANNED"
        elif getmode == 2:
            await chat.ban_member(user.id)
            await chat.unban_member(user.id)
            execstrings = "Kicked"
            tag = "KICKED"
        elif getmode == 3:
            await context.bot.restrict_chat_member(
                chat.id, user.id, permissions=ChatPermissions(can_send_messages=False),
            )
            execstrings = "Muted"
            tag = "MUTED"
        elif getmode == 4:
            bantime = extract_time(msg, getvalue)
            await chat.ban_member(user.id, until_date=bantime)
            execstrings = f"Banned for {getvalue}"
            tag = "TBAN"
        elif getmode == 5:
            mutetime = extract_time(msg, getvalue)
            await context.bot.restrict_chat_member(
                chat.id,
                user.id,
                until_date=mutetime,
                permissions=ChatPermissions(can_send_messages=False),
            )
            execstrings = f"Muted for {getvalue}"
            tag = "TMUTE"
        await send_message(
            update.effective_message, f"Beep Boop! Boop Beep!\n{execstrings}!",
        )

        return (
            f"<b>{tag}:</b>"
            "\n#{}"
            "\n<b>User:</b> {}"
            "\nFlooded the group.".format(
                html.escape(chat.title),
                mention_html(user.id, html.escape(user.first_name)),
            )
        )

    except BadRequest:
        await msg.reply_text(
            "I can't restrict people here, give me permissions first! Until then, I'll disable anti-flood.",
        )
        sql.set_flood(chat.id, 0)
        return (
            f"<b>{chat.title}:</b>"
            "\n#INFO"
            "\nDon't have enough permission to restrict users so automatically disabled anti-flood"
        )


@user_admin_no_reply
@bot_admin
async def flood_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    query = update.callback_query
    user = update.effective_user
    match = re.match(r"unmute_flooder\((.+?)\)", query.data)
    if match:
        user_id = match.group(1)
        chat = update.effective_chat.id
        try:
            await bot.restrict_chat_member(
                chat,
                int(user_id),
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            await update.effective_message.edit_text(
                f"Unmuted by {mention_html(user.id, html.escape(user.first_name))}.",
                parse_mode="HTML",
            )
        except Exception:
            pass


@user_admin
@loggable
async def set_flood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat_id = conn
        chat_name = (await app.bot.getChat(conn)).title
    else:
        if update.effective_message.chat.type == "private":
            await send_message(
                update.effective_message,
                "This command is meant to use in group not in PM",
            )
            return ""
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if len(args) >= 1:
        val = args[0].lower()
        if val in ["off", "no", "0"]:
            sql.set_flood(chat_id, 0)
            if conn:
                await message.reply_text(
                    f"Antiflood has been disabled in {chat_name}.",
                )
            else:
                await message.reply_text("Antiflood has been disabled.")

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat_id, 0)
                if conn:
                    await message.reply_text(
                        f"Antiflood has been disabled in {chat_name}.",
                    )
                else:
                    await message.reply_text("Antiflood has been disabled.")
                return (
                    f"<b>{html.escape(chat_name)}:</b>"
                    "\n#SETFLOOD"
                    f"\n<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}"
                    "\nDisable antiflood."
                )

            elif amount <= 3:
                await send_message(
                    update.effective_message,
                    "Antiflood must be either 0 (disabled) or number greater than 3!",
                )
                return ""

            else:
                sql.set_flood(chat_id, amount)
                if conn:
                    await message.reply_text(
                        f"Anti-flood has been set to {amount} in chat: {chat_name}",
                    )
                else:
                    await message.reply_text(
                        f"Successfully updated anti-flood limit to {amount}!",
                    )
                return (
                    f"<b>{html.escape(chat_name)}:</b>"
                    "\n#SETFLOOD"
                    f"\n<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}"
                    f"\nSet antiflood to <code>{amount}</code>."
                )

        else:
            await message.reply_text("Invalid argument please use a number, 'off' or 'no'")
    else:
        await message.reply_text(
            (
                "Use `/setflood number` to enable anti-flood.\nOr use `/setflood off` to disable antiflood!."
            ),
            parse_mode="markdown",
        )
    return ""


async def flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    conn = connected(context.bot, update, chat, user.id, need_admin=False)
    if conn:
        chat_id = conn
        chat_name = (await app.bot.getChat(conn)).title
    else:
        if update.effective_message.chat.type == "private":
            await send_message(
                update.effective_message,
                "This command is meant to use in group not in PM",
            )
            return
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        if conn:
            await msg.reply_text(
                f"I'm not enforcing any flood control in {chat_name}!",
            )
        else:
            await msg.reply_text("I'm not enforcing any flood control here!")
    else:
        if conn:
            await msg.reply_text(
                f"I'm currently restricting members after {limit} consecutive messages in {chat_name}.",
            )
        else:
            await msg.reply_text(
                f"I'm currently restricting members after {limit} consecutive messages.",
            )


@user_admin
async def set_flood_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = await app.bot.getChat(conn)
        chat_id = conn
        chat_name = chat.title
    else:
        if update.effective_message.chat.type == "private":
            await send_message(
                update.effective_message,
                "This command is meant to use in group not in PM",
            )
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if args:
        if args[0].lower() == "ban":
            settypeflood = "ban"
            sql.set_flood_strength(chat_id, 1, "0")
        elif args[0].lower() == "kick":
            settypeflood = "kick"
            sql.set_flood_strength(chat_id, 2, "0")
        elif args[0].lower() == "mute":
            settypeflood = "mute"
            sql.set_flood_strength(chat_id, 3, "0")
        elif args[0].lower() == "tban":
            if len(args) == 1:
                teks = """It looks like you tried to set time value for antiflood but you didn't specified time; Try, `/setfloodmode tban <timevalue>`.
Examples of time value: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks."""
                await send_message(update.effective_message, teks, parse_mode="markdown")
                return
            settypeflood = f"tban for {args[1]}"
            sql.set_flood_strength(chat_id, 4, str(args[1]))
        elif args[0].lower() == "tmute":
            if len(args) == 1:
                teks = """It looks like you tried to set time value for antiflood but you didn't specified time; Try, `/setfloodmode tmute <timevalue>`.
Examples of time value: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks."""
                await send_message(update.effective_message, teks, parse_mode="markdown")
                return
            settypeflood = f"tmute for {args[1]}"
            sql.set_flood_strength(chat_id, 5, str(args[1]))
        else:
            await send_message(
                update.effective_message, "I only understand ban/kick/mute/tban/tmute!",
            )
            return
        if conn:
            await msg.reply_text(
                f"Exceeding consecutive flood limit will result in {settypeflood} in {chat_name}!",
            )
        else:
            await msg.reply_text(
                f"Exceeding consecutive flood limit will result in {settypeflood}!",
            )
        return (
            f"<b>{settypeflood}:</b>\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            "Has changed antiflood mode. User will {}.".format(settypeflood)
        )
    else:
        getmode, getvalue = sql.get_flood_setting(chat.id)
        if getmode == 1:
            settypeflood = "ban"
        elif getmode == 2:
            settypeflood = "kick"
        elif getmode == 3:
            settypeflood = "mute"
        elif getmode == 4:
            settypeflood = f"tban for {getvalue}"
        elif getmode == 5:
            settypeflood = f"tmute for {getvalue}"
        if conn:
            await msg.reply_text(
                f"Sending more messages than flood limit will result in {settypeflood} in {chat_name}.",
            )
        else:
            await msg.reply_text(
                f"Sending more message than flood limit will result in {settypeflood}.",
            )
    return ""


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        return "Not enforcing to flood control."
    else:
        return f"Antiflood has been set to`{limit}`."


# [Previous imports and functions remain exactly the same...]

# Handlers
FLOOD_BAN_HANDLER = MessageHandler(
    filters.ALL & ~filters.StatusUpdate.ALL & filters.ChatType.GROUPS, 
    check_flood
)
FLOOD_QUERY_HANDLER = CallbackQueryHandler(flood_button, pattern=r"unmute_flooder_")
SET_FLOOD_HANDLER = CommandHandler("setflood", set_flood, filters=filters.ChatType.GROUPS)
FLOOD_HANDLER = CommandHandler("flood", flood, filters=filters.ChatType.GROUPS)
SET_FLOOD_MODE_HANDLER = CommandHandler("setfloodmode", set_flood_mode, filters=filters.ChatType.GROUPS)

def setup_antiflood_handlers(application):
    """Register antiflood handlers"""
    application.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
    application.add_handler(FLOOD_QUERY_HANDLER)
    application.add_handler(SET_FLOOD_HANDLER)
    application.add_handler(SET_FLOOD_MODE_HANDLER)
    application.add_handler(FLOOD_HANDLER)

__mod_name__ = "Anti-Flood"
__help__ = """
🛡️ *Anti-Flood Protection* 🛡️

Prevent spam by restricting users who send too many consecutive messages.

*Commands:*
• `/flood` - Check current flood settings
• `/setflood <number/off>` - Set message limit (e.g. `/setflood 10`)
• `/setfloodmode <action>` - Set punishment:
  `ban`/`kick`/`mute`/`tban 30m`/`tmute 1h`

*Examples:*
- `/setflood 5` + `/setfloodmode mute` = Mute after 5 rapid messages
- `/setflood off` = Disable protection
"""

__handlers__ = [
    (FLOOD_BAN_HANDLER, FLOOD_GROUP),
    SET_FLOOD_HANDLER,
    FLOOD_HANDLER,
    SET_FLOOD_MODE_HANDLER,
    FLOOD_QUERY_HANDLER
]

# Initialize
setup_antiflood_handlers(app)
