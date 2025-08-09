import re
import random
import html
import logging
from datetime import datetime
import humanize
from Hina.modules.disable import (
    DisableAbleCommandHandler,
    DisableAbleMessageHandler,
)
from Hina.modules.sql import afk_sql as sql
from Hina.modules.users import get_user_id
from telegram import MessageEntity, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, MessageHandler, filters, Application

LOGGER = logging.getLogger(__name__)

AFK_GROUP = 7
AFK_REPLY_GROUP = 8

async def afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.effective_message.text.split(None, 1)
    user = update.effective_user

    if not user:
        return

    if user.id in [777000, 1087968824]:
        return

    notice = ""
    reason = args[1] if len(args) >= 2 else ""
    
    if reason and len(reason) > 100:
        reason = reason[:100]
        notice = "\nYour afk reason was shortened to 100 characters."

    sql.set_afk(user.id, reason)
    fname = user.first_name
    
    try:
        await update.effective_message.reply_text(
            f"{fname} is now away!{notice}",
        )
    except BadRequest:
        pass

async def no_longer_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user or message.new_chat_members:
        return

    if sql.rm_afk(user.id):
        firstname = user.first_name
        options = [
            f"{firstname} is here!",
            f"{firstname} is back!",
            f"{firstname} is now in the chat!",
            f"{firstname} is awake!",
            f"{firstname} is back online!",
            f"{firstname} is finally here!",
            f"Welcome back! {firstname}",
            f"Where is {firstname}?\nIn the chat!",
        ]
        
        try:
            await message.reply_text(random.choice(options))
        except BadRequest:
            pass

async def reply_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    userc = update.effective_user
    userc_id = userc.id

    if message.entities:
        entities = message.parse_entities(
            [MessageEntity.TEXT_MENTION, MessageEntity.MENTION]
        )

        chk_users = []
        for ent in entities:
            if ent.type == MessageEntity.TEXT_MENTION:
                user_id = ent.user.id
                fst_name = ent.user.first_name
                
                if user_id in chk_users:
                    continue
                chk_users.append(user_id)
                
                await check_afk(update, context, user_id, fst_name, userc_id)

            elif ent.type == MessageEntity.MENTION:
                user_id = get_user_id(message.text[ent.offset:ent.offset + ent.length])
                if not user_id or user_id in chk_users:
                    continue
                    
                chk_users.append(user_id)
                
                try:
                    chat = await context.bot.get_chat(user_id)
                    await check_afk(update, context, user_id, chat.first_name, userc_id)
                except BadRequest:
                    print(f"Error: Could not fetch userid {user_id} for AFK module")

    elif message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        fst_name = message.reply_to_message.from_user.first_name
        await check_afk(update, context, user_id, fst_name, userc_id)

async def check_afk(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, fst_name: str, userc_id: int):
    if userc_id == user_id or not sql.is_afk(user_id):
        return

    user = sql.check_afk_status(user_id)
    time = humanize.naturaldelta(datetime.now() - user.time)
    
    if not user.reason:
        res = f"{fst_name} is afk.\n\nLast seen {time} ago."
    else:
        res = f"{html.escape(fst_name)} is afk.\nReason: <code>{html.escape(user.reason)}</code>\n\nLast seen {time} ago."
    
    try:
        await update.effective_message.reply_text(
            res,
            parse_mode=ParseMode.HTML if user.reason else None
        )
    except BadRequest:
        pass

# Handlers are defined at the top level for __handlers__ list
AFK_HANDLER = DisableAbleCommandHandler("afk", afk)
AFK_REGEX_HANDLER = DisableAbleMessageHandler(
    filters.Regex(pattern=r"(?i)^brb(.*)$"),
    afk,
    friendly="afk"
)
NO_AFK_HANDLER = MessageHandler(
    filters.ALL & filters.ChatType.GROUPS & ~filters.StatusUpdate.NEW_CHAT_MEMBERS,
    no_longer_afk
)
AFK_REPLY_HANDLER = MessageHandler(
    filters.ALL & filters.ChatType.GROUPS & 
    (filters.Entity(MessageEntity.MENTION) | 
     filters.Entity(MessageEntity.TEXT_MENTION) |
     filters.REPLY),
    reply_afk
)
