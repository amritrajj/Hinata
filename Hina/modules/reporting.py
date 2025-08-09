from Hina.config import app
import html
import re

from Hina.config import LOGGER, DRAGONS, TIGERS, WOLVES
from Hina.modules.helper_funcs.chat_status import user_admin, user_not_admin
from Hina.modules.log_channel import loggable
from Hina.modules.sql import reporting_sql as sql

from telegram import (
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode, ChatType
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    ContextTypes,
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.helpers import mention_html

REPORT_GROUP = 12
REPORT_IMMUNE_USERS = set(DRAGONS) | set(TIGERS) | set(WOLVES)

@user_admin
async def report_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    args = context.args
    chat = update.effective_chat
    msg = update.effective_message

    if chat.type == ChatType.PRIVATE:
        if len(args) >= 1:
            if args[0].lower() in ("yes", "on"):
                sql.set_user_setting(chat.id, True)
                await msg.reply_text(
                    "Turned on reporting! You'll be notified whenever anyone reports something.",
                )
            elif args[0].lower() in ("no", "off"):
                sql.set_user_setting(chat.id, False)
                await msg.reply_text("Turned off reporting! You won't get any reports.")
        else:
            await msg.reply_text(
                f"Your current report preference is: `{sql.user_should_report(chat.id)}`",
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        if len(args) >= 1:
            if args[0].lower() in ("yes", "on"):
                sql.set_chat_setting(chat.id, True)
                await msg.reply_text(
                    "Turned on reporting! Admins who have turned on reports will be notified when /report "
                    "or @admin is called.",
                )
            elif args[0].lower() in ("no", "off"):
                sql.set_chat_setting(chat.id, False)
                await msg.reply_text(
                    "Turned off reporting! No admins will be notified on /report or @admin.",
                )
        else:
            await msg.reply_text(
                f"This group's current setting is: `{sql.chat_should_report(chat.id)}`",
                parse_mode=ParseMode.MARKDOWN,
            )

@user_not_admin
@loggable
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    bot = context.bot
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not (chat and message.reply_to_message and sql.chat_should_report(chat.id)):
        return ""

    reported_user = message.reply_to_message.from_user
    chat_name = chat.title or chat.first_name or chat.username
    admin_list = await chat.get_administrators()

    if not args:
        await message.reply_text("Add a reason for reporting first.")
        return ""

    if user.id == reported_user.id:
        await message.reply_text("Uh yeah, Sure sure...maso much?")
        return ""

    if user.id == bot.id:
        await message.reply_text("Nice try.")
        return ""

    if reported_user.id in REPORT_IMMUNE_USERS:
        await message.reply_text("Uh? You reporting a disaster?")
        return ""

    if chat.username and chat.type == ChatType.SUPERGROUP:
        reported = f"{mention_html(user.id, user.first_name)} reported {mention_html(reported_user.id, reported_user.first_name)} to the admins!"

        msg = (
            f"<b>⚠️ Report: </b>{html.escape(chat.title)}\n"
            f"<b> • Report by:</b> {mention_html(user.id, user.first_name)}(<code>{user.id}</code>)\n"
            f"<b> • Reported user:</b> {mention_html(reported_user.id, reported_user.first_name)} (<code>{reported_user.id}</code>)\n"
        )
        link = f'<b> • Reported message:</b> <a href="https://t.me/{chat.username}/{message.reply_to_message.message_id}">click here</a>'
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "➡ Message",
                    url=f"https://t.me/{chat.username}/{message.reply_to_message.message_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚠ Kick",
                    callback_data=f"report_{chat.id}=kick={reported_user.id}={reported_user.first_name}",
                ),
                InlineKeyboardButton(
                    "⛔️ Ban",
                    callback_data=f"report_{chat.id}=banned={reported_user.id}={reported_user.first_name}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❎ Delete Message",
                    callback_data=f"report_{chat.id}=delete={reported_user.id}={message.reply_to_message.message_id}",
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        should_forward = False
    else:
        reported = f"{mention_html(user.id, user.first_name)} reported {mention_html(reported_user.id, reported_user.first_name)} to the admins!"
        msg = f'{mention_html(user.id, user.first_name)} is calling for admins in "{html.escape(chat_name)}"!'
        link = ""
        reply_markup = None
        should_forward = True

    for admin in admin_list:
        if admin.user.is_bot:  # Skip bots
            continue

        if sql.user_should_report(admin.user.id):
            try:
                if chat.type != ChatType.SUPERGROUP:
                    await bot.send_message(
                        admin.user.id, 
                        msg + link, 
                        parse_mode=ParseMode.HTML,
                    )
                    if should_forward:
                        await message.reply_to_message.forward(admin.user.id)
                        if len(message.text.split()) > 1:
                            await message.forward(admin.user.id)
                
                elif not chat.username:
                    await bot.send_message(
                        admin.user.id,
                        msg + link,
                        parse_mode=ParseMode.HTML,
                    )
                    if should_forward:
                        await message.reply_to_message.forward(admin.user.id)
                        if len(message.text.split()) > 1:
                            await message.forward(admin.user.id)
                
                else:
                    await bot.send_message(
                        admin.user.id,
                        msg + link,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                    )
                    if should_forward:
                        await message.reply_to_message.forward(admin.user.id)
                        if len(message.text.split()) > 1:
                            await message.forward(admin.user.id)

            except TelegramError:
                LOGGER.exception("Couldn't send report to admin %s", admin.user.id)
            except BadRequest as excp:
                LOGGER.exception("Exception while reporting user: %s", excp)

    await message.reply_to_message.reply_text(
        f"{mention_html(user.id, user.first_name)} reported the message to the admins.",
        parse_mode=ParseMode.HTML,
    )
    return msg

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    query = update.callback_query
    splitter = query.data.replace("report_", "").split("=")
    
    try:
        if splitter[1] == "kick":
            await bot.ban_chat_member(splitter[0], splitter[2])
            await bot.unban_chat_member(splitter[0], splitter[2])
            await query.answer("✅ Successfully kicked")
            
        elif splitter[1] == "banned":
            await bot.ban_chat_member(splitter[0], splitter[2])
            await query.answer("✅ Successfully Banned")
            
        elif splitter[1] == "delete":
            await bot.delete_message(splitter[0], splitter[3])
            await query.answer("✅ Message Deleted")
            
    except Exception as err:
        await query.answer("🛑 Failed to perform action")
        await bot.send_message(
            text=f"Error: {err}",
            chat_id=query.message.chat_id,
            parse_mode=ParseMode.HTML,
        )

def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)

def __chat_settings__(chat_id, _):
    return f"This chat is setup to send user reports to admins, via /report and @admin: `{sql.chat_should_report(chat_id)}`"

def __user_settings__(user_id):
    return (
        "You will receive reports from chats you're admin."
        if sql.user_should_report(user_id) 
        else "You will *not* receive reports from chats you're admin."
    )


__mod_name__ = "Reporting"
__help__ = """
 • `/report <reason>`*:* reply to a message to report it to admins.
 • `@admin`*:* reply to a message to report it to admins.
*NOTE:* Neither of these will get triggered if used by admins.

*Admins only:*
 • `/reports <on/off>`*:* change report setting, or view current status.
   • If done in pm, toggles your status.
   • If in group, toggles that groups's status.
"""

SETTING_HANDLER = CommandHandler("reports", report_setting)
REPORT_HANDLER = CommandHandler("report", report, filters=filters.ChatType.GROUPS)
ADMIN_REPORT_HANDLER = MessageHandler(filters.Regex(r"(?i)@admin(s)?"), report)
REPORT_BUTTON_USER_HANDLER = CallbackQueryHandler(buttons, pattern=r"report_")

app.add_handler(REPORT_BUTTON_USER_HANDLER)
app.add_handler(SETTING_HANDLER)
app.add_handler(REPORT_HANDLER, group=REPORT_GROUP)
app.add_handler(ADMIN_REPORT_HANDLER, group=REPORT_GROUP)

__handlers__ = [
    (REPORT_HANDLER, REPORT_GROUP),
    (ADMIN_REPORT_HANDLER, REPORT_GROUP),
    SETTING_HANDLER,
    REPORT_BUTTON_USER_HANDLER
]
