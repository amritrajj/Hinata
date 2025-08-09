from Hina.config import app
import io
import os
import textwrap
import traceback
from contextlib import redirect_stdout
from typing import Dict, Any

from Hina.config import LOGGER
from Hina.modules.helper_funcs.chat_status import dev_plus
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

namespaces: Dict[int, Dict[str, Any]] = {}


def namespace_of(chat_id: int, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    if chat_id not in namespaces:
        namespaces[chat_id] = {
            "__builtins__": globals()["__builtins__"],
            "bot": context.bot,
            "effective_message": update.effective_message,
            "effective_user": update.effective_user,
            "effective_chat": update.effective_chat,
            "update": update,
            "context": context,
        }
    return namespaces[chat_id]


async def log_input(update: Update) -> None:
    user = update.effective_user.id
    chat = update.effective_chat.id
    LOGGER.info(f"IN: {update.effective_message.text} (user={user}, chat={chat})")


async def send(msg: str, context: ContextTypes.DEFAULT_TYPE, update: Update) -> None:
    if len(str(msg)) > 2000:
        with io.BytesIO(str.encode(msg)) as out_file:
            out_file.name = "output.txt"
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=out_file
            )
    else:
        LOGGER.info(f"OUT: '{msg}'")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"`{msg}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


def cleanup_code(code: str) -> str:
    if code.startswith("```") and code.endswith("```"):
        return "\n".join(code.split("\n")[1:-1])
    return code.strip("` \n")


async def do(func, context: ContextTypes.DEFAULT_TYPE, update: Update) -> str:
    await log_input(update)
    content = update.message.text.split(" ", 1)[-1]
    body = cleanup_code(content)
    env = namespace_of(update.message.chat_id, update, context)

    os.chdir(os.getcwd())
    with open(
        os.path.join(os.getcwd(), "Hina/modules/helper_funcs/temp.txt"), "w", encoding="utf-8"
    ) as temp:
        temp.write(body)

    stdout = io.StringIO()

    to_compile = f'def func():\n{textwrap.indent(body, "  ")}'

    try:
        exec(to_compile, env)
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"

    func = env["func"]

    try:
        with redirect_stdout(stdout):
            func_return = func()
    except Exception as e:
        value = stdout.getvalue()
        return f"{value}{traceback.format_exc()}"
    else:
        value = stdout.getvalue()
        result = None
        if func_return is None:
            if value:
                result = f"{value}"
            else:
                try:
                    result = f"{repr(eval(body, env))}"
                except Exception:
                    pass
        else:
            result = f"{value}{func_return}"
        if result:
            return result
    return ""


@dev_plus
async def evaluate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = await do(eval, context, update)
    await send(result, context, update)


@dev_plus
async def execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = await do(exec, context, update)
    await send(result, context, update)


@dev_plus
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global namespaces
    await log_input(update)
    if update.message.chat_id in namespaces:
        del namespaces[update.message.chat_id]
    await send("Cleared locals.", context, update)


EVAL_HANDLER = CommandHandler(("e", "ev", "eva", "eval"), evaluate)
EXEC_HANDLER = CommandHandler(("x", "ex", "exe", "exec", "py"), execute)
CLEAR_HANDLER = CommandHandler("clearlocals", clear)

app.add_handler(EVAL_HANDLER)
app.add_handler(EXEC_HANDLER)
app.add_handler(CLEAR_HANDLER)

__mod_name__ = "Eval Module"
