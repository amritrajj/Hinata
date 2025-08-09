from Hina.config import app
import os
import math
import requests
import urllib.request as urllib
from PIL import Image, ImageOps
from html import escape
from bs4 import BeautifulSoup as bs
import re

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputSticker,
    constants
)
from telegram.constants import ParseMode, StickerFormat
from telegram.error import TelegramError, BadRequest
from telegram.helpers import mention_html
from telegram.ext import ContextTypes, CommandHandler, BaseHandler

from Hina.modules.disable import DisableAbleCommandHandler

combot_stickers_url = "https://combot.org/telegram/stickers?q="

# Helper function to validate emojis
def is_emoji(s):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "]+", 
        flags=re.UNICODE
    )
    return bool(emoji_pattern.fullmatch(s))

async def stickerid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.sticker:
        await msg.reply_text(
            f"Hello {mention_html(msg.from_user.id, msg.from_user.first_name)}, "
            f"The sticker ID you're replying to is:\n"
            f"<code>{escape(msg.reply_to_message.sticker.file_id)}</code>\n"
            f"Unique ID: <code>{msg.reply_to_message.sticker.file_unique_id}</code>",
            parse_mode=ParseMode.HTML
        )
    else:
        await msg.reply_text(
            f"Hello {mention_html(msg.from_user.id, msg.from_user.first_name)}, "
            "Please reply to a sticker message to get its ID",
            parse_mode=ParseMode.HTML
        )


