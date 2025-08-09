import importlib
import time
import re
from typing import Optional

from Hina.config import (
    ALLOW_EXCL,
    CERT_PATH,
    DONATION_LINK,
    LOGGER,
    OWNER_ID,
    PORT,
    TOKEN,
    URL,
    WEBHOOK,
    SUPPORT_CHAT,
    dispatcher,
    StartTime,
    telethn,
    PM_START_TEMPLATE,
    HELP_TEMPLATE,
    SAITAMA_IMG,
    DONATE_STRING,
    IMPORTED,
    MIGRATEABLE,
    HELPABLE,
    STATS,
    USER_INFO,
    DATA_IMPORT,
    DATA_EXPORT,
    CHAT_SETTINGS,
    USER_SETTINGS
)
from Hina.modules import ALL_MODULES
from Hina.modules.helper_funcs.chat_status import is_user_admin
from Hina.modules.helper_funcs.misc import paginate_modules

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, ChatMigrated, NetworkError, TelegramError, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.helpers import escape_markdown

def get_readable_time(seconds: int) -> str:
    count = 0
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        if count < 3:
            seconds, result = divmod(seconds, 60)
        else:
            seconds, result = divmod(seconds, 24)
        if seconds == 0 and result == 0:
            break
        time_list.append(int(result))
    formatted = []
    for idx, val in enumerate(time_list):
        formatted.append(f"{val}{time_suffix_list[idx]}")
    if len(formatted) == 4:
        days = formatted.pop()
        formatted.insert(0, days + ",")
    return ":".join(reversed(formatted))

for module_name in ALL_MODULES:
    imported_module = importlib.import_module("Hina.modules." + module_name)
    if not hasattr(imported_module, "__mod_name__"):
        imported_module.__mod_name__ = imported_module.__name__
    if imported_module.__mod_name__.lower() not in IMPORTED:
        IMPORTED[imported_module.__mod_name__.lower()] = imported_module
    else:
        raise Exception("Can't have two modules with the same name! Please change one")
    if hasattr(imported_module, "__help__") and imported_module.__help__:
        HELPABLE[imported_module.__mod_name__.lower()] = imported_module
    if hasattr(imported_module, "__migrate__"):
        MIGRATEABLE.append(imported_module)
    if hasattr(imported_module, "__stats__"):
        STATS.append(imported_module)
    if hasattr(imported_module, "__user_info__"):
        USER_INFO.append(imported_module)
    if hasattr(imported_module, "__import_data__"):
        DATA_IMPORT.append(imported_module)
    if hasattr(imported_module, "__export_data__"):
        DATA_EXPORT.append(imported_module)
    if hasattr(imported_module, "__chat_settings__"):
        CHAT_SETTINGS[imported_module.__mod_name__.lower()] = imported_module
    if hasattr(imported_module, "__user_settings__"):
        USER_SETTINGS[imported_module.__mod_name__.lower()] = imported_module

async def send_help(chat_id, text, app, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
    await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("This person edited a message")
    print(update.effective_message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    uptime = get_readable_time((time.time() - StartTime))
    if update.effective_chat.type == "private":
        if len(args) >= 1:
            if args[0].lower() == "help":
                await send_help(update.effective_chat.id, HELP_TEMPLATE, context.application)
            elif args[0].lower().startswith("ghelp_"):
                mod = args[0].lower().split("_", 1)[1]
                if not HELPABLE.get(mod, False):
                    return
                await send_help(
                    update.effective_chat.id,
                    HELPABLE[mod].__help__,
                    context.application,
                    InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="Back", callback_data="help_back")]],
                    ),
                )
            elif args[0].lower() == "markdownhelp":
                IMPORTED["extras"].markdown_help_sender(update)
            elif args[0].lower() == "disasters":
                IMPORTED["disasters"].send_disasters(update)
            elif args[0].lower().startswith("stngs_"):
                match = re.match("stngs_(.*)", args[0].lower())
                chat = await context.bot.getChat(match.group(1))
                if is_user_admin(chat, update.effective_user.id):
                    await send_settings(match.group(1), update.effective_user.id, context, False)
                else:
                    await send_settings(match.group(1), update.effective_user.id, context, True)
            elif args[0][1:].isdigit() and "rules" in IMPORTED:
                IMPORTED["rules"].send_rules(update, args[0], from_pm=True)
        else:
            first_name = update.effective_user.first_name
            await update.effective_message.reply_photo(
                SAITAMA_IMG,
                PM_START_TEMPLATE.format(
                    escape_markdown(first_name), escape_markdown(context.bot.first_name),
                ),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="☑️ Add me",
                                url=f"t.me/{context.bot.username}?startgroup=true",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="🚑 Support",
                                url=f"https://t.me/{SUPPORT_CHAT}",
                            ),
                            InlineKeyboardButton(
                                text="🔔 Updates",
                                url="https://t.me/OnePunchUpdates",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="🧾 Getting Started",
                                url="https://t.me/OnePunchUpdates/29",
                            ),
                            InlineKeyboardButton(
                                text="🗄 Source code",
                                url="https://github.com/AnimeKaizoku/Hina",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="☠️ Kaizoku Network",
                                url="https://t.me/Kaizoku/4",
                            ),
                        ],
                    ],
                ),
            )
    else:
        await update.effective_message.reply_text(
            f"I'm awake already!\n<b>Haven't slept since:</b> <code>{uptime}</code>",
            parse_mode=ParseMode.HTML,
        )

