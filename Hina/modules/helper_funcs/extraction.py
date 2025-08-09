from typing import Tuple, Optional, Any, Dict

from telegram import Message
from telegram.ext import ContextTypes
from telegram.constants import MessageEntityType


async def extract_user_and_text(message: Message, entities: Dict) -> Tuple[Optional[int], Optional[str]]:
    """
    Extracts the user ID and text from a message, prioritizing a replied message if available.
    
    :param message: The Message object.
    :param entities: A dictionary of message entities.
    :return: A tuple containing the extracted user ID and text.
    """
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        text = message.reply_to_message.text or message.reply_to_message.caption
    else:
        user_id = None
        text = None
        
        # Check for user mentions
        for ent, ent_text in entities.items():
            if ent.type == MessageEntityType.TEXT_MENTION:
                user_id = ent.user.id
            elif ent.type == MessageEntityType.MENTION:
                try:
                    user_id = int(ent_text)
                except (ValueError, TypeError):
                    pass
            
            if user_id:
                text = message.text[ent.offset + ent.length:].strip()
                break
        
        if not user_id:
            text = message.text

    return user_id, text
