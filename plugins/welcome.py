"""
Welcome new members / announce departures. Configurable per chat.
  /welcome on|off
  /setwelcome <text>   (supports {mention}, {first}, {chat_title})
"""
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message

from bot.database import get_chat_settings, update_chat_settings
from bot.utils import is_admin, mention


def register(app: Client):

    @app.on_message(filters.command("welcome") & filters.group)
    async def welcome_toggle_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        args = message.text.split()
        if len(args) < 2 or args[1].lower() not in ("on", "off"):
            return await message.reply_text("Usage: `/welcome on|off`")
        enable = args[1].lower() == "on"
        settings = await get_chat_settings(message.chat.id)
        welcome = settings.get("welcome", {})
        welcome["enabled"] = enable
        await update_chat_settings(message.chat.id, {"welcome": welcome})
        await message.reply_text(f"Welcome messages {'enabled' if enable else 'disabled'}.")

    @app.on_message(filters.command("setwelcome") & filters.group)
    async def set_welcome_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply_text(
                "Usage: `/setwelcome <text>`\nPlaceholders: {mention} {first} {chat_title}"
            )
        settings = await get_chat_settings(message.chat.id)
        welcome = settings.get("welcome", {})
        welcome["text"] = parts[1]
        await update_chat_settings(message.chat.id, {"welcome": welcome})
        await message.reply_text("✅ Welcome message updated.")

    @app.on_message(filters.new_chat_members)
    async def on_new_member(client: Client, message: Message):
        settings = await get_chat_settings(message.chat.id)
        welcome = settings.get("welcome", {})
        if not welcome.get("enabled"):
            return
        for member in message.new_chat_members:
            if member.is_self:
                continue
            text = welcome.get("text", "Welcome {mention}!").format(
                mention=mention(member),
                first=member.first_name,
                chat_title=message.chat.title,
            )
            await message.reply_text(text)
