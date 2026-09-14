"""
Async MongoDB access layer (motor). All persistence goes through this module:
 - chat settings (locks, welcome, flood limit)
 - warns
 - global bans (gban)
 - filters / notes
 - sudo/admin cache
"""
from motor.motor_asyncio import AsyncIOMotorClient
from bot.config import config

_client = AsyncIOMotorClient(config.MONGO_DB_URI)
db = _client[config.DB_NAME]

chats_col = db["chats"]          # per-chat settings
warns_col = db["warns"]          # user warns per chat
gban_col = db["gbans"]           # globally banned users
filters_col = db["filters"]      # custom keyword filters per chat
notes_col = db["notes"]          # saved notes per chat
users_col = db["users"]          # seen users (for id resolution)


DEFAULT_CHAT_SETTINGS = {
    "locks": {
        "stickers": False,
        "gifs": False,
        "links": False,
        "forward": False,
        "media": False,
        "polls": False,
        "games": False,
        "inline": False,
    },
    "welcome": {"enabled": False, "text": "Welcome {mention} to {chat_title}!"},
    "flood_limit": config.FLOOD_LIMIT_DEFAULT,
    "warn_limit": config.WARN_LIMIT_DEFAULT,
    "warn_mode": "mute",  # mute | kick | ban
    "vc_lock": False,      # if true, only admins may unmute themselves in VC
}


async def get_chat_settings(chat_id: int) -> dict:
    doc = await chats_col.find_one({"chat_id": chat_id})
    if not doc:
        doc = {"chat_id": chat_id, **DEFAULT_CHAT_SETTINGS}
        await chats_col.insert_one(doc)
    else:
        # backfill any new default keys added over time
        changed = False
        for k, v in DEFAULT_CHAT_SETTINGS.items():
            if k not in doc:
                doc[k] = v
                changed = True
        if changed:
            await chats_col.update_one({"chat_id": chat_id}, {"$set": doc}, upsert=True)
    return doc


async def update_chat_settings(chat_id: int, updates: dict):
    await chats_col.update_one({"chat_id": chat_id}, {"$set": updates}, upsert=True)


async def set_lock(chat_id: int, lock_type: str, value: bool):
    await chats_col.update_one(
        {"chat_id": chat_id},
        {"$set": {f"locks.{lock_type}": value}},
        upsert=True,
    )


async def get_locks(chat_id: int) -> dict:
    settings = await get_chat_settings(chat_id)
    return settings.get("locks", {})


# ---------------- Warns ----------------

async def add_warn(chat_id: int, user_id: int, reason: str = "No reason given"):
    doc = await warns_col.find_one({"chat_id": chat_id, "user_id": user_id})
    if doc:
        await warns_col.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$push": {"reasons": reason}, "$inc": {"count": 1}},
        )
        return doc["count"] + 1
    await warns_col.insert_one(
        {"chat_id": chat_id, "user_id": user_id, "count": 1, "reasons": [reason]}
    )
    return 1


async def reset_warns(chat_id: int, user_id: int):
    await warns_col.delete_one({"chat_id": chat_id, "user_id": user_id})


async def get_warns(chat_id: int, user_id: int) -> dict:
    doc = await warns_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return doc or {"count": 0, "reasons": []}


# ---------------- Global bans ----------------

async def gban_user(user_id: int, reason: str, by: int):
    await gban_col.update_one(
        {"user_id": user_id},
        {"$set": {"reason": reason, "by": by}},
        upsert=True,
    )


async def ungban_user(user_id: int):
    await gban_col.delete_one({"user_id": user_id})


async def is_gbanned(user_id: int) -> bool:
    return await gban_col.find_one({"user_id": user_id}) is not None


# ---------------- Filters ----------------

async def add_filter(chat_id: int, keyword: str, reply_text: str):
    await filters_col.update_one(
        {"chat_id": chat_id, "keyword": keyword.lower()},
        {"$set": {"reply": reply_text}},
        upsert=True,
    )


async def remove_filter(chat_id: int, keyword: str):
    await filters_col.delete_one({"chat_id": chat_id, "keyword": keyword.lower()})


async def get_filters(chat_id: int):
    cursor = filters_col.find({"chat_id": chat_id})
    return [doc async for doc in cursor]


async def get_filter(chat_id: int, keyword: str):
    return await filters_col.find_one({"chat_id": chat_id, "keyword": keyword.lower()})


# ---------------- User cache (for resolving @username / replies) ----------------

async def cache_user(user_id: int, username: str, first_name: str):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"username": username, "first_name": first_name}},
        upsert=True,
    )


async def get_cached_user(username: str):
    return await users_col.find_one({"username": username.lstrip("@")})
