import re
import time
from typing import Dict, List, Optional, Tuple, Union

import bleach
import markdown2
import emoji

from telegram import Message, MessageEntity
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

# NOTE: the url \ escape may cause double escapes
# match * (bold) (don't escape if in url)
# match _ (italics) (don't escape if in url)
# match ` (code)
# match []() (markdown link)
# else, escape *, _, `, and [
MATCH_MD = re.compile(
    r"\*(.*?)\*|"
    r"_(.*?)_|"
    r"`(.*?)`|"
    r"(?<!\\)(\[.*?\])(\(.*?\))|"
    r"(?P<esc>[*_`\[])",
)

# regex to find []() links -> hyperlinks/buttons
LINK_REGEX = re.compile(r"(?<!\\)\[.+?\]\((.*?)\)")
BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)\]\(buttonurl:(?:/{0,2})(.+?)(:same)?\))")


def _selective_escape(to_parse: str) -> str:
    """
    Escape all invalid markdown
    
    :param to_parse: text to escape
    :return: valid markdown string
    """
    offset = 0  # offset to be used as adding a \ character causes the string to shift
    for match in MATCH_MD.finditer(to_parse):
        if match.group("esc"):
            ent_start = match.start()
            to_parse = (
                to_parse[: ent_start + offset] + "\\" + to_parse[ent_start + offset :]
            )
            offset += 1
    return to_parse


def _calc_emoji_offset(to_calc: str) -> int:
    """
    Calculate emoji offset in UTF-16 encoding
    
    :param to_calc: text to calculate emoji offset for
    :return: total offset caused by emojis
    """
    emoticons = emoji.get_emoji_regexp().finditer(to_calc)
    return sum(len(e.group(0).encode("utf-16-le")) // 2 - 1 for e in emoticons)


def markdown_parser(
    txt: str,
    entities: Optional[Dict[MessageEntity, str]] = None,
    offset: int = 0,
) -> str:
    """
    Parse a string, escaping all invalid markdown entities.
    
    :param txt: text to parse
    :param entities: dict of message entities in text
    :param offset: message offset - command and notename length
    :return: valid markdown string
    """
    if not entities:
        entities = {}
    if not txt:
        return ""

    prev = 0
    res = ""
    for ent, ent_text in entities.items():
        if ent.offset < -offset:
            continue

        start = ent.offset + offset  # start of entity
        end = ent.offset + offset + ent.length - 1  # end of entity

        if ent.type in ("code", "url", "text_link"):
            count = _calc_emoji_offset(txt[:start])
            start -= count
            end -= count

            if ent.type == "url":
                if any(
                    match.start(1) <= start and end <= match.end(1)
                    for match in LINK_REGEX.finditer(txt)
                ):
                    continue
                res += _selective_escape(txt[prev:start] or "") + escape_markdown(ent_text)

            elif ent.type == "code":
                res += _selective_escape(txt[prev:start]) + "`" + ent_text + "`"

            elif ent.type == "text_link":
                res += _selective_escape(txt[prev:start]) + "[{}]({})".format(
                    ent_text, ent.url)

            end += 1

        prev = end

    res += _selective_escape(txt[prev:])
    return res


def button_markdown_parser(
    txt: str,
    entities: Optional[Dict[MessageEntity, str]] = None,
    offset: int = 0,
) -> Tuple[str, List[Tuple[str, str, bool]]]:
    """
    Parse markdown and extract buttons
    
    :param txt: text to parse
    :param entities: dict of message entities
    :param offset: message offset
    :return: tuple of (parsed text, list of buttons)
    """
    markdown_note = markdown_parser(txt, entities, offset)
    prev = 0
    note_data = ""
    buttons = []
    for match in BTN_URL_REGEX.finditer(markdown_note):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and markdown_note[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        if n_escapes % 2 == 1:
            continue

        note_data += markdown_note[prev : match.start(1)]
        prev = match.end(1)
        
        # Check if same line
        if match.group(4) and buttons:
            buttons[-1].append(
                (match.group(2), match.group(3), True)
            )
        else:
            buttons.append(
                [(match.group(2), match.group(3), False)]
            )
            
    note_data += markdown_note[prev:]
    
    return note_data, buttons

def escape_invalid_markdown(text: str) -> str:
    """Escape invalid markdown characters."""
    return re.sub(r"([_*`\[\]])", r"\\\1", text)
