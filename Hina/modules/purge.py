import time
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    filters,
)

from Hina.config import app
from Hina.modules.helper_funcs.chat_status import (
    is_bot_admin,
    can_delete,
)


async def purge_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.perf_counter()
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user

    if not await is_bot_admin(update, user.id) and user.id not in [1087968824]:
        await message.reply_text("Only Admins are allowed to use this command")
        return

    if not await can_delete(chat, context.bot.id):
        await message.reply_text("Can't seem to purge messages here")
        return

    reply_msg = message.reply_to_message
    if not reply_msg:
        await message.reply_text("Reply to a message to select where to start purging from.")
        return

    messages = []
    message_id = reply_msg.message_id
    delete_to = message.message_id

    # Calculate how many messages to delete
    if context.args and context.args[0].isdigit():
        purge_count = int(context.args[0])
        delete_to = message_id + purge_count
        if delete_to > message.message_id:
            delete_to = message.message_id
    else:
        purge_count = None

    # Collect message IDs
    for msg_id in range(message_id, delete_to + 1):
        messages.append(msg_id)
        if len(messages) == 100:  # Telegram API limit
            await context.bot.delete_messages(chat.id, messages)
            messages = []

    # Delete remaining messages
    if messages:
        try:
            await context.bot.delete_messages(chat.id, messages)
        except Exception as e:
            LOGGER.error(f"Error purging messages: {e}")

    time_ = time.perf_counter() - start
    text = f"Purged Successfully in {time_:0.2f} Second(s)"
    await message.reply_text(text)


async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user

    if not await is_bot_admin(update, user.id) and user.id not in [1087968824]:
        await message.reply_text("Only Admins are allowed to use this command")
        return

    if not await can_delete(chat, context.bot.id):
        await message.reply_text("Can't seem to delete messages here")
        return

    reply_msg = message.reply_to_message
    if not reply_msg:
        await message.reply_text("Whadya want to delete?")
        return

    try:
        await reply_msg.delete()
        await message.delete()
    except Exception as e:
        LOGGER.error(f"Error deleting message: {e}")
        await message.reply_text("Couldn't delete the message")


__help__ = """
*Admin only:*
 - /del: deletes the message you replied to
 - /purge: deletes all messages between this and the replied to message.
 - /purge <integer X>: deletes the replied message, and X messages following it if replied to a message.
"""

PURGE_HANDLER = CommandHandler("purge", purge_messages, filters=filters.ChatType.GROUPS)
DEL_HANDLER = CommandHandler("del", delete_message, filters=filters.ChatType.GROUPS)

app.add_handler(PURGE_HANDLER)
app.add_handler(DEL_HANDLER)

__mod_name__ = "Purges"
__command_list__ = ["del", "purge"]
__handlers__ = [PURGE_HANDLER, DEL_HANDLER]
