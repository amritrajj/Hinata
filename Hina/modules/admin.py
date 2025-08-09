from Hina.config import app
import html

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CommandHandler, filters
from telegram.helpers import mention_html
from contextlib import asynccontextmanager
from Hina.config import DRAGONS, app
from Hina.modules.disable import DisableAbleCommandHandler
from Hina.modules.helper_funcs.chat_status import (
    bot_admin,
    can_pin,
    can_promote,
    connection_status,
    user_admin,
    ADMIN_CACHE,
)
from Hina.modules.helper_funcs.extraction import (
    extract_user,
    extract_user_and_text,
)
from Hina.modules.log_channel import loggable
from Hina.modules.helper_funcs.alternate import send_message

HANDLER_GROUP=5
# --- PROMOTE ---
@connection_status
@bot_admin
@can_promote
@user_admin
@loggable
async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    bot = context.bot
    args = context.args

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    promoter = await chat.get_member(user.id)

    if (
        not (promoter.can_promote_members or promoter.status == "creator")
        and user.id not in DRAGONS
    ):
        await message.reply_text("You don't have the necessary rights to do that!")
        return

    user_id = extract_user(message, args)

    if not user_id:
        await message.reply_text(
            "You don't seem to be referring to a user or the ID specified is incorrect..",
        )
        return

    try:
        user_member = await chat.get_member(user_id)
    except Exception:
        return

    if user_member.status in ("administrator", "creator"):
        await message.reply_text("How am I meant to promote someone that's already an admin?")
        return

    if user_id == bot.id:
        await message.reply_text("I can't promote myself! Get an admin to do it for me.")
        return

    bot_member = await chat.get_member(bot.id)

    try:
        await bot.promote_chat_member(
            chat.id,
            user_id,
            can_change_info=bot_member.can_change_info,
            can_post_messages=bot_member.can_post_messages,
            can_edit_messages=bot_member.can_edit_messages,
            can_delete_messages=bot_member.can_delete_messages,
            can_invite_users=bot_member.can_invite_users,
            # can_promote_members=bot_member.can_promote_members,
            can_restrict_members=bot_member.can_restrict_members,
            can_pin_messages=bot_member.can_pin_messages,
        )
    except BadRequest as err:
        if err.message == "User_not_mutual_contact":
            await message.reply_text("I can't promote someone who isn't in the group.")
        else:
            await message.reply_text("An error occurred while promoting.")
        return

    await bot.send_message(
        chat.id,
        f"Sucessfully promoted <b>{user_member.user.first_name or user_id}</b>!",
        parse_mode=ParseMode.HTML,
    )

    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#PROMOTED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(user_member.user.id, user_member.user.first_name)}"
    )

    return log_message

# --- DEMOTE ---
@connection_status
@bot_admin
@can_promote
@user_admin
@loggable
async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    bot = context.bot
    args = context.args

    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user

    user_id = extract_user(message, args)
    if not user_id:
        await message.reply_text(
            "You don't seem to be referring to a user or the ID specified is incorrect..",
        )
        return

    try:
        user_member = await chat.get_member(user_id)
    except Exception:
        return

    if user_member.status == "creator":
        await message.reply_text("This person CREATED the chat, how would I demote them?")
        return

    if user_member.status != "administrator":
        await message.reply_text("Can't demote what wasn't promoted!")
        return

    if user_id == bot.id:
        await message.reply_text("I can't demote myself! Get an admin to do it for me.")
        return

    try:
        await bot.promote_chat_member(
            chat.id,
            user_id,
            can_change_info=False,
            can_post_messages=False,
            can_edit_messages=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_promote_members=False,
        )

        await bot.send_message(
            chat.id,
            f"Sucessfully demoted <b>{user_member.user.first_name or user_id}</b>!",
            parse_mode=ParseMode.HTML,
        )

        log_message = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#DEMOTED\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User:</b> {mention_html(user_member.user.id, user_member.user.first_name)}"
        )

        return log_message
    except BadRequest:
        await message.reply_text(
            "Could not demote. I might not be admin, or the admin status was appointed by another"
            " user, so I can't act upon them!",
        )
        return

