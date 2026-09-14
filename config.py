"""
Central configuration, loaded from environment variables.
On Heroku these are set via `heroku config:set` or the dashboard.
Locally, a .env file (see .env.example) is loaded via python-dotenv.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default=None):
    val = os.environ.get(name, default)
    if val in (None, ""):
        return None
    return int(val)


def _list_env(name: str, default=""):
    raw = os.environ.get(name, default) or ""
    return [x.strip() for x in raw.split(",") if x.strip()]


class Config:
    API_ID = _int_env("API_ID")
    API_HASH = os.environ.get("API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    SESSION_STRING = os.environ.get("SESSION_STRING")  # assistant account, for VC control

    MONGO_DB_URI = os.environ.get("MONGO_DB_URI")
    DB_NAME = os.environ.get("DB_NAME", "tg_group_manager")

    OWNER_ID = _int_env("OWNER_ID")
    SUDO_USERS = [int(x) for x in _list_env("SUDO_USERS")]
    LOG_GROUP_ID = _int_env("LOG_GROUP_ID")

    COMMAND_PREFIXES = _list_env("COMMAND_PREFIXES", "/,!")

    # sane defaults
    FLOOD_LIMIT_DEFAULT = 10          # messages
    FLOOD_WINDOW_SECONDS = 8          # within N seconds triggers flood action
    WARN_LIMIT_DEFAULT = 3


config = Config()

REQUIRED = ["API_ID", "API_HASH", "BOT_TOKEN", "MONGO_DB_URI", "OWNER_ID"]


def validate_config():
    missing = [name for name in REQUIRED if getattr(config, name) in (None, "")]
    if missing:
        raise SystemExit(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Set them in your Heroku config vars or a local .env file."
        )
