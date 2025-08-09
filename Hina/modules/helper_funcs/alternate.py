from telegram.error import BadRequest
from functools import wraps
from telegram.constants import ChatAction
from telegram.constants import ParseMode
from typing import Callable, Awaitable, Any, TypeVar, cast

# Type variable for generic function type
F = TypeVar('F', bound=Callable[..., Awaitable[Any]])


async def send_message(message, text, *args, **kwargs):
    try:
        return await message.reply_text(text, *args, **kwargs)
    except BadRequest as err:
        if str(err) == "Reply message not found":
            return await message.reply_text(text, quote=False, *args, **kwargs)


def typing_action(func: F) -> F:
    """Sends typing action while processing func command."""

    @wraps(func)
    async def command_func(update, context, *args, **kwargs):
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
        )
        return await func(update, context, *args, **kwargs)

    return cast(F, command_func)
