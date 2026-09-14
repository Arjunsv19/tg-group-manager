"""
Sticker-specific management, layered on top of the generic `stickers` lock
in chat_controls.py. Adds:
  /antisticker on|off  - shortcut for locking/unlocking all stickers
  /banpack (reply to a sticker)  - block a specific sticker pack
  /unbanpack <short_name>
  /packlist - list blocked packs
"""
from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import Message

from bot.database import chats_col, set_lock
from bot.utils import is_admin


async def _get_banned_packs(chat_id: int):
    doc = await chats_col.find_one({"chat_id": chat_id})
    return (doc or {}).get("banned_sticker_packs", [])


def register(app: Client):

    @app.on_message(filters.command("antisticker") & filters.group)
    async def antisticker_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        args = message.text.split()
        if len(args) < 2 or args[1].lower() not in ("on", "off"):
            return await message.reply_text("Usage: `/antisticker on|off`")
        enable = args[1].lower() == "on"
        await set_lock(message.chat.id, "stickers", enable)
        await message.reply_text(f"Stickers are now {'blocked' if enable else 'allowed'} for non-admins.")

    @app.on_message(filters.command("banpack") & filters.group)
    async def banpack_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        if not (message.reply_to_message and message.reply_to_message.sticker):
            return await message.reply_text("Reply to a sticker from the pack you want to ban.")
        set_name = message.reply_to_message.sticker.set_name
        if not set_name:
            return await message.reply_text("This sticker doesn't belong to a named pack.")
        await chats_col.update_one(
            {"chat_id": message.chat.id},
            {"$addToSet": {"banned_sticker_packs": set_name}},
            upsert=True,
        )
        await message.reply_text(f"🚫 Banned sticker pack `{set_name}`.")

    @app.on_message(filters.command("unbanpack") & filters.group)
    async def unbanpack_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply_text("Usage: `/unbanpack <short_name>`")
        await chats_col.update_one(
            {"chat_id": message.chat.id},
            {"$pull": {"banned_sticker_packs": args[1].strip()}},
        )
        await message.reply_text(f"✅ Unbanned sticker pack `{args[1].strip()}`.")

    @app.on_message(filters.command("packlist") & filters.group)
    async def packlist_cmd(client: Client, message: Message):
        packs = await _get_banned_packs(message.chat.id)
        if not packs:
            return await message.reply_text("No sticker packs are banned in this chat.")
        await message.reply_text("**Banned packs:**\n" + "\n".join(f"• `{p}`" for p in packs))

    # Enforce specific-pack bans (separate from the blanket stickers lock)
    @app.on_message(filters.group & filters.sticker, group=-1)
    async def pack_ban_guard(client: Client, message: Message):
        if not message.from_user:
            return
        if await is_admin(client, message.chat.id, message.from_user.id):
            return
        set_name = message.sticker.set_name
        if not set_name:
            return
        banned = await _get_banned_packs(message.chat.id)
        if set_name in banned:
            try:
                await message.delete()
            except RPCError:
                pass
