"""
Handling for "masked" senders — messages posted via anonymous group admin
identity, or via a linked channel pretending to be a user. Telegram lets
admins send messages as the group itself (sender_chat == the group), or a
linked channel can post as itself. This module lets real admins act on
those senders even though there's no normal `from_user`.

Commands:
  /banchannel (reply to a message sent by a channel/anon identity)
      -> blocks that channel from sending in the group (SetBotBroadcastDefaultAdmin
         isn't applicable; we use ban_chat_sender_chat).
  /unbanchannel <channel_id>
  /whois (reply) - reveals whether a message was sent anonymously and by which
      underlying chat, when Telegram exposes it (only to real admins).
"""
from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import Message

from bot.utils import is_admin


def register(app: Client):

    @app.on_message(filters.command("banchannel") & filters.group)
    async def banchannel_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")

        target = None
        if message.reply_to_message and message.reply_to_message.sender_chat:
            target = message.reply_to_message.sender_chat
        else:
            args = message.text.split()
            if len(args) > 1 and args[1].lstrip("-").isdigit():
                target_id = int(args[1])
                target = type("Obj", (), {"id": target_id, "title": str(target_id)})

        if not target:
            return await message.reply_text(
                "Reply to a message sent by a channel/anonymous admin, or give a channel id."
            )
        try:
            await client.ban_chat_sender_chat(message.chat.id, target.id)
        except RPCError as e:
            return await message.reply_text(f"Failed: {e}")
        await message.reply_text(f"🚫 Blocked channel **{getattr(target, 'title', target.id)}** from posting here.")

    @app.on_message(filters.command("unbanchannel") & filters.group)
    async def unbanchannel_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        args = message.text.split()
        if len(args) < 2 or not args[1].lstrip("-").isdigit():
            return await message.reply_text("Usage: `/unbanchannel <channel_id>`")
        try:
            await client.unban_chat_sender_chat(message.chat.id, int(args[1]))
        except RPCError as e:
            return await message.reply_text(f"Failed: {e}")
        await message.reply_text("✅ Channel unbanned.")

    @app.on_message(filters.command("whois") & filters.group)
    async def whois_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        target_msg = message.reply_to_message
        if not target_msg:
            return await message.reply_text("Reply to a message to inspect its sender.")
        if target_msg.sender_chat:
            kind = "this group (anonymous admin)" if target_msg.sender_chat.id == message.chat.id else "a linked channel"
            return await message.reply_text(
                f"This message was sent as **{target_msg.sender_chat.title}** ({kind}), id `{target_msg.sender_chat.id}`."
            )
        if target_msg.from_user:
            u = target_msg.from_user
            return await message.reply_text(
                f"Sent by [{u.first_name}](tg://user?id={u.id}) — id `{u.id}`"
                + (f" — @{u.username}" if u.username else "")
            )
        await message.reply_text("Couldn't determine the sender.")
