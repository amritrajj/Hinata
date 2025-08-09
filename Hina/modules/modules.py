from Hina.config import app
import importlib
from Hina.config import (
    CHAT_SETTINGS,
    DATA_EXPORT,
    DATA_IMPORT,
    HELPABLE,
    IMPORTED,
    MIGRATEABLE,
    STATS,
    USER_INFO,
    USER_SETTINGS,
)
from collections.abc import Callable  # Updated import
from typing import List, Dict, Any
from Hina.modules.helper_funcs.chat_status import dev_plus, sudo_plus
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, filters

# Assuming these are defined in your config
DEVS = []  # Add your developer IDs
SUDO_USERS = []  # Add your sudo user IDs

@dev_plus
async def load(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.reply_text("Usage: /load <module_name>")
        return

    text = args[1]
    load_message = await message.reply_text(
        f"Attempting to load module: <b>{text}</b>", 
        parse_mode=ParseMode.HTML
    )

    try:
        imported_module = importlib.import_module(f"Hina.modules.{text}")
    except ImportError:
        await load_message.edit_text("❌ Module doesn't exist or cannot be imported.")
        return

    # Set module name if not defined
    if not hasattr(imported_module, "__mod_name__"):
        imported_module.__mod_name__ = imported_module.__name__.split('.')[-1]

    mod_name = imported_module.__mod_name__.lower()
    
    if mod_name in IMPORTED:
        await load_message.edit_text("⚠️ Module is already loaded.")
        return

    IMPORTED[mod_name] = imported_module

    # Add handlers
    if hasattr(imported_module, "__handlers__"):
        handlers = imported_module.__handlers__
        for handler in handlers:
            if isinstance(handler, (list, tuple)):
                if len(handler) == 2 and isinstance(handler[0], Callable):
                    callback, event = handler
                    # Telethon support (if applicable)
                    if hasattr(app, 'add_event_handler'):
                        app.add_event_handler(callback, event)
                else:
                    handler_name, priority = handler
                    app.add_handler(handler_name, priority)
            else:
                app.add_handler(handler)

    # Register module features
    if hasattr(imported_module, "__help__") and imported_module.__help__:
        HELPABLE[mod_name] = imported_module

    # Lists to update
    feature_lists = [
        (MIGRATEABLE, "__migrate__"),
        (STATS, "__stats__"),
        (USER_INFO, "__user_info__"),
        (DATA_IMPORT, "__import_data__"),
        (DATA_EXPORT, "__export_data__"),
    ]

    for feature_list, attr in feature_lists:
        if hasattr(imported_module, attr):
            feature_list.append(imported_module)

    # Dictionaries to update
    settings_dicts = [
        (CHAT_SETTINGS, "__chat_settings__"),
        (USER_SETTINGS, "__user_settings__"),
    ]

    for settings_dict, attr in settings_dicts:
        if hasattr(imported_module, attr):
            settings_dict[mod_name] = imported_module

    await load_message.edit_text(
        f"✅ Successfully loaded module: <b>{text}</b>",
        parse_mode=ParseMode.HTML
    )


@dev_plus
async def unload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.reply_text("Usage: /unload <module_name>")
        return

    text = args[1]
    unload_message = await message.reply_text(
        f"Attempting to unload module: <b>{text}</b>",
        parse_mode=ParseMode.HTML
    )

    try:
        imported_module = importlib.import_module(f"Hina.modules.{text}")
    except ImportError:
        await unload_message.edit_text("❌ Module doesn't exist.")
        return

    mod_name = imported_module.__mod_name__.lower()
    
    if mod_name not in IMPORTED:
        await unload_message.edit_text("⚠️ Module isn't loaded.")
        return

    # Remove handlers
    if hasattr(imported_module, "__handlers__"):
        handlers = imported_module.__handlers__
        for handler in handlers:
            if isinstance(handler, (list, tuple)):
                if len(handler) == 2 and isinstance(handler[0], Callable):
                    callback, event = handler
                    # Telethon support (if applicable)
                    if hasattr(app, 'remove_event_handler'):
                        app.remove_event_handler(callback, event)
                else:
                    handler_name, priority = handler
                    app.remove_handler(handler_name, priority)
            else:
                app.remove_handler(handler)

    # Clean up module references
    IMPORTED.pop(mod_name)
    HELPABLE.pop(mod_name, None)

    # Lists to update
    feature_lists = [
        (MIGRATEABLE, "__migrate__"),
        (STATS, "__stats__"),
        (USER_INFO, "__user_info__"),
        (DATA_IMPORT, "__import_data__"),
        (DATA_EXPORT, "__export_data__"),
    ]

    for feature_list, attr in feature_lists:
        if hasattr(imported_module, attr) and imported_module in feature_list:
            feature_list.remove(imported_module)

    # Dictionaries to update
    settings_dicts = [
        (CHAT_SETTINGS, "__chat_settings__"),
        (USER_SETTINGS, "__user_settings__"),
    ]

    for settings_dict, attr in settings_dicts:
        if hasattr(imported_module, attr) and mod_name in settings_dict:
            settings_dict.pop(mod_name)

    await unload_message.edit_text(
        f"✅ Successfully unloaded module: <b>{text}</b>",
        parse_mode=ParseMode.HTML
    )


@sudo_plus
async def listmodules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    
    if not HELPABLE:
        await message.reply_text("ℹ️ No modules are currently loaded.")
        return

    module_list = ["<b>📦 Loaded Modules:</b>\n\n"]
    
    for module_name in sorted(HELPABLE.keys()):
        module = IMPORTED[module_name]
        file_name = module.__name__.rsplit('.', 1)[-1]
        mod_name = getattr(module, "__mod_name__", file_name)
        module_list.append(f"• <code>{mod_name}</code> (<i>{file_name}</i>)\n")

    await message.reply_text(
        "".join(module_list),
        parse_mode=ParseMode.HTML
    )


# Add handlers with proper filters
LOAD_HANDLER = CommandHandler(
    "load", 
    load, 
    filters=filters.User(DEVS)
)

UNLOAD_HANDLER = CommandHandler(
    "unload", 
    unload, 
    filters=filters.User(DEVS)
)

LISTMODULES_HANDLER = CommandHandler(
    "listmodules", 
    listmodules, 
    filters=filters.User(SUDO_USERS)
)

app.add_handler(LOAD_HANDLER)
app.add_handler(UNLOAD_HANDLER)
app.add_handler(LISTMODULES_HANDLER)

__mod_name__ = "Modules"
__help__ = """
<b>Module Management:</b>
• /load <module>: Load a module
• /unload <module>: Unload a module
• /listmodules: List all loaded modules

<i>Developers and sudo users only</i>
"""
