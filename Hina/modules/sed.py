from Hina.config import app
import re
import regex
import sre_constants
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode, MessageLimit
from telegram.ext import ContextTypes, filters
from telegram.helpers import escape_markdown

from Hina.modules.disable import DisableAbleMessageHandler
from Hina.modules.helper_funcs.regex_helper import infinite_loop_check
from Hina.config import LOGGER

DELIMITERS = ("/", ":", "|", "_")

async def separate_sed(sed_string: str) -> Optional[tuple]:
    """Parse sed command string into replace pattern, replacement, and flags"""
    if (
        len(sed_string) >= 3
        and sed_string[1] in DELIMITERS
        and sed_string.count(sed_string[1]) >= 2
    ):
        delim = sed_string[1]
        start = counter = 2
        
        # Extract pattern to replace
        while counter < len(sed_string):
            if sed_string[counter] == "\\":
                counter += 1
            elif sed_string[counter] == delim:
                replace = sed_string[start:counter]
                counter += 1
                start = counter
                break
            counter += 1
        else:
            return None

        # Extract replacement text
        while counter < len(sed_string):
            if (
                sed_string[counter] == "\\"
                and counter + 1 < len(sed_string)
                and sed_string[counter + 1] == delim
            ):
                sed_string = sed_string[:counter] + sed_string[counter + 1:]
            elif sed_string[counter] == delim:
                replace_with = sed_string[start:counter]
                counter += 1
                break
            counter += 1
        else:
            return replace, sed_string[start:], ""

        # Get any flags
        flags = sed_string[counter:].lower() if counter < len(sed_string) else ""
        return replace, replace_with, flags
    return None

async def sed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle sed commands"""
    if not update.effective_message or not update.effective_message.reply_to_message:
        return

    sed_result = await separate_sed(update.effective_message.text)
    if not sed_result:
        return

    # Get text to process
    to_fix = (
        update.effective_message.reply_to_message.text or 
        update.effective_message.reply_to_message.caption
    )
    if not to_fix:
        return

    repl, repl_with, flags = sed_result
    
    if not repl:
        await update.effective_message.reply_to_message.reply_text(
            "You're trying to replace nothing with something?"
        )
        return

    try:
        # Check for whole message match
        try:
            check = regex.match(repl, to_fix, flags=regex.IGNORECASE, timeout=5)
            if check and check.group(0).lower() == to_fix.lower():
                await update.effective_message.reply_to_message.reply_text(
                    f"Hey everyone, {update.effective_user.first_name} is trying to "
                    "make me say stuff I don't wanna say!"
                )
                return
        except TimeoutError:
            await update.effective_message.reply_text("Regex timed out")
            return

        # Check for infinite loops
        if infinite_loop_check(repl):
            await update.effective_message.reply_text("I'm afraid I can't run that regex.")
            return

        # Apply replacement
        flags_re = regex.IGNORECASE if "i" in flags else 0
        count = 0 if "g" in flags else 1
        
        try:
            text = regex.sub(
                repl, 
                repl_with, 
                to_fix, 
                count=count, 
                flags=flags_re, 
                timeout=3
            ).strip()
        except TimeoutError:
            await update.effective_message.reply_text("Replacement timed out")
            return
        except sre_constants.error as e:
            LOGGER.warning(f"Sed error: {e} - Input: {update.effective_message.text}")
            await update.effective_message.reply_text("Invalid regex pattern.")
            return

        # Send result
        if text and len(text) < MessageLimit.MAX_TEXT_LENGTH:
            await update.effective_message.reply_to_message.reply_text(text)
        elif text:
            await update.effective_message.reply_text(
                "The result of the sed command was too long for Telegram!"
            )
            
    except Exception as e:
        LOGGER.error(f"Sed error: {e}")
        await update.effective_message.reply_text("An error occurred processing your sed command.")

__help__ = """
• `s/<text1>/<text2>(/<flag>)`*:* Reply to a message to replace text using sed syntax.
Delimiters: `/`, `:`, `|`, `_`  
Flags:  
  • `i` - Case insensitive  
  • `g` - Global replacement  
Escape special chars like: `+*.?\\` with backslash  
*Example:* `s/hello/hi/i`  
Max result length: {} chars
""".format(MessageLimit.MAX_TEXT_LENGTH)

__mod_name__ = "Sed/Regex"

SED_HANDLER = DisableAbleMessageHandler(
    filters.Regex(r"s([{}]).*?\1.*".format("".join(DELIMITERS))),
    sed,
    friendly="sed",
    block=False
)

app.add_handler(SED_HANDLER)
