# Telegram Group Manager Bot

A production-ready Telegram group management bot in Python (Pyrogram),
covering moderation, chat controls, sticker management, anonymous/masked
admin handling, filters/notes, welcome messages, global bans, and full
**voice/video chat control** (mute, unmute, kick, ban participants) via a
companion userbot "assistant" account.

## ⚠️ Read this first: why two accounts?

Telegram's **Bot API cannot join or control voice/video chats** — that's a
platform limitation, not a bug in this code. To mute/unmute/kick people in
a group call, an actual **user account** (called the "assistant") has to
join the call over MTProto. This repo runs:

1. **The Bot** (`BOT_TOKEN`) — all normal admin commands (ban, mute, locks,
   filters, etc.) work with just this.
2. **The Assistant** (`SESSION_STRING`) — a secondary Telegram account,
   only needed if you want `/vcmute`, `/vcunmute`, `/vckick`, `/vcjoin`,
   etc. Without it, the bot still works fully for everything else and VC
   commands will just reply that they're unavailable.

Use a **secondary/throwaway account** for the assistant, not your main
personal account, and add it to your groups (ideally as admin, so it can
manage the call).

## Features

- **Moderation**: ban, unban, kick, mute/unmute (with optional durations
  like `10m`/`2h`/`1d`), warn system with configurable auto-action, promote/
  demote, pin/unpin, purge.
- **Chat controls**: lock/unlock stickers, gifs, links, forwards, media,
  polls, games, inline bots; anti-flood auto-mute.
- **Sticker management**: blanket sticker lock, plus per-pack bans.
- **Voice/Video chat control**: join/leave VC, server-mute/unmute a
  participant, stop someone's video, force-mute-all-on-join, remove/ban
  users from the call.
- **Anonymous/masked admin handling**: ban a linked channel or anonymous
  admin identity from posting, `/whois` to reveal who's really behind a
  message.
- **Filters & notes**: auto-replies on keywords, saved text/media notes.
- **Welcome messages**, configurable per chat.
- **Global ban (gban)**: owner/sudo can ban a user across every group the
  bot is in.
- MongoDB persistence, structured plugin architecture, Heroku-ready.

## Project layout

```
tg-group-manager/
├── bot/
│   ├── config.py          # env var loading
│   ├── database.py        # MongoDB (motor) access layer
│   ├── utils.py           # shared helpers (perms, parsing, mentions)
│   └── plugins/
│       ├── admin.py           # ban/kick/mute/warn/promote/pin/purge
│       ├── chat_controls.py   # locks + anti-flood
│       ├── stickers.py        # sticker pack bans
│       ├── anon_admin.py      # masked/anonymous admin handling
│       ├── voicechat.py       # VC mute/unmute/kick/ban via assistant
│       ├── filters_module.py  # keyword filters + notes
│       ├── welcome.py         # welcome messages
│       ├── gban.py            # global ban
│       └── misc.py            # start/help/ping/id/info
├── main.py                # entry point
├── generate_session.py    # one-off script to create SESSION_STRING
├── requirements.txt
├── Procfile                # Heroku: worker dyno
├── runtime.txt              # Python version pin
├── app.json                 # Heroku "Deploy" button config
└── .env.example
```

## 1. Get your credentials

| Variable | Where to get it |
|---|---|
| `API_ID` / `API_HASH` | https://my.telegram.org → API Development Tools |
| `BOT_TOKEN` | Message [@BotFather](https://t.me/BotFather) → `/newbot` |
| `SESSION_STRING` | Run `python3 generate_session.py` locally (optional, only for VC control) |
| `MONGO_DB_URI` | Free cluster at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) |
| `OWNER_ID` | Your numeric Telegram ID — get it from [@userinfobot](https://t.me/userinfobot) |

## 2. Run locally (recommended before deploying)

```bash
git clone https://github.com/YOUR_USERNAME/tg-group-manager.git
cd tg-group-manager
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in the values above

# optional, only if you want voice/video chat control:
python3 generate_session.py

python3 main.py
```

Add the bot to your group and promote it to **admin** with at least:
`ban users`, `delete messages`, `pin messages`, `manage voice chats`,
`add admins` (if you want it to `/promote`), `change info` (for locks).

If you're using the assistant for VC control, add that account to the
group too (admin recommended, or at least allowed to speak).

## 3. Push to your GitHub account

```bash
cd tg-group-manager
git init
git add .
git commit -m "Initial commit: Telegram group manager bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/tg-group-manager.git
git push -u origin main
```

**Do not commit your `.env` file or any session file** — `.gitignore`
below already excludes them.

## 4. Deploy to Heroku

### Option A — One-click deploy button
Add this to your GitHub README (replace the URL with your repo):

```markdown
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/YOUR_USERNAME/tg-group-manager)
```

Clicking it walks you through entering the config vars defined in
`app.json` and deploys automatically using the `Procfile`.

### Option B — Heroku CLI

```bash
heroku login
heroku create your-bot-name

heroku config:set API_ID=xxxxx API_HASH=xxxxx BOT_TOKEN=xxxxx \
  MONGO_DB_URI="mongodb+srv://..." OWNER_ID=123456789 \
  SESSION_STRING="..." DB_NAME=tg_group_manager

git push heroku main

# this bot runs as a worker, not a web dyno — turn the worker on:
heroku ps:scale worker=1 web=0
```

Check logs:

```bash
heroku logs --tail
```

> **Note:** This bot is a long-running background process (it uses
> Pyrogram's polling connection to Telegram), not an HTTP server — that's
> why it's declared as a `worker` dyno in the `Procfile`, and why the free
> "web" dyno type doesn't apply. Heroku's Eco/Basic dyno plans support
> worker dynos fine; there's no free tier anymore, but Eco dynos are cheap
> and enough for this bot.

## 5. Command reference

Send `/help` to the bot in any group for the full command list.

## Notes on scaling / reliability

- MongoDB Atlas free tier (M0) is plenty for moderate-sized deployments.
- If you run many large groups with heavy voice-chat usage, consider
  running the assistant/PyTgCalls process separately from the bot process
  so a VC issue can't affect core moderation commands (this repo runs
  them in one process for simplicity — splitting them is a straightforward
  refactor: move the `assistant`/`call_client` startup into its own
  `worker` dyno and communicate over the shared MongoDB).
- Rotate `SESSION_STRING` if it's ever exposed; it's equivalent to a login
  session for that Telegram account.

## License

Use and modify freely for your own deployment.
