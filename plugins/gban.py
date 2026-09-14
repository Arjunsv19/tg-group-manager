"""
Global ban system — owner/sudo only. Bans a user across every group the
bot administers, and auto-enforces on join in any group.
"""
from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import Message

from bot.database import gban_user, ungban_user, is_gbanned
from bot.utils import is_owner_or_sudo, extract_user_and_reason, mention


def register(app: Client):

    @app.on_message(filters.command("gban") & filters.private | filters.command("gban") & filters.group)
    async def gban_cmd(client: Client, message: Message):
        if not is_owner_or_sudo(message.from_user.id):
            return await message.reply_text("Only the bot owner/sudo users can use this.")
        user_id, user, reason = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to gban.")

        await gban_user(user_id, reason or "No reason given", message.from_user.id)

        banned_in = 0
        async for dialog in client.get_dialogs():
            if dialog.chat.type.name in ("GROUP", "SUPERGROUP"):
                try:
                    await client.ban_chat_member(dialog.chat.id, user_id)
                    banned_in += 1
                except RPCError:
                    continue

        await message.reply_text(
            f"🌐 Globally banned {mention(user)} in {banned_in} chat(s).\nReason: {reason or 'None'}"
        )

    @app.on_message(filters.command("ungban"))
    async def ungban_cmd(client: Client, message: Message):
        if not is_owner_or_sudo(message.from_user.id):
            return await message.reply_text("Only the bot owner/sudo users can use this.")
        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to ungban.")
        await ungban_user(user_id)

        unbanned_in = 0
        async for dialog in client.get_dialogs():
            if dialog.chat.type.name in ("GROUP", "SUPERGROUP"):
                try:
                    await client.unban_chat_member(dialog.chat.id, user_id)
                    unbanned_in += 1
                except RPCError:
                    continue

        await message.reply_text(f"✅ Un-gbanned {mention(user)} in {unbanned_in} chat(s).")

    # Enforce gban on join
    @app.on_message(filters.new_chat_members, group=-2)
    async def enforce_gban(client: Client, message: Message):
        for member in message.new_chat_members:
            if await is_gbanned(member.id):
                try:
                    await client.ban_chat_member(message.chat.id, member.id)
                    await message.reply_text(f"🌐 {mention(member)} is globally banned and was removed.")
                except RPCError:
                    pass
