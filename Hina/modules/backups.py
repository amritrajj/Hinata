from Hina.config import app, DATA_IMPORT
import json, time, os
from io import BytesIO

from telegram import Message, Update
from telegram.constants import ParseMode, ChatAction
from telegram.error import BadRequest
from telegram.ext import CommandHandler, ContextTypes

import Hina.modules.sql.notes_sql as sql
from Hina.modules.helper_funcs.chat_status import user_admin
from Hina.modules.helper_funcs.alternate import typing_action
import Hina.modules.sql.rules_sql as rulessql
import Hina.modules.sql.blacklist_sql as blacklistsql
from Hina.modules.sql import disable_sql as disabledsql
import Hina.modules.sql.locks_sql as locksql
from Hina.modules.connection import connected

@user_admin
@typing_action
async def import_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat_obj = await app.bot.getChat(conn)
        chat_name = chat_obj.title
        chat_id = conn
    else:
        if update.effective_message.chat.type == "private":
            await update.effective_message.reply_text("This is a group only command!")
            return ""
        chat_obj = update.effective_chat
        chat_name = chat_obj.title
        chat_id = chat_obj.id

    if msg.reply_to_message and msg.reply_to_message.document:
        try:
            file_info = await context.bot.get_file(msg.reply_to_message.document.file_id)
        except BadRequest:
            await msg.reply_text(
                "Try downloading and uploading the file yourself again, This one seem broken to me!",
            )
            return

        with BytesIO() as file:
            await file_info.download(out=file)
            file.seek(0)
            data = json.load(file)

        # only import one group
        if len(data) > 1 and str(chat_id) not in data:
            await msg.reply_text(
                "There are more than one group in this file and the chat.id is not same! How am i supposed to import it?",
            )
            return

        # Check if backup is this chat
        try:
            if data.get(str(chat_id)) is None:
                if conn:
                    text = "Backup comes from another chat, I can't return another chat to chat *{}*".format(
                        chat_name,
                    )
                else:
                    text = "Backup comes from another chat, I can't return another chat to this chat"
                return await msg.reply_text(text, parse_mode="markdown")
        except Exception:
            return await msg.reply_text("There was a problem while importing the data!")
        # Check if backup is from self
        try:
            if str(context.bot.id) != str(data[str(chat_id)]["bot"]):
                await msg.reply_text(
                    "Backup from another bot that is not suggested might cause the problem, documents, photos, videos, audios, records might not work as it should be.",
                )
        except Exception:
            pass
        # Select data source
        if str(chat_id) in data:
            data = data[str(chat_id)]["hashes"]
        else:
            data = data[list(data.keys())[0]]["hashes"]

        try:
            for mod in DATA_IMPORT:
                mod.__import_data__(str(chat_id), data)
        except Exception:
            await msg.reply_text(
                f"An error occurred while recovering your data. The process failed. If you experience a problem with this, please take it to @{SUPPORT_CHAT}",
            )
            # LOGGER.exception(...)  # Uncomment if LOGGER is defined
            return

        if conn:
            text = "Backup fully restored on *{}*.".format(chat_name)
        else:
            text = "Backup fully restored"
        await msg.reply_text(text, parse_mode="markdown")