async def error_callback(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    try:
        raise error
    except TelegramError:
        LOGGER.error(error)
    except BadRequest:
        LOGGER.error(f"BadRequest caught: {error}")
    except TimedOut:
        LOGGER.error("TimedOut")
    except NetworkError:
        LOGGER.error("NetworkError")
    except ChatMigrated as err:
        LOGGER.error(f"ChatMigrated: {err}")
    except Exception as err:
        LOGGER.error(f"Unknown error: {err}")

async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)
    try:
        if mod_match:
            module = mod_match.group(1)
            text = (
                f"Here is the help for the *{HELPABLE[module].__mod_name__}* module:\n"
                + HELPABLE[module].__help__
            )
            await query.message.edit_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="Back", callback_data="help_back")]],
                ),
            )
        elif prev_match:
            curr_page = int(prev_match.group(1))
            await query.message.edit_text(
                text=HELP_TEMPLATE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(curr_page - 1, HELPABLE, "help"),
                ),
            )
        elif next_match:
            next_page = int(next_match.group(1))
            await query.message.edit_text(
                text=HELP_TEMPLATE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(next_page + 1, HELPABLE, "help"),
                ),
            )
        elif back_match:
            await query.message.edit_text(
                text=HELP_TEMPLATE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, HELPABLE, "help"),
                ),
            )
        await context.bot.answer_callback_query(query.id)
    except BadRequest:
        pass

async def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = update.effective_message.text.split(None, 1)
    if chat.type != chat.PRIVATE:
        if len(args) >= 2 and any(args[1].lower() == x for x in HELPABLE):
            module = args[1].lower()
            await update.effective_message.reply_text(
                f"Contact me in PM to get help of {module.capitalize()}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="Help",
                                url=f"t.me/{context.bot.username}?start=ghelp_{module}",
                            ),
                        ],
                    ],
                ),
            )
            return
        await update.effective_message.reply_text(
            "Contact me in PM to get the list of possible commands.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Help",
                            url=f"t.me/{context.bot.username}?start=help",
                        ),
                    ],
                ],
            ),
        )
        return
    elif len(args) >= 2 and any(args[1].lower() == x for x in HELPABLE):
        module = args[1].lower()
        text = f"Here is the available help for the *{HELPABLE[module].__mod_name__}* module:\n" + HELPABLE[module].__help__
        await send_help(
            chat.id,
            text,
            context.application,
            InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="Back", callback_data="help_back")]],
            ),
        )
    else:
        await send_help(chat.id, HELP_TEMPLATE, context.application)

async def send_settings(chat_id, user_id, context, user=False):
    if user:
        if USER_SETTINGS:
            settings = "\n\n".join(
                f"*{mod.__mod_name__}*:\n{mod.__user_settings__(user_id)}"
                for mod in USER_SETTINGS.values()
            )
            await context.bot.send_message(
                user_id,
                "These are your current settings:\n\n" + settings,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await context.bot.send_message(
                user_id,
                "Seems like there aren't any user specific settings available :'(",
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        if CHAT_SETTINGS:
            chat_name = (await context.bot.getChat(chat_id)).title
            await context.bot.send_message(
                user_id,
                text=f"Which module would you like to check {chat_name}'s settings for?",
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id),
                ),
            )
        else:
            await context.bot.send_message(
                user_id,
                "Seems like there aren't any chat settings available :'(\nSend this "
                "in a group chat you're admin in to find its current settings!",
                parse_mode=ParseMode.MARKDOWN,
            )

