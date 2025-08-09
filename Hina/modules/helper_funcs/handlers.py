import time
from collections import defaultdict, deque
from typing import Optional, List, Union, Any

import Hina.modules.sql.blacklistusers_sql as sql
from Hina.config import ALLOW_EXCL, DEV_USERS, DRAGONS, DEMONS, TIGERS, WOLVES

from telegram import Update, Message
from telegram.ext import CommandHandler, MessageHandler, filters
from telegram.ext._utils.types import CCT, HandlerCallback
from telegram.ext._application import Application


# Command prefixes
CMD_STARTERS = ("/", "!") if ALLOW_EXCL else ("/",)


# ✅ Native AntiSpam (no external lib)
class AntiSpam:
    def __init__(self):
        self.whitelist = set().union(DEV_USERS, DRAGONS, DEMONS, TIGERS, WOLVES)
        self.user_logs = defaultdict(
            lambda: {
                "sec": deque(maxlen=6),
                "min": deque(maxlen=20),
                "hour": deque(maxlen=100),
                "day": deque(maxlen=1000),
            }
        )

    def check_user(self, user_id: int) -> bool:
        if user_id in self.whitelist:
            return False

        now = time.time()
        logs = self.user_logs[user_id]

        logs["sec"].append(now)
        logs["min"].append(now)
        logs["hour"].append(now)
        logs["day"].append(now)

        if len(logs["sec"]) >= 6 and now - logs["sec"][0] < 15:
            return True
        if len(logs["min"]) >= 20 and now - logs["min"][0] < 60:
            return True
        if len(logs["hour"]) >= 100 and now - logs["hour"][0] < 60 * 60:
            return True
        return False


# To use with CustomHandlers
MessageHandlerChecker = AntiSpam()


# ✅ CustomCommandHandler
class CustomCommandHandler(CommandHandler):
    def __init__(
        self,
        command: Union[str, List[str]],
        callback: HandlerCallback[Update, CCT, Any, Any],
        **kwargs,
    ):
        super().__init__(command, callback, **kwargs)

    async def check_update(self, update: Update) -> Optional[Union[bool, List[str]]]:
        msg = update.effective_message
        if not msg:
            return None

        user_id = update.effective_user.id if update.effective_user else None

        # 🔒 Blacklist
        if user_id and await sql.is_user_blacklisted(user_id):
            return None

        # 🚫 Spam
        if user_id and MessageHandlerChecker.check_user(user_id):
            return None

        # ✅ Command check
        return await super().check_update(update)

    async def handle_update(
        self,
        update: Update,
        application: Application,
        check_result: Optional[List[str]],
        context: CCT,
    ) -> None:
        await self.callback(update, context)


# ✅ CustomMessageHandler
class CustomMessageHandler(MessageHandler):
    def __init__(
        self,
        filters: filters.BaseFilter,
        callback: HandlerCallback[Update, CCT, Any, Any],
        allow_edit: bool = False,
        **kwargs,
    ):
        super().__init__(filters, callback, **kwargs)
        if not allow_edit:
            self.filters &= ~ (
                filters.UpdateType.EDITED_MESSAGE
                | filters.UpdateType.EDITED_CHANNEL_POST
            )

    async def check_update(self, update: Update) -> Optional[Union[bool, object]]:
        msg = update.effective_message
        if not msg:
            return None

        user_id = update.effective_user.id if update.effective_user else None

        # 🔒 Blacklist
        if user_id and await sql.is_user_blacklisted(user_id):
            return None

        # 🚫 Spam
        if user_id and MessageHandlerChecker.check_user(user_id):
            return None

        # ✅ Standard filters
        return await super().check_update(update)

    async def handle_update(
        self,
        update: Update,
        application: Application,
        check_result: Optional[object],
        context: CCT,
    ) -> None:
        await self.callback(update, context)
