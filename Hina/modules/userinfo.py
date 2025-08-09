from Hina.config import app, INFOPIC, DEV_USERS, OWNER_ID, DRAGONS, DEMONS, TIGERS, WOLVES, TOKEN
import html
import re
import os
import requests

from telegram import (
    Update,
    MessageEntity,
    constants,
    BotCommand
)
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    BaseHandler,
    CommandHandler,
)
from telegram.error import BadRequest
from telegram.helpers import escape_markdown, mention_html

import Hina.modules.sql.userinfo_sql as sql
from Hina.modules.disable import DisableAbleCommandHandler
from Hina.modules.sql.global_bans_sql import is_user_gbanned
from Hina.modules.sql.afk_sql import is_afk, check_afk_status
from Hina.modules.sql.users_sql import get_user_num_chats
from Hina.modules.helper_funcs.chat_status import sudo_plus
from Hina.modules.helper_funcs.extraction import extract_user


async def no_by_per(totalhp, percentage):
    """Calculate percentage of total"""
    return totalhp * percentage / 100


async def get_percentage(totalhp, earnedhp):
    """Calculate percentage earned"""
    matched_less = totalhp - earnedhp
    per_of_totalhp = 100 - matched_less * 100.0 / totalhp
    return str(int(per_of_totalhp))


async def hpmanager(user):
    """Calculate user health points"""
    total_hp = (await get_user_num_chats(user.id) + 10) * 10

    if not await is_user_gbanned(user.id):
        new_hp = total_hp

        if not user.username:
            new_hp -= await no_by_per(total_hp, 25)
        try:
            await app.bot.get_user_profile_photos(user.id).photos[0][-1]
        except IndexError:
            new_hp -= await no_by_per(total_hp, 25)
        if not await sql.get_user_me_info(user.id):
            new_hp -= await no_by_per(total_hp, 20)
        if not await sql.get_user_bio(user.id):
            new_hp -= await no_by_per(total_hp, 10)

        if await is_afk(user.id):
            afkst = await check_afk_status(user.id)
            if not afkst.reason:
                new_hp -= await no_by_per(total_hp, 7)
            else:
                new_hp -= await no_by_per(total_hp, 5)
    else:
        new_hp = await no_by_per(total_hp, 5)

    return {
        "earnedhp": int(new_hp),
        "totalhp": int(total_hp),
        "percentage": await get_percentage(total_hp, new_hp),
    }


