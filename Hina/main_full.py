# main.py - comprehensive startup file (rewritten)
"""
Main entrypoint for Hina bot. Designed to work with the comprehensive config
file (Hina.config). Starts PTB and Telethon concurrently. Imports modules
after the PTB Application is created so legacy modules can register handlers
at import-time.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import time
import signal
from typing import Optional, Iterable

from Hina import config as cfg
from Hina.modules import ALL_MODULES
from Hina.modules.helper_funcs.misc import paginate_modules

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, ChatMigrated, NetworkError, TelegramError, TimedOut
from telegram.ext import filters, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes
from telegram.helpers import escape_markdown
from telethon import events

LOGGER: logging.Logger = cfg.LOGGER
app = cfg.app
telethn = cfg.telethn
StartTime = cfg.StartTime

if app is None:
    LOGGER.error("PTB Application was not created in Hina.config. Aborting startup.")
    raise SystemExit(1)

# --- Import all modules after app exists ---
failed_modules = []
for module_name in ALL_MODULES:
    try:
        importlib.import_module("Hina.modules." + module_name)
    except Exception:
        LOGGER.exception("Failed to import module %s", module_name)
        failed_modules.append(module_name)

if failed_modules:
    LOGGER.warning("Some modules failed to import: %s", failed_modules)

# --- Core helper functions that must remain (kept from original design) ---
async def send_help(chat_id, text, application, keyboard=None):
    """
    Send the help text to chat_id using the given application instance.
    Preserves original signature used across modules.
    """
    if keyboard is None:
        keyboard = InlineKeyboardMarkup(paginate_modules(0, cfg.HELPABLE, "help"))
    await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A tiny test command used by modules for sanity checks."""
    await update.effective_message.reply_text("This person edited a message")
    LOGGER.debug("test command called: %s", update.effective_message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    The original start function signature is preserved to avoid touching any module
    that calls it by name.
    """
    args = context.args if hasattr(context, "args") else []
    uptime = cfg.get_readable_time(time.time() - StartTime)
    if update.effective_chat.type == "private":
        if len(args) >= 1:
            if args[0].lower() == "help":
                await send_help(update.effective_chat.id, cfg.HELP_TEMPLATE, context.application)
            elif args[0].lower().startswith("ghelp_"):
                mod = args[0].lower().split("_", 1)[1]
                if not cfg.HELPABLE.get(mod, False):
                    return
                await send_help(
                    update.effective_chat.id,
                    cfg.HELPABLE[mod].__help__,
                    context.application,
                    InlineKeyboardMarkup([[InlineKeyboardButton(text="Back", callback_data="help_back")]]),
                )
            elif args[0].lower() == "markdownhelp":
                if "extras" in cfg.IMPORTED:
                    try:
                        cfg.IMPORTED["extras"].markdown_help_sender(update)
                    except Exception:
                        LOGGER.exception("Failed to call markdown_help_sender in extras module.")
            elif args[0].lower() == "disasters":
                if "disasters" in cfg.IMPORTED:
                    try:
                        cfg.IMPORTED["disasters"].send_disasters(update)
                    except Exception:
                        LOGGER.exception("Failed to call send_disasters in disasters module.")
            elif args[0].lower().startswith("stngs_"):
                import re
                match = re.match("stngs_(.*)", args[0].lower())
                try:
                    chat = await context.bot.getChat(match.group(1))
                except Exception:
                    LOGGER.exception("Failed getting chat for stngs target: %s", match.group(1))
                    return
                if is_user_admin(chat, update.effective_user.id):
                    await send_settings(match.group(1), update.effective_user.id, context, False)
                else:
                    await send_settings(match.group(1), update.effective_user.id, context, True)
            elif args[0][1:].isdigit() and "rules" in cfg.IMPORTED:
                try:
                    cfg.IMPORTED["rules"].send_rules(update, args[0], from_pm=True)
                except Exception:
                    LOGGER.exception("Failed to call send_rules in rules module.")
        else:
            first_name = update.effective_user.first_name
            await update.effective_message.reply_photo(
                cfg.SAITAMA_IMG,
                cfg.PM_START_TEMPLATE.format(escape_markdown(first_name), escape_markdown(context.bot.first_name)),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(text="☑️ Add me", url=f"t.me/{context.bot.username}?startgroup=true"),
                        ],
                        [
                            InlineKeyboardButton(text="🚑 Support", url=f"https://t.me/{cfg.SUPPORT_CHAT}"),
                            InlineKeyboardButton(text="🔔 Updates", url="https://t.me/OnePunchUpdates"),
                        ],
                        [
                            InlineKeyboardButton(text="🧾 Getting Started", url="https://t.me/OnePunchUpdates/29"),
                            InlineKeyboardButton(text="🗄 Source code", url="https://github.com/AnimeKaizoku/Hina"),
                        ],
                        [InlineKeyboardButton(text="☠️ Kaizoku Network", url="https://t.me/Kaizoku/4")],
                    ]
                ),
            )
    else:
        await update.effective_message.reply_text(
            f"I'm awake already!\n<b>Haven't slept since:</b> <code>{uptime}</code>",
            parse_mode=ParseMode.HTML,
        )

async def error_callback(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Preserved original error handler signature for compatibility with older modules.
    It logs different exception types and falls back to a generic logger.
    """
    error = context.error if hasattr(context, "error") else context
    try:
        raise error
    except TelegramError:
        LOGGER.error(error)
    except BadRequest:
        LOGGER.error("BadRequest caught: %s", error)
    except TimedOut:
        LOGGER.error("TimedOut")
    except NetworkError:
        LOGGER.error("NetworkError")
    except ChatMigrated as err:
        LOGGER.error("ChatMigrated: %s", err)
    except Exception as err:
        LOGGER.error("Unknown error: %s", err)

# Helper functions referenced in start()
from Hina.modules.helper_funcs.chat_status import is_user_admin

async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    import re
    mod_match = re.match(r"help_module\\((.+?)\\)", data)
    prev_match = re.match(r"help_prev\\((.+?)\\)", data)
    next_match = re.match(r"help_next\\((.+?)\\)", data)
    back_match = re.match(r"help_back", data)
    try:
        if mod_match:
            module = mod_match.group(1)
            text = f"Here is the help for the *{cfg.HELPABLE[module].__mod_name__}* module:\\n" + cfg.HELPABLE[module].__help__
            await query.message.edit_text(text=text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="Back", callback_data="help_back")]]))
        elif prev_match:
            curr_page = int(prev_match.group(1))
            await query.message.edit_text(text=cfg.HELP_TEMPLATE, parse_mode=ParseMode.MARKDOWN,
                                          reply_markup=InlineKeyboardMarkup(paginate_modules(curr_page - 1, cfg.HELPABLE, "help")))
        elif next_match:
            next_page = int(next_match.group(1))
            await query.message.edit_text(text=cfg.HELP_TEMPLATE, parse_mode=ParseMode.MARKDOWN,
                                          reply_markup=InlineKeyboardMarkup(paginate_modules(next_page + 1, cfg.HELPABLE, "help")))
        elif back_match:
            await query.message.edit_text(text=cfg.HELP_TEMPLATE, parse_mode=ParseMode.MARKDOWN,
                                          reply_markup=InlineKeyboardMarkup(paginate_modules(0, cfg.HELPABLE, "help")))
        await context.bot.answer_callback_query(query.id)
    except BadRequest:
        # Ignore cases where message was not modified or invalid callback
        LOGGER.debug("BadRequest in help_button (likely message edit no-op).")

