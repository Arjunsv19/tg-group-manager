"""
Voice/Video chat controls.

IMPORTANT: Telegram's Bot API cannot join or manage group calls. All VC
control here is performed by the *assistant* user account (a normal
Telegram account logged in via SESSION_STRING, joined via PyTgCalls),
which must itself be a member (ideally admin) of the target chat.

Commands (bot side, admins only):
  /vcjoin           - assistant joins the current voice chat
  /vcleave          - assistant leaves the voice chat
  /vcmute [reply]   - server-mutes a participant in the group call
  /vcunmute [reply] - server-unmutes a participant
  /vcmuteall        - mutes everyone except admins
  /vckick [reply]   - removes a participant from the voice chat
  /vcban [reply]    - bans the user from the group AND removes them from VC

These use raw MTProto (phone.editGroupCallParticipant) via the assistant
client, since that's the only way to control *other users'* mute state.
"""
from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.raw import functions, types as raw_types
from pyrogram.types import Message

from bot.utils import is_admin, extract_user_and_reason, mention


async def _get_input_group_call(assistant: Client, chat_id: int):
    """Resolve the InputGroupCall for a chat's active voice chat, if any."""
    peer = await assistant.resolve_peer(chat_id)
    if isinstance(peer, raw_types.InputPeerChannel):
        full = await assistant.invoke(functions.channels.GetFullChannel(channel=raw_types.InputChannel(
            channel_id=peer.channel_id, access_hash=peer.access_hash
        )))
        call = full.full_chat.call
    elif isinstance(peer, raw_types.InputPeerChat):
        full = await assistant.invoke(functions.messages.GetFullChat(chat_id=peer.chat_id))
        call = full.full_chat.call
    else:
        return None
    if not call:
        return None
    return raw_types.InputGroupCall(id=call.id, access_hash=call.access_hash)


async def _edit_participant(assistant: Client, chat_id: int, user_id: int, *, muted=None, video_stopped=None):
    call = await _get_input_group_call(assistant, chat_id)
    if not call:
        return False, "There's no active voice chat in this group."
    try:
        target_peer = await assistant.resolve_peer(user_id)
    except RPCError:
        return False, "I couldn't resolve that user (they may need to message the group first)."

    kwargs = {}
    if muted is not None:
        kwargs["muted"] = muted
    if video_stopped is not None:
        kwargs["video_stopped"] = video_stopped

    try:
        await assistant.invoke(
            functions.phone.EditGroupCallParticipant(
                call=call,
                participant=target_peer,
                **kwargs,
            )
        )
    except RPCError as e:
        return False, f"Failed: {e}"
    return True, None


def register(app: Client, assistant: Client | None):

    def require_assistant(func):
        async def wrapper(client, message: Message):
            if assistant is None:
                return await message.reply_text(
                    "Voice/video chat controls are not configured. Set SESSION_STRING to enable them."
                )
            return await func(client, message)
        wrapper.__name__ = func.__name__
        return wrapper

    @app.on_message(filters.command("vcjoin") & filters.group)
    @require_assistant
    async def vcjoin_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        try:
            from pytgcalls import PyTgCalls
            from pytgcalls.types import MediaStream
        except ImportError:
            return await message.reply_text("py-tgcalls is not installed.")

        call_client: PyTgCalls = client.pytgcalls  # attached in main.py
        try:
            await call_client.play(
                message.chat.id,
                MediaStream(
                    "https://github.com/eyMarv/GitFiles/raw/refs/heads/main/example.mp3",
                ),
            )
        except Exception as e:
            return await message.reply_text(f"Couldn't join voice chat: {e}")
        await message.reply_text("🎙️ Joined the voice chat.")

    @app.on_message(filters.command("vcleave") & filters.group)
    @require_assistant
    async def vcleave_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        call_client = client.pytgcalls
        try:
            await call_client.leave_call(message.chat.id)
        except Exception as e:
            return await message.reply_text(f"Couldn't leave voice chat: {e}")
        await message.reply_text("👋 Left the voice chat.")

    @app.on_message(filters.command("vcmute") & filters.group)
    @require_assistant
    async def vcmute_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user in the voice chat to mute them.")
        ok, err = await _edit_participant(assistant, message.chat.id, user_id, muted=True)
        if not ok:
            return await message.reply_text(err)
        await message.reply_text(f"🔇 {mention(user)} muted in voice chat.")

    @app.on_message(filters.command("vcunmute") & filters.group)
    @require_assistant
    async def vcunmute_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user in the voice chat to unmute them.")
        ok, err = await _edit_participant(assistant, message.chat.id, user_id, muted=False)
        if not ok:
            return await message.reply_text(err)
        await message.reply_text(f"🔊 {mention(user)} unmuted in voice chat.")

    @app.on_message(filters.command("vcstopvideo") & filters.group)
    @require_assistant
    async def vcstopvideo_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user to stop their video.")
        ok, err = await _edit_participant(assistant, message.chat.id, user_id, video_stopped=True)
        if not ok:
            return await message.reply_text(err)
        await message.reply_text(f"📷 Stopped video for {mention(user)}.")

    @app.on_message(filters.command("vckick") & filters.group)
    @require_assistant
    async def vckick_cmd(client: Client, message: Message):
        """Removing a participant from a call isn't directly exposed; the reliable
        approach is a short kick from the chat (ban+unban), which also drops them
        from any active call. Use /vcban if you want it permanent."""
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, _ = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user to remove them from the voice chat.")
        try:
            await client.ban_chat_member(message.chat.id, user_id)
            await client.unban_chat_member(message.chat.id, user_id)
        except RPCError as e:
            return await message.reply_text(f"Failed: {e}")
        await message.reply_text(f"👢 {mention(user)} removed from voice chat and chat.")

    @app.on_message(filters.command("vcban") & filters.group)
    @require_assistant
    async def vcban_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        user_id, user, reason = await extract_user_and_reason(client, message)
        if not user_id:
            return await message.reply_text("Reply to a user to ban them (also removes from VC).")
        try:
            await client.ban_chat_member(message.chat.id, user_id)
        except RPCError as e:
            return await message.reply_text(f"Failed: {e}")
        text = f"🔨🎙️ {mention(user)} banned (removed from group & voice chat)."
        if reason:
            text += f"\nReason: {reason}"
        await message.reply_text(text)

    @app.on_message(filters.command("vcmuteall") & filters.group)
    @require_assistant
    async def vcmuteall_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        call = await _get_input_group_call(assistant, message.chat.id)
        if not call:
            return await message.reply_text("There's no active voice chat in this group.")
        try:
            await assistant.invoke(
                functions.phone.ToggleGroupCallSettings(
                    call=call,
                    join_muted=True,
                )
            )
        except RPCError as e:
            return await message.reply_text(f"Failed: {e}")
        await message.reply_text("🔇 New participants will now join muted.")