async def make_bar(per):
    """Create health bar visualization"""
    done = min(round(per / 10), 10)
    return "■" * done + "□" * (10 - done)


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user/chat ID"""
    bot, args = context.bot, context.args
    message = update.effective_message
    chat = update.effective_chat
    msg = update.effective_message
    user_id = await extract_user(msg, args)

    if user_id:
        if msg.reply_to_message and msg.reply_to_message.forward_from:
            user1 = message.reply_to_message.from_user
            user2 = message.reply_to_message.forward_from

            await msg.reply_text(
                f"<b>Telegram ID:</b>,"
                f"• {html.escape(user2.first_name)} - <code>{user2.id}</code>.\n"
                f"• {html.escape(user1.first_name)} - <code>{user1.id}</code>.",
                parse_mode=ParseMode.HTML,
            )
        else:
            user = await bot.get_chat(user_id)
            await msg.reply_text(
                f"{html.escape(user.first_name)}'s id is <code>{user.id}</code>.",
                parse_mode=ParseMode.HTML,
            )
    else:
        if chat.type == "private":
            await msg.reply_text(
                f"Your id is <code>{chat.id}</code>", 
                parse_mode=ParseMode.HTML,
            )
        else:
            await msg.reply_text(
                f"This group's id is <code>{chat.id}</code>",
                parse_mode=ParseMode.HTML,
            )


async def gifid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get GIF file ID"""
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.animation:
        await update.effective_message.reply_text(
            f"Gif ID:\n<code>{msg.reply_to_message.animation.file_id}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.effective_message.reply_text("Please reply to a gif to get its ID.")


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user information"""
    bot, args = context.bot, context.args
    message = update.effective_message
    chat = update.effective_chat
    user_id = await extract_user(update.effective_message, args)

    if user_id:
        user = await bot.get_chat(user_id)
    elif not message.reply_to_message and not args:
        user = message.from_user
    else:
        await message.reply_text("I can't extract a user from this.")
        return

    rep = await message.reply_text("<code>Appraising...</code>", parse_mode=ParseMode.HTML)

    text = (
        f"╒═══「<b> Appraisal results:</b> 」\n"
        f"ID: <code>{user.id}</code>\n"
        f"First Name: {html.escape(user.first_name)}"
    )

    if user.last_name:
        text += f"\nLast Name: {html.escape(user.last_name)}"

    if user.username:
        text += f"\nUsername: @{html.escape(user.username)}"

    text += f"\nPermalink: {mention_html(user.id, 'link')}"

    if chat.type != "private" and user_id != bot.id:
        _stext = "\nPresence: <code>{}</code>"
        afk_st = await is_afk(user.id)
        if afk_st:
            text += _stext.format("AFK")
        else:
            status = await bot.get_chat_member(chat.id, user.id).status
            if status:
                if status in {"left", "kicked"}:
                    text += _stext.format("Not here")
                elif status == "member":
                    text += _stext.format("Detected")
                elif status in {"administrator", "creator"}:
                    text += _stext.format("Admin")

    if user_id not in [bot.id, 777000, 1087968824]:
        userhp = await hpmanager(user)
        text += f"\n\n<b>Health:</b> <code>{userhp['earnedhp']}/{userhp['totalhp']}</code>\n[<i>{await make_bar(int(userhp['percentage']))} </i>{userhp['percentage']}%]"

    try:
        spamwtc = await sw.get_ban(int(user.id))
        if spamwtc:
            text += "\n\n<b>This person is Spamwatched!</b>"
            text += f"\nReason: <pre>{spamwtc.reason}</pre>"
            text += "\nAppeal at @SpamWatchSupport"
    except:
        pass

    disaster_level_present = False

    if user.id == OWNER_ID:
        text += "\n\nThe Disaster level of this person is 'God'."
        disaster_level_present = True
    elif user.id in DEV_USERS:
        text += "\n\nThis user is member of 'Hero Association'."
        disaster_level_present = True
    elif user.id in DRAGONS:
        text += "\n\nThe Disaster level of this person is 'Dragon'."
        disaster_level_present = True
    elif user.id in DEMONS:
        text += "\n\nThe Disaster level of this person is 'Demon'."
        disaster_level_present = True
    elif user.id in TIGERS:
        text += "\n\nThe Disaster level of this person is 'Tiger'."
        disaster_level_present = True
    elif user.id in WOLVES:
        text += "\n\nThe Disaster level of this person is 'Wolf'."
        disaster_level_present = True

    if disaster_level_present:
        text += ' [<a href="https://t.me/OnePunchUpdates/155">?</a>]'.format(bot.username)

    try:
        user_member = await chat.get_member(user.id)
        if user_member.status == "administrator":
            result = await bot.get_chat_member(chat.id, user.id)
            if result.custom_title:
                text += f"\n\nTitle:\n<b>{result.custom_title}</b>"
    except BadRequest:
        pass

    for mod in USER_INFO:
        try:
            mod_info = await mod.__user_info__(user.id).strip()
        except TypeError:
            mod_info = await mod.__user_info__(user.id, chat.id).strip()
        if mod_info:
            text += "\n\n" + mod_info

    if INFOPIC:
        try:
            profile = await bot.get_user_profile_photos(user.id)
            photo = await profile.photos[0][-1]
            _file = await bot.get_file(photo.file_id)
            await _file.download_to_drive(f"{user.id}.png")

            await message.reply_document(
                document=open(f"{user.id}.png", "rb"),
                caption=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            os.remove(f"{user.id}.png")
        except IndexError:
            await message.reply_text(
                text, parse_mode=ParseMode.HTML, disable_web_page_preview=True,
            )
    else:
        await message.reply_text(
            text, parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        )

    await rep.delete()


async def about_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user's about me info"""
    bot, args = context.bot, context.args
    message = update.effective_message
    user_id = await extract_user(message, args)

    if user_id:
        user = await bot.get_chat(user_id)
    else:
        user = message.from_user

    info = await sql.get_user_me_info(user.id)

    if info:
        await update.effective_message.reply_text(
            f"*{user.first_name}*:\n{escape_markdown_v2(info)}",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    elif message.reply_to_message:
        username = message.reply_to_message.from_user.first_name
        await update.effective_message.reply_text(
            f"{username} hasn't set an info message about themselves yet!",
        )
    else:
        await update.effective_message.reply_text("There isn't one, use /setme to set one.")


async def set_about_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's about me info"""
    message = update.effective_message
    user_id = message.from_user.id
    bot = context.bot
    
    if user_id in [777000, 1087968824]:
        await message.reply_text("Error! Unauthorized")
        return

    if message.reply_to_message:
        repl_message = message.reply_to_message
        repl_user_id = repl_message.from_user.id
        if repl_user_id in [bot.id, 777000, 1087968824] and (user_id in DEV_USERS):
            user_id = repl_user_id

    text = message.text
    info = text.split(None, 1)
    if len(info) == 2:
        if len(info[1]) < constants.MessageLimit.TEXT_LENGTH // 4:
            await sql.set_user_me_info(user_id, info[1])
            if user_id in [777000, 1087968824]:
                await message.reply_text("Authorized...Information updated!")
            elif user_id == bot.id:
                await message.reply_text("I have updated my info with the one you provided!")
            else:
                await message.reply_text("Information updated!")
        else:
            await message.reply_text(
                f"The info needs to be under {constants.MessageLimit.TEXT_LENGTH // 4} characters! "
                f"You have {len(info[1])}.",
            )


@sudo_plus
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get bot stats"""
    stats_text = "<b>📊 Current stats:</b>\n" + "\n".join([await mod.__stats__() for mod in STATS])
    result = re.sub(r"(\d+)", r"<code>\1</code>", stats_text)
    await update.effective_message.reply_text(result, parse_mode=ParseMode.HTML)


async def about_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user's bio"""
    bot, args = context.bot, context.args
    message = update.effective_message

    user_id = await extract_user(message, args)
    if user_id:
        user = await bot.get_chat(user_id)
    else:
        user = message.from_user

    info = await sql.get_user_bio(user.id)

    if info:
        await update.effective_message.reply_text(
            "*{}*:\n{}".format(user.first_name, escape_markdown_v2(info)),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    elif message.reply_to_message:
        username = user.first_name
        await update.effective_message.reply_text(
            f"{username} hasn't had a message set about themselves yet!\nSet one using /setbio",
        )
    else:
        await update.effective_message.reply_text(
            "You haven't had a bio set about yourself yet!",
        )


async def set_about_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's bio"""
    message = update.effective_message
    sender_id = update.effective_user.id
    bot = context.bot

    if message.reply_to_message:
        repl_message = message.reply_to_message
        user_id = repl_message.from_user.id

        if user_id == message.from_user.id:
            await message.reply_text(
                "Ha, you can't set your own bio! You're at the mercy of others here...",
            )
            return

        if user_id in [777000, 1087968824] and sender_id not in DEV_USERS:
            await message.reply_text("You are not authorized")
            return

        if user_id == bot.id and sender_id not in DEV_USERS:
            await message.reply_text(
                "Erm... yeah, I only trust Heroes Association to set my bio.",
            )
            return

        text = message.text
        bio = text.split(None, 1)

        if len(bio) == 2:
            if len(bio[1]) < constants.MessageLimit.TEXT_LENGTH // 4:
                await sql.set_user_bio(user_id, bio[1])
                await message.reply_text(
                    f"Updated {repl_message.from_user.first_name}'s bio!",
                )
            else:
                await message.reply_text(
                    f"Bio needs to be under {constants.MessageLimit.TEXT_LENGTH // 4} characters! "
                    f"You tried to set {len(bio[1])}.",
                )
    else:
        await message.reply_text("Reply to someone to set their bio!")


async def __user_info__(user_id, chat_id=None):
    """Format user info"""
    bio = html.escape(await sql.get_user_bio(user_id) or "")
    me = html.escape(await sql.get_user_me_info(user_id) or "")
    result = ""
    if me:
        result += f"<b>About user:</b>\n{me}\n"
    if bio:
        result += f"<b>What others say:</b>\n{bio}\n"
    return result.strip("\n")


__help__ = """
*ID:*
 • `/id`*:* get the current group id. If used by replying to a message, gets that user's id.
 • `/gifid`*:* reply to a gif to me to tell you its file ID.

*Self added information:*
 • `/setme <text>`*:* will set your info
 • `/me`*:* will get your or another user's info.
Examples:
 `/setme I am a wolf.`
 `/me @username(defaults to yours if no user specified)`

*Information others add on you:*
 • `/bio`*:* will get your or another user's bio. This cannot be set by yourself.
• `/setbio <text>`*:* while replying, will save another user's bio
Examples:
 `/bio @username(defaults to yours if not specified).`
 `/setbio This user is a wolf` (reply to the user)

*Overall Information about you:*
 • `/info`*:* get information about a user.

*What is that health thingy?*
 Come and see [HP System explained](https://t.me/OnePunchUpdates/192)
"""

SET_BIO_HANDLER = DisableAbleCommandHandler("setbio", set_about_bio, block=False)
GET_BIO_HANDLER = DisableAbleCommandHandler("bio", about_bio, block=False)
STATS_HANDLER = CommandHandler("stats", stats, block=False)
ID_HANDLER = DisableAbleCommandHandler("id", get_id, block=False)
GIFID_HANDLER = DisableAbleCommandHandler("gifid", gifid, block=False)
INFO_HANDLER = DisableAbleCommandHandler(("info", "book"), info, block=False)
SET_ABOUT_HANDLER = DisableAbleCommandHandler("setme", set_about_me, block=False)
GET_ABOUT_HANDLER = DisableAbleCommandHandler("me", about_me, block=False)

app.add_handler(STATS_HANDLER)
app.add_handler(ID_HANDLER)
app.add_handler(GIFID_HANDLER)
app.add_handler(INFO_HANDLER)
app.add_handler(SET_BIO_HANDLER)
app.add_handler(GET_BIO_HANDLER)
app.add_handler(SET_ABOUT_HANDLER)
app.add_handler(GET_ABOUT_HANDLER)

__mod_name__ = "Info"
__command_list__ = ["setbio", "bio", "setme", "me", "info"]
__handlers__ = [
    ID_HANDLER,
    GIFID_HANDLER,
    INFO_HANDLER,
    SET_BIO_HANDLER,
    GET_BIO_HANDLER,
    SET_ABOUT_HANDLER,
    GET_ABOUT_HANDLER,
    STATS_HANDLER,
]
