from Hina.config import app
from time import sleep
import asyncio

import Hina.modules.sql.global_bans_sql as gban_sql
import Hina.modules.sql.users_sql as user_sql
from Hina.config import DEV_USERS, OWNER_ID
from Hina.modules.helper_funcs.chat_status import dev_plus
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
    filters as Filters
)


async def get_invalid_chats(update: Update, context: ContextTypes.DEFAULT_TYPE, remove: bool = False):
    bot = context.bot
    chat_id = update.effective_chat.id
    chats = user_sql.get_all_chats()
    kicked_chats, progress = 0, 0
    chat_list = []
    progress_message = None

    for chat in chats:
        if ((100 * chats.index(chat)) / len(chats)) > progress:
            progress_bar = f"{progress}% completed in getting invalid chats."
            if progress_message:
                try:
                    await bot.edit_message_text(
                        progress_bar, chat_id, progress_message.message_id,
                    )
                except:
                    pass
            else:
                progress_message = await bot.send_message(chat_id, progress_bar)
            progress += 5

        cid = chat.chat_id
        await asyncio.sleep(0.1)
        try:
            await bot.get_chat(cid)
        except (BadRequest, TelegramError):
            kicked_chats += 1
            chat_list.append(cid)
        except:
            pass

    try:
        await progress_message.delete()
    except:
        pass

    if not remove:
        return kicked_chats
    else:
        for muted_chat in chat_list:
            await asyncio.sleep(0.1)
            user_sql.rem_chat(muted_chat)
        return kicked_chats


async def get_invalid_gban(update: Update, context: ContextTypes.DEFAULT_TYPE, remove: bool = False):
    bot = context.bot
    banned = gban_sql.get_gban_list()
    ungbanned_users = 0
    ungban_list = []

    for user in banned:
        user_id = user["user_id"]
        await asyncio.sleep(0.1)
        try:
            await bot.get_chat(user_id)
        except BadRequest:
            ungbanned_users += 1
            ungban_list.append(user_id)
        except:
            pass

    if not remove:
        return ungbanned_users
    else:
        for user_id in ungban_list:
            await asyncio.sleep(0.1)
            gban_sql.ungban_user(user_id)
        return ungbanned_users


@dev_plus
async def dbcleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    await msg.reply_text("Getting invalid chat count ...")
    invalid_chat_count = await get_invalid_chats(update, context)

    await msg.reply_text("Getting invalid gbanned count ...")
    invalid_gban_count = await get_invalid_gban(update, context)

    reply = f"Total invalid chats - {invalid_chat_count}\n"
    reply += f"Total invalid gbanned users - {invalid_gban_count}"

    buttons = [[InlineKeyboardButton("Cleanup DB", callback_data="db_cleanup")]]

    await msg.reply_text(
        reply, reply_markup=InlineKeyboardMarkup(buttons),
    )


async def callback_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    query = update.callback_query
    message = query.message
    chat_id = update.effective_chat.id
    query_type = query.data

    admin_list = [OWNER_ID] + DEV_USERS

    await query.answer()

    if query_type == "db_leave_chat":
        if query.from_user.id in admin_list:
            await bot.edit_message_text("Leaving chats ...", chat_id, message.message_id)
            chat_count = await get_muted_chats(update, context, True)
            await bot.send_message(chat_id, f"Left {chat_count} chats.")
        else:
            await query.answer("You are not allowed to use this.")
    elif query_type == "db_cleanup":
        if query.from_user.id in admin_list:
            await bot.edit_message_text("Cleaning up DB ...", chat_id, message.message_id)
            invalid_chat_count = await get_invalid_chats(update, context, True)
            invalid_gban_count = await get_invalid_gban(update, context, True)
            reply = "Cleaned up {} chats and {} gbanned users from db.".format(
                invalid_chat_count, invalid_gban_count,
            )
            await bot.send_message(chat_id, reply)
        else:
            await query.answer("You are not allowed to use this.")


DB_CLEANUP_HANDLER = CommandHandler("dbcleanup", dbcleanup, filters=Filters.ChatType.PRIVATE)
BUTTON_HANDLER = CallbackQueryHandler(callback_button, pattern="db_.*")

app.add_handler(DB_CLEANUP_HANDLER)
app.add_handler(BUTTON_HANDLER)

__mod_name__ = "DB Cleanup"
__handlers__ = [DB_CLEANUP_HANDLER, BUTTON_HANDLER]
