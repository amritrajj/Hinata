from Hina.config import app as app
import time
import re
from typing import Optional

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update, Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

import Hina.modules.sql.connection_sql as sql
from Hina.modules.helper_funcs import chat_status
from Hina.modules.helper_funcs.alternate import send_message, typing_action

user_admin = chat_status.user_admin

@user_admin
@typing_action
async def allow_connections(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    args = context.args

    if chat.type == chat.PRIVATE:
        await send_message(
            update.effective_message,
            "This command is for group only. Not in PM!",
        )
        return

    if not args:
        get_settings = sql.allow_connect_to_chat(chat.id)
        await send_message(
            update.effective_message,
            "Connections to this group are *Allowed* for members!" if get_settings 
            else "Connection to this group are *Not Allowed* for members!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    var = args[0].lower()
    if var not in ("yes", "no"):
        await send_message(
            update.effective_message,
            "Please enter `yes` or `no`!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    sql.set_allow_connect_to_chat(chat.id, var == "yes")
    await send_message(
        update.effective_message,
        f"Connection has been {'enabled' if var == 'yes' else 'disabled'} for this chat",
    )

@typing_action
async def connection_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user

    conn = await connected(context.bot, update, chat, user.id, need_admin=True)
    chat_name = (await context.bot.getChat(conn)).title if conn else update.effective_message.chat.title

    message = (
        f"You are currently connected to {chat_name}.\n" if conn 
        else "You are currently not connected in any group.\n"
    )
    await send_message(update.effective_message, message, parse_mode="markdown")

@typing_action
async def connect_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    args = context.args

    if chat.type != "private":
        if not args:
            await handle_group_connection(update, context)
            return

        if args[0].lower() in ("help", "h"):
            await help_connect_chat(update, context)
            return

    if not args:
        await show_connection_history(update, context)
        return

    try:
        connect_chat = int(args[0]) if args[0].isdigit() else args[0]
        chat_obj = await context.bot.getChat(connect_chat)
        connect_chat = chat_obj.id
        getstatusadmin = await context.bot.get_chat_member(connect_chat, user.id)
    except (ValueError, BadRequest):
        await send_message(update.effective_message, "Invalid Chat ID!")
        return

    isadmin = getstatusadmin.status in ("administrator", "creator")
    ismember = getstatusadmin.status == "member"
    isallow = sql.allow_connect_to_chat(connect_chat)

    if not (isadmin or (isallow and ismember) or (user.id in DRAGONS)):
        await send_message(
            update.effective_message,
            "Connection to this chat is not allowed!",
        )
        return

    if sql.connect(user.id, connect_chat):
        conn_chat = await app.bot.getChat(connect_chat)
        chat_name = conn_chat.title
        await send_message(
            update.effective_message,
            f"Successfully connected to *{chat_name}*.\nUse /helpconnect to check available commands.",
            parse_mode=ParseMode.MARKDOWN,
        )
        await sql.add_history_conn(user.id, str(conn_chat.id), chat_name)
    else:
        await send_message(update.effective_message, "Connection failed!")

async def handle_group_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user

    getstatusadmin = await context.bot.get_chat_member(chat.id, user.id)
    isadmin = getstatusadmin.status in ("administrator", "creator")
    ismember = getstatusadmin.status == "member"
    isallow = sql.allow_connect_to_chat(chat.id)

    if not (isadmin or (isallow and ismember) or (user.id in DRAGONS)):
        await send_message(
            update.effective_message,
            "Connection to this chat is not allowed!",
        )
        return

    if sql.connect(user.id, chat.id):
        chat_name = (await context.bot.getChat(chat.id)).title
        await send_message(
            update.effective_message,
            f"Successfully connected to *{chat_name}*.",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            await sql.add_history_conn(user.id, str(chat.id), chat_name)
            await context.bot.send_message(
                user.id,
                f"You are connected to *{chat_name}*. \nUse `/helpconnect` to check available commands.",
                parse_mode="markdown",
            )
        except (BadRequest, TelegramError):
            pass
    else:
        await send_message(update.effective_message, "Connection failed!")

async def show_connection_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    gethistory = sql.get_history_conn(user.id)

    if not gethistory:
        text = "Write the chat ID or tag to connect!"
        buttons = []
    else:
        text = "You are currently not connected to any group.\n\n*Connection history:*\n"
        text += "╒═══「 *Info* 」\n│  Sorted: `Newest`\n│\n"
        buttons = [
            InlineKeyboardButton("❎ Close", callback_data="connect_close"),
            InlineKeyboardButton("🧹 Clear", callback_data="connect_clear"),
        ]

        for x in sorted(gethistory.keys(), reverse=True):
            htime = time.strftime("%d/%m/%Y", time.localtime(x))
            text += f"╞═「 *{gethistory[x]['chat_name']}* 」\n│   `{gethistory[x]['chat_id']}`\n│   `{htime}`\n│\n"
            buttons.append([
                InlineKeyboardButton(
                    gethistory[x]["chat_name"],
                    callback_data=f"connect({gethistory[x]['chat_id']})",
                )
            ])

        text += f"╘══「 Total {len(gethistory)} Chats 」"
        buttons = [buttons[:2]] + buttons[2:]

    conn = await connected(context.bot, update, chat, user.id, need_admin=False)
    if conn:
        connectedchat = await app.bot.getChat(conn)
        text = f"You are currently connected to *{connectedchat.title}* (`{conn}`)"
        buttons.append(InlineKeyboardButton("🔌 Disconnect", callback_data="connect_disconnect"))

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    await send_message(
        update.effective_message,
        text,
        parse_mode="markdown",
        reply_markup=reply_markup,
    )

async def disconnect_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        await send_message(update.effective_message, "This command is only available in PM.")
        return

    if sql.disconnect(update.effective_message.from_user.id):
        await send_message(update.effective_message, "Disconnected from chat!")
    else:
        await send_message(update.effective_message, "You're not connected!")

async def connected(bot: Bot, update: Update, chat, user_id: int, need_admin: bool = True) -> Optional[Dict[str, Any]]:
    user = update.effective_user

    if chat.type == chat.PRIVATE:
        conn = sql.get_connected_chat(user_id)
        if not conn:
            return None

        try:
            # Get chat and verify connection
            chat_obj = await bot.get_chat(conn.chat_id)
            getstatusadmin = await bot.get_chat_member(chat_obj.id, user.id)
            
            isadmin = getstatusadmin.status in ("administrator", "creator")
            ismember = getstatusadmin.status == "member"
            isallow = sql.allow_connect_to_chat(chat_obj.id)

            if not (isadmin or (isallow and ismember) or (user.id in DRAGONS) or (user.id in DEV_USERS)):
                await send_message(
                    update.effective_message,
                    "Connection rights changed. Disconnecting you.",
                )
                await disconnect_chat(update, bot)
                return None

            return {
                'chat_id': chat_obj.id,
                'chat_title': chat_obj.title,
                'chat_type': chat_obj.type
            }
        except (BadRequest, TelegramError) as e:
            LOGGER.error(f"Connection error: {e}")
            return None
    return None

CONN_HELP = """
Actions are available with connected groups:
• View and edit Notes.
• View and edit filters.
• Get invite link of chat.
• Set and control AntiFlood settings.
• Set and control Blacklist settings.
• Set Locks and Unlocks in chat.
• Enable and Disable commands in chat.
• Export and Imports of chat backup.
• More in future!"""

async def help_connect_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message.chat.type != "private":
        await send_message(update.effective_message, "PM me with that command to get help.")
        return
    await send_message(update.effective_message, CONN_HELP, parse_mode="markdown")

async def connect_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat = update.effective_chat
    user = update.effective_user

    connect_match = re.match(r"connect\((.+?)\)", query.data)
    if connect_match:
        target_chat = connect_match.group(1)
        await handle_connect_button(query, context, user, target_chat)
    elif query.data == "connect_disconnect":
        await handle_disconnect_button(query, context)
    elif query.data == "connect_clear":
        await handle_clear_button(query, context)
    elif query.data == "connect_close":
        await handle_close_button(query)
    else:
        await connect_chat(update, context)

async def handle_connect_button(query, context, user, target_chat):
    try:
        getstatusadmin = await context.bot.get_chat_member(target_chat, user.id)
        isadmin = getstatusadmin.status in ("administrator", "creator")
        ismember = getstatusadmin.status == "member"
        isallow = sql.allow_connect_to_chat(target_chat)
    except BadRequest:
        await context.bot.answer_callback_query(
            query.id,
            "Invalid Chat ID!",
            show_alert=True,
        )
        return

    if not (isadmin or (isallow and ismember) or (user.id in DRAGONS)):
        await context.bot.answer_callback_query(
            query.id,
            "Connection to this chat is not allowed!",
            show_alert=True,
        )
        return

    if sql.connect(user.id, target_chat):
        conn_chat = await app.bot.getChat(target_chat)
        await query.message.edit_text(
            f"Successfully connected to *{conn_chat.title}*.\nUse `/helpconnect` to check available commands.",
            parse_mode=ParseMode.MARKDOWN,
        )
        await sql.add_history_conn(user.id, str(conn_chat.id), conn_chat.title)
    else:
        await query.message.edit_text("Connection failed!")

async def handle_disconnect_button(query, context):
    if sql.disconnect(query.from_user.id):
        await query.message.edit_text("Disconnected from chat!")
    else:
        await context.bot.answer_callback_query(
            query.id,
            "You're not connected!",
            show_alert=True,
        )

async def handle_clear_button(query, context):
    sql.clear_history_conn(query.from_user.id)
    await query.message.edit_text("History connected has been cleared!")

async def handle_close_button(query):
    await query.message.edit_text("Closed.\nTo open again, type /connect")

__mod_name__ = "Connection"

__help__ = """
Sometimes, you just want to add some notes and filters to a group chat, but you don't want everyone to see; This is where connections come in...
This allows you to connect to a chat's database, and add things to it without the commands appearing in chat! For obvious reasons, you need to be an admin to add things; but any member in the group can view your data.

• /connect: Connects to chat (Can be done in a group by /connect or /connect <chat id> in PM)
• /connection: List connected chats
• /disconnect: Disconnect from a chat
• /helpconnect: List available commands that can be used remotely

*Admin only:*
• /allowconnect <yes/no>: allow a user to connect to a chat
"""

CONNECT_CHAT_HANDLER = CommandHandler("connect", connect_chat)
CONNECTION_CHAT_HANDLER = CommandHandler("connection", connection_chat)
DISCONNECT_CHAT_HANDLER = CommandHandler("disconnect", disconnect_chat)
ALLOW_CONNECTIONS_HANDLER = CommandHandler("allowconnect", allow_connections)
HELP_CONNECT_CHAT_HANDLER = CommandHandler("helpconnect", help_connect_chat)
CONNECT_BTN_HANDLER = CallbackQueryHandler(connect_button, pattern=r"connect")

app.add_handler(CONNECT_CHAT_HANDLER)
app.add_handler(CONNECTION_CHAT_HANDLER)
app.add_handler(DISCONNECT_CHAT_HANDLER)
app.add_handler(ALLOW_CONNECTIONS_HANDLER)
app.add_handler(HELP_CONNECT_CHAT_HANDLER)
app.add_handler(CONNECT_BTN_HANDLER)
