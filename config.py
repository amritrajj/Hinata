import logging
import os
import sys
import time
import spamwatch
import telegram.ext as tg
from telethon import TelegramClient

StartTime = time.time()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)

# Check Python version
if sys.version_info < (3, 6):
    LOGGER.error("Python 3.12+ required. Bot quitting.")
    quit(1)

ENV = bool(os.environ.get("ENV", False))

# ✅ Local Development Config
class Development:
    TOKEN = "7141832146:AAHqGaW0IcEWKTzy6-LUGqQWNs1IchfA0W8"
    OWNER_ID = 1152303959
    JOIN_LOGGER = "-1001777503234"
    OWNER_USERNAME = "anin_network"
    ALLOW_CHATS = True
    DRAGONS = [1152303959]
    DEV_USERS = [1152303959]
    DEMONS = []
    WOLVES = []
    TIGERS = []
    EVENT_LOGS = "-1001794293836"
    WEBHOOK = False
    URL = "postgres://dvrramqa:xbEwlX2_hnYd8uPpj9hkEKlLVaCWtESy@tyke.db.elephantsql.com/dvrramqa"
    PORT = 5000
    CERT_PATH = None
    API_ID = "4951377"
    API_HASH = "b682525d7bd7be0b7f61502cc1c8b22e"
    DB_URI = "postgresql://hina_user:ZwE8zPuSc1tl0EOuMKpXShyqTFqR3Wfz@dpg-d26g8h15pdvs73ek8cm0-a.oregon-postgres.render.com/hina"
    DONATION_LINK = "https://example.com/donate"
    LOAD = []
    NO_LOAD = ["translation"]
    DEL_CMDS = True
    STRICT_GBAN = False
    WORKERS = 8
    BAN_STICKER = "CAADAgADOwADPPEcAXkko5EB3YGYAg"
    ALLOW_EXCL = True
    CASH_API_KEY = None
    TIME_API_KEY = None
    AI_API_KEY = None
    WALL_API = None
    SUPPORT_CHAT = "your_support_chat"
    SPAMWATCH_SUPPORT_CHAT = None
    SPAMWATCH_API = None
    BL_CHATS = []

if ENV:
    # Production (ENV) mode
    TOKEN = os.environ.get("TOKEN")

    try:
        OWNER_ID = int(os.environ.get("OWNER_ID"))
    except ValueError:
        raise Exception("OWNER_ID must be an integer")

    JOIN_LOGGER = os.environ.get("JOIN_LOGGER")
    OWNER_USERNAME = os.environ.get("OWNER_USERNAME")
    ALLOW_CHATS = bool(os.environ.get("ALLOW_CHATS", True))

    try:
        DRAGONS = set(map(int, os.environ.get("DRAGONS", "").split()))
        DEV_USERS = set(map(int, os.environ.get("DEV_USERS", "").split()))
        DEMONS = set(map(int, os.environ.get("DEMONS", "").split()))
        WOLVES = set(map(int, os.environ.get("WOLVES", "").split()))
        TIGERS = set(map(int, os.environ.get("TIGERS", "").split()))
    except ValueError:
        raise Exception("User ID lists must contain integers")

    INFOPIC = bool(os.environ.get("INFOPIC", False))
    EVENT_LOGS = os.environ.get("EVENT_LOGS")
    WEBHOOK = bool(os.environ.get("WEBHOOK", False))
    URL = os.environ.get("URL", "")
    PORT = int(os.environ.get("PORT", 5000))
    CERT_PATH = os.environ.get("CERT_PATH")
    API_ID = os.environ.get("API_ID")
    API_HASH = os.environ.get("API_HASH")
    DB_URI = os.environ.get("DATABASE_URL")
    DONATION_LINK = os.environ.get("DONATION_LINK")
    LOAD = os.environ.get("LOAD", "").split()
    NO_LOAD = os.environ.get("NO_LOAD", "translation").split()
    DEL_CMDS = bool(os.environ.get("DEL_CMDS", False))
    STRICT_GBAN = bool(os.environ.get("STRICT_GBAN", False))
    WORKERS = int(os.environ.get("WORKERS", 8))
    BAN_STICKER = os.environ.get("BAN_STICKER", "CAADAgADOwADPPEcAXkko5EB3YGYAg")
    ALLOW_EXCL = bool(os.environ.get("ALLOW_EXCL", False))
    CASH_API_KEY = os.environ.get("CASH_API_KEY")
    TIME_API_KEY = os.environ.get("TIME_API_KEY")
    AI_API_KEY = os.environ.get("AI_API_KEY")
    WALL_API = os.environ.get("WALL_API")
    SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT")
    SPAMWATCH_SUPPORT_CHAT = os.environ.get("SPAMWATCH_SUPPORT_CHAT")
    SPAMWATCH_API = os.environ.get("SPAMWATCH_API")

    try:
        BL_CHATS = set(map(int, os.environ.get("BL_CHATS", "").split()))
    except ValueError:
        raise Exception("BL_CHATS must contain integers")
