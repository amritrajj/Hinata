from enum import IntEnum, unique
from typing import Tuple, Optional, List, Any

from Hina.modules.helper_funcs.string_handling import button_markdown_parser
from telegram import Message
from telegram.constants import ParseMode


@unique
class Types(IntEnum):
    TEXT = 0
    BUTTON_TEXT = 1
    STICKER = 2
    DOCUMENT = 3
    PHOTO = 4
    AUDIO = 5
    VOICE = 6
    VIDEO = 7
    VIDEO_NOTE = 8


async def get_note_type(msg: Message) -> Tuple[str, Optional[str], Optional[Types], Optional[str], List[Any]]:
    data_type = None
    content = None
    text = ""
    raw_text = msg.text or msg.caption
    args = raw_text.split(None, 2)
    note_name = args[1]

    buttons = []
    if len(args) >= 3:
        offset = len(args[2]) - len(raw_text)
        text, buttons = await button_markdown_parser(
            args[2],
            entities=msg.parse_entities() or msg.parse_caption_entities(),
            offset=offset,
        )
        if buttons:
            data_type = Types.BUTTON_TEXT
        else:
            data_type = Types.TEXT
        content = text
    
    elif msg.reply_to_message:
        entities = msg.reply_to_message.parse_entities()
        msgtext = msg.reply_to_message.text or msg.reply_to_message.caption
        if msg.reply_to_message.text:
            text, buttons = await button_markdown_parser(msgtext, entities=entities)
            if buttons:
                data_type = Types.BUTTON_TEXT
            else:
                data_type = Types.TEXT
            content = text
        
        elif msg.reply_to_message.sticker:
            content = msg.reply_to_message.sticker.file_id
            data_type = Types.STICKER

        elif msg.reply_to_message.document:
            content = msg.reply_to_message.document.file_id
            text, buttons = await button_markdown_parser(msg.reply_to_message.caption or "", entities=entities)
            data_type = Types.DOCUMENT

        elif msg.reply_to_message.photo:
            content = msg.reply_to_message.photo[-1].file_id
            text, buttons = await button_markdown_parser(msg.reply_to_message.caption or "", entities=entities)
            data_type = Types.PHOTO

        elif msg.reply_to_message.audio:
            content = msg.reply_to_message.audio.file_id
            text, buttons = await button_markdown_parser(msg.reply_to_message.caption or "", entities=entities)
            data_type = Types.AUDIO

        elif msg.reply_to_message.voice:
            content = msg.reply_to_message.voice.file_id
            text, buttons = await button_markdown_parser(msg.reply_to_message.caption or "", entities=entities)
            data_type = Types.VOICE

        elif msg.reply_to_message.video:
            content = msg.reply_to_message.video.file_id
            text, buttons = await button_markdown_parser(msg.reply_to_message.caption or "", entities=entities)
            data_type = Types.VIDEO
            
        elif msg.reply_to_message.video_note:
            content = msg.reply_to_message.video_note.file_id
            text, buttons = await button_markdown_parser(msg.reply_to_message.caption or "", entities=entities)
            data_type = Types.VIDEO_NOTE

    return note_name, text, data_type, content, buttons


async def get_welcome_type(msg: Message) -> Tuple[Optional[str], Optional[Types], Optional[str], List[Any]]:
    data_type = None
    content = None
    text = ""
    buttons = []

    if msg.reply_to_message:
        reply_msg = msg.reply_to_message
        caption = reply_msg.caption if reply_msg.caption else ""
        entities = reply_msg.parse_entities() or reply_msg.parse_caption_entities()

        if reply_msg.sticker:
            content = reply_msg.sticker.file_id
            data_type = Types.STICKER
            text = caption
        elif reply_msg.document:
            content = reply_msg.document.file_id
            data_type = Types.DOCUMENT
            text = caption
        elif reply_msg.photo:
            content = reply_msg.photo[-1].file_id
            data_type = Types.PHOTO
            text = caption
        elif reply_msg.audio:
            content = reply_msg.audio.file_id
            data_type = Types.AUDIO
            text = caption
        elif reply_msg.voice:
            content = reply_msg.voice.file_id
            data_type = Types.VOICE
            text = caption
        elif reply_msg.video:
            content = reply_msg.video.file_id
            data_type = Types.VIDEO
            text = caption
        elif reply_msg.video_note:
            content = reply_msg.video_note.file_id
            data_type = Types.VIDEO_NOTE
            text = caption
        elif reply_msg.text:
            text = reply_msg.text
            data_type = Types.TEXT
            
        if data_type not in (Types.STICKER, Types.VIDEO_NOTE) and text:
            text, buttons = await button_markdown_parser(
                text,
                entities=entities,
            )

    else:
        args = msg.text.split(None, 1)
        if len(args) > 1:
            text, buttons = await button_markdown_parser(
                args[1],
                entities=msg.parse_entities(),
                offset=len(args[0]),
            )
            data_type = Types.TEXT
    
    if not data_type:
        if text and buttons:
            data_type = Types.BUTTON_TEXT
        elif text:
            data_type = Types.TEXT

    return text, data_type, content, buttons


async def get_filter_type(msg: Message) -> Tuple[Optional[str], Optional[Types], Optional[str]]:
    text = None
    data_type = None
    content = None
    
    if not msg.reply_to_message and msg.text and len(msg.text.split()) >= 3:
        text = msg.text.split(None, 2)[2]
        data_type = Types.TEXT

    elif msg.reply_to_message:
        reply_msg = msg.reply_to_message
        
        if reply_msg.text and len(msg.text.split()) >= 2:
            text = reply_msg.text
            data_type = Types.TEXT
            
        elif reply_msg.sticker:
            content = reply_msg.sticker.file_id
            data_type = Types.STICKER

        elif reply_msg.document:
            content = reply_msg.document.file_id
            text = reply_msg.caption
            data_type = Types.DOCUMENT

        elif reply_msg.photo:
            content = reply_msg.photo[-1].file_id
            text = reply_msg.caption
            data_type = Types.PHOTO

        elif reply_msg.audio:
            content = reply_msg.audio.file_id
            text = reply_msg.caption
            data_type = Types.AUDIO

        elif reply_msg.voice:
            content = reply_msg.voice.file_id
            text = reply_msg.caption
            data_type = Types.VOICE

        elif reply_msg.video:
            content = reply_msg.video.file_id
            text = reply_msg.caption
            data_type = Types.VIDEO

        elif reply_msg.video_note:
            content = reply_msg.video_note.file_id
            text = None
            data_type = Types.VIDEO_NOTE
            
    return text, data_type, content
