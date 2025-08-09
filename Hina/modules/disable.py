import importlib
import logging
import re
from typing import Union, Optional, List, Tuple, Any

from Hina.modules.helper_funcs.handlers import CMD_STARTERS, SpamChecker
from Hina.modules.helper_funcs.misc import is_module_loaded
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    filters,
    MessageHandler,
    BaseHandler,
    CallbackContext,
)
from telegram.ext._utils.types import HandlerCallback, CCT
from telegram.helpers import escape_markdown

LOGGER = logging.getLogger(__name__)

FILENAME = __name__.rsplit(".", 1)[-1]

if is_module_loaded(FILENAME):
    from Hina.modules.helper_funcs.chat_status import (
        connection_status,
        is_user_admin,
        user_admin,
    )
    from Hina.modules.sql import disable_sql as sql

    DISABLE_CMDS: List[str] = []
    DISABLE_OTHER: List[str] = []
    ADMIN_CMDS: List[str] = []

    class DisableAbleCommandHandler(CommandHandler):
        """Custom CommandHandler that supports disabling commands"""
        
        def __init__(
            self,
            command: Union[str, List[str]],
            callback: HandlerCallback[Update, CCT, Any],
            admin_ok: bool = False,
            **kwargs: Any,
        ):
            super().__init__(command, callback, **kwargs)
            self.admin_ok = admin_ok
            commands = [command] if isinstance(command, str) else command
            DISABLE_CMDS.extend(commands)
            if admin_ok:
                ADMIN_CMDS.extend(commands)

        async def check_update(self, update: Update) -> Optional[Union[bool, Tuple[List[str], Any]]]:
            """Check if command is disabled before processing"""
            if not await super().check_update(update):
                return False
                
            if not (update.effective_message and update.effective_chat and update.effective_user):
                return False

            message = update.effective_message
            chat = update.effective_chat
            user = update.effective_user

            if not message.text or len(message.text) <= 1:
                return False

            fst_word = message.text.split(None, 1)[0]
            if len(fst_word) <= 1 or not any(fst_word.startswith(start) for start in CMD_STARTERS):
                return False

            args = message.text.split()[1:]
            command = fst_word[1:].split("@")
            command.append(message.bot.username.lower())

            if not (command[0].lower() in self.command and command[1].lower() == message.bot.username.lower()):
                return None

            user_id = chat.id if user.id == 1087968824 else user.id

            if SpamChecker.check_user(user_id):
                return None
            
            try:
                if await sql.is_command_disabled(chat.id, command[0].lower()):
                    if command[0] in ADMIN_CMDS and await is_user_admin(chat, user.id):
                        return args
                    return None
            except Exception as e:
                LOGGER.error(f"Error checking if command is disabled: {e}", exc_info=True)
                return None

            return args

    class DisableAbleMessageHandler(MessageHandler):
        """Custom MessageHandler that supports disabling"""
        
        def __init__(
            self,
            filters: filters.BaseFilter,
            callback: HandlerCallback[Update, CCT, Any],
            friendly: str,
            **kwargs: Any,
        ):
            super().__init__(filters, callback, **kwargs)
            DISABLE_OTHER.append(friendly)
            self.friendly = friendly

        async def check_update(self, update: Update) -> Optional[Union[bool, Tuple[List[str], Any]]]:
            """Check if message type is disabled before processing"""
            if not await super().check_update(update) or not update.effective_chat:
                return False
            
            try:
                if await sql.is_command_disabled(update.effective_chat.id, self.friendly):
                    return False
            except Exception as e:
                LOGGER.error(f"Error checking if handler is disabled: {e}", exc_info=True)
                return False
            
            try:
                args = update.effective_message.text.split()[1:] if update.effective_message.text else []
                return args
            except Exception:
                return True

    class DisableAbleRegexHandler(MessageHandler):
        """Custom Regex Handler that supports disabling"""
        
        def __init__(
            self,
            pattern: str,
            callback: HandlerCallback[Update, CCT, Any],
            friendly: str = "",
            filters: Optional[filters.BaseFilter] = None,
            **kwargs: Any,
        ):
            super().__init__(filters or filters.Regex(pattern), callback, **kwargs)
            DISABLE_OTHER.append(friendly)
            self.friendly = friendly

        async def check_update(self, update: Update) -> Optional[bool]:
            """Check if regex pattern is disabled before processing"""
            try:
                is_disabled = update.effective_chat and await sql.is_command_disabled(update.effective_chat.id, self.friendly)
                return await super().check_update(update) and not is_disabled
            except Exception as e:
                LOGGER.error(f"Error checking if regex handler is disabled: {e}", exc_info=True)
                return False

    # ====================== COMMAND FUNCTIONS ======================
    @connection_status
    @user_admin
    async def disable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Disable a command in the chat"""
        args = context.args
        chat = update.effective_chat
        if not args:
            await update.effective_message.reply_text("What should I disable?")
            return

        disable_cmd = args[0]
        if disable_cmd.startswith(CMD_STARTERS):
            disable_cmd = disable_cmd[1:]

        if disable_cmd in set(DISABLE_CMDS + DISABLE_OTHER):
            try:
                if await sql.disable_command(chat.id, str(disable_cmd).lower()):
                    await update.effective_message.reply_text(
                        f"Disabled the use of `{escape_markdown_v2(disable_cmd)}`",
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )
                else:
                    await update.effective_message.reply_text("That command is already disabled.")
            except Exception as e:
                LOGGER.error(f"Failed to disable command {disable_cmd}: {e}", exc_info=True)
                await update.effective_message.reply_text("Failed to disable command due to an internal error.")
        else:
            await update.effective_message.reply_text("That command can't be disabled")

    @connection_status
    @user_admin
    async def disable_module(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Disable all commands in a module"""
        args = context.args
        chat = update.effective_chat
        if not args:
            await update.effective_message.reply_text("What should I disable?")
            return

        module_name = args[0].rsplit(".", 1)[0]
        disable_module = f"Hina.modules.{module_name}"

        try:
            module = importlib.import_module(disable_module)
        except ImportError:
            await update.effective_message.reply_text("Does that module even exist?")
            return

        if not hasattr(module, "__command_list__"):
            await update.effective_message.reply_text("Module does not contain command list!")
            return

        command_list = module.__command_list__
        disabled_cmds = []
        failed_disabled_cmds = []

        try:
            for cmd in command_list:
                clean_cmd = cmd[1:] if cmd.startswith(CMD_STARTERS) else cmd
                if clean_cmd in set(DISABLE_CMDS + DISABLE_OTHER):
                    if await sql.disable_command(chat.id, clean_cmd.lower()):
                        disabled_cmds.append(clean_cmd)
                    else:
                        failed_disabled_cmds.append(clean_cmd)
                else:
                    failed_disabled_cmds.append(clean_cmd)
        except Exception as e:
            LOGGER.error(f"Failed to disable commands in module {module_name}: {e}", exc_info=True)
            await update.effective_message.reply_text("Failed to disable commands due to an internal error.")
            return

        if disabled_cmds:
            disabled_text = ", ".join(f"`{escape_markdown_v2(cmd)}`" for cmd in disabled_cmds)
            await update.effective_message.reply_text(
                f"Disabled commands: {disabled_text}",
                parse_mode=ParseMode.MARKDOWN_V2,
            )

        if failed_disabled_cmds:
            failed_text = ", ".join(f"`{escape_markdown_v2(cmd)}`" for cmd in failed_disabled_cmds)
            await update.effective_message.reply_text(
                f"Commands couldn't be disabled: {failed_text}",
                parse_mode=ParseMode.MARKDOWN_V2,
            )

    @connection_status
    @user_admin
    async def enable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Enable a command in the chat"""
        args = context.args
        chat = update.effective_chat
        if not args:
            await update.effective_message.reply_text("What should I enable?")
            return

        enable_cmd = args[0]
        if enable_cmd.startswith(CMD_STARTERS):
            enable_cmd = enable_cmd[1:]

        try:
            if await sql.enable_command(chat.id, enable_cmd):
                await update.effective_message.reply_text(
                    f"Enabled the use of `{escape_markdown_v2(enable_cmd)}`", 
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            else:
                await update.effective_message.reply_text("Is that even disabled?")
        except Exception as e:
            LOGGER.error(f"Failed to enable command {enable_cmd}: {e}", exc_info=True)
            await update.effective_message.reply_text("Failed to enable command due to an internal error.")

    @connection_status
    @user_admin
    async def enable_module(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Enable all commands in a module"""
        args = context.args
        chat = update.effective_chat
        if not args:
            await update.effective_message.reply_text("What should I enable?")
            return

        module_name = args[0].rsplit(".", 1)[0]
        enable_module = f"Hina.modules.{module_name}"

        try:
            module = importlib.import_module(enable_module)
        except ImportError:
            await update.effective_message.reply_text("Does that module even exist?")
            return

        if not hasattr(module, "__command_list__"):
            await update.effective_message.reply_text("Module does not contain command list!")
            return

        command_list = module.__command_list__
        enabled_cmds = []
        failed_enabled_cmds = []

        try:
            for cmd in command_list:
                clean_cmd = cmd[1:] if cmd.startswith(CMD_STARTERS) else cmd
                if await sql.enable_command(chat.id, clean_cmd):
                    enabled_cmds.append(clean_cmd)
                else:
                    failed_enabled_cmds.append(clean_cmd)
        except Exception as e:
            LOGGER.error(f"Failed to enable commands in module {module_name}: {e}", exc_info=True)
            await update.effective_message.reply_text("Failed to enable commands due to an internal error.")
            return

        if enabled_cmds:
            enabled_text = ", ".join(f"`{escape_markdown_v2(cmd)}`" for cmd in enabled_cmds)
            await update.effective_message.reply_text(
                f"Enabled commands: {enabled_text}",
                parse_mode=ParseMode.MARKDOWN_V2,
            )

        if failed_enabled_cmds:
            failed_text = ", ".join(f"`{escape_markdown_v2(cmd)}`" for cmd in failed_enabled_cmds)
            await update.effective_message.reply_text(
                f"Commands weren't disabled: {failed_text}",
                parse_mode=ParseMode.MARKDOWN_V2,
            )

    @connection_status
    @user_admin
    async def list_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all toggleable commands"""
        if not (DISABLE_CMDS or DISABLE_OTHER):
            await update.effective_message.reply_text("No commands can be disabled.")
            return

        all_commands = sorted(set(DISABLE_CMDS + DISABLE_OTHER))
        result = "\n".join(f"- `{escape_markdown_v2(cmd)}`" for cmd in all_commands)
        await update.effective_message.reply_text(
            f"Toggleable commands:\n{result}",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    def build_curr_disabled(disabled_list: List[str]) -> str:
        """Build message showing currently disabled commands"""
        if not disabled_list:
            return "No commands are disabled!"

        result = "\n".join(f"- `{escape_markdown_v2(cmd)}`" for cmd in disabled_list)
        return f"The following commands are disabled:\n{result}"

    @connection_status
    async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show currently disabled commands"""
        chat = update.effective_chat
        try:
            disabled_list = await sql.get_all_disabled(chat.id)
            message = build_curr_disabled(disabled_list)
            await update.effective_message.reply_text(
                message, 
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            LOGGER.error(f"Failed to get disabled commands for chat {chat.id}: {e}", exc_info=True)
            await update.effective_message.reply_text("Failed to retrieve disabled commands due to an internal error.")

    # ====================== MODULE METADATA ======================
    async def __stats__() -> str:
        try:
            num_disabled_cmds = await sql.num_disabled()
            num_disabled_chats = await sql.num_chats()
            return f"• {num_disabled_cmds} disabled items, across {num_disabled_chats} chats."
        except Exception as e:
            LOGGER.error(f"Failed to get stats: {e}", exc_info=True)
            return "Failed to get stats due to an internal error."

    async def __migrate__(old_chat_id: int, new_chat_id: int) -> None:
        try:
            await sql.migrate_chat(old_chat_id, new_chat_id)
        except Exception as e:
            LOGGER.error(f"Failed to migrate chat {old_chat_id} to {new_chat_id}: {e}", exc_info=True)

    async def __chat_settings__(chat_id: int, user_id: int) -> str:
        try:
            disabled_list = await sql.get_all_disabled(chat_id)
            return build_curr_disabled(disabled_list)
        except Exception as e:
            LOGGER.error(f"Failed to get chat settings for {chat_id}: {e}", exc_info=True)
            return "Failed to retrieve chat settings due to an internal error."

    # ====================== HANDLER REGISTRATION ======================
    from Hina.config import app
    HANDLERS = [
        DisableAbleCommandHandler("disable", disable),
        DisableAbleCommandHandler("disablemodule", disable_module),
        DisableAbleCommandHandler("enable", enable),
        DisableAbleCommandHandler("enablemodule", enable_module),
        DisableAbleCommandHandler(["cmds", "disabled"], commands),
        DisableAbleCommandHandler("listcmds", list_cmds),
    ]

    for handler in HANDLERS:
        app.add_handler(handler)

    __help__ = """
    • `/cmds`*:* Check current disabled commands

    *Admins only:*
    • `/enable <cmd>`*:* Enable a command
    • `/disable <cmd>`*:* Disable a command
    • `/enablemodule <module>`*:* Enable all commands in a module
    • `/disablemodule <module>`*:* Disable all commands in a module
    • `/listcmds`*:* List all toggleable commands
    """

    __mod_name__ = "Disable"
    __command_list__ = ["cmds", "disabled", "disable", "enable", "disablemodule", "enablemodule", "listcmds"]

else:
    DisableAbleCommandHandler = CommandHandler
    DisableAbleMessageHandler = MessageHandler
    DisableAbleRegexHandler = MessageHandler
