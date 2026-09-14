"""
General-purpose commands: start, help, ping, id, chat/user info.
"""
import time

from pyrogram import Client, filters
from pyrogram.types import Message

HELP_TEXT = """
**🤖 Group Manager — Command List**

**Moderation**
`/ban` `/unban` `/kick` `/mute [time] [reason]` `/unmute`
`/warn` `/unwarn` `/warns` `/promote` `/demote` `/pin` `/unpin` `/purge`

**Chat Controls**
`/lock <type>` `/unlock <type>` `/locks` `/setflood <n>`
Types: stickers, gifs, links, forward, media, polls, games, inline

**Stickers**
`/antisticker on|off` `/banpack` (reply) `/unbanpack <name>` `/packlist`

**Voice/Video Chat**
`/vcjoin` `/vcleave` `/vcmute` `/vcunmute` `/vcstopvideo`
`/vckick` `/vcban` `/vcmuteall`

**Anonymous/Masked Admins**
`/banchannel` (reply) `/unbanchannel <id>` `/whois` (reply)

**Filters & Notes**
`/filter <kw> <text>` `/stop <kw>` `/filters`
`/save <name> <text>` `/get <name>` or `#name` `/notes` `/clear <name>`

**Welcome**
`/welcome on|off` `/setwelcome <text>`

**Global**
`/gban` (reply) `/ungban` (owner/sudo only)

**Info**
`/ping` `/id` `/info` (reply)
"""


def register(app: Client):

    @app.on_message(filters.command("start"))
    async def start_cmd(client: Client, message: Message):
        await message.reply_text(
            "👋 Hi! I'm a full-featured group management bot.\n"
            "Add me to a group as admin and send /help to see what I can do."
        )

    @app.on_message(filters.command("help"))
    async def help_cmd(client: Client, message: Message):
        await message.reply_text(HELP_TEXT)

    @app.on_message(filters.command("ping"))
    async def ping_cmd(client: Client, message: Message):
        start = time.monotonic()
        sent = await message.reply_text("Pinging...")
        elapsed = (time.monotonic() - start) * 1000
        await sent.edit_text(f"🏓 Pong! `{elapsed:.0f} ms`")

    @app.on_message(filters.command("id"))
    async def id_cmd(client: Client, message: Message):
        lines = [f"Chat ID: `{message.chat.id}`"]
        if message.reply_to_message and message.reply_to_message.from_user:
            lines.append(f"User ID: `{message.reply_to_message.from_user.id}`")
        elif message.from_user:
            lines.append(f"Your ID: `{message.from_user.id}`")
        await message.reply_text("\n".join(lines))

    @app.on_message(filters.command("info") & filters.group)
    async def info_cmd(client: Client, message: Message):
        target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
        if not target:
            return await message.reply_text("Couldn't determine the user.")
        text = (
            f"**User Info**\n"
            f"Name: {target.first_name or ''} {target.last_name or ''}\n"
            f"ID: `{target.id}`\n"
            f"Username: @{target.username}" if target.username else f"ID: `{target.id}`"
        )
        await message.reply_text(text)
