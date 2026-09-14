"""
Core moderation: ban, unban, kick, mute, unmute, warn, promote, demote.
All commands require the invoking user to be an admin, and the bot itself
must be an admin with the relevant rights.
"""
import time
from datetime import datetime, timezone

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError
from pyrogram.types import ChatPermissions, Message

from bot.database import add_warn, reset_warns, get_warns, get_chat_settings
from bot.utils import is_admin, bot_is_admin, extract_user_and_reason, parse_duration, mention

NO_PERMS = ChatPermissions()
FULL_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_other_messages=True,
    can_send_polls=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)


def register(app: Client):

    @app.on_message(filters.command("ban") & filters.group)
    async def ban_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        if not await bot_is_admin(client, message.chat.id):
            return await message.reply_text("I need admin rights to ban users.")

        user_id, user, reason = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to ban.")
        if await is_admin(client, message.chat.id, user_id):
            return await message.reply_text("I can't ban an admin.")

        try:
            await client.ban_chat_member(message.chat.id, user_id)
        except RPCError as e:
            return await message.reply_text(f"Failed to ban: {e}")

        text = f"🔨 **Banned:** {mention(user)}\n**By:** {mention(message.from_user)}"
        if reason:
            text += f"\n**Reason:** {reason}"
        await message.reply_text(text)

    @app.on_message(filters.command("unban") & filters.group)
    async def unban_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to or specify a user to unban.")
        try:
            await client.unban_chat_member(message.chat.id, user_id)
        except RPCError as e:
            return await message.reply_text(f"Failed to unban: {e}")
        await message.reply_text(f"✅ Unbanned {mention(user)}")

    @app.on_message(filters.command("kick") & filters.group)
    async def kick_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        if not await bot_is_admin(client, message.chat.id):
            return await message.reply_text("I need admin rights to kick users.")

        user_id, user, reason = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to kick.")
        if await is_admin(client, message.chat.id, user_id):
            return await message.reply_text("I can't kick an admin.")

        try:
            await client.ban_chat_member(message.chat.id, user_id)
            await client.unban_chat_member(message.chat.id, user_id)  # ban+unban = kick
        except RPCError as e:
            return await message.reply_text(f"Failed to kick: {e}")

        text = f"👢 **Kicked:** {mention(user)}\n**By:** {mention(message.from_user)}"
        if reason:
            text += f"\n**Reason:** {reason}"
        await message.reply_text(text)

    @app.on_message(filters.command(["mute", "vcmute_user"]) & filters.group)
    async def mute_cmd(client: Client, message: Message):
        """Text-chat mute (restrict sending messages). For VC muting see voicechat.py"""
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        if not await bot_is_admin(client, message.chat.id):
            return await message.reply_text("I need admin rights to restrict users.")

        user_id, user, rest = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to mute.")
        if await is_admin(client, message.chat.id, user_id):
            return await message.reply_text("I can't mute an admin.")

        parts = rest.split(None, 1) if rest else []
        duration = parse_duration(parts[0]) if parts else None
        reason = parts[1] if duration and len(parts) > 1 else (rest if not duration else "")

        until = None
        if duration:
            until = datetime.now(timezone.utc) + duration

        try:
            await client.restrict_chat_member(
                message.chat.id, user_id, NO_PERMS,
                until_date=until,
            )
        except RPCError as e:
            return await message.reply_text(f"Failed to mute: {e}")

        text = f"🔇 **Muted:** {mention(user)}\n**By:** {mention(message.from_user)}"
        if duration:
            text += f"\n**Duration:** {parts[0]}"
        if reason:
            text += f"\n**Reason:** {reason}"
        await message.reply_text(text)

    @app.on_message(filters.command("unmute") & filters.group)
    async def unmute_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")

        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to unmute.")

        try:
            await client.restrict_chat_member(message.chat.id, user_id, FULL_PERMS)
        except RPCError as e:
            return await message.reply_text(f"Failed to unmute: {e}")
        await message.reply_text(f"🔊 Unmuted {mention(user)}")

    @app.on_message(filters.command("warn") & filters.group)
    async def warn_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")

        user_id, user, reason = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to warn.")
        if await is_admin(client, message.chat.id, user_id):
            return await message.reply_text("I can't warn an admin.")

        count = await add_warn(message.chat.id, user_id, reason or "No reason given")
        settings = await get_chat_settings(message.chat.id)
        limit = settings.get("warn_limit", 3)

        if count >= limit:
            mode = settings.get("warn_mode", "mute")
            await reset_warns(message.chat.id, user_id)
            try:
                if mode == "ban":
                    await client.ban_chat_member(message.chat.id, user_id)
                    action = "banned"
                elif mode == "kick":
                    await client.ban_chat_member(message.chat.id, user_id)
                    await client.unban_chat_member(message.chat.id, user_id)
                    action = "kicked"
                else:
                    await client.restrict_chat_member(message.chat.id, user_id, NO_PERMS)
                    action = "muted"
            except RPCError as e:
                return await message.reply_text(f"Warn limit reached but action failed: {e}")
            return await message.reply_text(
                f"⚠️ {mention(user)} reached {limit} warns and has been **{action}**."
            )

        text = f"⚠️ **Warned:** {mention(user)} ({count}/{limit})"
        if reason:
            text += f"\n**Reason:** {reason}"
        await message.reply_text(text)

    @app.on_message(filters.command(["unwarn", "resetwarn"]) & filters.group)
    async def unwarn_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id.")
        await reset_warns(message.chat.id, user_id)
        await message.reply_text(f"✅ Warns cleared for {mention(user)}")

    @app.on_message(filters.command("warns") & filters.group)
    async def warns_cmd(client: Client, message: Message):
        user_id, user, _ = await extract_user_and_reason(client, message)
        target = user_id or message.from_user.id
        data = await get_warns(message.chat.id, target)
        if data["count"] == 0:
            return await message.reply_text("No warns on record.")
        reasons = "\n".join(f"• {r}" for r in data["reasons"])
        await message.reply_text(f"**Warns:** {data['count']}\n{reasons}")

    @app.on_message(filters.command("promote") & filters.group)
    async def promote_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, title = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to promote.")
        try:
            await client.promote_chat_member(
                message.chat.id, user_id,
                can_manage_chat=True, can_delete_messages=True,
                can_restrict_members=True, can_invite_users=True,
                can_pin_messages=True, can_manage_video_chats=True,
            )
            if title:
                try:
                    await client.set_administrator_title(message.chat.id, user_id, title[:16])
                except RPCError:
                    pass
        except RPCError as e:
            return await message.reply_text(f"Failed to promote: {e}")
        await message.reply_text(f"⬆️ Promoted {mention(user)}")

    @app.on_message(filters.command("demote") & filters.group)
    async def demote_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user or give a username/id to demote.")
        try:
            await client.promote_chat_member(
                message.chat.id, user_id,
                can_manage_chat=False, can_delete_messages=False,
                can_restrict_members=False, can_invite_users=False,
                can_pin_messages=False, can_manage_video_chats=False,
            )
        except RPCError as e:
            return await message.reply_text(f"Failed to demote: {e}")
        await message.reply_text(f"⬇️ Demoted {mention(user)}")

    @app.on_message(filters.command("pin") & filters.group)
    async def pin_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        if not message.reply_to_message:
            return await message.reply_text("Reply to the message you want to pin.")
        notify = "loud" in (message.text or "").lower()
        try:
            await client.pin_chat_message(
                message.chat.id, message.reply_to_message.id, disable_notification=not notify
            )
        except RPCError as e:
            return await message.reply_text(f"Failed to pin: {e}")
        await message.reply_text("📌 Pinned.")

    @app.on_message(filters.command("unpin") & filters.group)
    async def unpin_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        try:
            if message.reply_to_message:
                await client.unpin_chat_message(message.chat.id, message.reply_to_message.id)
            else:
                await client.unpin_all_chat_messages(message.chat.id)
        except RPCError as e:
            return await message.reply_text(f"Failed to unpin: {e}")
        await message.reply_text("📌 Unpinned.")

    @app.on_message(filters.command("purge") & filters.group)
    async def purge_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        if not message.reply_to_message:
            return await message.reply_text("Reply to the message to start purging from.")
        ids = list(range(message.reply_to_message.id, message.id + 1))
        try:
            await client.delete_messages(message.chat.id, ids)
        except RPCError as e:
            await message.reply_text(f"Failed to purge: {e}")
