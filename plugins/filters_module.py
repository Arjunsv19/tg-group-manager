"""
Custom keyword auto-responses ("filters") and saved notes.
  /filter <keyword> <reply text>
  /filters
  /stop <keyword>
  /save <name> <text>       (reply to save media as a note too)
  /get <name> | #<name>
  /notes
  /clear <name>
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot.database import (
    add_filter, remove_filter, get_filters, get_filter,
    notes_col,
)
from bot.utils import is_admin


def register(app: Client):

    @app.on_message(filters.command("filter") & filters.group)
    async def add_filter_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        parts = message.text.split(None, 2)
        if len(parts) < 3:
            return await message.reply_text("Usage: `/filter <keyword> <reply text>`")
        _, keyword, reply_text = parts
        await add_filter(message.chat.id, keyword, reply_text)
        await message.reply_text(f"✅ Filter saved for `{keyword.lower()}`.")

    @app.on_message(filters.command("stop") & filters.group)
    async def remove_filter_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply_text("Usage: `/stop <keyword>`")
        await remove_filter(message.chat.id, parts[1])
        await message.reply_text(f"🗑️ Filter removed for `{parts[1].lower()}`.")

    @app.on_message(filters.command("filters") & filters.group)
    async def list_filters_cmd(client: Client, message: Message):
        items = await get_filters(message.chat.id)
        if not items:
            return await message.reply_text("No filters set in this chat.")
        text = "**Filters:**\n" + "\n".join(f"• `{f['keyword']}`" for f in items)
        await message.reply_text(text)

    @app.on_message(filters.text & filters.group & ~filters.command(["filter", "stop", "filters"]))
    async def trigger_filter(client: Client, message: Message):
        if not message.text:
            return
        text = message.text.lower()
        items = await get_filters(message.chat.id)
        for f in items:
            if f["keyword"] in text:
                await message.reply_text(f["reply"])
                return

    @app.on_message(filters.command("save") & filters.group)
    async def save_note_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        parts = message.text.split(None, 2)
        if len(parts) < 2:
            return await message.reply_text("Usage: `/save <name> <text>` (or reply to media)")
        name = parts[1].lower()
        content = parts[2] if len(parts) > 2 else ""
        file_id, file_type = None, None
        if message.reply_to_message:
            r = message.reply_to_message
            if r.photo:
                file_id, file_type = r.photo.file_id, "photo"
            elif r.document:
                file_id, file_type = r.document.file_id, "document"
            elif r.video:
                file_id, file_type = r.video.file_id, "video"
            elif r.sticker:
                file_id, file_type = r.sticker.file_id, "sticker"
            if not content and r.caption:
                content = r.caption

        await notes_col.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"text": content, "file_id": file_id, "file_type": file_type}},
            upsert=True,
        )
        await message.reply_text(f"💾 Note `{name}` saved.")

    @app.on_message(filters.command("get") & filters.group)
    async def get_note_cmd(client: Client, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply_text("Usage: `/get <name>`")
        await _send_note(client, message, parts[1].lower())

    @app.on_message(filters.regex(r"^#\w+") & filters.group)
    async def get_note_hash(client: Client, message: Message):
        name = message.text[1:].split()[0].lower()
        await _send_note(client, message, name, silent_if_missing=True)

    async def _send_note(client, message, name, silent_if_missing=False):
        doc = await notes_col.find_one({"chat_id": message.chat.id, "name": name})
        if not doc:
            if not silent_if_missing:
                await message.reply_text("No such note.")
            return
        if doc.get("file_id"):
            sender = {
                "photo": client.send_photo,
                "document": client.send_document,
                "video": client.send_video,
                "sticker": client.send_sticker,
            }.get(doc["file_type"], client.send_document)
            kwargs = {"caption": doc.get("text")} if doc["file_type"] != "sticker" else {}
            await sender(message.chat.id, doc["file_id"], **kwargs)
        else:
            await message.reply_text(doc.get("text", ""))

    @app.on_message(filters.command("notes") & filters.group)
    async def list_notes_cmd(client: Client, message: Message):
        cursor = notes_col.find({"chat_id": message.chat.id})
        names = [doc["name"] async for doc in cursor]
        if not names:
            return await message.reply_text("No notes saved in this chat.")
        await message.reply_text("**Notes:**\n" + "\n".join(f"• `#{n}`" for n in names))

    @app.on_message(filters.command("clear") & filters.group)
    async def clear_note_cmd(client: Client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("You need to be an admin to use this.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply_text("Usage: `/clear <name>`")
        await notes_col.delete_one({"chat_id": message.chat.id, "name": parts[1].lower()})
        await message.reply_text("🗑️ Note deleted.")
