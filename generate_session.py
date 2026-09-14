"""
Run this ONCE, locally, to generate a Pyrogram session string for the
assistant account that will join voice/video chats.

    python3 generate_session.py

It will ask for your API_ID, API_HASH, phone number, and the login code
Telegram sends you. The resulting string goes into SESSION_STRING in your
.env (locally) or Heroku config vars (in production). Treat it like a
password — anyone with it can log in as that account.

Use a separate/secondary Telegram account for this, not your personal one,
since it will need to be a member (ideally admin) of every group you want
voice-chat control in.
"""
from pyrogram import Client

api_id = int(input("API_ID: ").strip())
api_hash = input("API_HASH: ").strip()

with Client("assistant_session_gen", api_id=api_id, api_hash=api_hash, in_memory=True) as app:
    session_string = app.export_session_string()
    print("\nYour SESSION_STRING (copy this into your .env / Heroku config):\n")
    print(session_string)
    print("\nKeep this secret — it grants full access to the account.")
