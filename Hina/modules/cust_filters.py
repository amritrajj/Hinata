from Hina.config import app
import re
import random
from html import escape

import telegram
from telegram import InlineKeyboardMarkup, Message, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters as Filters,
    ContextTypes
)
from telegram.helpers import mention_html, escape_markdown

from Hina.modules.disable import DisableAbleCommandHandler
from Hina.modules.helper_funcs.handlers import MessageHandlerChecker
from Hina.modules.helper_funcs.chat_status import user_admin
from Hina.modules.helper_funcs.extraction import extract_text
from Hina.modules.helper_funcs.filters import CustomFilters
from Hina.modules.helper_funcs.misc import build_keyboard_parser
from Hina.modules.helper_funcs.msg_types import get_filter_type
from Hina.modules.helper_funcs.string_handling import (
    split_quotes,
    button_markdown_parser,
    escape_invalid_curly_brackets,
    markdown_to_html,
)
from Hina.modules.sql import cust_filters_sql as sql

from Hina.modules.connection import connected

from Hina.modules.helper_funcs.alternate import send_message, typing_action

HANDLER_GROUP = 10

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: app.bot.send_message,
    sql.Types.BUTTON_TEXT.value: app.bot.send_message,
    sql.Types.STICKER.value: app.bot.send_sticker,
    sql.Types.DOCUMENT.value: app.bot.send_document,
    sql.Types.PHOTO.value: app.bot.send_photo,
    sql.Types.AUDIO.value: app.bot.send_audio,
    sql.Types.VOICE.value: app.bot.send_voice,
    sql.Types.VIDEO.value: app.bot.send_video,
}

