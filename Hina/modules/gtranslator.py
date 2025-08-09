from Hina.config import app
from emoji import EMOJI_DATA as UNICODE_EMOJI
from googletrans import LANGUAGES, Translator
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler
from Hina.modules.disable import DisableAbleCommandHandler

async def totranslate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    problem_lang_code = []
    for key in LANGUAGES:
        if "-" in key:
            problem_lang_code.append(key)

    try:
        if message.reply_to_message:
            args = update.effective_message.text.split(None, 1)
            if message.reply_to_message.text:
                text = message.reply_to_message.text
            elif message.reply_to_message.caption:
                text = message.reply_to_message.caption

            try:
                source_lang = args[1].split(None, 1)[0]
            except (IndexError, AttributeError):
                source_lang = "en"
        else:
            args = update.effective_message.text.split(None, 2)
            text = args[2]
            source_lang = args[1]

        dest_lang = None
        if source_lang.count("-") == 2:
            for lang in problem_lang_code:
                if lang in source_lang:
                    if source_lang.startswith(lang):
                        dest_lang = source_lang.rsplit("-", 1)[1]
                        source_lang = source_lang.rsplit("-", 1)[0]
                    else:
                        dest_lang = source_lang.split("-", 1)[1]
                        source_lang = source_lang.split("-", 1)[0]
        elif source_lang.count("-") == 1:
            for lang in problem_lang_code:
                if lang in source_lang:
                    dest_lang = source_lang
                    source_lang = None
                    break
            if dest_lang is None:
                dest_lang = source_lang.split("-")[1]
                source_lang = source_lang.split("-")[0]
        else:
            dest_lang = source_lang
            source_lang = None

        exclude_list = UNICODE_EMOJI.keys()
        for emoji in exclude_list:
            if emoji in text:
                text = text.replace(emoji, "")

        translator = Translator()
        if source_lang is None:
            detection = translator.detect(text)
            trans_str = translator.translate(text, dest=dest_lang).text
            await message.reply_text(
                f"Translated from `{detection.lang}` to `{dest_lang}`:\n`{trans_str}`",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            trans_str = translator.translate(text, src=source_lang, dest=dest_lang).text
            await message.reply_text(
                f"Translated from `{source_lang}` to `{dest_lang}`:\n`{trans_str}`",
                parse_mode=ParseMode.MARKDOWN,
            )

    except IndexError:
        await update.effective_message.reply_text(
            "Reply to messages or write messages from other languages for translating into the intended language\n\n"
            "Example: `/tr en-hi` to translate from English to Hindi\n"
            "Or use: `/tr hi` for automatic detection and translating it into Hindi.\n"
            "See [List of Language Codes](t.me/tech_sav_bots/12823) for a list of language codes.",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except ValueError as e:
        await update.effective_message.reply_text(f"Translation error: {str(e)}")
    except Exception as e:
        await update.effective_message.reply_text("An error occurred during translation")

__help__ = """
• `/tr` or `/tl` (language code) as reply to a long message
*Example:*
  `/tr en`*:* translates something to english
  `/tr hi-en`*:* translates hindi to english
"""

TRANSLATE_HANDLER = DisableAbleCommandHandler(["tr", "tl"], totranslate)

def register(app):
    app.add_handler(TRANSLATE_HANDLER)

__mod_name__ = "Translator"
__command_list__ = ["tr", "tl"]
__handlers__ = [TRANSLATE_HANDLER]