async def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = update.effective_message.text.split(None, 1)
    if chat.type != chat.PRIVATE:
        if len(args) >= 2 and any(args[1].lower() == x for x in cfg.HELPABLE):
            module = args[1].lower()
            await update.effective_message.reply_text(
                f"Contact me in PM to get help of {module.capitalize()}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="Help", url=f"t.me/{context.bot.username}?start=ghelp_{module}")]]
                ),
            )
            return
        await update.effective_message.reply_text(
            "Contact me in PM to get the list of possible commands.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="Help", url=f"t.me/{context.bot.username}?start=help")]]),
        )
        return
    elif len(args) >= 2 and any(args[1].lower() == x for x in cfg.HELPABLE):
        module = args[1].lower()
        text = f"Here is the available help for the *{cfg.HELPABLE[module].__mod_name__}* module:\\n" + cfg.HELPABLE[module].__help__
        await send_help(chat.id, text, context.application, InlineKeyboardMarkup([[InlineKeyboardButton(text="Back", callback_data="help_back")]]))
    else:
        await send_help(chat.id, cfg.HELP_TEMPLATE, context.application)

async def send_settings(chat_id, user_id, context, user=False):
    if user:
        if cfg.USER_SETTINGS:
            settings = "\n\n".join(f"*{mod.__mod_name__}*:\n{mod.__user_settings__(user_id)}" for mod in cfg.USER_SETTINGS.values())
            await context.bot.send_message(user_id, "These are your current settings:\n\n" + settings, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(user_id, "Seems like there aren't any user specific settings available :'(", parse_mode=ParseMode.MARKDOWN)
    else:
        if cfg.CHAT_SETTINGS:
            chat_name = (await context.bot.getChat(chat_id)).title
            await context.bot.send_message(user_id, text=f"Which module would you like to check {chat_name}'s settings for?",
                                           reply_markup=InlineKeyboardMarkup(paginate_modules(0, cfg.CHAT_SETTINGS, "stngs", chat=chat_id)))
        else:
            await context.bot.send_message(user_id, "Seems like there aren't any chat settings available :'(\\nSend this in a group chat you're admin in to find its current settings!",
                                           parse_mode=ParseMode.MARKDOWN)

async def settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    import re
    mod_match = re.match(r"stngs_module\\((.+?),(.+?)\\)", data)
    prev_match = re.match(r"stngs_prev\\((.+?),(.+?)\\)", data)
    next_match = re.match(r"stngs_next\\((.+?),(.+?)\\)", data)
    back_match = re.match(r"stngs_back\\((.+?)\\)", data)
    try:
        if mod_match:
            chat_id, module = mod_match.groups()
            text = f"Here are the settings for the *{cfg.CHAT_SETTINGS[module].__mod_name__}* module:\\n" + cfg.CHAT_SETTINGS[module].__chat_settings__(int(chat_id), query.from_user.id)
            await query.message.edit_text(text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="Back", callback_data=f"stngs_back({chat_id})")]]))
        elif prev_match:
            chat_id, curr_page = prev_match.groups()
            curr_page = int(curr_page)
            await query.message.edit_text(text="Hi there! Here are the available modules for settings:", parse_mode=ParseMode.MARKDOWN,
                                          reply_markup=InlineKeyboardMarkup(paginate_modules(curr_page - 1, cfg.CHAT_SETTINGS, "stngs", chat=chat_id)))
        elif next_match:
            chat_id, next_page = next_match.groups()
            next_page = int(next_page)
            await query.message.edit_text(text="Hi there! Here are the available modules for settings:", parse_mode=ParseMode.MARKDOWN,
                                          reply_markup=InlineKeyboardMarkup(paginate_modules(next_page + 1, cfg.CHAT_SETTINGS, "stngs", chat=chat_id)))
        elif back_match:
            chat_id = back_match.group(1)
            await query.message.edit_text(text="Hi there! Here are the available modules for settings:", parse_mode=ParseMode.MARKDOWN,
                                          reply_markup=InlineKeyboardMarkup(paginate_modules(0, cfg.CHAT_SETTINGS, "stngs", chat=chat_id)))
        await context.bot.answer_callback_query(query.id)
    except BadRequest:
        LOGGER.debug("BadRequest in settings_button (likely harmless).")