async def settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mod_match = re.match(r"stngs_module\((.+?),(.+?)\)", query.data)
    prev_match = re.match(r"stngs_prev\((.+?),(.+?)\)", query.data)
    next_match = re.match(r"stngs_next\((.+?),(.+?)\)", query.data)
    back_match = re.match(r"stngs_back\((.+?)\)", query.data)
    try:
        if mod_match:
            chat_id, module = mod_match.groups()
            text = (
                f"Here are the settings for the *{CHAT_SETTINGS[module].__mod_name__}* module:\n"
                + CHAT_SETTINGS[module].__chat_settings__(int(chat_id), query.from_user.id)
            )
            await query.message.edit_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="Back", callback_data=f"stngs_back({chat_id})")]],
                ),
            )
        elif prev_match:
            chat_id, curr_page = prev_match.groups()
            curr_page = int(curr_page)
            await query.message.edit_text(
                text="Hi there! Here are the available modules for settings:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(curr_page - 1, CHAT_SETTINGS, "stngs", chat=chat_id),
                ),
            )
        elif next_match:
            chat_id, next_page = next_match.groups()
            next_page = int(next_page)
            await query.message.edit_text(
                text="Hi there! Here are the available modules for settings:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(next_page + 1, CHAT_SETTINGS, "stngs", chat=chat_id),
                ),
            )
        elif back_match:
            chat_id = back_match.group(1)
            await query.message.edit_text(
                text="Hi there! Here are the available modules for settings:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id),
                ),
            )
        await context.bot.answer_callback_query(query.id)
    except BadRequest:
        pass

async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_message.from_user
    chat = update.effective_chat
    bot = context.bot
    if chat.type == "private":
        await update.effective_message.reply_text(
            DONATE_STRING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
        )
        if OWNER_ID != 254318997 and DONATION_LINK:
            await update.effective_message.reply_text(
                f"You can also donate to the person currently running me [here]({DONATION_LINK})",
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        try:
            await bot.send_message(
                user.id,
                DONATE_STRING,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            await update.effective_message.reply_text(
                "I've PM'ed you about donating to my creator!",
            )
        except TelegramError:
            await update.effective_message.reply_text(
                "Contact me in PM first to get donation information.",
            )

async def migrate_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.migrate_to_chat_id:
        for mod in MIGRATEABLE:
            mod.__migrate__(msg.chat.id, msg.migrate_to_chat_id)
        LOGGER.info(f"Migrated chat {msg.chat.id} to {msg.migrate_to_chat_id}")

async def ensure_bot_in_db(bot):
    # Add logic to ensure the bot is in your database if you use one
    pass

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    await ensure_bot_in_db(app.bot)
    # Notify support chat
    if SUPPORT_CHAT:
        try:
            await app.bot.send_message(
                chat_id=f"@{SUPPORT_CHAT}",
                text="✅ I am now online!",
            )
        except TelegramError:
            LOGGER.warning("Bot isn't able to send message to SUPPORT_CHAT.")
        except BadRequest as e:
            LOGGER.warning("BadRequest when messaging SUPPORT_CHAT: %s", e.message)
    # Handlers
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", get_help))
    app.add_handler(CallbackQueryHandler(help_button, pattern=r"help_.*"))
    app.add_handler(CommandHandler("settings", get_help))
    app.add_handler(CallbackQueryHandler(settings_button, pattern=r"stngs_.*"))
    app.add_handler(CommandHandler("donate", donate))
    app.add_handler(MessageHandler(filters.StatusUpdate.MIGRATE, migrate_chats))
    app.add_error_handler(error_callback)
    # Telethon Events — Add your pattern-based handlers here
    @telethn.on(events.NewMessage(pattern=r"^/alive$"))
    async def telethon_alive(event):
        await event.reply("✅ Bot is alive and working via Telethon!")
    @telethn.on(events.NewMessage(pattern=r"^/ping$"))
    async def telethon_ping(event):
        await event.reply("🏓 Pong from Telethon!")
    # Start both PTB and Telethon
    if WEBHOOK:
        LOGGER.info("Using webhooks.")
        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=URL + TOKEN,
            cert=CERT_PATH and open(CERT_PATH, "rb"),
        )
    else:
        LOGGER.info("Using long polling.")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
    LOGGER.info("Starting Telethon client...")
    await telethn.start(bot_token=TOKEN)
    await telethn.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())