else:
    # Local development mode using Development class
    TOKEN = Development.TOKEN
    OWNER_ID = Development.OWNER_ID
    JOIN_LOGGER = Development.JOIN_LOGGER
    OWNER_USERNAME = Development.OWNER_USERNAME
    ALLOW_CHATS = Development.ALLOW_CHATS
    DRAGONS = set(Development.DRAGONS)
    DEV_USERS = set(Development.DEV_USERS)
    DEMONS = set(Development.DEMONS)
    WOLVES = set(Development.WOLVES)
    TIGERS = set(Development.TIGERS)
    EVENT_LOGS = Development.EVENT_LOGS
    WEBHOOK = Development.WEBHOOK
    URL = Development.URL
    PORT = Development.PORT
    CERT_PATH = Development.CERT_PATH
    API_ID = Development.API_ID
    API_HASH = Development.API_HASH
    DB_URI = Development.DB_URI
    DONATION_LINK = Development.DONATION_LINK
    LOAD = Development.LOAD
    NO_LOAD = Development.NO_LOAD
    DEL_CMDS = Development.DEL_CMDS
    STRICT_GBAN = Development.STRICT_GBAN
    WORKERS = Development.WORKERS
    BAN_STICKER = Development.BAN_STICKER
    ALLOW_EXCL = Development.ALLOW_EXCL
    CASH_API_KEY = Development.CASH_API_KEY
    TIME_API_KEY = Development.TIME_API_KEY
    AI_API_KEY = Development.AI_API_KEY
    WALL_API = Development.WALL_API
    SUPPORT_CHAT = Development.SUPPORT_CHAT
    SPAMWATCH_SUPPORT_CHAT = Development.SPAMWATCH_SUPPORT_CHAT
    SPAMWATCH_API = Development.SPAMWATCH_API
    BL_CHATS = set(Development.BL_CHATS)

# === Shared Templates ===
PM_START_TEMPLATE = """
Hey hi {first_name}, I'm {bot_name}!
I am an Anime themed group management bot.
Built by weebs for weebs, I specialize in managing anime eccentric communities!
"""

HELP_TEMPLATE = """
Hey there! My name is *{bot_name}*.
I'm a Hero For Fun and help admins manage their groups with One Punch! Have a look at the following for a>
the things I can help you with.

*Main* commands available:
 • /help: PM's you this message.
 • /help <module name>: PM's you info about that module.
 • /donate: information on how to donate!
 • /settings:
   • in PM: will send you your settings for all supported modules.
   • in a group: will redirect you to pm, with all that chat's settings.

{excl_note}
And the following:
"""

SAITAMA_IMG = "https://telegra.ph/file/46e6d9dfcb3eb9eae95d9.jpg"

DONATE_STRING = """Heya, glad to hear you want to donate!
You can support the project via [Paypal](ko-fi.com/sawada) or by contacting @Sawada.
Supporting isn’t always financial — dev contributions welcome at @OnePunchDev."""

# === Shared Data Containers ===
IMPORTED = {}
MIGRATEABLE = []
HELPABLE = {}
STATS = []
USER_INFO = []
DATA_IMPORT = []
DATA_EXPORT = []
CHAT_SETTINGS = {}
USER_SETTINGS = {}

from telegram.ext import ApplicationBuilder
from telethon import TelegramClient

# --- PTB setup ---
application = ApplicationBuilder().token(TOKEN).build()
dispatcher = application  # for compatibility with older modules

# --- Telethon setup ---
telethn = TelegramClient("anon", API_ID, API_HASH)

# Legacy fallback only if you're using updater — usually not needed in PTB v20+
updater = None


# Dummy app object to avoid import error

from pyrogram import Client
app = Client("HinaBot", api_id=123456, api_hash="your_hash", bot_token="your_token")
