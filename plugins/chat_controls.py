"""
Chat-content controls: lock/unlock message types (stickers, gifs, links,
forwards, media, polls, games), and a lightweight anti-flood filter.
Enforcement happens in the `on_message` guard, which runs for every
incoming group message and deletes/handles violations before other
plugins see them (Pyrogram groups=-1 so this runs first).
"""
import time
from collections import defaultdict, deque

from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import Message

from bot.database import get_locks, get_chat_settings
from bot.utils import is_admin, mention

LOCK_NAMES = ["stickers", "gifs", "links", "forward", "media", "polls", "games", "inline"]

# per-chat, per-user recent message timestamps for flood detection
_flood_tracker: dict[tuple[int, int], deque] = defaultdict(lambda: deque(maxlen=30))


def _violates_lock(message: Message, locks: dict) -> str | None:
    if locks.get("stickers") and message.sticker:
        return "stickers"
    if locks.get("gifs") and message.animation:
        return "gifs"
    if locks.get("forward") and (message.forward_date or message.forward_from or message.forward_from_chat):
        return "forward"
    if locks.get("polls") and message.poll:
        return "polls"
    if locks.get("games") and message.game:
        return "games"
    if locks.get("media") and (message.photo or message.video or message.document or message.audio):
        return "media"
    if locks.get("links") and message.text:
        entities = message.entities or []
        for e in entities:
            if e.type.name in ("URL", "TEXT_LINK"):
                return "links"
    return None


def register(app: Client):

    @app.on_message(filters.command("lock") & filters.group)
    async def lock_cmd(client: Client, message: Message):
        from bot.database import set_lock
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        args = message.text.split()
        if len(args) < 2 or args[1].lower() not in LOCK_NAMES:
            return await message.reply_text(
                f"Usage: `/lock <type>`\nTypes: {', '.join(LOCK_NAMES)}"
            )
        lock_type = args[1].lower()
        await set_lock(message.chat.id, lock_type, True)
        await message.reply_text(f"🔒 Locked **{lock_type}** in this chat.")

    @app.on_message(filters.command("unlock") & filters.group)
    async def unlock_cmd(client: Client, message: Message):
        from bot.database import set_lock
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        args = message.text.split()
        if len(args) < 2 or args[1].lower() not in LOCK_NAMES:
            return await message.reply_text(
                f"Usage: `/unlock <type>`\nTypes: {', '.join(LOCK_NAMES)}"
            )
        lock_type = args[1].lower()
        await set_lock(message.chat.id, lock_type, False)
        await message.reply_text(f"🔓 Unlocked **{lock_type}** in this chat.")

    @app.on_message(filters.command("locks") & filters.group)
    async def locks_status_cmd(client: Client, message: Message):
        locks = await get_locks(message.chat.id)
        lines = [f"{'🔒' if locks.get(k) else '🔓'} {k}" for k in LOCK_NAMES]
        await message.reply_text("**Current locks:**\n" + "\n".join(lines))

    @app.on_message(filters.command("setflood") & filters.group)
    async def setflood_cmd(client: Client, message: Message):
        from bot.database import update_chat_settings
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        args = message.text.split()
        if len(args) < 2 or not args[1].isdigit():
            return await message.reply_text("Usage: `/setflood <count>` (0 to disable)")
        count = int(args[1])
        await update_chat_settings(message.chat.id, {"flood_limit": count})
        await message.reply_text(f"Flood limit set to {count} messages." if count else "Flood control disabled.")

    # Content-lock + flood enforcement, runs before other handlers.
    @app.on_message(filters.group & ~filters.service, group=-1)
    async def enforcement_guard(client: Client, message: Message):
        if not message.from_user:
            return
        if await is_admin(client, message.chat.id, message.from_user.id):
            return  # admins bypass locks & flood

        settings = await get_chat_settings(message.chat.id)
        locks = settings.get("locks", {})

        violated = _violates_lock(message, locks)
        if violated:
            try:
                await message.delete()
            except RPCError:
                pass
            return  # stop further processing of this message

        # --- flood check ---
        limit = settings.get("flood_limit", 0)
        if limit and limit > 0:
            key = (message.chat.id, message.from_user.id)
            now = time.time()
            dq = _flood_tracker[key]
            dq.append(now)
            recent = [t for t in dq if now - t <= 8]
            if len(recent) >= limit:
                try:
                    from pyrogram.types import ChatPermissions
                    await client.restrict_chat_member(
                        message.chat.id, message.from_user.id, ChatPermissions()
                    )
                    await message.reply_text(
                        f"🚨 {mention(message.from_user)} was muted for flooding."
                    )
                except RPCError:
                    pass
                dq.clear()
