from Hina.config import app
import os
import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from Hina.modules.helper_funcs.chat_status import dev_plus

# The following imports are removed as they are part of the telethon library
# from telethon import events
# from Hina.config import telethn

DEBUG_MODE = False


@dev_plus
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggles debug mode on or off."""
    global DEBUG_MODE
    args = context.args
    message = update.effective_message
    
    if args:
        if args[0].lower() in ("yes", "on"):
            DEBUG_MODE = True
            await message.reply_text("Debug mode is now on.")
        elif args[0].lower() in ("no", "off"):
            DEBUG_MODE = False
            await message.reply_text("Debug mode is now off.")
        else:
            await message.reply_text("Invalid argument. Use `yes/on` or `no/off`.")
    else:
        if DEBUG_MODE:
            await message.reply_text("Debug mode is currently on.")
        else:
            await message.reply_text("Debug mode is currently off.")


async def debug_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles messages when debug mode is on."""
    global DEBUG_MODE
    if DEBUG_MODE:
        message = update.effective_message
        if message and message.text:
            text = f"-{message.from_user.id} ({message.chat_id}) : {message.text}"
            print(text)
            
            # Append to updates.txt file
            if os.path.exists("updates.txt"):
                with open("updates.txt", "a") as f:
                    f.write(f"\n{text}")
            else:
                with open("updates.txt", "w") as f:
                    f.write(f"{text} | {datetime.datetime.now()}")


@dev_plus
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the log file."""
    user = update.effective_user
    if os.path.exists("log.txt"):
        with open("log.txt", "rb") as f:
            await context.bot.send_document(document=f, filename=f.name, chat_id=user.id)
    else:
        await update.effective_message.reply_text("Log file not found.")

# ==================== HANDLER REGISTRATION ====================
app.add_handler(CommandHandler("debug", debug))
app.add_handler(CommandHandler("logs", logs))

# The MessageHandler for debug mode is now registered here
app.add_handler(MessageHandler(filters.COMMAND, debug_message_handler))

__mod_name__ = "Debug"
__command_list__ = ["debug"]
__handlers__ = [
    CommandHandler("debug", debug),
    CommandHandler("logs", logs),
    MessageHandler(filters.COMMAND, debug_message_handler)
]
