# Hina/config.py - comprehensive version (rewritten line-by-line)
"""
Comprehensive configuration module for Hina.
This module prepares environment variables, logging, exports a PTB Application
named `app` and a Telethon client `telethn` for other modules to import.
It also exposes a handful of helper utilities used across the project.
This file intentionally creates `app` at import-time because many legacy
modules in the Hina project expect `from Hina.config import app` to work.
"""
from __future__ import annotations

import os
import sys
import time
import logging
from typing import Iterable, Set, Optional

# External libs (Telethon & python-telegram-bot)
from telethon import TelegramClient
from telegram.ext import ApplicationBuilder

# --- Version guard ---
MIN_PY_VERSION = (3, 10)
if sys.version_info < MIN_PY_VERSION:
    raise RuntimeError(f"Python {MIN_PY_VERSION[0]}.{MIN_PY_VERSION[1]}+ is required.")

# --- Basic timing ---
StartTime: float = time.time()

# --- Logging setup ---
LOG_FILE = os.environ.get("HINA_LOGFILE", "hina.log")
LOG_LEVEL = os.environ.get("HINA_LOGLEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
LOGGER = logging.getLogger("HinaConfig")
LOGGER.debug("Logger configured. Level=%s File=%s", LOG_LEVEL, LOG_FILE)

# --- Environment helpers ---
def _parse_int(value: Optional[str], default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _parse_int_set(s: Optional[str]) -> Set[int]:
    if not s:
        return set()
    try:
        parts = [p.strip() for p in s.strip().split() if p.strip()]
        return set(int(x) for x in parts)
    except Exception:
        LOGGER.exception("Failed to parse int set from: %s", s)
        return set()

def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")

# --- Primary configuration values (sane defaults for dev) ---
TOKEN: str = os.environ.get("TOKEN", "REPLACE_WITH_YOUR_TOKEN")
OWNER_ID: int = _parse_int(os.environ.get("OWNER_ID"), 0)
API_ID: Optional[str] = os.environ.get("API_ID") or None
API_HASH: Optional[str] = os.environ.get("API_HASH") or None
WEBHOOK: bool = _parse_bool(os.environ.get("WEBHOOK"), False)
URL: str = os.environ.get("URL", "")
PORT: int = _parse_int(os.environ.get("PORT"), 5000)
CERT_PATH: Optional[str] = os.environ.get("CERT_PATH") or None
DONATION_LINK: str = os.environ.get("DONATION_LINK", "")
SUPPORT_CHAT: str = os.environ.get("SUPPORT_CHAT", "")

# Feature toggles & role lists
ALLOW_EXCL: bool = _parse_bool(os.environ.get("ALLOW_EXCL", "true"), True)
DRAGONS: Set[int] = _parse_int_set(os.environ.get("DRAGONS"))
DEV_USERS: Set[int] = _parse_int_set(os.environ.get("DEV_USERS"))
DEMONS: Set[int] = _parse_int_set(os.environ.get("DEMONS"))
TIGERS: Set[int] = _parse_int_set(os.environ.get("TIGERS"))
WOLVES: Set[int] = _parse_int_set(os.environ.get("WOLVES"))

# --- Shared containers expected by modules ---
IMPORTED = {}          # name -> module
MIGRATEABLE = []       # modules with __migrate__
HELPABLE = {}          # modules with __help__
STATS = []             # modules with __stats__
USER_INFO = []         # modules with __user_info__
DATA_IMPORT = []       # modules with __import_data__
DATA_EXPORT = []       # modules with __export_data__
CHAT_SETTINGS = {}     # module -> settings provider
USER_SETTINGS = {}     # module -> user settings provider

# --- Telethon client ---
try:
    telethn = TelegramClient("hina_session", API_ID, API_HASH)
    LOGGER.debug("Telethon client object created.")
except Exception:
    LOGGER.exception("Failed to instantiate Telethon client (API_ID/API_HASH may be missing).")
    try:
        telethn = TelegramClient("hina_session", API_ID or None, API_HASH or None)
    except Exception:
        LOGGER.exception("Second attempt failed. telethn set to None.")
        telethn = None

# --- Build PTB Application at import time for legacy modules ---
if TOKEN == "REPLACE_WITH_YOUR_TOKEN":
    LOGGER.warning("TOKEN is not set. Create app but it cannot run until TOKEN is provided.")

try:
    app = ApplicationBuilder().token(TOKEN).build()
    LOGGER.info("PTB Application built and exported as `app`.")
except Exception as e:  # pragma: no cover - runtime environment specific
    LOGGER.exception("Failed building PTB Application: %s", e)
    app = None

# --- Small compatibility helper ---
def set_app_bot(bot) -> None:
    """
    Attach a compatible `bot` attribute to exported `app` for modules that
    check `app.bot` before the application fully starts.
    """
    global app
    if app is None:
        LOGGER.debug("set_app_bot called but app is None; skipping.")
        return
    try:
        # Store under a private attribute to avoid conflicting with internals.
        setattr(app, "_bot_compat", bot)
        LOGGER.debug("set_app_bot: bot attached to app._bot_compat")
    except Exception:
        LOGGER.exception("Failed to attach bot to app compatibility slot.")

# --- Common templates & strings used across modules ---
PM_START_TEMPLATE = (
    "Hey {0},\n"
    "I'm {1} — an Anime themed management bot. Send /help in PM for commands."
)
HELP_TEMPLATE = "Use /help in PM to list modules. Use /help <module> in PM for module help."
SAITAMA_IMG = "https://telegra.ph/file/46e6d9dfcb3eb9eae95d9.jpg"
DONATE_STRING = (
    "Thanks for thinking of donating!\n"
    "You can donate via the project links or contact the owner."
)

# --- Utility: readable uptime formatting used by other modules ---
def get_readable_time(seconds: int) -> str:
    """
    Return a compact readable time string like '2days,3h:12m:45s' for a given
    number of seconds. Function exists in config for modules to reuse.
    """
    seconds = int(seconds)
    parts = []
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        parts.append(f"{days}days")
    if hours or parts:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return ",".join(parts) if days else ":".join(parts)

# --- Export list ---
__all__ = [
    "TOKEN", "OWNER_ID", "API_ID", "API_HASH", "WEBHOOK", "URL", "PORT", "CERT_PATH",
    "DONATION_LINK", "SUPPORT_CHAT", "ALLOW_EXCL", "DRAGONS", "DEV_USERS", "DEMONS",
    "WOLVES", "TIGERS", "IMPORTED", "MIGRATEABLE", "HELPABLE", "STATS", "USER_INFO",
    "DATA_IMPORT", "DATA_EXPORT", "CHAT_SETTINGS", "USER_SETTINGS", "telethn",
    "app", "StartTime", "LOGGER", "PM_START_TEMPLATE", "HELP_TEMPLATE", "SAITAMA_IMG",
    "DONATE_STRING", "set_app_bot", "get_readable_time"
]
