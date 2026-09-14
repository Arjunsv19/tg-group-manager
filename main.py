"""
Entry point.

Starts:
  - `app`: the Bot API client (python-telegram admin commands)
  - `assistant`: optional MTProto user client (for voice/video chat control),
     only started if SESSION_STRING is configured.
  - PyTgCalls bound to the assistant, for joining/leaving voice chats.

Run locally:  python3 main.py
On Heroku:    handled by the Procfile (`worker: python3 main.py`)
"""
import asyncio
import logging

from pyrogram import Client

from bot.config import config, validate_config
from bot.plugins import register_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
log = logging.getLogger("main")


async def main():
    validate_config()

    app = Client(
        "bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    )

    assistant = None
    call_client = None

    if config.SESSION_STRING:
        assistant = Client(
            "assistant",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=config.SESSION_STRING,
            in_memory=True,
        )
        try:
            from pytgcalls import PyTgCalls
            call_client = PyTgCalls(assistant)
        except ImportError:
            log.warning("py-tgcalls not installed; voice-chat join/leave will be unavailable.")
    else:
        log.warning("SESSION_STRING not set — voice/video chat controls will be disabled.")

    register_all(app, assistant)

    await app.start()
    log.info("Bot client started.")

    if assistant:
        await assistant.start()
        log.info("Assistant client started.")
        app.pytgcalls = call_client
        if call_client:
            await call_client.start()
            log.info("PyTgCalls started.")

    me = await app.get_me()
    log.info(f"Logged in as @{me.username} ({me.id})")

    # Keep the process alive
    await idle()

    await app.stop()
    if assistant:
        await assistant.stop()


async def idle():
    """Block forever until interrupted (SIGINT/SIGTERM), Heroku-friendly."""
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        try:
            import signal
            loop.add_signal_handler(getattr(signal, sig_name), stop_event.set)
        except (NotImplementedError, RuntimeError):
            pass  # not supported on this platform
    await stop_event.wait()


if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    asyncio.run(main())