async def cb_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    args = context.args
    if not args:
        await msg.reply_text("Please provide a sticker name to search.")
        return
        
    search_query = " ".join(args)
    try:
        text = requests.get(combot_stickers_url + search_query).text
        soup = bs(text, "lxml")
        results = soup.find_all("a", {"class": "sticker-pack__btn"})
        titles = soup.find_all("div", "sticker-pack__title")
        
        if not results:
            await msg.reply_text(f"No results found for: {search_query}")
            return
            
        reply = f"Stickers for *{escape(search_query)}*:\n"
        for result, title in zip(results, titles):
            link = result["href"]
            title_text = title.get_text().strip()
            reply += f"\n• [{escape(title_text)}]({escape(link)})"
        
        await msg.reply_text(reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        await msg.reply_text(f"Error searching stickers: {str(e)}")


async def getsticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if not msg.reply_to_message:
        await msg.reply_text("Please reply to a sticker message.")
        return
        
    replied = msg.reply_to_message
    
    if replied.sticker:
        sticker = replied.sticker
        if sticker.is_animated or sticker.is_video:
            await msg.reply_text(
                "Animated and video stickers can't be exported as PNG. "
                "Use /stickerid to get their ID instead."
            )
            return
            
        try:
            file = await context.bot.get_file(sticker.file_id)
            await file.download_to_drive(f"{sticker.file_unique_id}.png")
            
            with open(f"{sticker.file_unique_id}.png", "rb") as f:
                await context.bot.send_document(
                    chat_id, 
                    document=f,
                    caption=f"Sticker PNG for @{user.username}" if user.username else "Sticker PNG",
                    filename=f"{sticker.file_unique_id}.png"
                )
            os.remove(f"{sticker.file_unique_id}.png")
        except Exception as e:
            await msg.reply_text(f"Failed to process sticker: {str(e)}")
    elif replied.photo:
        try:
            file = await context.bot.get_file(replied.photo[-1].file_id)
            await file.download_to_drive("photo.png")
            
            with Image.open("photo.png") as img:
                img.save("sticker.png", "PNG")
                
            with open("sticker.png", "rb") as f:
                await context.bot.send_document(chat_id, document=f)
                
            os.remove("photo.png")
            os.remove("sticker.png")
        except Exception as e:
            await msg.reply_text(f"Failed to process photo: {str(e)}")
    else:
        await msg.reply_text("Unsupported message type. Please reply to a static sticker or photo.")


async def kang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    args = context.args

    # Initialize variables
    pack_prefix = "a"
    pack_format = StickerFormat.STATIC
    file_path = "kangsticker.png"
    animated = False
    video = False
    emoji = "🤔"
    kang_image = False
    url_kang = False

    # Process arguments and replied message
    if not msg.reply_to_message:
        if args and args[0].startswith(('http://', 'https://')):
            # Handle URL kang
            url = args[0]
            try:
                # Download from URL
                urllib.request.urlretrieve(url, file_path)
                kang_image = True
                
                # Set emoji if provided
                if len(args) >= 2:
                    emoji = args[1]
                    if not is_emoji(emoji):
                        emoji = "🤔"
                url_kang = True
            except Exception as e:
                await msg.reply_text(f"Failed to download image: {str(e)}")
                return
        else:
            await msg.reply_text("Please reply to a sticker/photo or provide a URL to kang it!")
            return
    else:
        # Handle replied message
        replied = msg.reply_to_message
        kang_file = None

        # Determine sticker type and get file
        if replied.sticker:
            if replied.sticker.is_animated:
                pack_prefix = "animated"
                pack_format = StickerFormat.ANIMATED
                animated = True
                file_path = "kangsticker.tgs"
            elif replied.sticker.is_video:
                pack_prefix = "video"
                pack_format = StickerFormat.VIDEO
                video = True
                file_path = "kangsticker.webm"
            else:
                kang_image = True
            kang_file = await replied.sticker.get_file()
        elif replied.photo:
            kang_image = True
            kang_file = await replied.photo[-1].get_file()
        elif replied.document and replied.document.mime_type in ["image/png", "image/jpeg"]:
            kang_image = True
            kang_file = await replied.document.get_file()
        else:
            await msg.reply_text("Unsupported file type!")
            return

        # Download sticker content if not URL kang
        if not url_kang:
            await kang_file.download_to_drive(file_path)

        # Determine emoji from args or sticker
        if args:
            emoji = args[0]
            if not is_emoji(emoji) and len(emoji) > 1:
                emoji = "🤔"
        elif replied.sticker and replied.sticker.emoji:
            emoji = replied.sticker.emoji

    # Process static images (resize and make sticker-ready)
    if kang_image:
        try:
            with Image.open(file_path) as img:
                # Remove alpha channel for JPEG compatibility
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                
                # Resize with proper aspect ratio
                width, height = img.size
                max_size = 512
                
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))
                
                img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Create canvas with transparent background
                canvas = Image.new("RGBA", (max_size, max_size), (0, 0, 0, 0))
                position = (
                    (max_size - new_width) // 2,
                    (max_size - new_height) // 2
                )
                canvas.paste(img, position)
                canvas.save(file_path, "PNG")
        except Exception as e:
            await msg.reply_text(f"Error processing image: {str(e)}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return

    # Find or create pack
    pack_name = f"{pack_prefix}_{user.id}_by_{context.bot.username}"
    pack_title = f"@{user.username}'s kang pack" if user.username else f"{user.first_name}'s kang pack"
    pack_title = pack_title[:64]  # Limit to 64 characters
    max_stickers = 50 if animated or video else 120
    pack_num = 0
    created_new = False
    pack_found = False

    # Try to find existing pack with space
    while pack_num < 100:  # Limit to 100 packs per user
        try:
            pack = await context.bot.get_sticker_set(pack_name)
            if len(pack.stickers) >= max_stickers:
                pack_num += 1
                pack_name = f"{pack_prefix}{pack_num}_{user.id}_by_{context.bot.username}"
            else:
                pack_found = True
                break
        except BadRequest as e:
            if "Stickerset_invalid" in str(e):
                break  # Pack doesn't exist
            else:
                await msg.reply_text(f"Error: {str(e)}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return

    try:
        # Create input sticker
        with open(file_path, "rb") as sticker_file:
            sticker_data = InputSticker(
                sticker=sticker_file,
                emoji_list=[emoji]
            )

            if pack_found:
                # Add to existing pack
                await context.bot.add_sticker_to_set(
                    user_id=user.id,
                    name=pack_name,
                    sticker=sticker_data,
                    format=pack_format
                )
            else:
                # Create new pack
                await context.bot.create_new_sticker_set(
                    user_id=user.id,
                    name=pack_name,
                    title=pack_title,
                    stickers=[sticker_data],
                    sticker_format=pack_format
                )
                created_new = True
                
        # Format success message
        message_text = (
            f"Sticker successfully {'added to' if not created_new else 'kanged to new'} "
            f"[pack](t.me/addstickers/{pack_name})\n"
            f"• Emoji: {emoji}\n"
            f"• Type: {'Animated' if animated else 'Video' if video else 'Static'}"
        )
        
        # Add pack info if user has multiple packs
        if pack_num > 0:
            message_text += f"\n• Pack #: {pack_num + 1}"
            
        await msg.reply_text(
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_to_message_id=msg.reply_to_message.message_id if msg.reply_to_message else None
        )
    except TelegramError as e:
        error_message = f"Failed to add sticker: {str(e)}"
        
        # Handle specific errors
        if "Stickers_too_much" in str(e):
            error_message = "This pack is full. Please try kanging again to create a new pack."
        elif "Stickerset_invalid" in str(e):
            error_message = "Pack creation failed. Please start a chat with me first."
        elif "Invalid sticker emojis" in str(e):
            error_message = "Invalid emoji specified. Please use a single valid emoji."
        elif "Peer_id_invalid" in str(e):
            error_message = "Please start a private chat with me first to create sticker packs."
            
        await msg.reply_text(error_message)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

async def sticker_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = "📚 Your sticker packs:\n\n"
    
    # Search for all packs
    pack_prefixes = ["a", "animated", "video"]
    found_packs = []
    
    for prefix in pack_prefixes:
        pack_num = 0
        while True:
            if pack_num == 0:
                pack_name = f"{prefix}_{user.id}_by_{context.bot.username}"
            else:
                pack_name = f"{prefix}{pack_num}_{user.id}_by_{context.bot.username}"
                
            try:
                pack = await context.bot.get_sticker_set(pack_name)
                pack_link = f"• [{pack.title}](t.me/addstickers/{pack_name})"
                pack_info = f"({len(pack.stickers)}/{50 if prefix != 'a' else 120} stickers)"
                found_packs.append(f"{pack_link} {pack_info}")
                pack_num += 1
            except BadRequest:
                # No more packs for this prefix
                break
    
    if found_packs:
        message_text += "\n".join(found_packs)
    else:
        message_text = "You don't have any sticker packs yet! Use /kang to create one."
    
    await update.effective_message.reply_text(
        message_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


__help__ = """
🖼️ *Sticker Tools:*
• `/stickerid` - Reply to sticker to get ID
• `/getsticker` - Reply to static sticker to get PNG
• `/kang` [emoji] - Add sticker to your pack (reply to sticker/image)
• `/stickers` <query> - Search sticker packs
• `/mypacks` - List your sticker packs
"""

__mod_name__ = "Stickers"
STICKERID_HANDLER = DisableAbleCommandHandler("stickerid", stickerid)
GETSTICKER_HANDLER = DisableAbleCommandHandler("getsticker", getsticker)
KANG_HANDLER = DisableAbleCommandHandler("kang", kang)
STICKERS_HANDLER = DisableAbleCommandHandler("stickers", cb_sticker)
PACKS_HANDLER = DisableAbleCommandHandler("mypacks", sticker_packs)

app.add_handler(STICKERS_HANDLER)
app.add_handler(STICKERID_HANDLER)
app.add_handler(GETSTICKER_HANDLER)
app.add_handler(KANG_HANDLER)
app.add_handler(PACKS_HANDLER)
