"""
Registers every plugin's handlers onto the bot Client.
Voice-chat plugin additionally needs the assistant client (may be None if
SESSION_STRING isn't configured — VC commands will politely no-op).
"""
from pyrogram import Client

from . import admin
from . import chat_controls
from . import stickers
from . import anon_admin
from . import filters_module
from . import welcome
from . import gban
from . import misc
from . import voicechat


def register_all(app: Client, assistant: Client | None):
    admin.register(app)
    chat_controls.register(app)
    stickers.register(app)
    anon_admin.register(app)
    filters_module.register(app)
    welcome.register(app)
    gban.register(app)
    misc.register(app)
    voicechat.register(app, assistant)
