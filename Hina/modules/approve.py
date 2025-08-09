from Hina.config import app
import html
from Hina.modules.disable import DisableAbleCommandHandler
from Hina.modules.helper_funcs.extraction import extract_user
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler, filters
import Hina.modules.sql.approve_sql as sql
from Hina.modules.helper_funcs.chat_status import user_admin
from Hina.modules.log_channel import loggable
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ParseMode
from telegram.helpers import mention_html
from telegram.error import BadRequest

APPROVE_GROUP = 9
@loggable
@user_admin
def approve(update, context):
    message = update.effective_message
    chat_title = message.chat.title
    chat = update.effective_chat
    args = context.args
    user = update.effective_user
    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text(
            "I don't know who you're talking about, you're going to need to specify a user!",
        )
        return ""
    try:
        member = chat.get_member(user_id)
    except BadRequest:
        return ""
    if member.status == "administrator" or member.status == "creator":
        message.reply_text(
            "User is already admin - locks, blocklists, and antiflood already don't apply to them.",
        )
        return ""
    if sql.is_approved(message.chat_id, user_id):
        message.reply_text(
            f"[{member.user['first_name']}](tg://user?id={member.user['id']}) is already approved in {chat_title}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ""
    sql.approve(message.chat_id, user_id)
    message.reply_text(
        f"[{member.user['first_name']}](tg://user?id={member.user['id']}) has been approved in {chat_title}! They will now be ignored by automated admin actions like locks, blocklists, and antiflood.",
        parse_mode=ParseMode.MARKDOWN,
    )
    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#APPROVED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
    )

    return log_message


@loggable
@user_admin
def disapprove(update, context):
    message = update.effective_message
    chat_title = message.chat.title
    chat = update.effective_chat
    args = context.args
    user = update.effective_user
    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text(
            "I don't know who you're talking about, you're going to need to specify a user!",
        )
        return ""
    try:
        member = chat.get_member(user_id)
    except BadRequest:
        return ""
    if member.status == "administrator" or member.status == "creator":
        message.reply_text("This user is an admin, they can't be unapproved.")
        return ""
    if not sql.is_approved(message.chat_id, user_id):
        message.reply_text(f"{member.user['first_name']} isn't approved yet!")
        return ""
    sql.disapprove(message.chat_id, user_id)
    message.reply_text(
        f"{member.user['first_name']} is no longer approved in {chat_title}.",
    )
    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#UNAPPROVED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
    )

    return log_message


@user_admin
def approved(update, context):
    message = update.effective_message
    chat_title = message.chat.title
    chat = update.effective_chat
    msg = "The following users are approved.\n"
    approved_users = sql.list_approved(message.chat_id)
    for i in approved_users:
        member = chat.get_member(int(i.user_id))
        msg += f"- `{i.user_id}`: {member.user['first_name']}\n"
    if msg.endswith("approved.\n"):
        message.reply_text(f"No users are approved in {chat_title}.")
        return ""
    else:
        message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


@user_admin
def approval(update, context):
    message = update.effective_message
    chat = update.effective_chat
    args = context.args
    user_id = extract_user(message, args)
    member = chat.get_member(int(user_id))
    if not user_id:
        message.reply_text(
            "I don't know who you're talking about, you're going to need to specify a user!",
        )
        return ""
    if sql.is_approved(message.chat_id, user_id):
        message.reply_text(
            f"{member.user['first_name']} is an approved user. Locks, antiflood, and blocklists won't apply to them.",
        )
    else:
        message.reply_text(
            f"{member.user['first_name']} is not an approved user. They are affected by normal commands.",
        )


def unapproveall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    member = chat.get_member(user.id)
    if member.status != "creator" and user.id not in DRAGONS:
        update.effective_message.reply_text(
            "Only the chat owner can unapprove all users at once.",
        )
    else:
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Unapprove all users", callback_data="unapproveall_user",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="Cancel", callback_data="unapproveall_cancel",
                    ),
                ],
            ],
        )
        update.effective_message.reply_text(
            f"Are you sure you would like to unapprove ALL users in {chat.title}? This action cannot be undone.",
            reply_markup=buttons,
            parse_mode=ParseMode.MARKDOWN,
        )


def unapproveall_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = update.effective_chat
    message = update.effective_message
    member = chat.get_member(query.from_user.id)
    if query.data == "unapproveall_user":
        if member.status == "creator" or query.from_user.id in DRAGONS:
            approved_users = sql.list_approved(chat.id)
            users = [int(i.user_id) for i in approved_users]
            for user_id in users:
                sql.disapprove(chat.id, user_id)      
            message.edit_text("Successfully Unapproved all user in this Chat.")
            return

        if member.status == "administrator":
            query.answer("Only owner of the chat can do this.")

        if member.status == "member":
            query.answer("You need to be admin to do this.")
    elif query.data == "unapproveall_cancel":
        if member.status == "creator" or query.from_user.id in DRAGONS:
            message.edit_text("Removing of all approved users has been cancelled.")
            return ""
        if member.status == "administrator":
            query.answer("Only owner of the chat can do this.")
        if member.status == "member":
            query.answer("You need to be admin to do this.")


# [Previous imports and functions remain exactly the same...]

# Handlers
APPROVE_HANDLER = CommandHandler("approve", approve, filters=filters.ChatType.GROUPS)
DISAPPROVE_HANDLER = CommandHandler(["disapprove", "unapprove"], disapprove, filters=filters.ChatType.GROUPS)
APPROVED_HANDLER = CommandHandler("approved", approved, filters=filters.ChatType.GROUPS)
UNAPPROVEALL_HANDLER = CommandHandler("unapproveall", unapproveall, filters=filters.ChatType.GROUPS)
UNAPPROVEALL_BTN_HANDLER = CallbackQueryHandler(unapproveall_btn, pattern=r"unapproveall_")

# Add handlers directly to app like afk.py does
app.add_handler(APPROVE_HANDLER, APPROVE_GROUP)
app.add_handler(DISAPPROVE_HANDLER, APPROVE_GROUP)
app.add_handler(APPROVED_HANDLER, APPROVE_GROUP)
app.add_handler(UNAPPROVEALL_HANDLER, APPROVE_GROUP)
app.add_handler(UNAPPROVEALL_BTN_HANDLER)

__mod_name__ = "Approvals"
__help__ = """
✅ *Approval System*

Sometimes, you might want to approve users to bypass certain restrictions like antiflood, blacklists, or warns. This module handles that!

*Commands:*
• `/approve <user> [reason]` - Approve a user in the chat
• `/disapprove` or `/unapprove <user>` - Remove a user's approval
• `/approved` - List all approved users
• `/unapproveall` - Unapprove ALL users in a chat (owner only)
"""

__handlers__ = [
    (APPROVE_HANDLER, APPROVE_GROUP),
    (DISAPPROVE_HANDLER, APPROVE_GROUP),
    (APPROVED_HANDLER, APPROVE_GROUP),
    (UNAPPROVEALL_HANDLER, APPROVE_GROUP),
    (UNAPPROVEALL_BTN_HANDLER)
]