async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_message.from_user
    chat = update.effective_chat
    bot = context.bot
    if chat.type == "private":
        await update.effective_message.reply_text(cfg.DONATE_STRING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        if cfg.OWNER_ID and cfg.DONATION_LINK:
            await update.effective_message.reply_text(f"You can also donate to the person currently running me [here]({cfg.DONATION_LINK})", parse_mode=ParseMode.MARKDOWN)
    else:
        try:
            await bot.send_message(user.id, cfg.DONATE_STRING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            await update.effective_message.reply_text("I've PM'ed you about donating to my creator!")
        except TelegramError:
            await update.effective_message.reply_text("Contact me in PM first to get donation information.")

async def migrate_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if getattr(msg, "migrate_to_chat_id", None):
        for mod in cfg.MIGRATEABLE:
            try:
                mod.__migrate__(msg.chat.id, msg.migrate_to_chat_id)
            except Exception:
                LOGGER.exception("Module migration failed for %s", getattr(mod, "__mod_name__", str(mod)))
        LOGGER.info("Migrated chat %s to %s", msg.chat.id, msg.migrate_to_chat_id)

async def ensure_bot_in_db(bot):
    # Placeholder: implement DB logic if you have a persistence layer.
    LOGGER.debug("ensure_bot_in_db called (no-op).")
    return

# --- Register core handlers if modules didn't already ---
def _safe_add_handler(handler):
    try:
        app.add_handler(handler)
    except Exception:
        LOGGER.exception("Failed to add handler: %s", handler)

# Add common handlers but avoid duplicates - best-effort check
try:
    # PTB stores handlers by group number in app.handlers; we do a naive uniqueness check
    existing_cmds = set()
    for group_handlers in app.handlers.values():
        for h in group_handlers:
            if hasattr(h, "command"):
                existing_cmds.update(getattr(h, "command", []))
except Exception:
    existing_cmds = set()

if "start" not in existing_cmds:
    _safe_add_handler(CommandHandler("start", start))
_safe_add_handler(CommandHandler("help", get_help))
_safe_add_handler(CommandHandler("test", test))
_safe_add_handler(CallbackQueryHandler(help_button, pattern=r"help_.*"))
_safe_add_handler(CallbackQueryHandler(settings_button, pattern=r"stngs_.*"))
_safe_add_handler(CommandHandler("donate", donate))
_safe_add_handler(MessageHandler(filters.StatusUpdate.MIGRATE, migrate_chats))
# Global error handler
app.add_error_handler(error_callback)

# --- Graceful shutdown helpers ---
async def _shutdown_tasks(*tasks):
    for t in tasks:
        try:
            if not t.done():
                t.cancel()
        except Exception:
            LOGGER.exception("Error cancelling task %s", t)

async def _stop_telethon():
    if telethn:
        try:
            await telethn.disconnect()
            LOGGER.info("Telethon client disconnected.")
        except Exception:
            LOGGER.exception("Failed to disconnect Telethon client.")

async def _stop_ptb():
    try:
        await app.stop()
        LOGGER.info("PTB application stopped.")
    except Exception:
        LOGGER.exception("Failed to stop PTB application.")

# capture signals to perform a graceful shutdown
def _register_signal_handlers(loop: asyncio.AbstractEventLoop):
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown_signal()))
    except Exception:
        LOGGER.debug("Signal handlers not available on this platform.")