async def list_handlers(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    conn = await connected(context.bot, update, chat, user.id, need_admin=False)
    if conn is not False:
        chat_id = conn
        chat_name = (await app.bot.get_chat(conn)).title
        filter_list = "*Filter in {}:*\n"
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            chat_name = "Local filters"
            filter_list = "*local filters:*\n"
        else:
            chat_name = chat.title
            filter_list = "*Filters in {}*:\n"

    all_handlers = sql.get_chat_triggers(chat_id)

    if not all_handlers:
        await send_message(
            update.effective_message, f"No filters saved in {chat_name}!"
        )
        return

    for keyword in all_handlers:
        entry = f" • `{escape_markdown_v2(keyword, version=2)}`\n"
        if len(entry) + len(filter_list) > telegram.constants.MessageLimit.MAX_TEXT_LENGTH:
            await send_message(
                update.effective_message,
                filter_list.format(chat_name),
                parse_mode=ParseMode.MARKDOWN,
            )
            filter_list = entry
        else:
            filter_list += entry

    await send_message(
        update.effective_message,
        filter_list.format(chat_name),
        parse_mode=ParseMode.MARKDOWN,
    )

@user_admin
@typing_action
async def filters(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = msg.text.split(None, 1)

    conn = await connected(context.bot, update, chat, user.id)
    if conn is not False:
        chat_id = conn
        chat_name = (await app.bot.get_chat(conn)).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            chat_name = "local filters"
        else:
            chat_name = chat.title

    if not msg.reply_to_message and len(args) < 2:
        await send_message(
            update.effective_message,
            "Please provide keyboard keyword for this filter to reply with!",
        )
        return

    if msg.reply_to_message:
        if len(args) < 2:
            await send_message(
                update.effective_message,
                "Please provide keyword for this filter to reply with!",
            )
            return
        else:
            keyword = args[1]
    else:
        extracted = split_quotes(args[1])
        if len(extracted) < 1:
            return
        keyword = extracted[0].lower()

    # Remove existing handler
    for handler in app.handlers.get(HANDLER_GROUP, []):
        if handler.filters == (keyword, chat_id):
            app.remove_handler(handler, HANDLER_GROUP)

    text, file_type, file_id = get_filter_type(msg)
    if not msg.reply_to_message and len(extracted) >= 2:
        offset = len(extracted[1]) - len(msg.text)
        text, buttons = button_markdown_parser(
            extracted[1], entities=msg.parse_entities(), offset=offset
        )
        text = text.strip()
        if not text:
            await send_message(
                update.effective_message,
                "There is no note message - You can't JUST have buttons, you need a message to go with it!",
            )
            return

    elif msg.reply_to_message and len(args) >= 2:
        text_to_parsing = msg.reply_to_message.text or msg.reply_to_message.caption or ""
        offset = len(text_to_parsing)
        text, buttons = button_markdown_parser(
            text_to_parsing, entities=msg.parse_entities(), offset=offset
        )
        text = text.strip()

    elif not text and not file_type:
        await send_message(
            update.effective_message,
            "Please provide keyword for this filter reply with!",
        )
        return

    elif msg.reply_to_message:
        text_to_parsing = msg.reply_to_message.text or msg.reply_to_message.caption or ""
        offset = len(text_to_parsing)
        text, buttons = button_markdown_parser(
            text_to_parsing, entities=msg.parse_entities(), offset=offset
        )
        text = text.strip()
        if text_to_parsing and not text:
            await send_message(
                update.effective_message,
                "There is no note message - You can't JUST have buttons, you need a message to go with it!",
            )
            return

    else:
        await send_message(update.effective_message, "Invalid filter!")
        return

    add = await addnew_filter(update, chat_id, keyword, text, file_type, file_id, buttons)
    if add:
        await send_message(
            update.effective_message,
            f"Saved filter '{keyword}' in *{chat_name}*!",
            parse_mode=ParseMode.MARKDOWN,
        )
    raise DispatcherHandlerStop

@user_admin
@typing_action
async def stop_filter(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    args = update.effective_message.text.split(None, 1)

    conn = await connected(context.bot, update, chat, user.id)
    if conn is not False:
        chat_id = conn
        chat_name = (await app.bot.get_chat(conn)).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            chat_name = "Local filters"
        else:
            chat_name = chat.title

    if len(args) < 2:
        await send_message(update.effective_message, "What should i stop?")
        return

    chat_filters = sql.get_chat_triggers(chat_id)

    if not chat_filters:
        await send_message(update.effective_message, "No filters active here!")
        return

    for keyword in chat_filters:
        if keyword == args[1]:
            sql.remove_filter(chat_id, args[1])
            await send_message(
                update.effective_message,
                f"Okay, I'll stop replying to that filter in *{chat_name}*.",
                parse_mode=ParseMode.MARKDOWN,
            )
            raise DispatcherHandlerStop

    await send_message(
        update.effective_message,
        "That's not a filter - Click: /filters to get currently active filters.",
    )

async def reply_filter(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message

    if not update.effective_user or update.effective_user.id == 777000:
        return

    to_match = extract_text(message)
    if not to_match:
        return

    chat_filters = sql.get_chat_triggers(chat.id)
    for keyword in chat_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            if MessageHandlerChecker.check_user(update.effective_user.id):
                return
            filt = sql.get_filter(chat.id, keyword)
            if filt.reply == "there is should be a new reply":
                buttons = sql.get_buttons(chat.id, filt.keyword)
                keyb = build_keyboard_parser(context.bot, chat.id, buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                VALID_WELCOME_FORMATTERS = ["first", "last", "fullname", "username", "id", "chatname", "mention"]
                if filt.reply_text:
                    if "%%%" in filt.reply_text:
                        split = filt.reply_text.split("%%%")
                        text = random.choice(split) if all(split) else filt.reply_text
                    else:
                        text = filt.reply_text
                    
                    if text.startswith("~!") and text.endswith("!~"):
                        sticker_id = text.replace("~!", "").replace("!~", "")
                        try:
                            await context.bot.send_sticker(
                                chat.id,
                                sticker_id,
                                reply_to_message_id=message.message_id,
                            )
                            return
                        except BadRequest as excp:
                            if excp.message == "Wrong remote file identifier specified: wrong padding in the string":
                                await context.bot.send_message(
                                    chat.id,
                                    "Message couldn't be sent, Is the sticker id valid?",
                                )
                                return
                            raise

                    valid_format = escape_invalid_curly_brackets(text, VALID_WELCOME_FORMATTERS)
                    if valid_format:
                        filtext = valid_format.format(
                            first=escape(message.from_user.first_name),
                            last=escape(message.from_user.last_name or message.from_user.first_name),
                            fullname=" ".join(
                                [escape(message.from_user.first_name), escape(message.from_user.last_name)]
                                if message.from_user.last_name
                                else [escape(message.from_user.first_name)]
                            ),
                            username=f"@{escape(message.from_user.username)}" if message.from_user.username 
                                   else mention_html(message.from_user.id, message.from_user.first_name),
                            mention=mention_html(message.from_user.id, message.from_user.first_name),
                            chatname=escape(message.chat.title) if message.chat.type != "private"
                                   else escape(message.from_user.first_name),
                            id=message.from_user.id,
                        )
                    else:
                        filtext = ""
                else:
                    filtext = ""

                if filt.file_type in (sql.Types.BUTTON_TEXT, sql.Types.TEXT):
                    try:
                        await context.bot.send_message(
                            chat.id,
                            markdown_to_html(filtext),
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard,
                            reply_to_message_id=message.message_id
                        )
                    except BadRequest as excp:
                        LOGGER.exception("Error in filters: %s", excp.message)
                        try:
                            await send_message(update.effective_message, get_exception(excp, filt, chat))
                        except BadRequest:
                            LOGGER.exception("Failed to send message")
                else:
                    try:
                        await ENUM_FUNC_MAP[filt.file_type](
                            chat.id,
                            filt.file_id,
                            reply_markup=keyboard,
                            reply_to_message_id=message.message_id
                        )
                    except BadRequest:
                        await send_message(
                            message,
                            "I don't have the permission to send the content of the filter.",
                        )
                break
            else:
                if filt.is_sticker:
                    await message.reply_sticker(filt.reply)
                elif filt.is_document:
                    await message.reply_document(filt.reply)
                elif filt.is_image:
                    await message.reply_photo(filt.reply)
                elif filt.is_audio:
                    await message.reply_audio(filt.reply)
                elif filt.is_voice:
                    await message.reply_voice(filt.reply)
                elif filt.is_video:
                    await message.reply_video(filt.reply)
                elif filt.has_markdown:
                    buttons = sql.get_buttons(chat.id, filt.keyword)
                    keyb = build_keyboard_parser(context.bot, chat.id, buttons)
                    keyboard = InlineKeyboardMarkup(keyb)

                    try:
                        await context.bot.send_message(
                            chat.id,
                            filt.reply,
                            parse_mode=ParseMode.MARKDOWN,
                            disable_web_page_preview=True,
                            reply_markup=keyboard,
                            reply_to_message_id=message.message_id
                        )
                    except BadRequest as excp:
                        if excp.message == "Unsupported url protocol":
                            try:
                                await send_message(
                                    update.effective_message,
                                    "You seem to be trying to use an unsupported url protocol. "
                                    "Telegram doesn't support buttons for some protocols, such as tg://. Please try "
                                    "again...",
                                )
                            except BadRequest:
                                LOGGER.exception("Error in filters")
                        else:
                            try:
                                await send_message(
                                    update.effective_message,
                                    "This message couldn't be sent as it's incorrectly formatted.",
                                )
                            except BadRequest:
                                LOGGER.exception("Error in filters")
                else:
                    try:
                        await context.bot.send_message(chat.id, filt.reply, reply_to_message_id=message.message_id)
                    except BadRequest:
                        LOGGER.exception("Error in filters")
                break

async def rmall_filters(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    member = await chat.get_member(user.id)
    
    if member.status != "creator" and user.id not in DRAGONS:
        await update.effective_message.reply_text(
            "Only the chat owner can clear all notes at once.",
        )
    else:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(text="Stop all filters", callback_data="filters_rmall")],
            [InlineKeyboardButton(text="Cancel", callback_data="filters_cancel")]
        ])
        await update.effective_message.reply_text(
            f"Are you sure you would like to stop ALL filters in {chat.title}? This action cannot be undone.",
            reply_markup=buttons,
            parse_mode=ParseMode.MARKDOWN,
        )

async def rmall_callback(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = update.effective_chat
    msg = update.effective_message
    member = await chat.get_member(query.from_user.id)
    
    if query.data == "filters_rmall":
        if member.status == "creator" or query.from_user.id in DRAGONS:
            allfilters = sql.get_chat_triggers(chat.id)
            if not allfilters:
                await msg.edit_text("No filters in this chat, nothing to stop!")
                return

            count = len(allfilters)
            for filt in allfilters:
                sql.remove_filter(chat.id, filt)

            await msg.edit_text(f"Cleaned {count} filters in {chat.title}")

        elif member.status == "administrator":
            await query.answer("Only owner of the chat can do this.")
        else:
            await query.answer("You need to be admin to do this.")
    elif query.data == "filters_cancel":
        await msg.edit_text("Cancelled removal of filters.")

# Add handlers
app.add_handler(CommandHandler("filters", list_handlers, filters=Filters.ChatType.GROUPS))
app.add_handler(CommandHandler("filter", filters, filters=Filters.ChatType.GROUPS))
app.add_handler(CommandHandler("stop", stop_filter, filters=Filters.ChatType.GROUPS))
app.add_handler(CommandHandler("rmallfilters", rmall_filters, filters=Filters.ChatType.GROUPS))
app.add_handler(CallbackQueryHandler(rmall_callback, pattern=r"filters_.*"))
app.add_handler(MessageHandler(Filters.TEXT & Filters.ChatType.GROUPS, reply_filter), group=HANDLER_GROUP)
