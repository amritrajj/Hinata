from Hina.config import app
import subprocess
import asyncio
from typing import Optional

from Hina.config import LOGGER
from Hina.modules.helper_funcs.chat_status import dev_plus
from telegram import Update, Message
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

@dev_plus
async def shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute shell commands (Devs only)"""
    message: Optional[Message] = update.effective_message
    if not message:
        return

    cmd = message.text.split(maxsplit=1)
    if len(cmd) == 1:
        await message.reply_text("No command to execute was given.")
        return

    cmd = cmd[1]
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    except asyncio.TimeoutError:
        process.kill()
        await message.reply_text("Command timed out after 60 seconds")
        return

    reply = ""
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()

    if stdout:
        reply += f"*Stdout*\n`{escape_markdown_v2(stdout, 2)}`\n"
        LOGGER.info(f"Shell - {cmd} - {stdout}")
    if stderr:
        reply += f"*Stderr*\n`{escape_markdown_v2(stderr, 2)}`\n"
        LOGGER.error(f"Shell - {cmd} - {stderr}")

    if not reply:
        reply = "No output"

    # Send output
    if len(reply) > 4000:  # Telegram message limit
        with open("shell_output.txt", "w") as file:
            file.write(reply)
        with open("shell_output.txt", "rb") as doc:
            await message.reply_document(
                document=doc,
                caption=f"Output for `{cmd}`",
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        await message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

def escape_markdown_v2(text: str, version: int = 2) -> str:
    """Helper function to escape markdown"""
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

__mod_name__ = "Shell"
__command_list__ = ["sh"]
__handlers__ = [CommandHandler(["sh", "shell"], shell, block=False)]

app.add_handler(__handlers__[0])
