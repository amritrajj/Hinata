from Hina.config import app
from typing import Optional

import Hina.modules.sql.rules_sql as sql
from Hina.modules.helper_funcs.chat_status import user_admin
from Hina.modules.helper_funcs.string_handling import markdown_parser
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
    User,
)
from telegram.constants import ParseMode, ChatType
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CommandHandler, filters
from telegram.helpers import escape_markdown

async def get_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await send_rules(update, chat_id)

async def send_rules(update: Update, chat_id: int, from_pm: bool = False):
    bot = context.bot if hasattr(context, 'bot') else app.bot
    user = update.effective_user  # type: Optional[User]
    reply_msg = update.message.reply_to_message if update.message else None
    
    try:
        chat = await bot.get_chat(chat_id)
    except BadRequest as excp:
        if excp.message == "Chat not found" and from_pm:
            await bot.send_message(
                user.id,
                "The rules shortcut for this chat hasn't been set properly! Ask admins to "
                "fix this.\nMaybe they forgot the hyphen in ID",
            )
            return
        raise

    rules = sql.get_rules(chat_id)
    text = f"The rules for *{escape_markdown_v2(chat.title)}* are:\n\n{rules}"

    if from_pm and rules:
        await bot.send_message(
            user.id, 
            text, 
            parse_mode=ParseMode.MARKDOWN, 
            disable_web_page_preview=True,
        )
    elif from_pm:
        await bot.send_message(
            user.id,
            "The group admins haven't set any rules for this chat yet. "
            "This probably doesn't mean it's lawless though...!",
        )
    elif rules and reply_msg:
        await reply_msg.reply_text(
            "Please click the button below to see the rules.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Rules", 
                            url=f"t.me/{bot.username}?start={chat_id}",
                        ),
                    ],
                ],
            ),
        )
    elif rules:
        await update.effective_message.reply_text(
            "Please click the button below to see the rules.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Rules",
                            url=f"t.me/{bot.username}?start={chat_id}",
                        ),
                    ],
                ],
            ),
        )
    else:
        await update.effective_message.reply_text(
            "The group admins haven't set any rules for this chat yet. "
            "This probably doesn't mean it's lawless though...!",
        )

@user_admin
async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = update.effective_message  # type: Optional[Message]
    raw_text = msg.text or msg.caption
    args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args
    
    if len(args) == 2:
        txt = args[1]
        offset = len(txt) - len(raw_text)  # set correct offset relative to command
        markdown_rules = markdown_parser(
            txt, entities=msg.parse_entities(), offset=offset,
        )

        sql.set_rules(chat_id, markdown_rules)
        await update.effective_message.reply_text("Successfully set rules for this group.")

@user_admin
async def clear_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sql.set_rules(chat_id, "")
    await update.effective_message.reply_text("Successfully cleared rules!")

def __stats__():
    return f"• {sql.num_chats()} chats have rules set."

def __import_data__(chat_id, data):
    # set chat rules
    rules = data.get("info", {}).get("rules", "")
    sql.set_rules(chat_id, rules)

def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)

def __chat_settings__(chat_id, user_id):
    return f"This chat has had its rules set: `{bool(sql.get_rules(chat_id))}`"

__help__ = """
 • `/rules`*:* get the rules for this chat.

*Admins only:*
 • `/setrules <your rules here>`*:* set the rules for this chat.
 • `/clearrules`*:* clear the rules for this chat.
"""

__mod_name__ = "Rules"

GET_RULES_HANDLER = CommandHandler("rules", get_rules, filters=filters.ChatType.GROUPS)
SET_RULES_HANDLER = CommandHandler("setrules", set_rules, filters=filters.ChatType.GROUPS)
RESET_RULES_HANDLER = CommandHandler("clearrules", clear_rules, filters=filters.ChatType.GROUPS)

app.add_handler(GET_RULES_HANDLER)
app.add_handler(SET_RULES_HANDLER)
app.add_handler(RESET_RULES_HANDLER)