@user_admin
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_data = context.chat_data
    msg = update.effective_message
    user = update.effective_user
    chat_id = update.effective_chat.id
    chat = update.effective_chat
    current_chat_id = update.effective_chat.id
    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat_obj = await app.bot.getChat(conn)
        chat = chat_obj
        chat_id = conn
    else:
        if update.effective_message.chat.type == "private":
            await update.effective_message.reply_text("This is a group only command!")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id

    jam = time.time()
    new_jam = jam + 10800
    checkchat = get_chat(chat_id, chat_data)
    if checkchat.get("status"):
        if jam <= int(checkchat.get("value")):
            timeformatt = time.strftime(
                "%H:%M:%S %d/%m/%Y", time.localtime(checkchat.get("value")),
            )
            await update.effective_message.reply_text(
                "You can only backup once a day!\nYou can backup again in about `{}`".format(
                    timeformatt,
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        else:
            if user.id != OWNER_ID:
                put_chat(chat_id, new_jam, chat_data)
    else:
        if user.id != OWNER_ID:
            put_chat(chat_id, new_jam, chat_data)

    note_list = sql.get_all_chat_notes(chat_id)
    backup = {}
    buttonlist = []
    namacat = ""
    isicat = ""
    count = 0
    countbtn = 0
    for note in note_list:
        count += 1
        namacat += "{}<###splitter###>".format(note.name)
        if note.msgtype == 1:
            tombol = sql.get_buttons(chat_id, note.name)
            for btn in tombol:
                countbtn += 1
                if btn.same_line:
                    buttonlist.append(
                        ("{}".format(btn.name), "{}".format(btn.url), True),
                    )
                else:
                    buttonlist.append(
                        ("{}".format(btn.name), "{}".format(btn.url), False),
                    )
            isicat += "###button###: {}<###button###>{}<###splitter###>".format(
                note.value, str(buttonlist),
            )
            buttonlist.clear()
        elif note.msgtype == 2:
            isicat += "###sticker###:{}<###splitter###>".format(note.file)
        elif note.msgtype == 3:
            isicat += "###file###:{}<###TYPESPLIT###>{}<###splitter###>".format(
                note.file, note.value,
            )
        elif note.msgtype == 4:
            isicat += "###photo###:{}<###TYPESPLIT###>{}<###splitter###>".format(
                note.file, note.value,
            )
        elif note.msgtype == 5:
            isicat += "###audio###:{}<###TYPESPLIT###>{}<###splitter###>".format(
                note.file, note.value,
            )
        elif note.msgtype == 6:
            isicat += "###voice###:{}<###TYPESPLIT###>{}<###splitter###>".format(
                note.file, note.value,
            )
        elif note.msgtype == 7:
            isicat += "###video###:{}<###TYPESPLIT###>{}<###splitter###>".format(
                note.file, note.value,
            )
        elif note.msgtype == 8:
            isicat += "###video_note###:{}<###TYPESPLIT###>{}<###splitter###>".format(
                note.file, note.value,
            )
        else:
            isicat += "{}<###splitter###>".format(note.value)
    notes = {
        "#{}".format(namacat.split("<###splitter###>")[x]): "{}".format(
            isicat.split("<###splitter###>")[x],
        )
        for x in range(count)
    }
    rules = rulessql.get_rules(chat_id)
    bl = list(blacklistsql.get_chat_blacklist(chat_id))
    disabledcmd = list(disabledsql.get_all_disabled(chat_id))
    curr_locks = locksql.get_locks(chat_id)
    curr_restr = locksql.get_restr(chat_id)

    if curr_locks:
        locked_lock = {
            "sticker": curr_locks.sticker,
            "audio": curr_locks.audio,
            "voice": curr_locks.voice,
            "document": curr_locks.document,
            "video": curr_locks.video,
            "contact": curr_locks.contact,
            "photo": curr_locks.photo,
            "gif": curr_locks.gif,
            "url": curr_locks.url,
            "bots": curr_locks.bots,
            "forward": curr_locks.forward,
            "game": curr_locks.game,
            "location": curr_locks.location,
            "rtl": curr_locks.rtl,
        }
    else:
        locked_lock = {}

    if curr_restr:
        locked_restr = {
            "messages": curr_restr.messages,
            "media": curr_restr.media,
            "other": curr_restr.other,
            "previews": curr_restr.preview,
            "all": all(
                [
                    curr_restr.messages,
                    curr_restr.media,
                    curr_restr.other,
                    curr_restr.preview,
                ],
            ),
        }
    else:
        locked_restr = {}

    locks = {"locks": locked_lock, "restrict": locked_restr}

    backup[chat_id] = {
        "bot": context.bot.id,
        "hashes": {
            "info": {"rules": rules},
            "extra": notes,
            "blacklist": bl,
            "disabled": disabledcmd,
            "locks": locks,
        },
    }
    baccinfo = json.dumps(backup, indent=4)
    backup_filename = f"Hina{chat_id}.backup"
    with open(backup_filename, "w") as f:
        f.write(str(baccinfo))
    await context.bot.send_chat_action(current_chat_id, ChatAction.UPLOAD_DOCUMENT)
    tgl = time.strftime("%H:%M:%S - %d/%m/%Y", time.localtime(time.time()))
    try:
        await context.bot.send_message(
            JOIN_LOGGER,
            "*Successfully imported backup:*\nChat: `{}`\nChat ID: `{}`\nOn: `{}`".format(
                chat.title, chat_id, tgl,
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    except BadRequest:
        pass
    with open(backup_filename, "rb") as doc_file:
        await context.bot.send_document(
            current_chat_id,
            document=doc_file,
            caption="*Successfully Exported backup:*\nChat: `{}`\nChat ID: `{}`\nOn: `{}`\n\nNote: This `Hina-Backup` was specially made for notes.".format(
                chat.title, chat_id, tgl,
            ),
            timeout=360,
            reply_to_message_id=msg.message_id,
            parse_mode=ParseMode.MARKDOWN,
        )
    os.remove(backup_filename)

def put_chat(chat_id, value, chat_data):
    status = value is not False
    chat_data[chat_id] = {"backups": {"status": status, "value": value}}

def get_chat(chat_id, chat_data):
    try:
        return chat_data[chat_id]["backups"]
    except KeyError:
        return {"status": False, "value": False}

__mod_name__ = "Backups"

__help__ = """
*Only for group owner:*

 • /import: Reply to the backup file for the butler / emilia group to import as much as possible, making transfers very easy! \
 Note that files / photos cannot be imported due to telegram restrictions.

 • /export: Export group data, which will be exported are: rules, notes (documents, images, music, video, audio, voice, text, text buttons) \

"""

IMPORT_HANDLER = CommandHandler("import", import_data)
EXPORT_HANDLER = CommandHandler("export", export_data)

app.add_handler(IMPORT_HANDLER)
app.add_handler(EXPORT_HANDLER)