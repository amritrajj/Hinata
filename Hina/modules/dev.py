from Hina.config import app, DEV_USERS
import os
import subprocess
import sys
import asyncio
from contextlib import suppress

from Hina.modules.helper_funcs.chat_status import dev_plus
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes, CommandHandler, filters as Filters

@dev_plus
async def allow_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        state = "Lockdown is " + ("on" if not Hina.config.ALLOW_CHATS else "off")
        await update.effective_message.reply_text(f"Current state: {state}")
        return
    if args[0].lower() in ["off", "no"]:
        Hina.config.ALLOW_CHATS = True
    elif args[0].lower() in ["yes", "on"]:
        Hina.config.ALLOW_CHATS = False
    else:
        await update.effective_message.reply_text("Format: /lockdown Yes/No or Off/On")
        return
    await update.effective_message.reply_text("Done! Lockdown value toggled.")

@dev_plus
async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    args = context.args
    if args:
        chat_id = str(args[0])
        try:
            await bot.leave_chat(int(chat_id))
        except TelegramError:
            await update.effective_message.reply_text(
                "Beep boop, I could not leave that group(dunno why tho).",
            )
            return
        with suppress(TelegramError):
            await update.effective_message.reply_text("Beep boop, I left that soup!.")
    else:
        await update.effective_message.reply_text("Send a valid chat ID")

@dev_plus
async def gitpull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sent_msg = await update.effective_message.reply_text(
        "Pulling all changes from remote and then attempting to restart.",
    )
    subprocess.Popen("git pull", stdout=subprocess.PIPE, shell=True)

    sent_msg_text = sent_msg.text + "\n\nChanges pulled...I guess.. Restarting in "

    for i in reversed(range(5)):
        await sent_msg.edit_text(sent_msg_text + str(i + 1))
        await asyncio.sleep(1)

    await sent_msg.edit_text("Restarted.")

    os.system("restart.bat")
    os.execv("start.bat", sys.argv)

@dev_plus
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Starting a new instance and shutting down this one",
    )
    os.system("restart.bat")
    os.execv("start.bat", sys.argv)

LEAVE_HANDLER = CommandHandler("leave", leave, filters=Filters.User(DEV_USERS))
GITPULL_HANDLER = CommandHandler("gitpull", gitpull, filters=Filters.User(DEV_USERS))
RESTART_HANDLER = CommandHandler("reboot", restart, filters=Filters.User(DEV_USERS))
ALLOWGROUPS_HANDLER = CommandHandler("lockdown", allow_groups, filters=Filters.User(DEV_USERS))

app.add_handler(ALLOWGROUPS_HANDLER)
app.add_handler(LEAVE_HANDLER)
app.add_handler(GITPULL_HANDLER)
app.add_handler(RESTART_HANDLER)

__mod_name__ = "Dev"
__handlers__ = [LEAVE_HANDLER, GITPULL_HANDLER, RESTART_HANDLER, ALLOWGROUPS_HANDLER]
