"""
Shared helpers used across plugins: permission checks, extracting the
"target user" from a command (reply / @username / id), duration parsing,
and safe wrappers around Pyrogram calls that commonly fail (rights errors).
"""
import re
from datetime import datetime, timedelta

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError
from pyrogram.types import Message

from bot.config import config

TIME_RE = re.compile(r"^(\d+)([mhdw])$")
UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}


def is_owner_or_sudo(user_id: int) -> bool:
    return user_id == config.OWNER_ID or user_id in config.SUDO_USERS


async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if is_owner_or_sudo(user_id):
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
    except RPCError:
        return False
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


async def bot_is_admin(client: Client, chat_id: int) -> bool:
    me = await client.get_me()
    return await is_admin(client, chat_id, me.id)


def parse_duration(text: str):
    """Parse strings like '10m', '2h', '1d', '1w' -> timedelta, or None if invalid."""
    if not text:
        return None
    match = TIME_RE.match(text.strip().lower())
    if not match:
        return None
    value, unit = match.groups()
    return timedelta(seconds=int(value) * UNIT_SECONDS[unit])


async def extract_user_and_reason(client: Client, message: Message):
    """
    Figures out the target user and remaining text (reason/duration) from a
    command such as:
      /mute @user 1h spamming
      /mute 1h spamming          (as a reply to the user)
      (reply) /mute spamming
    Returns (user_id_or_None, user_obj_or_None, remaining_text)
    """
    args = message.text.split(None, 1)
    rest = args[1] if len(args) > 1 else ""

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        return target.id, target, rest.strip()

    if not rest:
        return None, None, ""

    parts = rest.split(None, 1)
    first = parts[0]
    remaining = parts[1] if len(parts) > 1 else ""

    user_ref = first
    if user_ref.startswith("@") or user_ref.lstrip("-").isdigit():
        try:
            user = await client.get_users(user_ref)
            return user.id, user, remaining.strip()
        except RPCError:
            return None, None, rest.strip()

    return None, None, rest.strip()


def mention(user) -> str:
    name = user.first_name or "User"
    return f"[{name}](tg://user?id={user.id})"


async def safe_send(client: Client, chat_id: int, text: str, **kwargs):
    try:
        return await client.send_message(chat_id, text, **kwargs)
    except RPCError:
        return None
