from Hina.config import app
import html
from telethon import TelegramClient
from Hina.config import ALLOW_EXCL
from Hina.modules.helper_funcs.handlers import CustomCommandHandler
from Hina.modules.disable import DisableAbleCommandHandler
from Hina.modules.helper_funcs.chat_status import (
    bot_can_delete,
    connection_status,
    dev_plus,
    user_admin,
)
from Hina.modules.sql import cleaner_sql as sql
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    BaseHandler,
    filters,
    Application,
    MessageHandler,
)

CMD_STARTERS = ("/", "!") if ALLOW_EXCL else "/"
BLUE_TEXT_CLEAN_GROUP = 13
CommandHandlerList = (CommandHandler, CustomCommandHandler, DisableAbleCommandHandler)

command_list = [
    "cleanblue",
    "ignoreblue",
    "unignoreblue",
    "listblue",
    "ungignoreblue",
    "gignoreblue",
    "start",
    "help",
    "settings",
    "donate",
    "stalk",
    "aka",
    "leaderboard",
]

# Collect all commands from registered handlers
for handler_list in app.handlers.values():
    for handler in handler_list:
        if isinstance(handler, CommandHandlerList):
            if hasattr(handler, "commands"):  # For newer PTB versions
                command_list.extend(handler.commands)
            elif hasattr(handler, "command"):  # For older versions
                command_list.extend(handler.command)

# Remove duplicates while preserving order
seen = set()
command_list = [cmd for cmd in command_list if not (cmd in seen or seen.add(cmd))]

async def clean_blue_text_must_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat = update.effective_chat
    message = update.effective_message
    
    if not message.text or not chat.get_member(bot.id).can_delete_messages:
        return
        
    if not sql.is_enabled(chat.id):
        return

    fst_word = message.text.strip().split(None, 1)[0]
    if len(fst_word) > 1 and any(fst_word.startswith(start) for start in CMD_STARTERS):
        command = fst_word[1:].split("@")[0]  # Remove bot username if present
        if sql.is_command_ignored(chat.id, command):
            return
            
        if command not in command_list:
            try:
                await message.delete()
            except BadRequest:
                pass

@connection_status
@bot_can_delete
@user_admin
async def set_blue_text_must_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    args = context.args
    
    if len(args) >= 1:
        val = args[0].lower()
        if val in ("off", "no"):
            sql.set_cleanbt(chat.id, False)
            reply = f"Bluetext cleaning has been disabled for <b>{html.escape(chat.title)}</b>"
        elif val in ("yes", "on"):
            sql.set_cleanbt(chat.id, True)
            reply = f"Bluetext cleaning has been enabled for <b>{html.escape(chat.title)}</b>"
        else:
            reply = "Invalid argument. Accepted values are 'yes', 'on', 'no', 'off'"
        await message.reply_text(reply, parse_mode=ParseMode.HTML)
    else:
        clean_status = "Enabled" if sql.is_enabled(chat.id) else "Disabled"
        reply = f"Bluetext cleaning for <b>{html.escape(chat.title)}</b> : <b>{clean_status}</b>"
        await message.reply_text(reply, parse_mode=ParseMode.HTML)

@user_admin
async def add_bluetext_ignore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    args = context.args
    
    if len(args) >= 1:
        val = args[0].lower()
        if sql.chat_ignore_command(chat.id, val):
            reply = f"<b>{val}</b> has been added to bluetext cleaner ignore list."
        else:
            reply = "Command is already ignored."
        await message.reply_text(reply, parse_mode=ParseMode.HTML)
    else:
        await message.reply_text("No command supplied to be ignored.")

@user_admin
async def remove_bluetext_ignore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    args = context.args
    
    if len(args) >= 1:
        val = args[0].lower()
        if sql.chat_unignore_command(chat.id, val):
            reply = f"<b>{val}</b> has been removed from bluetext cleaner ignore list."
        else:
            reply = "Command isn't ignored currently."
        await message.reply_text(reply, parse_mode=ParseMode.HTML)
    else:
        await message.reply_text("No command supplied to be unignored.")

@dev_plus
async def add_bluetext_ignore_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    args = context.args
    
    if len(args) >= 1:
        val = args[0].lower()
        if sql.global_ignore_command(val):
            reply = f"<b>{val}</b> has been added to global bluetext cleaner ignore list."
        else:
            reply = "Command is already ignored."
        await message.reply_text(reply, parse_mode=ParseMode.HTML)
    else:
        await message.reply_text("No command supplied to be ignored.")

