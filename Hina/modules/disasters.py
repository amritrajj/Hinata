import html
import json
import os
from typing import Optional
import logging

from Hina.config import (
    DEV_USERS,
    OWNER_ID,
    DRAGONS,
    SUPPORT_CHAT,
    DEMONS,
    TIGERS,
    WOLVES,
)
from Hina.modules.helper_funcs.chat_status import (
    dev_plus,
    sudo_plus,
    whitelist_plus,
)
from Hina.modules.helper_funcs.extraction import extract_user
from Hina.modules.log_channel import gloggable
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, Application
from telegram.helpers import mention_html
from telegram.error import TelegramError

LOGGER = logging.getLogger(__name__)

ELEVATED_USERS_FILE = os.path.join(os.getcwd(), "Hina/elevated_users.json")


def check_user_id(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    bot = context.bot
    if not user_id:
        return "That...is a chat! baka ka omae?"
    elif user_id == bot.id:
        return "This does not work that way."
    return None


@dev_plus
@gloggable
async def addsudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot = context.bot
    args = context.args
    user_id = await extract_user(message, args)
    user_member = await bot.get_chat(user_id)
    rt = ""

    reply = check_user_id(user_id, context)
    if reply:
        await message.reply_text(reply)
        return ""

    try:
        with open(ELEVATED_USERS_FILE, "r") as infile:
            data = json.load(infile)
    except FileNotFoundError:
        data = {"sudos": [], "supports": [], "whitelists": [], "tigers": []}

    if user_id in DRAGONS:
        await message.reply_text("This member is already a Dragon Disaster")
        return ""

    if user_id in DEMONS:
        rt += "Requested HA to promote a Demon Disaster to Dragon."
        data["supports"].remove(user_id)
        DEMONS.remove(user_id)

    if user_id in WOLVES:
        rt += "Requested HA to promote a Wolf Disaster to Dragon."
        data["whitelists"].remove(user_id)
        WOLVES.remove(user_id)

    data["sudos"].append(user_id)
    DRAGONS.append(user_id)

    with open(ELEVATED_USERS_FILE, "w") as outfile:
        json.dump(data, outfile, indent=4)

    await message.reply_text(
        rt
        + "\nSuccessfully set Disaster level of {} to Dragon!".format(
            user_member.first_name,
        ),
    )

    log_message = (
        f"#SUDO\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

    return log_message


@sudo_plus
@gloggable
async def addsupport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot = context.bot
    args = context.args
    user_id = await extract_user(message, args)
    user_member = await bot.get_chat(user_id)
    rt = ""

    reply = check_user_id(user_id, context)
    if reply:
        await message.reply_text(reply)
        return ""

    try:
        with open(ELEVATED_USERS_FILE, "r") as infile:
            data = json.load(infile)
    except FileNotFoundError:
        data = {"sudos": [], "supports": [], "whitelists": [], "tigers": []}

    if user_id in DRAGONS:
        rt += "Requested HA to demote this Dragon to Demon"
        data["sudos"].remove(user_id)
        DRAGONS.remove(user_id)

    if user_id in DEMONS:
        await message.reply_text("This user is already a Demon Disaster.")
        return ""

    if user_id in WOLVES:
        rt += "Requested HA to promote this Wolf Disaster to Demon"
        data["whitelists"].remove(user_id)
        WOLVES.remove(user_id)

    data["supports"].append(user_id)
    DEMONS.append(user_id)

    with open(ELEVATED_USERS_FILE, "w") as outfile:
        json.dump(data, outfile, indent=4)

    await message.reply_text(
        rt + f"\n{user_member.first_name} was added as a Demon Disaster!",
    )

    log_message = (
        f"#SUPPORT\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

    return log_message


@sudo_plus
@gloggable
async def addwhitelist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot = context.bot
    args = context.args
    user_id = await extract_user(message, args)
    user_member = await bot.get_chat(user_id)
    rt = ""

    reply = check_user_id(user_id, context)
    if reply:
        await message.reply_text(reply)
        return ""

    try:
        with open(ELEVATED_USERS_FILE, "r") as infile:
            data = json.load(infile)
    except FileNotFoundError:
        data = {"sudos": [], "supports": [], "whitelists": [], "tigers": []}

    if user_id in DRAGONS:
        rt += "This member is a Dragon Disaster, Demoting to Wolf."
        data["sudos"].remove(user_id)
        DRAGONS.remove(user_id)

    if user_id in DEMONS:
        rt += "This user is already a Demon Disaster, Demoting to Wolf."
        data["supports"].remove(user_id)
        DEMONS.remove(user_id)

    if user_id in WOLVES:
        await message.reply_text("This user is already a Wolf Disaster.")
        return ""

    data["whitelists"].append(user_id)
    WOLVES.append(user_id)

    with open(ELEVATED_USERS_FILE, "w") as outfile:
        json.dump(data, outfile, indent=4)

    await message.reply_text(
        rt + f"\nSuccessfully promoted {user_member.first_name} to a Wolf Disaster!",
    )

    log_message = (
        f"#WHITELIST\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))} \n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

    return log_message


@sudo_plus
@gloggable
async def addtiger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot = context.bot
    args = context.args
    user_id = await extract_user(message, args)
    user_member = await bot.get_chat(user_id)
    rt = ""

    reply = check_user_id(user_id, context)
    if reply:
        await message.reply_text(reply)
        return ""

    try:
        with open(ELEVATED_USERS_FILE, "r") as infile:
            data = json.load(infile)
    except FileNotFoundError:
        data = {"sudos": [], "supports": [], "whitelists": [], "tigers": []}

    if user_id in DRAGONS:
        rt += "This member is a Dragon Disaster, Demoting to Tiger."
        data["sudos"].remove(user_id)
        DRAGONS.remove(user_id)

    if user_id in DEMONS:
        rt += "This user is a Demon Disaster, Demoting to Tiger."
        data["supports"].remove(user_id)
        DEMONS.remove(user_id)

    if user_id in WOLVES:
        rt += "This user is a Wolf Disaster, Demoting to Tiger."
        data["whitelists"].remove(user_id)
        WOLVES.remove(user_id)

    if user_id in TIGERS:
        await message.reply_text("This user is already a Tiger Disaster.")
        return ""

    data["tigers"].append(user_id)
    TIGERS.append(user_id)

    with open(ELEVATED_USERS_FILE, "w") as outfile:
        json.dump(data, outfile, indent=4)

    await message.reply_text(
        rt + f"\nSuccessfully promoted {user_member.first_name} to a Tiger Disaster!",
    )

    log_message = (
        f"#TIGER\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))} \n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

    return log_message


@dev_plus
@gloggable
async def removesudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot = context.bot
    args = context.args
    user_id = await extract_user(message, args)
    user_member = await bot.get_chat(user_id)

    if not user_id:
        await message.reply_text("You don't seem to be referring to a user or the ID specified is incorrect..")
        return ""
    
    if user_id == bot.id:
        await message.reply_text("This does not work that way.")
        return ""

    if user_id == OWNER_ID:
        await message.reply_text("This person is the owner of the bot, they cannot be demoted.")
        return ""

    try:
        with open(ELEVATED_USERS_FILE, "r") as infile:
            data = json.load(infile)
    except FileNotFoundError:
        data = {"sudos": [], "supports": [], "whitelists": [], "tigers": []}

    if user_id in DRAGONS:
        await message.reply_text("Requested HA to demote this user to Civilian")
        DRAGONS.remove(user_id)
        data["sudos"].remove(user_id)

        with open(ELEVATED_USERS_FILE, "w") as outfile:
            json.dump(data, outfile, indent=4)

        log_message = (
            f"#UNSUDO\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

        return log_message
    else:
        await message.reply_text("This user is not a Dragon Disaster!")
        return ""


@sudo_plus
@gloggable
async def removesupport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot = context.bot
    args = context.args
    user_id = await extract_user(message, args)
    user_member = await bot.get_chat(user_id)

    if not user_id:
        await message.reply_text("You don't seem to be referring to a user or the ID specified is incorrect..")
        return ""
    
    if user_id == bot.id:
        await message.reply_text("This does not work that way.")
        return ""

    if user_id == OWNER_ID:
        await message.reply_text("This person is the owner of the bot, they cannot be demoted.")
        return ""

    try:
        with open(ELEVATED_USERS_FILE, "r") as infile:
            data = json.load(infile)
    except FileNotFoundError:
        data = {"sudos": [], "supports": [], "whitelists": [], "tigers": []}

    if user_id in DEMONS:
        await message.reply_text("Requested HA to demote this user to Civilian")
        DEMONS.remove(user_id)
        data["supports"].remove(user_id)

        with open(ELEVATED_USERS_FILE, "w") as outfile:
            json.dump(data, outfile, indent=4)

        log_message = (
            f"#UNSUPPORT\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

        return log_message
    else:
        await message.reply_text("This user is not a Demon Disaster!")
        return ""


@sudo_plus
@gloggable
async def removewhitelist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot = context.bot
    args = context.args
    user_id = await extract_user(message, args)
    user_member = await bot.get_chat(user_id)

    if not user_id:
        await message.reply_text("You don't seem to be referring to a user or the ID specified is incorrect..")
        return ""
    
    if user_id == bot.id:
        await message.reply_text("This does not work that way.")
        return ""

    if user_id == OWNER_ID:
        await message.reply_text("This person is the owner of the bot, they cannot be demoted.")
        return ""

    try:
        with open(ELEVATED_USERS_FILE, "r") as infile:
            data = json.load(infile)
    except FileNotFoundError:
        data = {"sudos": [], "supports": [], "whitelists": [], "tigers": []}

    if user_id in WOLVES:
        await message.reply_text("Requested HA to demote this user to Civilian")
        WOLVES.remove(user_id)
        data["whitelists"].remove(user_id)

        with open(ELEVATED_USERS_FILE, "w") as outfile:
            json.dump(data, outfile, indent=4)

        log_message = (
            f"#UNWHITELIST\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

        return log_message
    else:
        await message.reply_text("This user is not a Wolf Disaster!")
        return ""


@sudo_plus
@gloggable
async def removetiger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot = context.bot
    args = context.args
    user_id = await extract_user(message, args)
    user_member = await bot.get_chat(user_id)

    if not user_id:
        await message.reply_text("You don't seem to be referring to a user or the ID specified is incorrect..")
        return ""
    
    if user_id == bot.id:
        await message.reply_text("This does not work that way.")
        return ""

    if user_id == OWNER_ID:
        await message.reply_text("This person is the owner of the bot, they cannot be demoted.")
        return ""

    try:
        with open(ELEVATED_USERS_FILE, "r") as infile:
            data = json.load(infile)
    except FileNotFoundError:
        data = {"sudos": [], "supports": [], "whitelists": [], "tigers": []}

    if user_id in TIGERS:
        await message.reply_text("Requested HA to demote this user to Civilian")
        TIGERS.remove(user_id)
        data["tigers"].remove(user_id)

        with open(ELEVATED_USERS_FILE, "w") as outfile:
            json.dump(data, outfile, indent=4)

        log_message = (
            f"#UNTIGER\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

        return log_message
    else:
        await message.reply_text("This user is not a Tiger Disaster!")
        return ""

@dev_plus
async def dragons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    m = await update.effective_message.reply_text(
        "<code>Gathering intel..</code>", parse_mode=ParseMode.HTML,
    )
    
    reply = "<b>Disaster Level: Dragon 🐉:</b>\n"
    for each_user in DRAGONS:
        user_id = int(each_user)
        try:
            user = await bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    await m.edit_text(reply, parse_mode=ParseMode.HTML)


@sudo_plus
async def demons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    m = await update.effective_message.reply_text(
        "<code>Gathering intel..</code>", parse_mode=ParseMode.HTML,
    )
    
    reply = "<b>Disaster Level: Demon 😈:</b>\n"
    for each_user in DEMONS:
        user_id = int(each_user)
        try:
            user = await bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    await m.edit_text(reply, parse_mode=ParseMode.HTML)


@sudo_plus
async def tigers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    m = await update.effective_message.reply_text(
        "<code>Gathering intel..</code>", parse_mode=ParseMode.HTML,
    )
    
    reply = "<b>Disaster Level: Tiger 🐯:</b>\n"
    for each_user in TIGERS:
        user_id = int(each_user)
        try:
            user = await bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    await m.edit_text(reply, parse_mode=ParseMode.HTML)


@whitelist_plus
async def wolves(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    m = await update.effective_message.reply_text(
        "<code>Gathering intel..</code>", parse_mode=ParseMode.HTML,
    )
    
    reply = "<b>Disaster Level: Wolf 🐺:</b>\n"
    for each_user in WOLVES:
        user_id = int(each_user)
        try:
            user = await bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    await m.edit_text(reply, parse_mode=ParseMode.HTML)


@dev_plus
async def heroes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    m = await update.effective_message.reply_text(
        "<code>Gathering intel..</code>", parse_mode=ParseMode.HTML,
    )
    true_dev = list(set(DEV_USERS) - {OWNER_ID})
    reply = "<b>Hero Association Members ⚡️:</b>\n"
    for each_user in true_dev:
        user_id = int(each_user)
        try:
            user = await bot.get_chat(user_id)
            reply += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    await m.edit_text(reply, parse_mode=ParseMode.HTML)


async def setup_module(application: Application):
    LOGGER.info("Starting disasters module setup.")
    application.add_handler(CommandHandler("adddragon", addsudo))
    application.add_handler(CommandHandler("adddemon", addsupport))
    application.add_handler(CommandHandler("addwolf", addwhitelist))
    application.add_handler(CommandHandler("addtiger", addtiger))
    application.add_handler(CommandHandler("rmdragon", removesudo))
    application.add_handler(CommandHandler("rmdemon", removesupport))
    application.add_handler(CommandHandler("rmwolf", removewhitelist))
    application.add_handler(CommandHandler("rmtiger", removetiger))
    application.add_handler(CommandHandler("dragons", dragons))
    application.add_handler(CommandHandler("demons", demons))
    application.add_handler(CommandHandler("tigers", tigers))
    application.add_handler(CommandHandler("wolves", wolves))
    application.add_handler(CommandHandler("heroes", heroes))
    LOGGER.info("Disasters module handlers registered.")


__help__ = f"""
*⚠️ Notice:* Commands listed here only work for users with special access and are mainly used for troubleshooting, debugging purposes. Group admins/group owners do not need these commands.
╔ *List all special users:*
╠ `/dragons`*:* Lists all Dragon disasters
╠ `/demons`*:* Lists all Demon disasters
╠ `/tigers`*:* Lists all Tigers disasters
╠ `/wolves`*:* Lists all Wolf disasters
╠ `/heroes`*:* Lists all Hero Association members
╠ `/adddragon`*:* Promotes a user to a Dragon disaster
╠ `/rmdragon`*:* Demotes a Dragon disaster to a normal user
╠ `/adddemon`*:* Promotes a user to a Demon disaster
╠ `/rmdemon`*:* Demotes a Demon disaster to a normal user
╠ `/addtiger`*:* Promotes a user to a Tiger disaster
╠ `/rmtiger`*:* Demotes a Tiger disaster to a normal user
╠ `/addwolf`*:* Promotes a user to a Wolf disaster
╚ `/rmwolf`*:* Demotes a Wolf disaster to a normal user
"""

__mod_name__ = "Disasters"