# --- REFRESH ADMIN CACHE ---
@user_admin
async def refresh_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ADMIN_CACHE.pop(update.effective_chat.id)
    except KeyError:
        pass

    await update.effective_message.reply_text("Admins cache refreshed!")

# --- SET TITLE ---
@connection_status
@bot_admin
@can_promote
@user_admin
async def set_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    args = context.args

    chat = update.effective_chat
    message = update.effective_message

    user_id, title = extract_user_and_text(message, args)
    try:
        user_member = await chat.get_member(user_id)
    except Exception:
        return

    if not user_id:
        await message.reply_text(
            "You don't seem to be referring to a user or the ID specified is incorrect..",
        )
        return

    if user_member.status == "creator":
        await message.reply_text(
            "This person CREATED the chat, how can i set custom title for him?",
        )
        return

    if user_member.status != "administrator":
        await message.reply_text(
            "Can't set title for non-admins!\nPromote them first to set custom title!",
        )
        return

    if user_id == bot.id:
        await message.reply_text(
            "I can't set my own title myself! Get the one who made me admin to do it for me.",
        )
        return

    if not title:
        await message.reply_text("Setting blank title doesn't do anything!")
        return

    if len(title) > 16:
        await message.reply_text(
            "The title length is longer than 16 characters.\nTruncating it to 16 characters.",
        )

    try:
        await bot.set_chat_administrator_custom_title(chat.id, user_id, title[:16])
    except BadRequest:
        await message.reply_text("Either they aren't promoted by me or you set a title text that is impossible to set.")
        return

    await bot.send_message(
        chat.id,
        f"Sucessfully set title for <code>{user_member.user.first_name or user_id}</code> "
        f"to <code>{html.escape(title[:16])}</code>!",
        parse_mode=ParseMode.HTML,
    )

# --- PIN ---
@bot_admin
@can_pin
@user_admin
@loggable
async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    bot = context.bot
    args = context.args

    user = update.effective_user
    chat = update.effective_chat

    is_group = chat.type not in ("private", "channel")
    prev_message = update.effective_message.reply_to_message

    is_silent = True
    if len(args) >= 1:
        is_silent = not (
            args[0].lower() == "notify"
            or args[0].lower() == "loud"
            or args[0].lower() == "violent"
        )

    if prev_message and is_group:
        try:
            await bot.pin_chat_message(
                chat.id, prev_message.message_id, disable_notification=is_silent,
            )
        except BadRequest as excp:
            if excp.message == "Chat_not_modified":
                pass
            else:
                raise
        log_message = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#PINNED\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}"
        )

        return log_message

# --- UNPIN ---
@bot_admin
@can_pin
@user_admin
@loggable
async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    bot = context.bot
    chat = update.effective_chat
    user = update.effective_user

    try:
        await bot.unpin_chat_message(chat.id)
    except BadRequest as excp:
        if excp.message == "Chat_not_modified":
            pass
        else:
            raise

    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#UNPINNED\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}"
    )

    return log_message

# --- INVITE LINK ---
@bot_admin
@user_admin
@connection_status
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat = update.effective_chat

    if chat.username:
        await update.effective_message.reply_text(f"https://t.me/{chat.username}")
    elif chat.type in ["supergroup", "channel"]:
        bot_member = await chat.get_member(bot.id)
        if bot_member.can_invite_users:
            invitelink = await bot.export_chat_invite_link(chat.id)
            await update.effective_message.reply_text(invitelink)
        else:
            await update.effective_message.reply_text(
                "I don't have access to the invite link, try changing my permissions!",
            )
    else:
        await update.effective_message.reply_text(
            "I can only give you invite links for supergroups and channels, sorry!",
        )