@dev_plus
async def remove_bluetext_ignore_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    args = context.args
    
    if len(args) >= 1:
        val = args[0].lower()
        if sql.global_unignore_command(val):
            reply = f"<b>{val}</b> has been removed from global bluetext cleaner ignore list."
        else:
            reply = "Command isn't ignored currently."
        await message.reply_text(reply, parse_mode=ParseMode.HTML)
    else:
        await message.reply_text("No command supplied to be unignored.")

@dev_plus
async def bluetext_ignore_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat

    global_ignored_list, local_ignore_list = sql.get_all_ignored(chat.id)
    text = ""

    if global_ignored_list:
        text = "The following commands are currently ignored globally from bluetext cleaning:\n"
        text += "\n".join(f" - <code>{x}</code>" for x in global_ignored_list)

    if local_ignore_list:
        text += "\n\nThe following commands are currently ignored locally from bluetext cleaning:\n"
        text += "\n".join(f" - <code>{x}</code>" for x in local_ignore_list)

    if not text:
        text = "No commands are currently ignored from bluetext cleaning."

    await message.reply_text(text, parse_mode=ParseMode.HTML)


__mod_name__ = "Blue Cleaner"
__help__ = """
Blue text cleaner removes any made up commands that people send in your chat.
 • `/cleanblue <on/off/yes/no>`*:* clean commands after sending
 • `/ignoreblue <word>`*:* prevent auto cleaning of the command
 • `/unignoreblue <word>`*:* remove prevent auto cleaning of the command
 • `/listblue`*:* list currently whitelisted commands

*Following are Disasters only commands, admins cannot use these:*
 • `/gignoreblue <word>`*:* globally ignore bluetext cleaning of saved word across Hina.
 • `/ungignoreblue <word>`*:* remove said command from global cleaning list
"""

SET_CLEAN_BLUE_TEXT_HANDLER = CommandHandler("cleanblue", set_blue_text_must_click)
ADD_CLEAN_BLUE_TEXT_HANDLER = CommandHandler("ignoreblue", add_bluetext_ignore)
REMOVE_CLEAN_BLUE_TEXT_HANDLER = CommandHandler("unignoreblue", remove_bluetext_ignore)
ADD_CLEAN_BLUE_TEXT_GLOBAL_HANDLER = CommandHandler("gignoreblue", add_bluetext_ignore_global)
REMOVE_CLEAN_BLUE_TEXT_GLOBAL_HANDLER = CommandHandler("ungignoreblue", remove_bluetext_ignore_global)
LIST_CLEAN_BLUE_TEXT_HANDLER = CommandHandler("listblue", bluetext_ignore_list)
CLEAN_BLUE_TEXT_HANDLER = MessageHandler(
    filters.COMMAND & filters.ChatType.GROUPS,
    clean_blue_text_must_click
)

app.add_handler(SET_CLEAN_BLUE_TEXT_HANDLER)
app.add_handler(ADD_CLEAN_BLUE_TEXT_HANDLER)
app.add_handler(REMOVE_CLEAN_BLUE_TEXT_HANDLER)
app.add_handler(ADD_CLEAN_BLUE_TEXT_GLOBAL_HANDLER)
app.add_handler(REMOVE_CLEAN_BLUE_TEXT_GLOBAL_HANDLER)
app.add_handler(LIST_CLEAN_BLUE_TEXT_HANDLER)
app.add_handler(CLEAN_BLUE_TEXT_HANDLER, group=BLUE_TEXT_CLEAN_GROUP)

__handlers__ = [
    SET_CLEAN_BLUE_TEXT_HANDLER,
    ADD_CLEAN_BLUE_TEXT_HANDLER,
    REMOVE_CLEAN_BLUE_TEXT_HANDLER,
    ADD_CLEAN_BLUE_TEXT_GLOBAL_HANDLER,
    REMOVE_CLEAN_BLUE_TEXT_GLOBAL_HANDLER,
    LIST_CLEAN_BLUE_TEXT_HANDLER,
    (CLEAN_BLUE_TEXT_HANDLER, BLUE_TEXT_CLEAN_GROUP)
]
