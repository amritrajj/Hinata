from telegram import Message, Chat
from telegram.ext import filters
from typing import Callable, Awaitable, Any, TypeVar, cast

from Hina.config import DEV_USERS, DRAGONS, DEMONS
from Hina.modules.helper_funcs.chat_status import bot_admin

# Type variable for generic function type
F = TypeVar('F', bound=Callable[..., Awaitable[Any]])


class CustomFilters:
    # Supporters filter
    @staticmethod
    async def support_filter(message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in DEMONS)

    # Sudoers filter
    @staticmethod
    async def sudo_filter(message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in DRAGONS)

    # Developers filter
    @staticmethod
    async def dev_filter(message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in DEV_USERS)

    # Bot is admin filter
    @staticmethod
    async def bot_is_admin(chat: Chat) -> bool:
        return await bot_admin(chat, chat.bot.id)

    # MimeType filter (e.g., 'application/zip')
    @staticmethod
    def mime_type(mimetype: str):
        async def _check(message: Message) -> bool:
            return (
                message.document
                and message.document.mime_type == mimetype
            )
        return filters.create(_check)

    # Filter messages that have content (text, sticker, photo, etc.)
    @staticmethod
    async def has_text(message: Message) -> bool:
        return bool(
            message.text
            or message.sticker
            or message.photo
            or message.document
            or message.video
        )

# Example usage (as a filter):
# my_filter = filters.create(CustomFilters.support_filter)