# --- ADMIN LIST ---
@connection_status
async def adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    args = context.args
    bot = context.bot

    if update.effective_message.chat.type == "private":
        await send_message(update.effective_message, "This command only works in Groups.")
        return

    chat = update.effective_chat
    chat_id = update.effective_chat.id

    try:
        msg = await update.effective_message.reply_text(
            "Fetching group admins...", parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        msg = await update.effective_message.reply_text(
            "Fetching group admins...", quote=False, parse_mode=ParseMode.HTML,
        )

    administrators = await bot.get_chat_administrators(chat_id)
    text = f"Admins in <b>{html.escape(update.effective_chat.title)}</b>:"

    for admin in administrators:
        user = admin.user
        status = admin.status
        custom_title = admin.custom_title

        if user.first_name == "":
            name = "☠ Deleted Account"
        else:
            name = f"{mention_html(user.id, html.escape(user.first_name + ' ' + (user.last_name or '')))}"

        if user.is_bot:
            continue

        if status == "creator":
            text += "\n 👑 Creator:"
            text += f"\n<code> • </code>{name}\n"

            if custom_title:
                text += f"<code> ┗━ {html.escape(custom_title)}</code>\n"

    text += "\n🔱 Admins:"

    custom_admin_list = {}
    normal_admin_list = []

    for admin in administrators:
        user = admin.user
        status = admin.status
        custom_title = admin.custom_title

        if user.first_name == "":
            name = "☠ Deleted Account"
        else:
            name = f"{mention_html(user.id, html.escape(user.first_name + ' ' + (user.last_name or '')))}"

        if status == "administrator":
            if custom_title:
                custom_admin_list.setdefault(custom_title, []).append(name)
            else:
                normal_admin_list.append(name)

    for admin in normal_admin_list:
        text += f"\n<code> • </code>{admin}"

    for admin_group in list(custom_admin_list):
        if len(custom_admin_list[admin_group]) == 1:
            text += f"\n<code> • </code>{custom_admin_list[admin_group][0]} | <code>{html.escape(admin_group)}</code>"
            custom_admin_list.pop(admin_group)

    text += "\n"
    for admin_group, value in custom_admin_list.items():
        text += f"\n🚨 <code>{html.escape(admin_group)}</code>"
        for admin in value:
            text += f"\n<code> • </code>{admin}"
        text += "\n"

    try:
        await msg.edit_text(text, parse_mode=ParseMode.HTML)
    except BadRequest:
        return

# --- HANDLERS ---


# --- Help Text ---
__help__ = """
✪ Admin Tools ✪

• /admins - List all admins
• /invitelink - Get group invite link
• /promote <user> [title] - Promote with optional title
• /demote <user> - Demote an admin
• /title <title> - Set admin title
• /admincache - Refresh admin list
• /pin [loud] - Pin message (add 'loud' to notify)
• /unpin - Unpin current message
"""

def setup_admin_handlers():
    handlers = [
        CommandHandler("admins", adminlist, filters=filters.ChatType.GROUPS),
        CommandHandler("pin", pin, filters=filters.ChatType.GROUPS),
        CommandHandler("unpin", unpin, filters=filters.ChatType.GROUPS),
        DisableAbleCommandHandler("promote", promote, filters=filters.ChatType.GROUPS),
        DisableAbleCommandHandler("demote", demote, filters=filters.ChatType.GROUPS),
        CommandHandler("invitelink", invite, filters=filters.ChatType.GROUPS),
        CommandHandler("title", set_title, filters=filters.ChatType.GROUPS),
        CommandHandler("admincache", refresh_admin, filters=filters.ChatType.GROUPS)
    ]
    
    for handler in handlers:
        app.add_handler(handler, group=HANDLER_GROUP)

__mod_name__ = "Admin"
__command_list__ = [
    "admins", "invitelink", "promote", 
    "demote", "admincache", "pin", "unpin", "title"
]
__handlers__ = [setup_admin_handlers()]

# Initialize handlers
setup_admin_handlers()