_shutdown_in_progress = False
async def _shutdown_signal():
    global _shutdown_in_progress
    if _shutdown_in_progress:
        return
    _shutdown_in_progress = True
    LOGGER.info("Shutdown initiated.")
    await _stop_telethon()
    await _stop_ptb()
    LOGGER.info("Shutdown complete. Exiting.")
    try:
        asyncio.get_event_loop().stop()
    except Exception:
        pass

# --- Main entrypoint ---
async def main():
    # Set compat bot pointer for modules
    if hasattr(app, "bot"):
        cfg.set_app_bot(app.bot)
    # Ensure bot is recorded in DB if necessary
    await ensure_bot_in_db(app.bot)
    # Support chat notification
    if cfg.SUPPORT_CHAT:
        try:
            await app.bot.send_message(chat_id=f"@{cfg.SUPPORT_CHAT}", text="✅ I am now online!")
        except Exception:
            LOGGER.exception("Failed to contact SUPPORT_CHAT.")

    # Telethon sample events
    if telethn:
        @telethn.on(events.NewMessage(pattern=r"^/alive$"))
        async def telethon_alive(event):
            await event.reply("✅ Bot is alive and working via Telethon!")

        @telethn.on(events.NewMessage(pattern=r"^/ping$"))
        async def telethon_ping(event):
            await event.reply("🏓 Pong from Telethon!")

    # Start telethon and ptb concurrently and wait for both
    LOGGER.info("Starting PTB polling and Telethon (if configured).")
    telethon_task = None
    if telethn:
        try:
            await telethn.start(bot_token=cfg.TOKEN)
            telethon_task = asyncio.create_task(telethn.run_until_disconnected())
            LOGGER.info("Telethon started.")
        except Exception:
            LOGGER.exception("Failed to start Telethon.")
    # Run PTB polling as a task (this returns when stop is called)
    ptb_task = asyncio.create_task(app.run_polling())
    # Register signals
    _register_signal_handlers(asyncio.get_event_loop())
    # Wait for tasks
    tasks = [ptb_task]
    if telethon_task:
        tasks.append(telethon_task)
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        LOGGER.info("Main gather cancelled.")
    finally:
        LOGGER.info("Main finishing, attempting graceful shutdown.")
        if telethon_task:
            await _stop_telethon()
        await _stop_ptb()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Received keyboard interrupt or exit, quitting.")