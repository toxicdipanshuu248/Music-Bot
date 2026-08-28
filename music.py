#!/usr/bin/env python3
# ============================================================
#  DEV X CORE — ALL-IN-ONE (Single File)  [FIXED]
#  Railway 24x7 build — same features / same hardcoded config
# ============================================================

import asyncio
import os
import re
import sys
import logging
import sqlite3
import uuid
import time
import math
import hashlib
import random
import html
import functools
from io import BytesIO
from collections import deque
from datetime import datetime
import json

# ==================== EVENT LOOP (critical) ====================
# MUST run BEFORE importing pyrogram/pytgcalls (Python 3.12+/3.14 fix).
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)

import yt_dlp
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.enums import ChatType, ChatMemberStatus, MessageServiceType

_CHAT_STARTED = {
    getattr(MessageServiceType, n) for n in ("VIDEO_CHAT_STARTED", "VOICE_CHAT_STARTED")
    if getattr(MessageServiceType, n, None) is not None
}
_CHAT_ENDED = {
    getattr(MessageServiceType, n) for n in ("VIDEO_CHAT_ENDED", "VOICE_CHAT_ENDED")
    if getattr(MessageServiceType, n, None) is not None
}
from pyrogram.storage.memory_storage import MemoryStorage
from pyrogram.errors import (
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    FloodWait,
    PhoneNumberInvalid,
    PasswordHashInvalid,
    PhoneNumberBanned,
    PhoneNumberUnoccupied,
)

from pytgcalls import PyTgCalls, idle
from pytgcalls.types.stream import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    StreamEnded,
)
from pytgcalls.exceptions import NoActiveGroupCall


def _ver_tuple(v):
    try:
        return tuple(int(x) for x in re.findall(r"\d+", v)[:3])
    except Exception:
        return (0, 0, 0)


def check_engine_compat():
    """Return (ok, problem_text) for the py-tgcalls + pyrogram combo."""
    try:
        import pyrogram as _pg
        pgv = _ver_tuple(getattr(_pg, "__version__", "0"))
    except Exception:
        pgv = (0, 0, 0)
    try:
        from importlib.metadata import version as _dist_version
        ptv = _ver_tuple(_dist_version("py-tgcalls"))
    except Exception:
        ptv = (0, 0, 0)
    if pgv and pgv[:2] <= (2, 0) and ptv[:3] >= (2, 2, 6):
        return False, (
            "py-tgcalls {} is NOT compatible with pyrogram {} "
            "(GroupcallForbidden missing).\n"
            "Fix: pip install \"pyrogram==2.0.106\" "
            "\"py-tgcalls[pyrogram]==2.2.5\""
        ).format(".".join(map(str, ptv)), ".".join(map(str, pgv)))
    return True, ""


# ==================== CONFIG (hardcoded — same as original) ====================
API_ID = 31633970
API_HASH = "702925952d6f164b1cca78e9fa9c5488"
BOT_TOKEN = "7964165741:AAFs5mv-EhceprLe5O93iMmY_NINeYAoO4o"
OWNER_ID = 5206554804

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()

PREFIX = "."
DEFAULT_VOLUME = 100
BOOST_ON = False
AUTO_UNMUTE = True
ENFORCE_INTERVAL = 5

BOT_NAME = "DEV X CORE"
BRAND = "𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄"
CORE_VERSION = "5.4"
START_TIME = time.time()
SESSION_NAME = "devx_music"

# Railway volume at /data (set by start.py). Falls back to local dir.
DATA_DIR = os.getenv("DATA_DIR") or ("/data" if os.path.isdir("/data") else ".")
SESSION_FILE = os.path.join(DATA_DIR, "session_string.txt")
DB_PATH = os.path.join(DATA_DIR, "devx_music.db")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
TEMP_DIR = os.path.join(DATA_DIR, "temp")
BANNER_DIR = os.path.join(DATA_DIR, "banner")
BACKUPS_DIR = os.path.join(DATA_DIR, "backups")
COOKIES_FILE = os.path.join(DATA_DIR, "cookies.txt")

# ==================== SESSION STRING ====================
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
if not SESSION_STRING and os.path.exists(SESSION_FILE):
    with open(SESSION_FILE, "r") as _f:
        SESSION_STRING = _f.read().strip()

# ==================== DIRS + LOGGING ====================
for _d in (LOGS_DIR, TEMP_DIR, BANNER_DIR, BACKUPS_DIR):
    os.makedirs(_d, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "bot.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("DEVX_MUSIC")
# ==================== DATABASE ====================
class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.c = self.conn.cursor()
        self._init()

    def _init(self):
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                last_name TEXT, joined_at TEXT, is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0)"""
        )
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY, value INTEGER DEFAULT 0)"""
        )
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY, value TEXT)"""
        )
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                title TEXT,
                source TEXT,
                size INTEGER DEFAULT 0,
                chat_id INTEGER DEFAULT 0,
                created_at TEXT)"""
        )
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner INTEGER,
                title TEXT,
                body TEXT,
                created_at TEXT)"""
        )
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS playlists (
                name TEXT, chat_id INTEGER, songs TEXT, created_at TEXT,
                PRIMARY KEY (name, chat_id))"""
        )
        self.conn.commit()
        logger.info("Database ready")

    def add_user(self, uid, username, first_name, last_name=""):
        now = datetime.now().isoformat()
        self.c.execute(
            "INSERT OR IGNORE INTO users (id, username, first_name, last_name, joined_at) VALUES (?,?,?,?,?)",
            (uid, username or "", first_name or "", last_name or "", now),
        )
        if self.c.rowcount > 0:
            self.c.execute(
                "INSERT INTO stats (key, value) VALUES ('total_users', 1) "
                "ON CONFLICT(key) DO UPDATE SET value = value + 1"
            )
        self.conn.commit()

    def get_users(self, limit=5000):
        return self.c.execute("SELECT * FROM users WHERE is_active=1 LIMIT ?", (limit,)).fetchall()

    def ban_user(self, uid):
        self.c.execute("UPDATE users SET is_active=0 WHERE id=?", (uid,))
        self.conn.commit()

    def unban_user(self, uid):
        self.c.execute("UPDATE users SET is_active=1 WHERE id=?", (uid,))
        self.conn.commit()

    def bump(self, key, amount=1):
        self.c.execute(
            "INSERT INTO stats (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = value + ?",
            (key, amount, amount),
        )
        self.conn.commit()

    def get_stat(self, key):
        r = self.c.execute("SELECT value FROM stats WHERE key=?", (key,)).fetchone()
        return r[0] if r else 0

    def set_config(self, key, value):
        self.c.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
        )
        self.conn.commit()

    def get_config(self, key, default=None):
        r = self.c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return r[0] if r else default

    def add_file(self, path, title="", source="", chat_id=0):
        if not path:
            return
        size = os.path.getsize(path) if os.path.exists(path) else 0
        now = datetime.now().isoformat()
        self.c.execute(
            "INSERT OR REPLACE INTO files (path, title, source, size, chat_id, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (path, title or os.path.basename(path), source or "", size, chat_id or 0, now),
        )
        self.conn.commit()

    def get_files(self):
        rows = self.c.execute(
            "SELECT id, path, title, source, size, chat_id, created_at "
            "FROM files ORDER BY id"
        ).fetchall()
        alive = []
        for r in rows:
            if os.path.exists(r[1]):
                try:
                    real = os.path.getsize(r[1])
                    if real != r[4]:
                        self.c.execute("UPDATE files SET size=? WHERE id=?", (real, r[0]))
                        r = (r[0], r[1], r[2], r[3], real, r[5], r[6])
                except Exception:
                    pass
                alive.append(r)
            else:
                self.c.execute("DELETE FROM files WHERE id=?", (r[0],))
        self.conn.commit()
        return alive

    def add_note(self, owner, title, body):
        now = datetime.now().isoformat()
        self.c.execute(
            "INSERT INTO notes (owner, title, body, created_at) VALUES (?,?,?,?)",
            (owner, title or "note", body or "", now),
        )
        self.conn.commit()
        return self.c.lastrowid

    def get_notes(self, owner, limit=30):
        return self.c.execute(
            "SELECT id, title, body, created_at FROM notes WHERE owner=? ORDER BY id DESC LIMIT ?",
            (owner, limit),
        ).fetchall()

    def delete_note(self, owner, note_id):
        self.c.execute("DELETE FROM notes WHERE owner=? AND id=?", (owner, note_id))
        self.conn.commit()
        return self.c.rowcount > 0

    def delete_file_by_path(self, path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        self.c.execute("DELETE FROM files WHERE path=?", (path,))
        self.conn.commit()

    def close(self):
        self.conn.close()

db = Database()

# ==================== QUEUE / STATE ====================
class MusicQueue:
    def __init__(self):
        self.songs = deque()
        self.current = None
        self.loop = False
        self.repeat = False
        self.boost_level = 0
        self.eco_level = 0
        self.gain_level = 0
        self.loud_level = 0
        self.treble = 0
        self.volume = DEFAULT_VOLUME
        self.silent_loop = False
        self.speed = 1.0
        self.nightcore = False
        self.bass = 0

queues = {}
active_calls = set()
awaiting = {}
search_cache = {}
search_seq = [0]
last_search = {}
current_files = {}
replay_lock = set()
err_notified = set()
_last_vol_applied = {}
_muted_state = {}
END_GUARD = {}
_vol_auto = {}
AUTO_MAX_VOLUME = 200
PLAY_TIMERS = {}

def _reset_timer(chat_id, seek=0):
    PLAY_TIMERS[chat_id] = {
        "start": time.time() - max(0, int(seek or 0)),
        "paused_elapsed": 0.0,
        "paused": False,
    }

def _pause_timer(chat_id):
    t = PLAY_TIMERS.get(chat_id)
    if t and not t["paused"]:
        t["paused_elapsed"] += time.time() - t["start"]
        t["paused"] = True

def _resume_timer(chat_id):
    t = PLAY_TIMERS.get(chat_id)
    if t and t["paused"]:
        t["start"] = time.time()
        t["paused"] = False

def get_elapsed(chat_id):
    t = PLAY_TIMERS.get(chat_id)
    if not t:
        return 0
    if t["paused"]:
        return t["paused_elapsed"]
    return t["paused_elapsed"] + (time.time() - t["start"])

def get_rjoin_spec(chat_id):
    raw = (db.get_config(f"rjoin:{chat_id}") or "").strip()
    return raw or None

def set_rjoin_spec(chat_id, spec):
    db.set_config(f"rjoin:{chat_id}", spec or "")
async def _rjoin_play_files(chat_id, indices, silent=True):
    rows = db.get_files()
    songs = []
    for i in indices:
        if 0 <= i < len(rows):
            _id, path, title, source, size, _chat, created = rows[i]
            if path and os.path.exists(path):
                name = title or os.path.basename(path)
                songs.append({
                    "title": name,
                    "duration": 0,
                    "uploader": "DEV X CORE",
                    "local_path": path,
                    "source": "local",
                    "loudspeaker": True,
                    "rjoin": True,
                })
    if not songs:
        return False
    q = get_queue(chat_id)
    if len(songs) == 1:
        q.repeat = True
        q.loop = False
        q.silent_loop = True
        q.songs.clear()
        q.current = songs[0]
    else:
        q.loop = True
        q.repeat = False
        q.silent_loop = True
        q.songs.clear()
        for s in songs[1:]:
            q.songs.append(s)
        q.current = songs[0]
    active_calls.add(chat_id)
    err_notified.discard(chat_id)
    ok = await play_song(chat_id, q.current, announce=False, silent=silent)
    if not ok:
        q.loop = False
        q.repeat = False
        q.current = None
        active_calls.discard(chat_id)
    return ok

async def rjoin_on_call_started(chat_id):
    if not vc_ready():
        return None
    spec = get_rjoin_spec(chat_id)
    if spec is None:
        return None
    _q = get_queue(chat_id)
    if _q.current is not None or chat_id in active_calls:
        return None
    joined = False
    await asyncio.sleep(3)
    for attempt in range(6):
        try:
            await vc.play(chat_id)
            joined = True
            break
        except NoActiveGroupCall:
            logger.warning("rjoin: NoActiveGroupCall (attempt %d) — retrying…", attempt + 1)
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning("rjoin join error (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(3)
    if not joined:
        return None
    active_calls.add(chat_id)
    if spec == "join":
        return "joined"
    sync_saved_files()
    rows = db.get_files()
    indices = resolve_file_spec(spec, rows)
    if not indices:
        return "joined"
    ok = await _rjoin_play_files(chat_id, indices)
    return "playing" if ok else "joined"

def get_queue(chat_id):
    if chat_id not in queues:
        queues[chat_id] = MusicQueue()
    return queues[chat_id]

async def chat_locked(chat_id):
    return db.get_config(f"lock:{chat_id}") == "1"

async def is_group_admin(client, chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False

def get_core_admins():
    raw = db.get_config("core_admins", "") or ""
    ids = {int(x) for x in raw.split(",") if x.strip().isdigit()}
    ids.add(OWNER_ID)
    return ids

def is_core_admin(user_id):
    try:
        return int(user_id) in get_core_admins()
    except Exception:
        return False

def add_core_admin(user_id):
    ids = {int(x) for x in (db.get_config("core_admins", "") or "").split(",") if x.strip().isdigit()}
    ids.add(int(user_id))
    db.set_config("core_admins", ",".join(str(i) for i in sorted(ids)))

def del_core_admin(user_id):
    ids = {int(x) for x in (db.get_config("core_admins", "") or "").split(",") if x.strip().isdigit()}
    ids.discard(int(user_id))
    db.set_config("core_admins", ",".join(str(i) for i in sorted(ids)))

def core_admins_text():
    admins = sorted(get_core_admins())
    lines = [f"👑 **{BRAND} — {stylish('Core Admins')}**", "━━━━━━━━━━━━━━━━━━━━━"]
    for a in admins:
        tag = " • owner" if a == OWNER_ID else ""
        lines.append(f"• `{a}`{tag}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"👉 `.admin add <id>` / `.admin del <id>` — {stylish('owner only')}")
    return "\n".join(lines)

async def can_control(client, chat_id, user_id):
    if is_core_admin(user_id):
        return True
    try:
        if uid_gbanned(user_id):
            return False
    except Exception:
        pass
    if await chat_locked(chat_id):
        return False
    mode = get_mode()
    if mode == "private":
        return False
    return await is_group_admin(client, chat_id, user_id)

def get_mode():
    return db.get_config("mode", "public")

def set_mode(mode):
    db.set_config("mode", mode)

async def _deny_reply(message):
    try:
        if get_mode() == "private":
            t = (
                f"🔐 『{BRAND}』 — {stylish('PRIVATE MODE')}\n\n"
                f"{stylish('Sirf OWNER aur .admin se add kiye gaye log hi bot chala sakte hain.')} 👑\n"
                f"`.public` — {stylish('mode badalne ke liye (owner)')}"
            )
        else:
            t = (
                f"🔒 『{BRAND}』 — {stylish('PUBLIC MODE')}\n\n"
                f"{stylish('Sirf group ke owner/admins hi control kar sakte hain.')}\n"
                f"`.private` — {stylish('sirf owner + core admins (owner cmd)')}"
            )
        await message.reply_text(t)
    except Exception:
        pass

async def _deny_answer(cb):
    try:
        txt = ("🔐 Private mode — sirf owner/core admins 👑"
               if get_mode() == "private" else
               "🔒 Sirf group owner/admins (public mode)")
        await cb.answer(txt, show_alert=True)
    except Exception:
        pass

CONTROL_CALLBACKS = {
    "cb_pause", "cb_resume", "cb_skip", "cb_stop", "cb_loop",
    "cb_repeat", "cb_boost", "cb_volup", "cb_voldown", "cb_play", "cb_voice",
    "cb_mute", "cb_vol200", "cb_vol_10", "cb_vol_50", "cb_vol_100", "cb_vol_150",
}

FONT_MAP = {
    'A': '𝐀','B': '𝐁','C': '𝐂','D': '𝐃','E': '𝐄','F': '𝐅','G': '𝐆','H': '𝐇',
    'I': '𝐈','J': '𝐉','K': '𝐊','L': '𝐋','M': '𝐌','N': '𝐍','O': '𝐎','P': '𝐏',
    'Q': '𝐐','R': '𝐑','S': '𝐒','T': '𝐓','U': '𝐔','V': '𝐕','W': '𝐖','X': '𝐗',
    'Y': '𝐘','Z': '𝐙',
    'a': 'ᴀ','b': 'ʙ','c': 'ᴄ','d': 'ᴅ','e': 'ᴇ','f': 'ғ','g': 'ɢ','h': 'ʜ',
    'i': 'ɪ','j': 'ᴊ','k': 'ᴋ','l': 'ʟ','m': 'ᴍ','n': 'ɴ','o': 'ᴏ','p': 'ᴘ',
    'q': 'ǫ','r': 'ʀ','s': 's','t': 'ᴛ','u': 'ᴜ','v': 'ᴠ','w': 'ᴡ','x': 'x',
    'y': 'ʏ','z': 'ᴢ',
}

def stylish(text):
    return "".join(FONT_MAP.get(c, c) for c in text)

RULE = "◈━━━━━━━━━━━━━━━━━━━━━━━━━━◈"
RULE_THIN = "─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─"

def core_card(title, body, footer=None):
    lines = [
        RULE,
        f"   {BRAND}",
        f"   ⌁  {stylish(title)}  ⌁",
        RULE,
        "",
        body.rstrip(),
        "",
        RULE,
    ]
    if footer:
        lines.append(f"   {footer}")
        lines.append(RULE)
    return "\n".join(lines)

def fmt_uptime(seconds=None):
    seconds = int(seconds if seconds is not None else (time.time() - START_TIME))
    d, rem = divmod(max(0, seconds), 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

def hub_home_text(extra=""):
    body = (
        f"  🟢 {stylish('status')}     online\n"
        f"  🎭 {stylish('mood')}       `{get_mode()}`\n"
        f"  📦 {stylish('version')}    `{CORE_VERSION}`\n"
        f"  ⏱️  {stylish('uptime')}     `{fmt_uptime()}`\n"
        f"  ⌨️  {stylish('prefix')}     `.`\n"
        f"  🎧 {stylish('active vc')}  `{len(active_calls)}`\n"
        "\n"
        f"  〔 01 〕  🎵 {stylish('music deck')}\n"
        f"  〔 02 〕  🎛️  {stylish('player + files')}\n"
        f"  〔 03 〕  🛠️  {stylish('tools + notes')}\n"
        f"  〔 04 〕  🎮 {stylish('fun + studio')}\n"
    )
    if extra:
        body += "\n" + extra
    return core_card("userbot system", body, stylish("tap a key  ·  .alive  ·  .help"))

def page_music_text():
    body = (
        f"{stylish('PLAY')}\n"
        f"  `.play <song>`   🎵 {stylish('search karke play')}\n"
        f"  `.nplay <song>`  🎧 {stylish('natural sound')}\n"
        f"  `.voice`         🎙️ {stylish('replied note')}\n"
        "\n"
        f"{stylish('LOOP')}\n"
        f"  `.run`           🔁 {stylish('replied media loop')}\n"
        f"  `.run 1,2,3`     🔁 {stylish('saved files loop')}\n"
        f"  `.vrun`          🎬 {stylish('video loop')}\n"
        f"  `.rjoin`         🤖 {stylish('call pe auto-join')}\n"
        "\n"
        f"{stylish('CONTROL')}\n"
        f"  `.pause` `.resume` `.skip` `.stop`\n"
        f"  `.queue` `.now` `.volume`\n"
        "\n"
        f"{stylish('SOUND (0-100 = max loud)')}\n"
        f"  `.loud 100` `.gain 100` `.boost 100` `.eco 50`\n"
        f"  `.bass 100` `.treble 50` `.mix 100` `.max` 💯\n"
        f"  `.volume <0-200>` `.loop` `.repeat`\n"
    )
    return core_card("music deck", body, stylish(".play kesariya"))

def page_files_text():
    body = (
        f"  `.files`       📁 {stylish('saved list')}\n"
        f"  `.run 1`       🔁 {stylish('loop file')}\n"
        f"  `.run 1,2,3`   🔁 {stylish('multi loop')}\n"
        f"  `.nplay 3`     🎧 {stylish('natural')}\n"
        f"  `.del 1-10`    🗑️ {stylish('delete')}\n"
        f"  `.delall`      🗑️ {stylish('sab clear')}\n"
        f"  `.set`         🎬 {stylish('GIF banner (reply media)')}\n"
        f"  `.set off`     🚫 {stylish('banner hatao')}\n"
        f"  `.save <song>` 💾 {stylish('vault me save')}\n"
        f"  `.ytdl <url>`  🎬 {stylish('video save')}\n"
    )
    return core_card("vault / files", body, stylish("saved files kabhi delete nahi hote"))

def page_tools_text():
    body = (
        f"  `.alive` `.ping` `.status`\n"
        f"  `.id` `.chatid` `.whois`\n"
        f"  `.time` `.sysinfo`\n"
        "\n"
        f"{stylish('PROFILE')}\n"
        f"  `.setname` `.setbio` `.setpp` `.getpp`\n"
        "\n"
        f"{stylish('UTIL')}\n"
        f"  `.tts` `.qr` `.calc` `.weather`\n"
        f"  `.fancy` `.md5` `.password`\n"
        "\n"
        f"{stylish('SUPER')}\n"
        f"  `.lyrics` `.radio` `.speed` `.nightcore` `.bass`\n"
        f"  `.seek` `.playlist` `.gban` `.restart` `.backup`\n"
        f"  `.ytdl` `.save` `.clean`\n"
        "\n"
        f"{stylish('NOTES')}\n"
        f"  `.notesadd` `.noteslist` `.notesdel`\n"
    )
    return core_card("toolkit", body, stylish("sab kuch ek jagah"))

def page_fun_text():
    body = (
        f"  `.flip` `.dice` `.8ball`\n"
        f"  `.rps` `.joke` `.choose`\n"
        f"  `.truth` `.dare`\n"
    )
    return core_card("fun deck", body, stylish("just for the room"))

def page_admin_text():
    body = (
        f"{stylish('OWNER + ADMIN')}\n"
        f"  `.admin` (reply)  👑 {stylish('replied user ko admin banao')}\n"
        f"  `.admin add <id|@user>`  👑 {stylish('admin banao')}\n"
        f"  `.rm <id>` / `.rm all`  🗑️\n"
        f"  `.alist`           📋 {stylish('admin list')}\n"
        f"  `.public` / `.private`  🎭\n"
        "\n"
        f"{stylish('EXTRA')}\n"
        f"  `.broadcast` `.stats` `.ytupdate`\n"
        f"  `.lockmusic` / `.unlockmusic`\n"
        "\n"
        f"{stylish('GROUP')}\n"
        f"  `.ban` `.unban` `.kick` `.purge`\n"
        f"  `.promote` `.demote` `.pin` `.unpin`\n"
    )
    return core_card("control room", body, stylish("admins / owner"))

def hub_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♪  Music", callback_data="hub_music"),
         InlineKeyboardButton("🎛  Player", callback_data="cb_panel")],
        [InlineKeyboardButton("📁  Vault", callback_data="hub_files"),
         InlineKeyboardButton("🛠  Tools", callback_data="hub_tools")],
        [InlineKeyboardButton("🎮  Fun", callback_data="hub_fun"),
         InlineKeyboardButton("👑  Admin", callback_data="cb_admin")],
        [InlineKeyboardButton("📖  Help", callback_data="hub_help"),
         InlineKeyboardButton("✦  Alive", callback_data="hub_alive")],
        [InlineKeyboardButton("ℹ  About", callback_data="hub_about")],
    ])

def fmt_duration(seconds):
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

def _fmt_mss(seconds):
    seconds = int(seconds or 0)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def fmt_vol(vol):
    return f"{vol}%"

def fmt_size(n):
    n = int(n or 0)
    if n >= 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024 * 1024):.1f} GB"
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"

def is_url(text):
    return bool(re.match(r"^https?://", (text or "").strip()))

def _song_dict(info):
    return {
        "title": info.get("title") or "Unknown",
        "duration": info.get("duration") or 0,
        "uploader": info.get("uploader") or info.get("channel") or "YouTube",
        "webpage_url": info.get("webpage_url"),
        "direct_url": info.get("url") or info.get("webpage_url"),
        "thumbnail": info.get("thumbnail") or "",
        "source": "youtube",
    }

def search_results_text(results, query, natural=False):
    head_icon = "🎧" if natural else "🎵"
    head_title = stylish("Natural Search") if natural else stylish("Search Results")
    text = (
        f"{head_icon} 『{BRAND}』 — {head_title}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔎 {stylish('Query')}: `{query}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    for i, s in enumerate(results):
        tag = SOURCE_TAG.get(s.get("source"), "🎵")
        text += f"{i+1}. {tag} **{s.get('title', 'Unknown')}**\n"
        bits = []
        if s.get("uploader"):
            bits.append(f"👤 {s.get('uploader')}")
        if s.get("album"):
            bits.append(f"💿 {s.get('album')}")
        if s.get("year"):
            bits.append(f"📅 {s.get('year')}")
        if s.get("quality"):
            bits.append(f"🔊 {s.get('quality')}")
        bits.append(f"⏱️ {_fmt_mss(s.get('duration', 0))}")
        text += "    " + " · ".join(bits) + "\n"
    text += (
        "\n👇 "
        + (stylish("Select — natural sound me play hoga") if natural else stylish("Select a song"))
        + ":\n"
        f"🔢 {stylish('reply karo')} `1` · `1,3,5` · `1-3` · `all` {stylish('ya button dabao')}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"   ✦ {BRAND} ✦"
    )
    return text
def _ydl_opts(extra=None):
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "default_search": "auto",
        "skip_download": True,
        "extractor_retries": 2,
        "retries": 2,
        "socket_timeout": 15,
        "nocheckcertificate": True,
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    else:
        opts["extractor_args"] = {
            "youtube": {"player_client": ["android", "android_vr", "tv_embedded", "web_embedded"]}
        }
    if extra:
        opts.update(extra)
    return opts

def _try_resolve(query):
    attempts = []
    if os.path.exists(COOKIES_FILE):
        attempts = [None]
    else:
        attempts = [
            {"youtube": {"player_client": ["android", "android_vr"]}},
            {"youtube": {"player_client": ["tv_embedded", "web_embedded"]}},
            {"youtube": {"player_client": ["ios"]}},
            None,
        ]
    last_err = None
    for ea in attempts:
        try:
            opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "default_search": "auto",
                "skip_download": True,
                "extractor_retries": 2,
                "retries": 2,
                "socket_timeout": 15,
                "nocheckcertificate": True,
            }
            if os.path.exists(COOKIES_FILE):
                opts["cookiefile"] = COOKIES_FILE
            if ea:
                opts["extractor_args"] = ea
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=False)
            return info
        except Exception as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError("yt-dlp failed")

def resolve_song(query):
    if not is_url(query):
        query = f"ytsearch1:{query}"
    info = _try_resolve(query)
    if info.get("entries"):
        info = info["entries"][0]
    if not info or not info.get("webpage_url"):
        return None
    return _song_dict(info)

def resolve_songs(query, limit=5):
    if not is_url(query):
        query = f"ytsearch{limit}:{query}"
    info = _try_resolve(query)
    entries = info.get("entries", []) if info else []
    return [_song_dict(e) for e in entries if e and e.get("webpage_url")]

def playing_paths():
    return {p for p in current_files.values() if p}

TEMP_PREFIXES = ("yt_", "saavn_", "inv_", "ytv_")

def _is_temp_song(song):
    return bool(song and song.get("temp"))

def _delete_temp_song_files(song):
    if not _is_temp_song(song):
        return
    playing = playing_paths()
    for key in ("_file", "local_path"):
        p = song.get(key)
        if not p:
            continue
        try:
            if os.path.exists(p) and p not in playing:
                os.remove(p)
        except Exception:
            pass
        try:
            db.c.execute("DELETE FROM files WHERE path=?", (p,))
        except Exception:
            pass
    try:
        db.conn.commit()
    except Exception:
        pass

def _cleanup_temp_queue(q):
    for s in list(q.songs):
        _delete_temp_song_files(s)

def register_saved_file(path, title=None, source="", chat_id=0):
    if not path or not os.path.exists(path):
        return
    db.add_file(path, title or os.path.basename(path), source, chat_id)

def sync_saved_files():
    try:
        known = {r[0] for r in db.c.execute("SELECT path FROM files").fetchall()}
    except Exception:
        known = set()
    try:
        for name in os.listdir(TEMP_DIR):
            if name.startswith(TEMP_PREFIXES):
                continue
            fp = os.path.join(TEMP_DIR, name)
            if os.path.isfile(fp) and fp not in known:
                src = "saavn" if name.startswith("saavn_") else (
                    "youtube" if name.startswith("yt_") else "local"
                )
                db.add_file(fp, name, src, 0)
    except Exception as e:
        logger.error("sync_saved_files: %s", e)

def parse_index_spec(spec, total):
    indices = set()
    spec = (spec or "").replace(" ", "")
    if not spec:
        raise ValueError("empty")
    for part in spec.split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            if not a.isdigit() or not b.isdigit():
                raise ValueError(part)
            start, end = int(a), int(b)
            if start > end:
                start, end = end, start
            if start < 1 or end < 1:
                raise ValueError(part)
            for i in range(start, end + 1):
                if 1 <= i <= total:
                    indices.add(i - 1)
        else:
            if not part.isdigit():
                raise ValueError(part)
            i = int(part)
            if 1 <= i <= total:
                indices.add(i - 1)
    return sorted(indices)

def resolve_file_spec(spec, rows):
    spec = (spec or "").strip().replace(" ", "")
    if not spec:
        return None
    low = spec.lower()
    if low in ("all", "*", "etc"):
        return list(range(len(rows))) if rows else []
    if low.endswith("etc"):
        head = spec[:-3].rstrip(",").rstrip("-")
        base = set()
        if head:
            try:
                base = set(parse_index_spec(head, len(rows)))
            except ValueError:
                return None
        start = max(base) + 1 if base else 0
        base.update(range(start, len(rows)))
        return sorted(base) if base else None
    if spec.isdigit():
        i = int(spec)
        return [i - 1] if 1 <= i <= len(rows) else None
    try:
        indices = parse_index_spec(spec, len(rows))
        return indices if indices else None
    except ValueError:
        return None

def files_list_text(page=0, per_page=15):
    sync_saved_files()
    rows = db.get_files()
    total = len(rows)
    total_size = sum(r[4] or 0 for r in rows)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    start = page * per_page
    chunk = rows[start:start + per_page]
    playing = playing_paths()

    text = (
        f"📁 『{BRAND}』 — {stylish('Saved Files')}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
    )
    if not chunk:
        text += f"📭 {stylish('No saved files.')}\n"
    else:
        for n, r in enumerate(chunk, start + 1):
            _id, path, title, source, size, _chat, created = r
            tag = "🎧" if source == "saavn" else ("📺" if source == "youtube" else "💾")
            now = " ▶️" if path in playing else ""
            name = (title or os.path.basename(path) or "?")[:50]
            text += f"`{n}.` {tag} {name}{now}\n    {fmt_size(size)} · {source or 'file'}\n"
    text += (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{stylish('Total')}: {total} {stylish('files')} · {fmt_size(total_size)}"
    )
    if total:
        text += f" · {stylish('Page')} {page + 1}/{pages}"
    text += (
        f"\n\n`.files` — {stylish('list files')}\n"
        f"`.run1` / `.run 1` — {stylish('loop saved file #1')}\n"
        f"`.run 1,2,3` / `.run 5,etc` / `.run all` — 🔁 {stylish('sequential loop')}\n"
        f"`.nplay 3` — 🎧 {stylish('natural play (no fx)')}\n"
        f"`.vrun1` — {stylish('loop saved file as video')}\n"
        f"`.del 1-10` — {stylish('delete 1 to 10')}\n"
        f"`.del 1,2,3` — {stylish('delete selected')}\n"
        f"`.delall` — {stylish('delete all (skips playing)')}"
    )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cb_fpage_{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"cb_fpage_{page + 1}"))
    rows_kb = [nav] if nav else []
    rows_kb.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"cb_fpage_{page}"),
        InlineKeyboardButton("🗑 Del All", callback_data="cb_delall"),
    ])
    rows_kb.append([InlineKeyboardButton("🏠 Main Menu", callback_data="cb_menu")])
    return text, InlineKeyboardMarkup(rows_kb)

def delete_files_by_indices(indices):
    rows = db.get_files()
    playing = playing_paths()
    deleted, skipped, missing = [], [], []
    for i in indices:
        if i < 0 or i >= len(rows):
            missing.append(i + 1)
            continue
        _id, path, title, source, size, _chat, created = rows[i]
        name = title or os.path.basename(path)
        if path in playing:
            skipped.append(name)
            continue
        db.delete_file_by_path(path)
        deleted.append(name)
    return deleted, skipped, missing

def delete_all_saved_files():
    rows = db.get_files()
    playing = playing_paths()
    deleted = 0
    skipped = 0
    for r in rows:
        path = r[1]
        if path in playing:
            skipped += 1
            continue
        db.delete_file_by_path(path)
        deleted += 1
    try:
        for name in os.listdir(TEMP_DIR):
            fp = os.path.join(TEMP_DIR, name)
            if os.path.isfile(fp) and fp not in playing:
                try:
                    os.remove(fp)
                    deleted += 1
                except Exception:
                    pass
    except Exception:
        pass
    return deleted, skipped

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}

def _run_ffmpeg(args):
    import shutil as _sh, subprocess as _sp
    if _sh.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found")
    r = _sp.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
                capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "ffmpeg failed").strip()[:300])

def video_to_gif(src, dest, max_dur=15, fps=15, width=480):
    _run_ffmpeg([
        "-i", src,
        "-t", str(max_dur),
        "-vf", f"fps={fps},scale='min({width},iw)':-2:flags=lanczos",
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        dest,
    ])

def photo_to_gif(src, dest, width=480, frames=10):
    try:
        from PIL import Image
    except Exception:
        raise RuntimeError("Pillow not installed — pip install pillow")
    im = Image.open(src).convert("RGB")
    im.thumbnail((width, width), Image.LANCZOS)
    w, h = im.size
    base = min(w, h)
    n = max(2, frames)
    out = []
    for i in range(n):
        k = 1.0 + 0.045 * (0.5 - 0.5 * math.cos(2 * math.pi * i / n))
        cw, ch = min(w, int(base * k)), min(h, int(base * k))
        x0, y0 = (w - cw) // 2, (h - ch) // 2
        crop = im.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.LANCZOS)
        out.append(crop)
    out[0].save(dest, save_all=True, append_images=out[1:],
                duration=80, loop=0, optimize=True)

def convert_default_logo():
    src = os.path.join(BANNER_DIR, "devx_logo.png")
    dst = os.path.join(BANNER_DIR, "devx_logo.gif")
    if not os.path.exists(src) or os.path.exists(dst):
        return
    try:
        photo_to_gif(src, dst)
        logger.info("Default logo converted to GIF")
    except Exception as e:
        logger.error("logo->gif failed: %s", e)

async def send_with_banner(message, text, reply_markup=None):
    path = db.get_config("banner_path") or ""
    kind = (db.get_config("banner_kind") or "animation").lower()
    default_logo = os.path.join(BANNER_DIR, "devx_logo.png")
    default_gif = os.path.join(BANNER_DIR, "devx_logo.gif")
    if not path or not os.path.exists(path):
        if os.path.exists(default_gif):
            path, kind = default_gif, "animation"
        elif os.path.exists(default_logo):
            path, kind = default_logo, "photo"
    if path and os.path.exists(path):
        caption = text if len(text) <= 1024 else None
        try:
            if kind in ("animation", "gif"):
                await message.reply_animation(path, caption=caption, reply_markup=reply_markup)
            elif kind == "photo":
                await message.reply_photo(path, caption=caption, reply_markup=reply_markup)
            else:
                await message.reply_video(path, caption=caption, reply_markup=reply_markup,
                                          supports_streaming=True)
            if caption is not None:
                return
        except Exception as e:
            logger.error("banner send: %s", e)
    await message.reply_text(text, reply_markup=reply_markup)
async def start_local_loop(chat_id, path, title, video=False, status=None):
    song = {
        "title": title or os.path.basename(path),
        "duration": 0,
        "uploader": "DEV X CORE",
        "local_path": path,
        "source": "local",
        "loudspeaker": True,
        "video": bool(video),
    }
    q = get_queue(chat_id)
    q.repeat = True
    q.loop = False
    q.songs.clear()
    q.current = song
    active_calls.add(chat_id)
    err_notified.discard(chat_id)
    ok = await play_song(chat_id, song, announce=False, silent=True)
    if ok:
        kind = stylish("Video Looping") if video else stylish("Looping (Loudspeaker)")
        icon = "🎬" if video else "🔁"
        msg = (
            f"{icon} 『{BRAND}』 — {kind}\n"
            f"🎵 `{song['title']}`\n"
            f"📢 {stylish('Extra gain + loudspeaker ON')}\n"
            f"💾 {stylish('Saved file — silent loop, no spam')}"
        )
        if status:
            await status.edit_text(msg)
        else:
            await music.send_message(chat_id, msg)
        return True
    q.repeat = False
    active_calls.discard(chat_id)
    fail = (
        f"❌ 『{BRAND}』 — {stylish('Could not start loop')}\n"
        f"{stylish('Start a voice chat first, then retry.')}"
    )
    if status:
        await status.edit_text(fail)
    else:
        await music.send_message(chat_id, fail)
    return False

async def play_saved_index(message, index_1based, as_video=False, natural=False):
    sync_saved_files()
    rows = db.get_files()
    if not rows:
        await message.reply_text(f"📭 {stylish('No saved files.')} `.files`")
        return
    if index_1based < 1 or index_1based > len(rows):
        await message.reply_text(
            f"❌ {stylish('Invalid number.')} {stylish('Valid')}: `1`–`{len(rows)}`\n`.files`"
        )
        return
    _id, path, title, source, size, _chat, created = rows[index_1based - 1]
    if not path or not os.path.exists(path):
        await message.reply_text("❌ File missing from disk. `.files` to refresh.")
        return
    name = title or os.path.basename(path)

    if natural:
        song = {
            "title": name,
            "duration": 0,
            "uploader": "DEV X CORE",
            "local_path": path,
            "source": "local",
            "normal": True,
        }
        q = get_queue(message.chat.id)
        q.songs.append(song)
        if not q.current:
            q.current = q.songs.popleft()
            active_calls.add(message.chat.id)
            await play_song(message.chat.id, q.current)
        else:
            await message.reply_text(f"✅ 🎧 {stylish('Queued (natural)')}: **{name}**")
        return

    st = await message.reply_text(
        f"🔁 『{BRAND}』 — {stylish('Playing saved file')} `#{index_1based}`\n🎵 {name}"
    )
    await start_local_loop(message.chat.id, path, name, video=as_video, status=st)

async def play_saved_list(message, indices, as_video=False, natural=False):
    sync_saved_files()
    rows = db.get_files()
    if not rows:
        await message.reply_text(f"📭 {stylish('No saved files.')} `.files`")
        return
    q = get_queue(message.chat.id)
    songs = []
    names = []
    for i in indices:
        if i < 0 or i >= len(rows):
            continue
        _id, path, title, source, size, _chat, created = rows[i]
        if not path or not os.path.exists(path):
            continue
        name = title or os.path.basename(path)
        songs.append({
            "title": name,
            "duration": 0,
            "uploader": "DEV X CORE",
            "local_path": path,
            "source": "local",
            "loudspeaker": not natural,
            "normal": bool(natural),
            "video": bool(as_video),
        })
        names.append(name)
    if not songs:
        await message.reply_text(
            f"❌ {stylish('No valid files found.')}\n"
            f"{stylish('Valid range')}: `1`–`{len(rows)}` — `.files`"
        )
        return
    q.loop = not natural
    q.repeat = False
    q.silent_loop = True
    q.songs.clear()
    for s in songs[1:]:
        q.songs.append(s)
    q.current = songs[0]
    active_calls.add(message.chat.id)
    err_notified.discard(message.chat.id)
    ok = await play_song(message.chat.id, q.current, announce=True)
    if ok:
        shown = names[:25]
        listing = "\n".join(f"  {n + 1}. 🎵 {nm}" for n, nm in enumerate(shown))
        if len(names) > len(shown):
            listing += f"\n  … +{len(names) - len(shown)} more"
        head = f"{'🎧' if natural else '🔁'} 『{BRAND}』 — " + stylish(
            "Natural Playlist" if natural else "Sequential Loop"
        )
        footer = (
            f"{stylish('ek ke baad ek — set ek baar chala kar ruk jayega')}"
            if natural else
            f"{stylish('ek ke baad ek chalenge — set repeat hota rahega')}"
        )
        await message.reply_text(
            head + "\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"{listing}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📚 {stylish('total')}: {len(names)} {stylish('tracks')}\n"
            f"{footer}"
        )
    else:
        q.loop = False
        q.current = None
        active_calls.discard(message.chat.id)

SAAVN_API = "https://www.jiosaavn.com/api.php"
SAAVN_FALLBACK = "https://saavnapi-nine.vercel.app/result/"
DEEZER_API = "https://api.deezer.com"
SAAVN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.jiosaavn.com/",
    "Accept": "application/json, text/plain, */*",
}

async def saavn_auth_url(enc_url, bitrate=320):
    if not enc_url:
        return None
    timeout = aiohttp.ClientTimeout(total=20)
    params = {
        "__call": "song.generateAuthToken",
        "url": enc_url,
        "bitrate": str(bitrate),
        "api_version": "4",
        "_format": "json",
        "ctx": "web6dot0",
        "_marker": "0",
    }
    try:
        async with aiohttp.ClientSession(headers=SAAVN_HEADERS) as session:
            async with session.get(SAAVN_API, params=params, timeout=timeout) as resp:
                data = await resp.json(content_type=None)
        return (data or {}).get("auth_url")
    except Exception as e:
        logger.error("Saavn auth token error: %s", e)
        return None

def _saavn_thumb(r):
    img = r.get("image")
    if isinstance(img, str):
        return img.replace("50x50", "500x500").replace("150x150", "500x500")
    if isinstance(img, list) and img:
        last = img[-1]
        return last.get("url", "") if isinstance(last, dict) else (last or "")
    return ""

def _saavn_artist(r):
    mi = r.get("more_info") or {}
    am = mi.get("artistMap") or r.get("artistMap") or {}
    prim = am.get("primary_artists") or []
    if isinstance(prim, list) and prim:
        names = [a.get("name", "") for a in prim if isinstance(a, dict)]
        names = [n for n in names if n]
        if names:
            return ", ".join(names)
    return (
        r.get("primary_artists")
        or r.get("singers")
        or r.get("subtitle")
        or mi.get("music")
        or "JioSaavn"
    )

def _saavn_duration(r):
    mi = r.get("more_info") if isinstance(r.get("more_info"), dict) else {}
    raw = (mi or {}).get("duration") or r.get("duration") or 0
    try:
        return int(float(raw))
    except Exception:
        return 0

def _saavn_direct_url(r):
    for key in ("media_url", "download_url", "url"):
        v = r.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None

async def _saavn_nine_raw(query):
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(headers=SAAVN_HEADERS) as session:
        async with session.get(SAAVN_FALLBACK, params={"query": query}, timeout=timeout) as resp:
            data = await resp.json(content_type=None)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("result") or data.get("results") or []
    return []

async def saavn_search(query, limit=5):
    timeout = aiohttp.ClientTimeout(total=25)
    songs = []
    try:
        raw = await _saavn_nine_raw(query)
        for r in (raw or [])[:limit]:
            if not isinstance(r, dict):
                continue
            enc = r.get("encrypted_media_url")
            direct = _saavn_direct_url(r)
            if enc and not direct:
                try:
                    direct = await saavn_auth_url(enc)
                except Exception:
                    direct = None
            if not direct:
                continue
            songs.append({
                "title": r.get("song") or r.get("name") or r.get("title") or "Unknown",
                "duration": _saavn_duration(r),
                "uploader": r.get("singers") or r.get("primary_artists") or r.get("artist") or "JioSaavn",
                "album": r.get("album") or "",
                "year": str(r.get("year") or ""),
                "quality": "320kbps" if r.get("320kbps") else (r.get("quality") or ""),
                "webpage_url": r.get("perma_url") or direct,
                "direct_url": direct,
                "enc_url": enc,
                "thumbnail": r.get("image") or r.get("thumbnail") or "",
                "source": "saavn",
            })
        if songs:
            logger.info("Saavn nine search: %d hits for %r", len(songs), query)
            return songs
    except Exception as e:
        logger.error("Saavn nine search error: %s", e)
    try:
        params = {
            "__call": "search.getResults",
            "_format": "json",
            "_marker": "0",
            "cc": "in",
            "p": "1",
            "n": str(max(int(limit), 5)),
            "q": query,
            "api_version": "4",
            "ctx": "web6dot0",
        }
        async with aiohttp.ClientSession(headers=SAAVN_HEADERS) as session:
            async with session.get(SAAVN_API, params=params, timeout=timeout) as resp:
                data = await resp.json(content_type=None)
        raw = []
        if isinstance(data, dict):
            raw = data.get("results") or []
            if not raw and isinstance(data.get("data"), dict):
                raw = data["data"].get("results") or []
        for r in (raw or [])[:limit]:
            if not isinstance(r, dict):
                continue
            mi = r.get("more_info") if isinstance(r.get("more_info"), dict) else {}
            enc = r.get("encrypted_media_url") or (mi or {}).get("encrypted_media_url")
            if not enc:
                continue
            auth = await saavn_auth_url(enc)
            if not auth:
                continue
            songs.append({
                "title": r.get("title") or r.get("song") or "Unknown",
                "duration": _saavn_duration(r),
                "uploader": _saavn_artist(r),
                "album": (mi or {}).get("album") or "",
                "year": str((mi or {}).get("year") or ""),
                "quality": "320kbps" if (mi or {}).get("320kbps") else ((mi or {}).get("quality") or ""),
                "webpage_url": r.get("perma_url") or r.get("url") or auth or "",
                "direct_url": auth,
                "enc_url": enc,
                "thumbnail": _saavn_thumb(r),
                "source": "saavn",
            })
        if songs:
            logger.info("Saavn official search: %d hits for %r", len(songs), query)
    except Exception as e:
        logger.error("Saavn official search error: %s", e)
    return songs

SPOTIFY_TOKEN = {"token": None, "expires": 0}

def spotify_enabled():
    return bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)

def spotify_setup_help():
    return (
        f"🟢 『{BRAND}』 — {stylish('Spotify API Setup')}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{stylish('Free keys banao (2 min)')}:\n"
        "1️⃣ https://developer.spotify.com/dashboard\n"
        "2️⃣ Login → Create app (name: DEV X CORE)\n"
        "3️⃣ App settings me Client ID + Client Secret milega\n"
        "4️⃣ Optional env: SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{stylish('Bina keys ke bhi chalega')}: YouTube · Saavn · Deezer · SoundCloud"
    )

async def spotify_get_token():
    if SPOTIFY_TOKEN["token"] and time.time() < SPOTIFY_TOKEN["expires"] - 60:
        return SPOTIFY_TOKEN["token"]
    if not spotify_enabled():
        return None
    try:
        import base64 as _b64
        cred = _b64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {cred}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                timeout=timeout,
            ) as r:
                data = await r.json(content_type=None)
        tok = data.get("access_token")
        if tok:
            SPOTIFY_TOKEN["token"] = tok
            SPOTIFY_TOKEN["expires"] = time.time() + int(data.get("expires_in", 3600))
        return tok
    except Exception as e:
        logger.error("Spotify token error: %s", e)
        return None

def _sp_track_to_song(t):
    name = t.get("name") or "Unknown"
    artists = ", ".join(a.get("name", "") for a in (t.get("artists") or [])) or "Spotify"
    album = (t.get("album") or {}).get("name", "")
    images = (t.get("album") or {}).get("images") or []
    dur = int((t.get("duration_ms") or 0) / 1000)
    release = (t.get("album") or {}).get("release_date", "") or ""
    return {
        "title": name,
        "duration": dur,
        "uploader": artists,
        "album": album,
        "year": release[:4],
        "quality": "Spotify",
        "webpage_url": (t.get("external_urls") or {}).get("spotify") or "",
        "thumbnail": images[0].get("url", "") if images else "",
        "source": "spotify",
        "resolve_query": f"{name} {artists.split(',')[0]}",
    }

async def spotify_search(query, limit=3):
    try:
        tok = await spotify_get_token()
        if not tok:
            return []
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://api.spotify.com/v1/search",
                params={"q": query, "type": "track", "limit": str(max(int(limit), 3))},
                headers={"Authorization": f"Bearer {tok}"},
                timeout=timeout,
            ) as r:
                data = await r.json(content_type=None)
        items = ((data or {}).get("tracks") or {}).get("items") or []
        songs = [_sp_track_to_song(t) for t in items if isinstance(t, dict)]
        if songs:
            logger.info("Spotify search: %d hits for %r", len(songs), query)
        return songs[:limit]
    except Exception as e:
        logger.error("Spotify search error: %s", e)
        return []

SPOTIFY_LINK_RE = re.compile(r"open\.spotify\.com/(track|album|playlist)/([A-Za-z0-9]+)")

async def spotify_expand(query):
    m = SPOTIFY_LINK_RE.search(query or "")
    if not m:
        return None
    tok = await spotify_get_token()
    if not tok:
        raise RuntimeError("spotify_not_configured")
    kind, sid = m.group(1), m.group(2)
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"Authorization": f"Bearer {tok}"}
    items = []
    try:
        async with aiohttp.ClientSession() as s:
            if kind == "track":
                async with s.get(f"https://api.spotify.com/v1/tracks/{sid}",
                                 headers=headers, timeout=timeout) as r:
                    data = await r.json(content_type=None)
                items = [data] if data and data.get("name") else []
            else:
                url = f"https://api.spotify.com/v1/{kind}s/{sid}/tracks?limit=50"
                while url:
                    async with s.get(url, headers=headers, timeout=timeout) as r:
                        data = await r.json(content_type=None)
                    if kind == "playlist":
                        chunk = [(i.get("track") or {}) for i in (data.get("items") or [])]
                    else:
                        chunk = data.get("items") or []
                    items.extend(c for c in chunk if isinstance(c, dict) and c.get("name"))
                    url = data.get("next") or None
        songs = [_sp_track_to_song(t) for t in items]
        logger.info("Spotify expand %s/%s: %d tracks", kind, sid, len(songs))
        return songs
    except Exception as e:
        logger.error("Spotify expand error: %s", e)
        return []

DEEZER_LINK_RE = re.compile(r"deezer\.com/(?:[a-z]{2}/)?(track|album|playlist)/(\d+)")

def _dz_track_to_song(t):
    artist = (t.get("artist") or {}).get("name", "") if isinstance(t.get("artist"), dict) else ""
    album = (t.get("album") or {}).get("title", "") if isinstance(t.get("album"), dict) else ""
    cover = (t.get("album") or {}).get("cover_big", "") if isinstance(t.get("album"), dict) else ""
    title = t.get("title") or "Unknown"
    return {
        "title": title,
        "duration": int(t.get("duration") or 0),
        "uploader": artist or "Deezer",
        "album": album,
        "quality": "Deezer",
        "webpage_url": t.get("link") or "",
        "thumbnail": cover,
        "source": "deezer",
        "resolve_query": f"{title} {artist}",
    }

async def deezer_search(query, limit=3):
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{DEEZER_API}/search",
                             params={"q": query, "limit": str(max(int(limit), 3))},
                             timeout=timeout) as r:
                data = await r.json(content_type=None)
        items = ((data or {}).get("data") or []) if isinstance(data, dict) else []
        songs = [_dz_track_to_song(t) for t in items if isinstance(t, dict)]
        if songs:
            logger.info("Deezer search: %d hits for %r", len(songs), query)
        return songs[:limit]
    except Exception as e:
        logger.error("Deezer search error: %s", e)
        return []

async def deezer_expand(query):
    m = DEEZER_LINK_RE.search(query or "")
    if not m:
        return None
    kind, did = m.group(1), m.group(2)
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{DEEZER_API}/{kind}/{did}", timeout=timeout) as r:
                data = await r.json(content_type=None)
        if kind == "track":
            items = [data] if data and data.get("title") else []
        else:
            items = (((data or {}).get("tracks") or {}).get("data") or []) if isinstance(data, dict) else []
        songs = [_dz_track_to_song(t) for t in items if isinstance(t, dict)]
        logger.info("Deezer expand %s/%s: %d tracks", kind, did, len(songs))
        return songs
    except Exception as e:
        logger.error("Deezer expand error: %s", e)
        return []

def soundcloud_search(query, limit=2):
    try:
        opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "extract_flat": True,
            "socket_timeout": 15,
            "extractor_retries": 2,
        }
        if os.path.exists(COOKIES_FILE):
            opts["cookiefile"] = COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch{max(int(limit), 2)}:{query}", download=False)
        entries = (info or {}).get("entries") or []
        songs = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            songs.append({
                "title": e.get("title") or "Unknown",
                "duration": e.get("duration") or 0,
                "uploader": e.get("uploader") or e.get("channel") or "SoundCloud",
                "webpage_url": e.get("url") or e.get("webpage_url") or "",
                "thumbnail": e.get("thumbnail") or "",
                "source": "soundcloud",
            })
        if songs:
            logger.info("SoundCloud search: %d hits for %r", len(songs), query)
        return songs[:limit]
    except Exception as e:
        logger.error("SoundCloud search error: %s", e)
        return []
def _sync_play_loop(q):
    total = (1 if q.current is not None else 0) + len(q.songs)
    if total <= 1:
        q.repeat = True
        q.loop = False
    else:
        q.loop = True
        q.repeat = False
    q.silent_loop = True

async def _queue_songs(message, songs, natural=False, label=""):
    chat_id = message.chat.id
    q = get_queue(chat_id)
    if natural:
        for s in songs:
            s["normal"] = True
    q.songs.extend(songs)
    _sync_play_loop(q)
    if not q.current:
        q.current = q.songs.popleft()
        active_calls.add(chat_id)
        await play_song(chat_id, q.current)
    extra = f" +{len(songs) - 1} more" if len(songs) > 1 else ""
    await message.reply_text(
        f"✅ 『{BRAND}』 — {stylish('Added')}: {len(songs)} {stylish('tracks')}"
        + (f" · {label}" if label else "") + "\n"
        f"🎵 {songs[0]['title']}{extra}"
    )

async def _play_picked_songs(message, sid, indices, natural=False):
    results = search_cache.get(sid)
    if not results:
        await message.reply_text("❌ Search expired — dobara `.play <song>` karo.")
        return False, 0, None
    q = get_queue(message.chat.id)
    songs = []
    for i in indices:
        if 0 <= i < len(results):
            s = results[i]
            if natural:
                s["normal"] = True
            songs.append(s)
    if not songs:
        await message.reply_text(
            f"❌ {stylish('Invalid number')} — {stylish('Valid')}: `1`–`{len(results)}`"
        )
        return False, 0, None
    started = False
    q.songs.extend(songs)
    _sync_play_loop(q)
    if not q.current:
        q.current = q.songs.popleft()
        active_calls.add(message.chat.id)
        started = await play_song(message.chat.id, q.current)
        if not started:
            q.current = None
            return False, 0, None
    return started, len(songs), songs[0].get("title", "")

SOURCE_TAG = {"saavn": "🎧", "youtube": "📺", "soundcloud": "🟠",
              "spotify": "🟢", "deezer": "🔴"}

def _atempo_chain(speed):
    speed = float(speed)
    if speed <= 0.1:
        return "atempo=1.0"
    parts = []
    remaining = speed
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    parts.append(f"atempo={remaining:.3f}")
    return ",".join(parts)

def _loudspeaker_filter(level):
    lvl = max(0, min(100, int(level or 0)))
    vol = round(0.8 + (lvl / 100.0) * 6.2, 2)
    g60 = round((lvl / 100.0) * 4, 1)
    g120 = round((lvl / 100.0) * 3.5, 1)
    g250 = round(1 + (lvl / 100.0) * 3, 1)
    g500 = round(2 + (lvl / 100.0) * 3, 1)
    g1k = round(3 + (lvl / 100.0) * 3, 1)
    g8k = round(2 + (lvl / 100.0) * 3, 1)
    g14k = round(1 + (lvl / 100.0) * 3, 1)
    return (
        "loudnorm=I=-7:TP=-0.3:LRA=11,"
        f"equalizer=f=60:t=q:w=1.5:g={g60},"
        f"equalizer=f=120:t=q:w=1.5:g={g120},"
        f"equalizer=f=250:t=q:w=1.5:g={g250},"
        f"equalizer=f=500:t=q:w=1.2:g={g500},"
        f"equalizer=f=1000:t=q:w=1:g={g1k},"
        f"equalizer=f=8000:t=q:w=1:g={g8k},"
        f"equalizer=f=14000:t=q:w=1:g={g14k},"
        "alimiter=limit=0.92:attack=0.1:release=1,"
        f"volume={vol}"
    )

def _ultra_boost_filter(level):
    lvl = max(0, min(100, int(level or 0)))
    vol = round(1.0 + (lvl / 100.0) * 8.0, 2)
    g60 = round((lvl / 100.0) * 6, 1)
    g120 = round((lvl / 100.0) * 5, 1)
    g250 = round(1 + (lvl / 100.0) * 4, 1)
    g500 = round(2 + (lvl / 100.0) * 5, 1)
    g1k = round(3 + (lvl / 100.0) * 5, 1)
    g8k = round(3 + (lvl / 100.0) * 4, 1)
    g14k = round(2 + (lvl / 100.0) * 3, 1)
    echo = round(0.1 + (lvl / 100.0) * 0.15, 2)
    return (
        "loudnorm=I=-5:TP=-0.2:LRA=11,"
        f"equalizer=f=60:t=q:w=1.5:g={g60},"
        f"equalizer=f=120:t=q:w=1.5:g={g120},"
        f"equalizer=f=250:t=q:w=1.5:g={g250},"
        f"equalizer=f=500:t=q:w=1.2:g={g500},"
        f"equalizer=f=1000:t=q:w=1:g={g1k},"
        f"equalizer=f=8000:t=q:w=1:g={g8k},"
        f"equalizer=f=14000:t=q:w=1:g={g14k},"
        f"aecho=0.6:0.7:40:{echo},"
        f"aecho=0.6:0.7:400:{round(echo * 0.7, 2)},"
        "alimiter=limit=0.88:attack=0.1:release=1,"
        f"volume={vol}"
    )

def _echo_filter(level):
    lvl = max(0, min(100, int(level or 0)))
    g1 = round((lvl / 100.0) * 0.5, 2)
    g2 = round(g1 * 0.8, 2)
    g3 = round(g1 * 0.6, 2)
    g4 = round(g1 * 0.45, 2)
    return (
        f"aecho=0.7:0.8:40:{g1},"
        f"aecho=0.6:0.7:200:{g2},"
        f"aecho=0.5:0.6:400:{g3},"
        f"aecho=0.4:0.5:800:{g4}"
    )

def _bass_filter(level):
    lvl = max(0, min(100, int(level or 0)))
    g = round((lvl / 100.0) * 20, 1)
    if g <= 0:
        return None
    return f"bass=g={g}:f=80:w=0.8"

def _treble_filter(level):
    lvl = max(0, min(100, int(level or 0)))
    g = round((lvl / 100.0) * 12, 1)
    if g <= 0:
        return None
    return f"equalizer=f=8000:t=q:w=1:g={g}"

def make_ffmpeg_params(boost_level=0, eco_level=0, loudspeaker_level=0, bass=0, treble=0,
                       loop=False, seek=None, speed=1.0, nightcore=False):
    filters = []
    if loudspeaker_level:
        filters.append(_loudspeaker_filter(loudspeaker_level))
    if boost_level:
        filters.append(_ultra_boost_filter(boost_level))
    if eco_level:
        filters.append(_echo_filter(eco_level))
    _b = _bass_filter(bass)
    if _b:
        filters.append(_b)
    _t = _treble_filter(treble)
    if _t:
        filters.append(_t)
    if nightcore:
        filters.append("asetrate=44100*1.35,aresample=44100,atempo=1.35")
    else:
        try:
            _sp = float(speed or 1.0)
        except Exception:
            _sp = 1.0
        if _sp != 1.0:
            filters.append(_atempo_chain(_sp))
    first = "-stream_loop -1" if loop else ""
    seek_pre = f"-ss {int(seek)} " if (seek and int(seek) > 0) else ""
    if filters:
        return f"{seek_pre}{first} ---mid -filter:a ---mid {','.join(filters)}"
    if loop:
        return f"{seek_pre}-stream_loop -1"
    if seek_pre:
        return seek_pre.strip()
    return None

def build_stream(source, boost_level=0, eco_level=0, loudspeaker_level=0, bass=0, treble=0,
                  loop=False, seek=None, speed=1.0, nightcore=False, headers=None):
    return MediaStream(
        source,
        audio_parameters=AudioQuality.HIGH,
        video_flags=MediaStream.Flags.IGNORE,
        ffmpeg_parameters=make_ffmpeg_params(boost_level, eco_level, loudspeaker_level, bass, treble,
                                             loop=loop, seek=seek, speed=speed, nightcore=nightcore),
        headers=headers,
    )

def build_video_stream(source, boost_level=0, eco_level=0, loudspeaker_level=0, bass=0, treble=0,
                       loop=False, seek=None, speed=1.0, nightcore=False, headers=None):
    return MediaStream(
        source,
        audio_parameters=AudioQuality.HIGH,
        video_parameters=VideoQuality.HD_720p,
        ffmpeg_parameters=make_ffmpeg_params(boost_level, eco_level, loudspeaker_level, bass, treble,
                                             loop=loop, seek=seek, speed=speed, nightcore=nightcore),
        headers=headers,
    )

music = Client(
    SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True,
)

bot = Client(
    "login_helper_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

vc = None
music_started = False
login_state = {}

def vc_ready():
    return vc is not None and music_started

async def _engine_down_reply(message):
    try:
        await message.reply_text(
            f"❌ 『{BRAND}』 — {stylish('Voice engine not running')}\n\n"
            f"{stylish('PyTgCalls failed to start (see server logs).')}\n\n"
            f"🔧 {stylish('Fix the version mismatch')}:\n"
            "`pip install \"pyrogram==2.0.106\" \"py-tgcalls[pyrogram]==2.2.5\"`\n"
            f"{stylish('then restart the bot.')}\n\n"
            f"👉 {stylish('Check')} /status {stylish('on the login bot')} · `.diag` {stylish('here')}."
        )
    except Exception:
        pass

def needs_vc(func):
    @functools.wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        if not vc_ready():
            await _engine_down_reply(message)
            return
        return await func(client, message, *args, **kwargs)
    return wrapper

def player_panel(q=None):
    q = q or MusicQueue()
    loop_txt = "Loop ON" if q.loop else "Loop OFF"
    rep_txt = "Repeat ON" if q.repeat else "Repeat OFF"
    boost_txt = f"Boost {q.boost_level}%" if q.boost_level else "Boost OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏸", callback_data="cb_pause"),
         InlineKeyboardButton("▶", callback_data="cb_resume"),
         InlineKeyboardButton("⏭", callback_data="cb_skip"),
         InlineKeyboardButton("⏹", callback_data="cb_stop")],
        [InlineKeyboardButton(loop_txt, callback_data="cb_loop"),
         InlineKeyboardButton(rep_txt, callback_data="cb_repeat"),
         InlineKeyboardButton(boost_txt, callback_data="cb_boost")],
        [InlineKeyboardButton("Vol −", callback_data="cb_voldown"),
         InlineKeyboardButton("Mute", callback_data="cb_mute"),
         InlineKeyboardButton("200%", callback_data="cb_vol200"),
         InlineKeyboardButton("Vol +", callback_data="cb_volup")],
        [InlineKeyboardButton("▶  Play", callback_data="cb_play"),
         InlineKeyboardButton("🎙  Voice", callback_data="cb_voice")],
        [InlineKeyboardButton("🔊 Sound", callback_data="cb_sound"),
         InlineKeyboardButton("Queue", callback_data="cb_queue"),
         InlineKeyboardButton("Now", callback_data="cb_now")],
        [InlineKeyboardButton("Vault", callback_data="cb_files")],
        [InlineKeyboardButton("⌂  Hub", callback_data="cb_menu")],
    ])

def main_menu():
    return hub_keyboard()

def volume_panel(q):
    q = q or MusicQueue()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Mute", callback_data="cb_mute"),
         InlineKeyboardButton("200%", callback_data="cb_vol200")],
        [InlineKeyboardButton("− 10", callback_data="cb_voldown"),
         InlineKeyboardButton("+ 10", callback_data="cb_volup")],
        [InlineKeyboardButton("10%", callback_data="cb_vol_10"),
         InlineKeyboardButton("50%", callback_data="cb_vol_50")],
        [InlineKeyboardButton("100%", callback_data="cb_vol_100"),
         InlineKeyboardButton("150%", callback_data="cb_vol_150")],
        [InlineKeyboardButton("←  Deck", callback_data="cb_panel")],
    ])

def owner_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Stats", callback_data="cb_stats"),
         InlineKeyboardButton("Users", callback_data="cb_users")],
        [InlineKeyboardButton("Servers", callback_data="cb_servers"),
         InlineKeyboardButton("Broadcast", callback_data="cb_broadcast")],
        [InlineKeyboardButton("Vault", callback_data="cb_files"),
         InlineKeyboardButton("Wipe files", callback_data="cb_delall")],
        [InlineKeyboardButton("Lock", callback_data="cb_lock"),
         InlineKeyboardButton("Unlock", callback_data="cb_unlock")],
        [InlineKeyboardButton("👑 Add Admin", callback_data="cb_addadmin"),
         InlineKeyboardButton("🗑️ Del Admin", callback_data="cb_deladmin")],
        [InlineKeyboardButton("📋 Admin List", callback_data="cb_adminlist")],
        [InlineKeyboardButton("⌂  Hub", callback_data="cb_menu")],
    ])

def queue_panel(q, page=0, per_page=5):
    q = q or MusicQueue()
    songs = list(q.songs)
    total = len(songs)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages - 1)
    start = page * per_page
    chunk = songs[start:start + per_page]

    body = ""
    if q.current:
        body += f"  ▸  now  **{q.current.get('title','?')}**\n\n"
    if not chunk:
        body += f"  {stylish('queue is empty.')}"
    for i, s in enumerate(chunk, start + 1):
        body += f"  `{i}.` {s.get('title','?')}  ·  {fmt_duration(s.get('duration',0))}\n"
    body += (
        f"\n  {stylish('page')} {page+1}/{pages}  ·  {total} {stylish('tracks')}\n"
        f"  loop {'on' if q.loop else 'off'}  ·  repeat {'on' if q.repeat else 'off'}  ·  {fmt_vol(q.volume)}"
    )
    text = core_card("queue", body)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cb_qpage_{page-1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"cb_qpage_{page+1}"))
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton("🎛️ Panel", callback_data="cb_panel")])
    return text, InlineKeyboardMarkup(rows)

BANNER = None

def get_banner():
    return hub_home_text()
async def download_saavn_file(url):
    path = os.path.join(TEMP_DIR, f"saavn_{uuid.uuid4().hex}.m4a")
    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(headers=SAAVN_HEADERS) as session:
        async with session.get(url, timeout=timeout, allow_redirects=True) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Saavn download HTTP {resp.status}")
            with open(path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 256):
                    f.write(chunk)
    if not os.path.exists(path) or os.path.getsize(path) < 1024:
        raise RuntimeError("Saavn download empty / too small")
    return path

def download_youtube_file(query):
    path = os.path.join(TEMP_DIR, f"yt_{uuid.uuid4().hex}.m4a")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_retries": 2,
        "retries": 2,
        "socket_timeout": 20,
        "nocheckcertificate": True,
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    else:
        opts["extractor_args"] = {
            "youtube": {"player_client": ["android", "android_vr", "tv_embedded", "web_embedded"]}
        }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(query, download=True)
    return path

YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/|/v/)([A-Za-z0-9_-]{11})")

def extract_youtube_id(query):
    m = YT_ID_RE.search(query or "")
    return m.group(1) if m else None

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://yewtu.be",
    "https://invidious.f5.si",
]

async def invidious_stream_url(video_id):
    if not video_id:
        return None
    for base in INVIDIOUS_INSTANCES:
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{base}/api/v1/videos/{video_id}", timeout=timeout) as r:
                    data = await r.json(content_type=None)
            fmts = (data or {}).get("adaptiveFormats") or (data or {}).get("formatStreams") or []
            best = None
            for f in fmts:
                if not isinstance(f, dict):
                    continue
                if "audio" in (f.get("type") or ""):
                    if best is None or int(f.get("bitrate") or 0) > int(best.get("bitrate") or 0):
                        best = f
            if best and best.get("url"):
                logger.info("Invidious hit: %s (%s)", base, best.get("type"))
                return best["url"]
        except Exception as e:
            logger.warning("Invidious %s fail: %s", base, e)
            continue
    return None

async def download_http_audio(url):
    path = os.path.join(TEMP_DIR, f"inv_{uuid.uuid4().hex}.m4a")
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            with open(path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 256):
                    f.write(chunk)
    if not os.path.exists(path) or os.path.getsize(path) < 1024:
        raise RuntimeError("download empty")
    return path

async def _search_guard(coro, seconds=15):
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except Exception as e:
        logger.warning("search guarded (%ss): %s", seconds, e)
        return []

async def _fetch_youtube_audio(query, title, chat_id, video=False, max_wait=100):
    try:
        if video:
            local = await asyncio.wait_for(
                asyncio.to_thread(download_youtube_video, query), timeout=max_wait)
        else:
            local = await asyncio.wait_for(
                asyncio.to_thread(download_youtube_file, query), timeout=max_wait)
        if local and os.path.exists(local) and os.path.getsize(local) > 1024:
            return local, "youtube"
    except Exception as e:
        logger.warning("yt-dlp download fail (%s) -> fallback chain", e)

    if not video:
        vid = extract_youtube_id(query)
        if vid:
            try:
                url = await asyncio.wait_for(invidious_stream_url(vid), timeout=40)
                if url:
                    local = await asyncio.wait_for(download_http_audio(url), timeout=90)
                    if local:
                        return local, "invidious"
            except Exception as e:
                logger.warning("Invidious fallback fail: %s", e)

        if title:
            try:
                hits = await asyncio.wait_for(saavn_search(title, limit=1), timeout=25)
                if hits and hits[0].get("direct_url"):
                    local = await asyncio.wait_for(
                        download_saavn_file(hits[0]["direct_url"]), timeout=90)
                    if local:
                        return local, "saavn"
            except Exception as e:
                logger.warning("Saavn fallback fail: %s", e)
    raise RuntimeError("All download sources failed — .ytupdate karke retry karo")

def download_youtube_video(query):
    uid = uuid.uuid4().hex
    outtmpl = os.path.join(TEMP_DIR, f"ytv_{uid}.%(ext)s")
    opts = {
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_retries": 2,
        "retries": 2,
        "socket_timeout": 20,
        "nocheckcertificate": True,
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    else:
        opts["extractor_args"] = {
            "youtube": {"player_client": ["android", "android_vr", "tv_embedded", "web_embedded"]}
        }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query, download=True)
        path = ydl.prepare_filename(info)
    if path and os.path.exists(path):
        return path
    base = os.path.join(TEMP_DIR, f"ytv_{uid}")
    for ext in (".mp4", ".mkv", ".webm", ".m4a"):
        cand = base + ext
        if os.path.exists(cand):
            return cand
    raise RuntimeError("YouTube video download produced no file")

async def _build_stream_for(song, q, seek=None):
    src = song.get("source", "youtube")
    normal = bool(song.get("normal"))
    do_loop = bool(q.repeat)
    chat_id = song.get("chat_id") or 0
    speed = float(getattr(q, "speed", 1.0) or 1.0)
    nightcore = bool(getattr(q, "nightcore", False))
    bass = int(getattr(q, "bass", 0) or 0)
    treble = int(getattr(q, "treble", 0) or 0)
    loudspeaker_level = 0
    if not normal:
        if int(getattr(q, "loud_level", 0) or 0) > 0:
            loudspeaker_level = int(q.loud_level)
        elif int(getattr(q, "gain_level", 0) or 0) > 0:
            loudspeaker_level = int(q.gain_level)
        elif song.get("loudspeaker"):
            loudspeaker_level = 100
    boost_level = int(getattr(q, "boost_level", 0) or 0) if not normal else 0
    eco_level = int(getattr(q, "eco_level", 0) or 0) if not normal else 0

    existing = song.get("local_path") or song.get("_file")
    if existing and os.path.exists(existing):
        song["_file"] = existing
        song["local_path"] = existing
        if not song.get("temp"):
            register_saved_file(existing, song.get("title"), song.get("source", "local"), chat_id)
        if song.get("video"):
            return build_video_stream(existing, loop=do_loop, seek=seek, speed=speed, nightcore=nightcore,
                            bass=bass, treble=treble, loudspeaker_level=loudspeaker_level, boost_level=boost_level, eco_level=eco_level)
        return build_stream(existing, loop=do_loop, seek=seek, speed=speed, nightcore=nightcore,
                            bass=bass, treble=treble, loudspeaker_level=loudspeaker_level, boost_level=boost_level, eco_level=eco_level)

    if src in ("spotify", "deezer"):
        rq = song.get("resolve_query") or f"{song.get('title', '')} {song.get('uploader', '')}"
        local, via = await _fetch_youtube_audio(
            f"ytsearch1:{rq}", song.get("title", ""), chat_id)
        if normal:
            register_saved_file(local, song.get("title"), src, chat_id)
        else:
            song["temp"] = True
        song["_file"] = local
        song["local_path"] = local
        return build_stream(local, loop=do_loop, seek=seek, speed=speed, nightcore=nightcore,
                            bass=bass, treble=treble, loudspeaker_level=loudspeaker_level, boost_level=boost_level, eco_level=eco_level)

    if src == "soundcloud":
        query = song.get("webpage_url") or song.get("direct_url")
        if not query:
            raise RuntimeError("SoundCloud URL missing")
        local = await asyncio.wait_for(
            asyncio.to_thread(download_youtube_file, query), timeout=120)
        if normal:
            register_saved_file(local, song.get("title"), src, chat_id)
        else:
            song["temp"] = True
        song["_file"] = local
        song["local_path"] = local
        return build_stream(local, loop=do_loop, seek=seek, speed=speed, nightcore=nightcore,
                            bass=bass, treble=treble, loudspeaker_level=loudspeaker_level, boost_level=boost_level, eco_level=eco_level)

    if src == "saavn":
        direct = song.get("direct_url")
        enc = song.get("enc_url")
        if enc:
            fresh = await saavn_auth_url(enc)
            if fresh:
                direct = fresh
                song["direct_url"] = fresh
        if not direct:
            raise RuntimeError("Saavn stream URL missing")
        local = await asyncio.wait_for(download_saavn_file(direct), timeout=120)
        if normal:
            register_saved_file(local, song.get("title"), src, chat_id)
        else:
            song["temp"] = True
        song["_file"] = local
        song["local_path"] = local
        return build_stream(local, loop=do_loop, seek=seek, speed=speed, nightcore=nightcore,
                            bass=bass, treble=treble, loudspeaker_level=loudspeaker_level, boost_level=boost_level, eco_level=eco_level)

    if src == "radio":
        url = song.get("direct_url")
        if not url:
            raise RuntimeError("Radio stream URL missing")
        return build_stream(url, loop=False, seek=seek, speed=speed, nightcore=nightcore,
                            bass=bass, treble=treble, loudspeaker_level=loudspeaker_level,
                            boost_level=boost_level, eco_level=eco_level)

    query = song.get("webpage_url") or song.get("direct_url")
    if song.get("video"):
        local = await asyncio.wait_for(
            asyncio.to_thread(download_youtube_video, query), timeout=150)
        if normal:
            register_saved_file(local, song.get("title"), src, chat_id)
        else:
            song["temp"] = True
        song["_file"] = local
        song["local_path"] = local
        return build_video_stream(local, loop=do_loop, seek=seek, speed=speed, nightcore=nightcore,
                            bass=bass, treble=treble, loudspeaker_level=loudspeaker_level, boost_level=boost_level, eco_level=eco_level)
    local, via = await _fetch_youtube_audio(query, song.get("title", ""), chat_id)
    if normal:
        register_saved_file(local, song.get("title"), "youtube", chat_id)
    else:
        song["temp"] = True
    song["_file"] = local
    song["local_path"] = local
    return build_stream(local, loop=do_loop, seek=seek, speed=speed, nightcore=nightcore,
                            bass=bass, treble=treble, loudspeaker_level=loudspeaker_level, boost_level=boost_level, eco_level=eco_level)

def _is_join_error(e):
    s = str(e)
    return ("GROUPCALL" in s.upper()) or ("JOINGROUPCALL" in s.upper()) or ("NOT_IN_CALL" in s.upper())

async def play_song(chat_id, song, announce=True, silent=False, seek=None):
    q = get_queue(chat_id)

    if not vc_ready():
        active_calls.discard(chat_id)
        if not silent:
            await _engine_down_reply_play(chat_id)
        return False

    st = None
    if announce and not silent and not (song.get("local_path") and os.path.exists(song.get("local_path") or "")):
        try:
            st = await music.send_message(chat_id, f"⏳ 『{BRAND}』 — {stylish('Downloading audio')}…")
        except Exception:
            st = None

    try:
        song["chat_id"] = chat_id
        stream = await _build_stream_for(song, q, seek=seek)
        current_files[chat_id] = song.get("_file") or song.get("local_path")

        last_err = None
        for attempt in range(4):
            try:
                await vc.play(chat_id, stream)
                last_err = None
                break
            except NoActiveGroupCall:
                raise
            except Exception as e:
                last_err = e
                if _is_join_error(e):
                    logger.warning("Join error (attempt %d): %s", attempt + 1, e)
                    try:
                        await vc.leave_call(chat_id)
                    except Exception:
                        pass
                    active_calls.discard(chat_id)
                    await asyncio.sleep(3)
                    continue
                raise
        if last_err is not None:
            raise last_err

        _reset_timer(chat_id, seek)

        if _vol_auto.get(chat_id, True):
            q.volume = AUTO_MAX_VOLUME
        try:
            await vc.change_volume_call(chat_id, q.volume)
            _last_vol_applied[chat_id] = q.volume
        except Exception:
            pass
        END_GUARD.pop(chat_id, None)
        db.bump("total_played")
        err_notified.discard(chat_id)
        logger.info("Now playing: %s", song.get("title"))
        if announce and not silent:
            try:
                np = now_playing_text(song)
                kb = player_panel(q)
                if st is not None:
                    await st.edit_text(np, reply_markup=kb)
                else:
                    await music.send_message(chat_id, np, reply_markup=kb)
            except Exception:
                pass
        return True
    except NoActiveGroupCall:
        active_calls.discard(chat_id)
        current_files.pop(chat_id, None)
        _delete_temp_song_files(song)
        if st is not None:
            try:
                await st.delete()
            except Exception:
                pass
        if not silent:
            try:
                await music.send_message(
                    chat_id,
                    f"❌ 『{BRAND}』 — {stylish('No active voice chat')}\n\n"
                    "Start a **voice chat** in this group first.\n"
                    "Also make sure this account is an **admin** in the group,\n"
                    "so it can auto-join the voice chat.\n\n"
                    "👉 Then run `.play <song>` again.",
                )
            except Exception:
                pass
        return False
    except Exception as e:
        logger.error("Play error: %s", e)
        active_calls.discard(chat_id)
        current_files.pop(chat_id, None)
        _delete_temp_song_files(song)
        if st is not None:
            try:
                await st.delete()
            except Exception:
                pass
        if not silent:
            try:
                await music.send_message(
                    chat_id,
                    f"❌ 『{BRAND}』 — {stylish('Playback failed')}\n"
                    f"`{e}`\n\n"
                    f"👉 Run `.diag` to check the problem.\n"
                    f"💡 {stylish('Tip: .ytupdate karke retry karo')}.\n"
                    f"💡 {stylish('Ya restart the voice chat, then retry')}.",
                )
            except Exception:
                pass
        return False

async def reapply_current_effects(chat_id):
    q = get_queue(chat_id)
    if not q.current:
        return False
    pos = max(0, int(get_elapsed(chat_id)))
    dur = int(q.current.get("duration") or 0)
    if pos and dur and pos >= dur:
        if q.repeat or q.loop:
            pos = pos % dur
        else:
            pos = 0
    return await play_song(chat_id, q.current, announce=False, seek=pos)

async def _engine_down_reply_play(chat_id):
    try:
        await music.send_message(
            chat_id,
            f"❌ 『{BRAND}』 — {stylish('Voice engine not running')}\n\n"
            f"{stylish('PyTgCalls failed to start. Version mismatch?')}\n"
            "Fix:\n"
            "`pip install \"pyrogram==2.0.106\" \"py-tgcalls[pyrogram]==2.2.5\"`\n"
            f"{stylish('then restart the bot.')}\n\n"
            f"👉 /status {stylish('on the login bot')} · `.diag` {stylish('here')}",
        )
    except Exception:
        pass

def now_playing_text(song):
    icon = "🎬" if song.get("video") else ("🎙️" if song.get("local_path") else "🎵")
    lines = [
        f"▶️ 『{BRAND}』 — {stylish('Now Playing')}",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"{icon} {song.get('title', 'Unknown')}",
        f"⏱️ {fmt_duration(song.get('duration', 0))}",
        f"👤 {song.get('uploader', 'DEV X CORE')}",
    ]
    if song.get("album"):
        line = f"💿 {song.get('album')}"
        if song.get("year"):
            line += f" · 📅 {song.get('year')}"
        lines.append(line)
    if song.get("quality"):
        lines.append(f"🔊 {song.get('quality')}")
    if song.get("normal"):
        lines.append(f"🎧 {stylish('natural sound — no effects')}")
    return "\n".join(lines)
async def on_stream_end(pytgcalls_client, update: StreamEnded):
    if not vc_ready():
        return
    chat_id = update.chat_id
    q = get_queue(chat_id)
    if not q.current:
        return
    if q.repeat:
        if chat_id in replay_lock:
            return
        path = q.current.get("local_path") or q.current.get("_file")
        if path and not os.path.exists(path):
            q.repeat = False
            q.current = None
            current_files.pop(chat_id, None)
            active_calls.discard(chat_id)
            PLAY_TIMERS.pop(chat_id, None)
            if chat_id not in err_notified:
                err_notified.add(chat_id)
                try:
                    await music.send_message(
                        chat_id,
                        f"❌ 『{BRAND}』 — {stylish('Loop stopped')}\n"
                        f"{stylish('Saved file is missing. Use .run / .vrun again.')}",
                    )
                except Exception:
                    pass
            return
        replay_lock.add(chat_id)
        try:
            _pos = max(0, int(get_elapsed(chat_id)))
            ok = await play_song(chat_id, q.current, announce=False, silent=True, seek=_pos)
            if not ok and chat_id not in err_notified:
                err_notified.add(chat_id)
                try:
                    await music.send_message(
                        chat_id,
                        f"❌ 『{BRAND}』 — {stylish('Loop stopped')}\n"
                        f"{stylish('Could not restart. Check voice chat, then .run again.')}",
                    )
                except Exception:
                    pass
                q.repeat = False
                active_calls.discard(chat_id)
                PLAY_TIMERS.pop(chat_id, None)
        finally:
            replay_lock.discard(chat_id)
        return
    _elapsed = get_elapsed(chat_id)
    _dur = int(q.current.get("duration") or 0)
    _natural = False
    if _dur and _elapsed >= _dur - 3:
        _natural = True
    elif not _dur:
        _now_t = time.time()
        _g = END_GUARD.get(chat_id)
        if _g and (_now_t - _g["ts"]) < 60:
            _g["count"] += 1
        else:
            _g = {"count": 1, "ts": _now_t}
        END_GUARD[chat_id] = _g
        _natural = _g["count"] > 3
    if not _natural:
        _pos = max(0, int(_elapsed))
        await play_song(chat_id, q.current, announce=False, silent=True, seek=_pos)
        return
    finished = q.current
    requeued = False
    if q.loop and q.current:
        q.songs.append(q.current)
        requeued = True
    current_files.pop(chat_id, None)
    q.current = None
    if q.songs:
        q.current = q.songs.popleft()
        await play_song(chat_id, q.current, announce=not q.silent_loop)
        if not requeued and finished is not None:
            _delete_temp_song_files(finished)
    else:
        if finished is not None:
            _delete_temp_song_files(finished)
        active_calls.discard(chat_id)
        PLAY_TIMERS.pop(chat_id, None)

async def auto_enforce_loop():
    while True:
        await asyncio.sleep(ENFORCE_INTERVAL)
        if not vc_ready():
            continue
        for chat_id in list(active_calls):
            q = get_queue(chat_id)
            if AUTO_UNMUTE and not _muted_state.get(chat_id):
                try:
                    await vc.unmute(chat_id)
                except Exception:
                    pass
            if _last_vol_applied.get(chat_id) != q.volume:
                try:
                    await vc.change_volume_call(chat_id, q.volume)
                    _last_vol_applied[chat_id] = q.volume
                except Exception:
                    pass

async def download_reply_media(message: Message):
    r = message.reply_to_message
    if r is None:
        return None
    media = None
    ext = "bin"
    title = None
    if r.audio:
        media, ext = r.audio, (r.audio.file_name or "audio.mp3").rsplit(".", 1)[-1]
        title = getattr(r.audio, "title", None) or r.audio.file_name
    elif r.voice:
        media, ext = r.voice, "ogg"
        title = "voice_note.ogg"
    elif r.video:
        media, ext = r.video, (r.video.file_name or "video.mp4").rsplit(".", 1)[-1]
        title = r.video.file_name or "video.mp4"
    elif r.video_note:
        media, ext = r.video_note, "mp4"
        title = "video_note.mp4"
    elif r.document and (r.document.mime_type or "").startswith(("audio/", "video/")):
        media, ext = r.document, (r.document.file_name or "doc.bin").rsplit(".", 1)[-1]
        title = r.document.file_name
    else:
        return None
    path = os.path.join(TEMP_DIR, f"{message.chat.id}_{message.id}.{ext}")
    try:
        await r.download(file_name=path)
        register_saved_file(path, title or os.path.basename(path), "local", message.chat.id)
        return path
    except Exception as e:
        logger.error("Download error: %s", e)
        return None

@music.on_message(filters.command("join", prefixes=PREFIX))
@needs_vc
async def join_cmd(client, message):
    chat_id = message.chat.id
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    try:
        await vc.play(chat_id)
        active_calls.add(chat_id)
        await message.reply_text(f"✅ 『{BRAND}』 — {stylish('Joined voice chat!')}\n\nNow run `.play <song>`.")
    except NoActiveGroupCall:
        await message.reply_text(
            f"❌ {stylish('No voice chat found')}\n\n"
            "Start a **voice chat** in this group first, then run `.join` again."
        )
    except Exception as e:
        await message.reply_text(f"❌ Join failed: `{e}`\n\n👉 Make sure this account is **admin** in the group.")

@music.on_message(filters.command("diag", prefixes=PREFIX))
async def diag_cmd(client, message):
    import shutil
    chat_id = message.chat.id
    q = get_queue(chat_id)
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None
    in_call = chat_id in active_calls
    cur = q.current
    admin_ok = await is_group_admin(client, chat_id, client.me.id if hasattr(client, 'me') else OWNER_ID)
    try:
        from importlib.metadata import version as _dist_version
        pt_version = _dist_version("py-tgcalls")
    except Exception:
        pt_version = "?"
    compat_ok, compat_msg = check_engine_compat()
    try:
        yt_version = yt_dlp.version.__version__
    except Exception:
        yt_version = "?"
    lines = [
        f"🩺 『{BRAND}』 — {stylish('Diagnostic')}",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"🔧 ffmpeg: {'✅ INSTALLED' if ffmpeg_ok else '❌ MISSING'}",
        f"🔧 ffprobe: {'✅ INSTALLED' if ffprobe_ok else '❌ MISSING'}",
        f"🎵 Music bot: {'✅ RUNNING' if music_started else '❌ NOT STARTED'}",
        f"📞 In voice call: {'✅ YES' if in_call else '❌ NO — start a voice chat first!'}",
        f"🎶 Current song: {cur.get('title') if cur else '❌ NONE'}",
        f"👑 Account admin here: {'✅ YES' if admin_ok else '❌ NO — make bot admin to auto-join'}",
        f"🔗 pytgcalls: `{pt_version}` · {'✅ compatible' if compat_ok else '❌ INCOMPATIBLE'}",
        f"🎭 Mode: `{get_mode()}`",
        f"📦 yt-dlp: `{yt_version}`",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]
    lines.append(f"💡 {stylish('yt-dlp purana ho to')}: `.ytupdate` ({stylish('owner')})")
    if not compat_ok:
        lines.append(f"💊 {stylish('Fix')}: `pip install \"pyrogram==2.0.106\" \"py-tgcalls[pyrogram]==2.2.5\"`")
    await message.reply_text("\n".join(lines))

@music.on_message(filters.command("start", prefixes=PREFIX) & filters.private)
async def start_cmd(client, message):
    u = message.from_user
    db.add_user(u.id, u.username, u.first_name, u.last_name or "")
    await send_with_banner(
        message,
        hub_home_text(f"  {stylish('welcome')}, **{u.first_name}**.\n  {stylish('add me to a group + start vc.')}"),
        hub_keyboard(),
    )

CMD_HELP = {
    "play": ".play — 🎵 gaana search karke play",
    "rjoin": ".rjoin — 🔁 call pe auto-join; .rjoin 1,2,3 = files repeat pe",
    "nplay": ".nplay — 🎧 natural",
    "run": ".run — loop media",
    "vrun": ".vrun — video loop",
    "skip": ".skip — skip",
    "pause": ".pause — pause",
    "resume": ".resume — resume",
    "stop": ".stop — stop",
    "now": ".now — now playing",
    "queue": ".queue — queue",
    "loop": ".loop — loop queue",
    "repeat": ".repeat — repeat track",
    "volume": ".volume — volume",
    "menu": ".menu — main menu",
    "files": ".files — saved files",
}

def help_panel():
    return hub_keyboard()

HELP_PAGES = {
    "hpg_music": ("♪ music deck", page_music_text),
    "hpg_files": ("📁 vault / files", page_files_text),
    "hpg_tools": ("🛠️ toolkit", page_tools_text),
    "hpg_fun": ("🎮 fun deck", page_fun_text),
    "hpg_admin": ("👑 control room", page_admin_text),
}

def help_nav(current="hpg_music"):
    def btn(label, key):
        return InlineKeyboardButton(("▸ " if key == current else "") + label,
                                    callback_data=key)
    return InlineKeyboardMarkup([
        [btn("🎵 Music", "hpg_music"), btn("📁 Vault", "hpg_files")],
        [btn("🛠️ Tools", "hpg_tools"), btn("🎮 Fun", "hpg_fun")],
        [btn("👑 Admin", "hpg_admin"),
         InlineKeyboardButton("⌂ Hub", callback_data="cb_menu")],
    ])

async def _show_help_page(message, page_key="hpg_music"):
    _title, fn = HELP_PAGES.get(page_key, HELP_PAGES["hpg_music"])
    text = fn()
    if len(text) > 1024:
        text = text[:1020] + "…"
    await send_with_banner(message, text, help_nav(page_key))

@music.on_message(filters.command(["help", "cmds"], prefixes=PREFIX))
async def help_cmd(client, message):
    await _show_help_page(message)

@music.on_message(filters.command("menu", prefixes=PREFIX))
async def menu_cmd(client, message):
    await send_with_banner(message, hub_home_text(), hub_keyboard())

@music.on_message(filters.command("panel", prefixes=PREFIX))
async def panel_cmd(client, message):
    await message.reply_text(
        core_card("player deck", stylish("transport  ·  loop  ·  boost  ·  volume")),
        reply_markup=player_panel(get_queue(message.chat.id)),
    )
@music.on_message(filters.command(["files", "saved", "listfiles"], prefixes=PREFIX))
async def files_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    text, kb = files_list_text(page=0)
    await message.reply_text(text, reply_markup=kb)

@music.on_message(filters.command(["del", "delete"], prefixes=PREFIX))
async def del_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    if len(message.command) < 2:
        await message.reply_text(
            f"❌ {stylish('Usage')}:\n"
            f"`.del 1-10` — {stylish('delete 1 to 10')}\n"
            f"`.del 1,2,3` — {stylish('delete selected')}\n"
            f"`.files` — {stylish('see the list first')}"
        )
        return
    sync_saved_files()
    rows = db.get_files()
    if not rows:
        await message.reply_text(f"📭 {stylish('No saved files.')}")
        return
    spec = "".join(message.command[1:])
    try:
        indices = parse_index_spec(spec, len(rows))
    except ValueError:
        await message.reply_text(f"❌ {stylish('Invalid list.')}\nExamples: `.del 1-10`  ·  `.del 1,2,3`")
        return
    if not indices:
        await message.reply_text(f"❌ {stylish('No matching numbers.')}\n{stylish('Valid range')}: `1`–`{len(rows)}`")
        return
    deleted, skipped, missing = delete_files_by_indices(indices)
    lines = [
        f"🗑 『{BRAND}』 — {stylish('Delete Files')}",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"✅ {stylish('Deleted')}: {len(deleted)}",
    ]
    for name in deleted[:15]:
        lines.append(f"  • {name[:50]}")
    if skipped:
        lines.append(f"▶️ {stylish('Skipped (playing)')}: {len(skipped)}")
    text, kb = files_list_text(page=0)
    await message.reply_text("\n".join(lines) + "\n\n" + text, reply_markup=kb)

@music.on_message(filters.command(["delall", "deleteall"], prefixes=PREFIX))
async def delall_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    deleted, skipped = delete_all_saved_files()
    await message.reply_text(
        f"🗑 『{BRAND}』 — {stylish('Delete All')}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ {stylish('Deleted')}: {deleted}\n"
        f"▶️ {stylish('Skipped (now playing)')}: {skipped}\n"
        "━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=main_menu(),
    )

@music.on_message(filters.command("play", prefixes=PREFIX))
@needs_vc
async def play_cmd(client, message):
    chat_id = message.chat.id
    q = get_queue(chat_id)
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    if message.reply_to_message:
        path = await download_reply_media(message)
        if path:
            song = {
                "title": os.path.basename(path),
                "duration": 0,
                "uploader": "DEV X MUSIC",
                "local_path": path,
                "source": "local",
                "temp": True,
            }
            db.bump("total_voice")
            q.songs.append(song)
            _sync_play_loop(q)
            if not q.current:
                q.current = q.songs.popleft()
                active_calls.add(chat_id)
                await play_song(chat_id, q.current)
            else:
                await message.reply_text(f"✅ Queued: **{song['title']}**")
            return
    if len(message.command) < 2:
        await message.reply_text(
            f"❌ Please provide a song name or URL.\nExample: `{PREFIX}play despacito`",
            reply_markup=main_menu(),
        )
        return
    query = " ".join(message.command[1:])
    st = await message.reply_text(f"🔎 『{BRAND}』 — {stylish('Searching')}…")
    if is_url(query):
        if "open.spotify.com" in query:
            try:
                sp = await spotify_expand(query)
            except RuntimeError:
                await st.delete()
                await message.reply_text(spotify_setup_help())
                return
            if not sp:
                await st.delete()
                await message.reply_text("❌ Spotify link se tracks nahi mile.")
                return
            await st.delete()
            await _queue_songs(message, sp, natural=False, label="🎵 playlist")
            return
        if "deezer.com" in query:
            dz = await deezer_expand(query)
            if not dz:
                await st.delete()
                await message.reply_text("❌ Deezer link se tracks nahi mile.")
                return
            await st.delete()
            await _queue_songs(message, dz, natural=False, label="🎵 playlist")
            return
        song = await _search_guard(asyncio.to_thread(resolve_song, query), 25)
        await st.delete()
        if not song:
            await message.reply_text("❌ Couldn't find that song.", reply_markup=main_menu())
            return
        if "soundcloud.com" in query:
            song["source"] = "soundcloud"
        q.songs.append(song)
        _sync_play_loop(q)
        if not q.current:
            q.current = q.songs.popleft()
            active_calls.add(chat_id)
            await play_song(chat_id, q.current)
        else:
            await message.reply_text(
                f"✅ 『{BRAND}』 — {stylish('Added')}:\n"
                f"🎵 {song['title']}\n⏱️ {fmt_duration(song['duration'])} — {stylish('Position')} {len(q.songs)}",
                reply_markup=player_panel(q),
            )
        return
    saavn_results, yt_results, sc_results, sp_results, dz_results = await asyncio.gather(
        _search_guard(saavn_search(query, limit=4), 15),
        _search_guard(asyncio.to_thread(resolve_songs, query, 4), 15),
        _search_guard(asyncio.to_thread(soundcloud_search, query, 2), 15),
        _search_guard(spotify_search(query, 3), 12),
        _search_guard(deezer_search(query, 3), 12),
    )
    await st.delete()
    results = (saavn_results or []) + (yt_results or []) + (sc_results or []) + (sp_results or []) + (dz_results or [])
    if not results:
        await message.reply_text("❌ No results found.", reply_markup=main_menu())
        return
    search_seq[0] += 1
    sid = search_seq[0]
    search_cache[sid] = results
    last_search[(chat_id, message.from_user.id)] = {"sid": sid, "natural": False, "ts": time.time()}
    text = search_results_text(results, query, natural=False)
    buttons = []
    for i, s in enumerate(results):
        tag = SOURCE_TAG.get(s.get("source"), "🎵")
        label = s['title'][:25]
        buttons.append([InlineKeyboardButton(
            f"{i+1}. {tag} {label}", callback_data=f"cb_pick_{sid}_{i}"
        )])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cb_cancel")])
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@music.on_message(filters.command("nplay", prefixes=PREFIX))
@needs_vc
async def nplay_cmd(client, message):
    chat_id = message.chat.id
    q = get_queue(chat_id)
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    if not message.reply_to_message and len(message.command) >= 2:
        arg = "".join(message.command[1:])
        sync_saved_files()
        rows = db.get_files()
        if arg.isdigit():
            await play_saved_index(message, int(arg), as_video=False, natural=True)
            return
        indices = resolve_file_spec(arg, rows)
        if indices:
            await play_saved_list(message, indices, as_video=False, natural=True)
            return
    if message.reply_to_message:
        path = await download_reply_media(message)
        if path:
            song = {
                "title": os.path.basename(path),
                "duration": 0,
                "uploader": "DEV X CORE",
                "local_path": path,
                "source": "local",
                "normal": True,
            }
            db.bump("total_voice")
            q.songs.append(song)
            _sync_play_loop(q)
            if not q.current:
                q.current = q.songs.popleft()
                active_calls.add(chat_id)
                await play_song(chat_id, q.current)
            else:
                await message.reply_text(f"✅ Queued (natural 🎧): **{song['title']}**")
            return
    if len(message.command) < 2:
        await message.reply_text(
            f"❌ Song name ya URL do.\nExample: `{PREFIX}nplay despacito`\n\n"
            f"🎧 {stylish('Natural sound')} — {stylish('no boost, no echo, no extra gain')}\n"
            f"💾 {stylish('Saved files')}: `.nplay 3` · `.nplay 1,2,3` · `.nplay all`",
            reply_markup=main_menu(),
        )
        return
    query = " ".join(message.command[1:])
    st = await message.reply_text(f"🔎 『{BRAND}』 — {stylish('Searching natural')}…")
    if is_url(query):
        if "open.spotify.com" in query:
            try:
                sp = await spotify_expand(query)
            except RuntimeError:
                await st.delete()
                await message.reply_text(spotify_setup_help())
                return
            if not sp:
                await st.delete()
                await message.reply_text("❌ Spotify link se tracks nahi mile.")
                return
            await st.delete()
            await _queue_songs(message, sp, natural=True, label="🎧 playlist")
            return
        if "deezer.com" in query:
            dz = await deezer_expand(query)
            if not dz:
                await st.delete()
                await message.reply_text("❌ Deezer link se tracks nahi mile.")
                return
            await st.delete()
            await _queue_songs(message, dz, natural=True, label="🎧 playlist")
            return
        song = await _search_guard(asyncio.to_thread(resolve_song, query), 25)
        await st.delete()
        if not song:
            await message.reply_text("❌ Couldn't find that song.", reply_markup=main_menu())
            return
        if "soundcloud.com" in query:
            song["source"] = "soundcloud"
        song["normal"] = True
        q.songs.append(song)
        _sync_play_loop(q)
        if not q.current:
            q.current = q.songs.popleft()
            active_calls.add(chat_id)
            await play_song(chat_id, q.current)
        else:
            await message.reply_text(
                f"✅ 『{BRAND}』 — {stylish('Added (natural)')}:\n"
                f"🎵 {song['title']}\n⏱️ {fmt_duration(song['duration'])}",
                reply_markup=player_panel(q),
            )
        return
    saavn_results, yt_results, sc_results, sp_results, dz_results = await asyncio.gather(
        _search_guard(saavn_search(query, limit=4), 15),
        _search_guard(asyncio.to_thread(resolve_songs, query, 4), 15),
        _search_guard(asyncio.to_thread(soundcloud_search, query, 2), 15),
        _search_guard(spotify_search(query, 3), 12),
        _search_guard(deezer_search(query, 3), 12),
    )
    await st.delete()
    results = (saavn_results or []) + (yt_results or []) + (sc_results or []) + (sp_results or []) + (dz_results or [])
    if not results:
        await message.reply_text("❌ No results found.", reply_markup=main_menu())
        return
    search_seq[0] += 1
    sid = search_seq[0]
    search_cache[sid] = results
    last_search[(chat_id, message.from_user.id)] = {"sid": sid, "natural": True, "ts": time.time()}
    text = search_results_text(results, query, natural=True)
    buttons = []
    for i, s in enumerate(results):
        tag = SOURCE_TAG.get(s.get("source"), "🎵")
        label = s['title'][:25]
        buttons.append([InlineKeyboardButton(
            f"{i+1}. {tag} {label}", callback_data=f"cb_npick_{sid}_{i}"
        )])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cb_cancel")])
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
@music.on_message(filters.command("run", prefixes=PREFIX))
@needs_vc
async def run_cmd(client, message):
    chat_id = message.chat.id
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    if not message.reply_to_message:
        if len(message.command) >= 2:
            sync_saved_files()
            rows = db.get_files()
            indices = resolve_file_spec("".join(message.command[1:]), rows)
            if indices:
                await play_saved_list(message, indices, as_video=False)
                return
            if not rows:
                await message.reply_text(f"📭 {stylish('No saved files.')} `.files`")
                return
            await message.reply_text(
                "❌ Usage:\n"
                f"`.run 1` · `.run 1,2,3` · `.run 1-10` · `.run all`\n"
                f"{stylish('Ya reply to voice/audio/video to loop it.')}"
            )
            return
        await message.reply_text("❌ Reply to a voice/audio/video to loop it.\nOr saved files: `.run 1` · `.run all`")
        return
    st = await message.reply_text(f"⏳ 『{BRAND}』 — {stylish('Processing')}…\n📥 {stylish('Downloading media')}…")
    path = await download_reply_media(message)
    if not path:
        await st.edit_text("❌ That reply has no audio/video.")
        return
    song = {
        "title": os.path.basename(path),
        "duration": 0,
        "uploader": "DEV X CORE",
        "local_path": path,
        "source": "local",
        "loudspeaker": True,
    }
    q = get_queue(chat_id)
    q.repeat = True
    q.loop = False
    q.songs.clear()
    q.current = song
    active_calls.add(chat_id)
    err_notified.discard(chat_id)
    ok = await play_song(chat_id, song, announce=False, silent=True)
    if ok:
        await st.edit_text(
            f"🔁 『{BRAND}』 — {stylish('Looping (Loudspeaker)')}\n"
            f"🎵 `{os.path.basename(path)}`\n"
            f"💾 {stylish('File saved — loops silently, no spam')}"
        )
    else:
        q.repeat = False
        active_calls.discard(chat_id)
        await st.edit_text(
            f"❌ 『{BRAND}』 — {stylish('Could not start loop')}\n"
            f"{stylish('Start a voice chat first, then .run again.')}"
        )

@music.on_message(filters.regex(rf"^{re.escape(PREFIX)}(v?run|nplay)(\d+)\s*$"))
@needs_vc
async def run_index_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    kind = (message.matches[0].group(1) or "run").lower()
    num = int(message.matches[0].group(2))
    if kind == "nplay":
        await play_saved_index(message, num, as_video=False, natural=True)
    else:
        await play_saved_index(message, num, as_video=kind.startswith("v"))

@music.on_message(filters.command(["set", "unset", "setbanner"], prefixes=PREFIX))
async def set_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    cmd = (message.command[0] or "set").lower()
    arg = (message.command[1].lower() if len(message.command) >= 2 else "")
    if cmd == "unset" or arg in ("off", "clear", "none", "remove"):
        old = db.get_config("banner_path") or ""
        db.set_config("banner_path", "")
        db.set_config("banner_kind", "")
        if old and os.path.exists(old) and os.path.abspath(old).startswith(os.path.abspath(BANNER_DIR)):
            try:
                os.remove(old)
            except Exception:
                pass
        await message.reply_text(f"✅ 『{BRAND}』 — {stylish('Banner removed.')}")
        return
    r = message.reply_to_message
    if r is None:
        await message.reply_text(
            f"🎬 『{BRAND}』 — {stylish('Set GIF banner')}\n"
            f"{stylish('Reply to a video / photo / gif with')} `.set`\n"
            f"`.set off` — {stylish('remove banner')}"
        )
        return
    media_kind = None
    if r.animation:
        media_kind = "animation"
    elif r.video or r.video_note:
        media_kind = "video"
    elif r.photo:
        media_kind = "photo"
    elif r.document and (r.document.mime_type or "").startswith(("video/", "image/")):
        mime = r.document.mime_type or ""
        media_kind = "animation" if "gif" in mime else ("photo" if mime.startswith("image/") else "video")
    else:
        await message.reply_text("❌ Reply to a **video / photo / gif** with `.set`")
        return
    st = await message.reply_text(f"⏳ 『{BRAND}』 — {stylish('Converting to GIF')}…")
    src = os.path.join(TEMP_DIR, f"banner_src_{uuid.uuid4().hex}")
    try:
        await r.download(file_name=src)
        for name in os.listdir(BANNER_DIR):
            if name in ("devx_logo.png", "devx_logo.gif"):
                continue
            fp = os.path.join(BANNER_DIR, name)
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass
        if media_kind == "animation":
            ext = (r.document.file_name or "").rsplit(".", 1)[-1].lower() if r.document and r.document.file_name else ""
            ext = ("." + ext) if ext in ("gif", "mp4", "webm") else ".gif"
            dest = os.path.join(BANNER_DIR, f"menu_banner{ext}")
            os.replace(src, dest)
            kind = "animation"
        elif media_kind == "video":
            dest = os.path.join(BANNER_DIR, "menu_banner.mp4")
            video_to_gif(src, dest)
            kind = "animation"
        else:
            dest = os.path.join(BANNER_DIR, "menu_banner.gif")
            try:
                photo_to_gif(src, dest)
                kind = "animation"
            except Exception:
                os.replace(src, dest)
                kind = "photo"
        if os.path.exists(src):
            try:
                os.remove(src)
            except Exception:
                pass
        db.set_config("banner_path", dest)
        db.set_config("banner_kind", kind)
        await st.edit_text(f"✅ 『{BRAND}』 — {stylish('GIF banner saved')}")
    except Exception as e:
        await st.edit_text(f"❌ {stylish('Save failed')}: `{e}`")

@music.on_message(filters.command("voice", prefixes=PREFIX))
async def voice_cmd(client, message):
    if not message.reply_to_message:
        await message.reply_text(f"❌ Reply to a voice note with {PREFIX}voice")
        return
    await play_cmd(client, message)

@music.on_message(filters.command("vrun", prefixes=PREFIX))
@needs_vc
async def vrun_cmd(client, message):
    chat_id = message.chat.id
    q = get_queue(chat_id)
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    st = await message.reply_text(f"🎬 『{BRAND}』 — {stylish('Processing video')}…")
    song = None
    if message.reply_to_message:
        path = await download_reply_media(message)
        if not path:
            await st.edit_text("❌ Reply to a video to loop it.")
            return
        song = {
            "title": os.path.basename(path),
            "duration": 0,
            "uploader": "DEV X CORE",
            "local_path": path,
            "source": "local",
            "video": True,
            "loudspeaker": True,
        }
    elif len(message.command) >= 2:
        arg = "".join(message.command[1:])
        if arg.isdigit():
            await st.delete()
            await play_saved_index(message, int(arg), as_video=True)
            return
        sync_saved_files()
        rows = db.get_files()
        indices = resolve_file_spec(arg, rows)
        if indices:
            await st.delete()
            await play_saved_list(message, indices, as_video=True)
            return
        url = arg
        if not is_url(url):
            await st.edit_text("❌ Reply to a video, ya video URL do.")
            return
        await st.edit_text(f"🎬 『{BRAND}』 — {stylish('Downloading video')}…")
        try:
            info = await asyncio.to_thread(_try_resolve, url)
            if info.get("entries"):
                info = info["entries"][0]
            vurl = info.get("webpage_url") or info.get("url")
            if not vurl:
                await st.edit_text("❌ Couldn't resolve that video.")
                return
            local = await asyncio.to_thread(download_youtube_video, vurl)
            song = {
                "title": info.get("title") or os.path.basename(local),
                "duration": info.get("duration") or 0,
                "uploader": info.get("uploader") or info.get("channel") or "YouTube",
                "local_path": local,
                "webpage_url": info.get("webpage_url"),
                "source": "youtube",
                "video": True,
                "loudspeaker": True,
            }
            register_saved_file(local, song["title"], "youtube", chat_id)
        except Exception as e:
            await st.edit_text(f"❌ Video download failed: {e}")
            return
    else:
        await st.edit_text(f"❌ Reply to a video, or use: `{PREFIX}vrun <video url>`")
        return
    q.repeat = True
    q.loop = False
    q.songs.clear()
    q.current = song
    active_calls.add(chat_id)
    err_notified.discard(chat_id)
    ok = await play_song(chat_id, song, announce=False, silent=True)
    if ok:
        await st.edit_text(
            f"🎬 『{BRAND}』 — {stylish('Video Looping (Loudspeaker)')}\n"
            f"🎥 `{song['title']}`"
        )
    else:
        q.repeat = False
        active_calls.discard(chat_id)
        await st.edit_text(f"❌ 『{BRAND}』 — {stylish('Could not start video loop')}")

@music.on_message(filters.command("skip", prefixes=PREFIX))
@needs_vc
async def skip_cmd(client, message):
    chat_id = message.chat.id
    q = get_queue(chat_id)
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    if q.songs:
        old = q.current
        q.current = q.songs.popleft()
        await play_song(chat_id, q.current)
        if old is not None:
            _delete_temp_song_files(old)
        await message.reply_text("⏭️ Skipped! 🎶")
    else:
        old = q.current
        q.current = None
        if old is not None:
            _delete_temp_song_files(old)
        try:
            await vc.leave_call(chat_id)
        except Exception:
            pass
        active_calls.discard(chat_id)
        await message.reply_text("⏭️ Skipped. Queue empty — stopped.")

@music.on_message(filters.command("pause", prefixes=PREFIX))
@needs_vc
async def pause_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    try:
        await vc.pause(message.chat.id)
        _pause_timer(message.chat.id)
        await message.reply_text("⏸️ Paused.")
    except Exception:
        await message.reply_text("❌ Nothing is playing.")

@music.on_message(filters.command("resume", prefixes=PREFIX))
@needs_vc
async def resume_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    try:
        await vc.resume(message.chat.id)
        _resume_timer(message.chat.id)
        await message.reply_text("▶️ Resumed.")
    except Exception:
        await message.reply_text("❌ Nothing is paused.")

@music.on_message(filters.command("stop", prefixes=PREFIX))
@needs_vc
async def stop_cmd(client, message):
    chat_id = message.chat.id
    q = get_queue(chat_id)
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    queued = list(q.songs)
    q.songs.clear()
    old = q.current
    q.current = None
    q.loop = False
    q.repeat = False
    q.silent_loop = False
    active_calls.discard(chat_id)
    current_files.pop(chat_id, None)
    err_notified.discard(chat_id)
    replay_lock.discard(chat_id)
    PLAY_TIMERS.pop(chat_id, None)
    if old is not None:
        _delete_temp_song_files(old)
    for _s in queued:
        _delete_temp_song_files(_s)
    try:
        await vc.leave_call(chat_id)
        await message.reply_text(
            "⏹️ Stopped & left the voice chat.\n"
            f"📁 {stylish('Files kept')} — `.files` {stylish('to view')}"
        )
    except Exception:
        await message.reply_text("❌ Not in a voice chat.")

@music.on_message(filters.command("queue", prefixes=PREFIX))
async def queue_cmd(client, message):
    q = get_queue(message.chat.id)
    if not q.songs and not q.current:
        await message.reply_text("📭 Queue is empty.", reply_markup=main_menu())
        return
    text, kb = queue_panel(q, page=0)
    await message.reply_text(text, reply_markup=kb)

@music.on_message(filters.command("now", prefixes=PREFIX))
async def now_cmd(client, message):
    q = get_queue(message.chat.id)
    if not q.current:
        await message.reply_text("❌ Nothing is playing.", reply_markup=main_menu())
        return
    await message.reply_text(now_playing_text(q.current), reply_markup=player_panel(q))

@music.on_message(filters.command("loop", prefixes=PREFIX))
async def loop_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    q.loop = not q.loop
    if q.loop:
        q.repeat = False
        q.silent_loop = True
    else:
        q.silent_loop = False
    await message.reply_text(f"🔁 『{BRAND}』 — {stylish('Loop')}: {stylish('ON' if q.loop else 'OFF')}")

@music.on_message(filters.command("repeat", prefixes=PREFIX))
@needs_vc
async def repeat_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    q.repeat = not q.repeat
    if q.repeat:
        q.loop = False
        q.silent_loop = True
    else:
        q.silent_loop = False
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"🔂 『{BRAND}』 — {stylish('Repeat')}: {stylish('ON' if q.repeat else 'OFF')}")

def _arg(message, default=""):
    if len(message.command) < 2:
        return default
    return " ".join(message.command[1:]).strip()

@music.on_message(filters.command("boost", prefixes=PREFIX))
@needs_vc
async def boost_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message).lower()
    if arg in ("on", "max"):
        q.boost_level = 100
    elif arg in ("off", "0", "none", "reset"):
        q.boost_level = 0
    elif arg.replace(".", "", 1).isdigit():
        q.boost_level = max(0, min(100, int(float(arg))))
    else:
        q.boost_level = 0 if q.boost_level > 0 else 100
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"🚀 『{BRAND}』 — {stylish('Ultra Booster')}: `{q.boost_level}%`")

@music.on_message(filters.command("eco", prefixes=PREFIX))
@needs_vc
async def eco_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message).lower()
    if arg in ("on", "max"):
        q.eco_level = 100
    elif arg in ("off", "0", "none", "reset"):
        q.eco_level = 0
    elif arg.replace(".", "", 1).isdigit():
        q.eco_level = max(0, min(100, int(float(arg))))
    else:
        q.eco_level = 0 if q.eco_level > 0 else 100
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"🎤 『{BRAND}』 — {stylish('Echo')}: `{q.eco_level}%`")

@music.on_message(filters.command("gain", prefixes=PREFIX))
@needs_vc
async def gain_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message).lower()
    if arg in ("on", "max"):
        q.gain_level = 100
    elif arg in ("off", "0", "none", "reset"):
        q.gain_level = 0
    elif arg.replace(".", "", 1).isdigit():
        q.gain_level = max(0, min(100, int(float(arg))))
    else:
        q.gain_level = 0 if q.gain_level > 0 else 100
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"📢 『{BRAND}』 — {stylish('Gain Mode')}: `{q.gain_level}%`")

@music.on_message(filters.command("mix", prefixes=PREFIX))
@needs_vc
async def mix_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message).lower()
    if arg in ("off", "0", "none", "reset"):
        lvl = 0
    elif arg.replace(".", "", 1).isdigit():
        lvl = max(0, min(100, int(float(arg))))
    else:
        lvl = 0 if (q.boost_level > 0 or q.eco_level > 0 or q.gain_level > 0) else 100
    q.boost_level = q.eco_level = q.gain_level = lvl
    q.loud_level = 0
    if lvl == 0:
        q.treble = 0
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"⚡ 『{BRAND}』 — {stylish('MIX MODE')}: `{lvl}%`")

@music.on_message(filters.command("loud", prefixes=PREFIX))
@needs_vc
async def loud_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message).lower()
    if arg in ("on", "max"):
        q.loud_level = 100
    elif arg in ("off", "0", "none", "reset"):
        q.loud_level = 0
    elif arg.replace(".", "", 1).isdigit():
        q.loud_level = max(0, min(100, int(float(arg))))
    else:
        q.loud_level = 0 if q.loud_level > 0 else 100
    if q.current:
        q.current["loudspeaker"] = q.loud_level > 0
    await reapply_current_effects(message.chat.id)
    await message.reply_text(f"🔊 『{BRAND}』 — {stylish('Loudspeaker')}: `{q.loud_level}%`")

@music.on_message(filters.command("volume", prefixes=PREFIX))
async def volume_cmd(client, message):
    q = get_queue(message.chat.id)
    if len(message.command) >= 2 and not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    if len(message.command) < 2:
        await message.reply_text(f"🎚️ Volume: {fmt_vol(q.volume)}", reply_markup=volume_panel(q))
        return
    try:
        v = int(message.command[1])
        if not (0 <= v <= 5000):
            raise ValueError
        q.volume = v
        _vol_auto[message.chat.id] = False
        if vc_ready():
            try:
                await vc.change_volume_call(message.chat.id, min(v, 200))
                _last_vol_applied[message.chat.id] = min(v, 200)
            except Exception:
                pass
        await message.reply_text(f"🔊 Volume set to {fmt_vol(v)}")
    except ValueError:
        await message.reply_text("❌ Volume must be 0–5000.")
@music.on_message(filters.command("stats", prefixes=PREFIX))
async def stats_cmd(client, message):
    sync_saved_files()
    saved = db.get_files()
    saved_size = sum(r[4] or 0 for r in saved)
    try:
        real_users = len(db.get_users())
    except Exception:
        real_users = db.get_stat("total_users")
    body = (
        f"  👥 {stylish('users')}        `{real_users}`\n"
        f"  🎵 {stylish('played')}       `{db.get_stat('total_played')}`\n"
        f"  🎙️  {stylish('voice notes')}  `{db.get_stat('total_voice')}`\n"
        f"  📞 {stylish('live vc')}      `{len(active_calls)}`\n"
        f"  📁 {stylish('vault')}        `{len(saved)}`  ({fmt_size(saved_size)})\n"
        f"  ⏱️  {stylish('uptime')}       `{fmt_uptime()}`\n"
    )
    await message.reply_text(core_card("telemetry", body), reply_markup=hub_keyboard())

@music.on_message(filters.command("lockmusic", prefixes=PREFIX))
async def lockmusic_cmd(client, message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Only group admins can change this.")
        return
    db.set_config(f"lock:{message.chat.id}", "1")
    await message.reply_text("🔒🛡️ Per-chat HARD LOCK — ab is chat me SIRF owner + core admins hi chala sakte hain. 👑")

@music.on_message(filters.command("unlockmusic", prefixes=PREFIX))
async def unlockmusic_cmd(client, message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Only group admins can change this.")
        return
    db.set_config(f"lock:{message.chat.id}", "0")
    await message.reply_text("🔓🎉 Hard lock hata — ab bot mood (.public/.private) ke hisaab se control chalega.")

@music.on_message(filters.command("admin", prefixes=PREFIX))
async def admin_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admins only.")
        return
    if message.reply_to_message:
        if message.from_user.id != OWNER_ID:
            await message.reply_text("❌ Sirf **OWNER** hi admin add/remove kar sakta hai. 👑")
            return
        _r = message.reply_to_message
        _ru = getattr(_r, "from_user", None)
        if _ru is None or getattr(_ru, "is_bot", False):
            await message.reply_text("❌ Reply me koi user nahi hai (ya bot hai).")
            return
        _act = (message.command[1].lower() if len(message.command) >= 2 else "add")
        if _act not in ("add", "del", "remove", "rm"):
            _act = "add"
        db.add_user(_ru.id, _ru.username, _ru.first_name, _ru.last_name or "")
        _nm = f"@{_ru.username}" if getattr(_ru, "username", None) else (_ru.first_name or str(_ru.id))
        if _act in ("del", "remove", "rm"):
            if _ru.id == OWNER_ID:
                await message.reply_text("❌ Owner ko remove nahi kar sakte. 👑")
                return
            del_core_admin(_ru.id)
            await message.reply_text(f"🗑️ 👑 {_nm} (`{_ru.id}`) admin list se hata diya.\n\n" + core_admins_text())
        else:
            add_core_admin(_ru.id)
            await message.reply_text(f"✅ 👑 {_nm} (`{_ru.id}`) ab **core admin** hai!\n\n" + core_admins_text())
        return
    args = message.command[1:]
    if args:
        action = args[0].lower()
        if action in ("add", "del", "remove"):
            if message.from_user.id != OWNER_ID:
                await message.reply_text("❌ Sirf **OWNER** hi admin add/remove kar sakta hai. 👑")
                return
            if len(args) < 2:
                await message.reply_text("❌ `.admin add <id|@user>`")
                return
            target = args[1]
            uid = None
            if target.lstrip("-").isdigit():
                uid = int(target)
            elif target.startswith("@"):
                try:
                    _u = await client.get_users(target)
                    uid = _u.id
                except Exception:
                    await message.reply_text(f"❌ `{target}` user nahi mila.")
                    return
            else:
                await message.reply_text("❌ Usage: `.admin add <id | @username>`")
                return
            if action == "add":
                add_core_admin(uid)
                await message.reply_text(f"✅ 👑 `{uid}` ab **core admin** hai!\n\n" + core_admins_text())
            else:
                if uid == OWNER_ID:
                    await message.reply_text("❌ Owner ko remove nahi kar sakte. 👑")
                    return
                del_core_admin(uid)
                await message.reply_text(f"🗑️ 👑 `{uid}` admin list se hata diya.\n\n" + core_admins_text())
            return
        if action in ("list", "admins"):
            await message.reply_text(core_admins_text())
            return
    await message.reply_text(
        "👑 **𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄 — Owner Panel**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{stylish('Admin manage')}:\n"
        "`.admin` (reply) — replied user ko admin banao 👑\n"
        "`.admin add <id|@user>` · `.admin del` (reply) · `.rm` · `.alist`",
        reply_markup=owner_panel(),
    )

@music.on_message(filters.command("rjoin", prefixes=PREFIX))
async def rjoin_cmd(client, message):
    chat_id = message.chat.id
    if chat_id > 0:
        await message.reply_text("❌ Sirf group me chalta hai — private chat me nahi.")
        return
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    args = message.command[1:]
    if not args:
        set_rjoin_spec(chat_id, "join")
        body = (
            f"  🔁 {stylish('AUTO-JOIN ON (join only)')}\n\n"
            f"  ▸  {stylish('jab bhi call lagega, bot khud join karega')}\n"
            f"  ▸  {stylish('audio ke liye')}: `.rjoin 1,2,3`\n"
            f"  ▸  {stylish('band')}: `.rjoin off`"
        )
        await message.reply_text(core_card("auto join", body))
        return
    arg = args[0].strip().lower()
    if arg in ("off", "stop", "disable", "0"):
        set_rjoin_spec(chat_id, "")
        await message.reply_text(f"🔕 『{BRAND}』 — {stylish('Auto-join OFF')}.")
        return
    if arg in ("status", "info"):
        spec = get_rjoin_spec(chat_id)
        if spec is None:
            await message.reply_text(f"📭 {stylish('Auto-join set nahi hai.')}")
        else:
            await message.reply_text(f"🔁 Auto-Join spec: `{spec}`")
        return
    sync_saved_files()
    rows = db.get_files()
    if not rows:
        await message.reply_text(f"📭 {stylish('No saved files.')} `.files`")
        return
    indices = resolve_file_spec("".join(args), rows)
    if not indices:
        await message.reply_text(f"❌ {stylish('Invalid spec')}. `.rjoin 1,2,3` · `.rjoin all`")
        return
    names = []
    for i in indices:
        if 0 <= i < len(rows):
            names.append(rows[i][2] or os.path.basename(rows[i][1]))
    spec = ",".join(str(i + 1) for i in indices)
    set_rjoin_spec(chat_id, spec)
    listing = "\n".join(f"  {n + 1}. 🎵 {nm}" for n, nm in enumerate(names[:25]))
    await message.reply_text(
        f"🔁 『{BRAND}』 — {stylish('Auto-Join + Repeat ON')}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{listing}\n"
        f"📚 {stylish('total')}: {len(names)} {stylish('files')}"
    )

@music.on_message(filters.command(["public", "private"], prefixes=PREFIX))
async def mode_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text("❌ Sirf **OWNER** hi mood change kar sakta hai. 👑")
        return
    mode = "public" if (message.command[0] or "").replace(PREFIX, "", 1).lower() == "public" else "private"
    set_mode(mode)
    await message.reply_text(core_card("bot mood", f"  mood: `{mode}`", stylish(f"mood: {mode}")))

@music.on_message(filters.command(["rm", "removeadmin"], prefixes=PREFIX))
async def rm_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text("❌ Sirf **OWNER** admin remove kar sakta hai. 👑")
        return
    arg = _arg(message).strip().lower()
    if arg in ("all", "*"):
        removed = sorted(get_core_admins() - {OWNER_ID})
        for a in removed:
            del_core_admin(a)
        await message.reply_text(f"🗑️ {stylish('All core admins removed')}: {len(removed)}\n\n" + core_admins_text())
        return
    uid = None
    if message.reply_to_message and message.reply_to_message.from_user:
        uid = message.reply_to_message.from_user.id
    elif arg.lstrip("-").isdigit():
        uid = int(arg)
    if not uid:
        await message.reply_text("❌ `.rm <user_id>` / reply / `.rm all`")
        return
    if uid == OWNER_ID:
        await message.reply_text("❌ Owner ko remove nahi kar sakte. 👑")
        return
    del_core_admin(uid)
    await message.reply_text(f"🗑️ `{uid}` removed.\n\n" + core_admins_text())

def _admin_display(uid):
    try:
        r = db.c.execute("SELECT username, first_name FROM users WHERE id=?", (uid,)).fetchone()
    except Exception:
        r = None
    if r and r[0]:
        return f"@{r[0]}"
    if r and r[1]:
        return r[1]
    return str(uid)

def admin_list_card():
    admins = sorted(get_core_admins())
    lines = [f"📋 『{BRAND}』 — {stylish('Core Admin List')}", "━━━━━━━━━━━━━━━━━━━━━"]
    for a in admins:
        tag = "👑 owner" if a == OWNER_ID else "🛡️ admin"
        lines.append(f"• {_admin_display(a)} · `{a}` · {tag}")
    return "\n".join(lines)

def admin_list_kb():
    admins = sorted(get_core_admins())
    rows = []
    for a in admins:
        if a == OWNER_ID:
            continue
        rows.append([InlineKeyboardButton(f"🗑️ {_admin_display(a)}", callback_data=f"alist_del_{a}")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="cb_adminlist"),
                 InlineKeyboardButton("⌂ Hub", callback_data="cb_menu")])
    return InlineKeyboardMarkup(rows)

@music.on_message(filters.command(["alist", "adminlist"], prefixes=PREFIX))
async def alist_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    await message.reply_text(admin_list_card(), reply_markup=admin_list_kb())

@music.on_message(filters.command("servers", prefixes=PREFIX))
async def servers_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    groups = []
    async for d in client.get_dialogs():
        if d.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            groups.append(f"• {d.chat.title} (`{d.chat.id}`)")
    await message.reply_text("🌐 **Groups:**\n" + "\n".join(groups[:30] or ["No groups."]))

@music.on_message(filters.command("users", prefixes=PREFIX))
async def users_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    users = db.get_users(50)
    text = "👥 **Users:**\n"
    for u in users:
        text += f"• `{u[0]}` @{u[1] or '—'}\n"
    await message.reply_text(text or "No users yet.")

@music.on_message(filters.command("broadcast", prefixes=PREFIX))
async def broadcast_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    if len(message.command) < 2:
        await message.reply_text(f"❌ `{PREFIX}broadcast <text>`")
        return
    text = "📢 **𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄 — Announcement**\n\n" + " ".join(message.command[1:])
    users = db.get_users()
    ok = fail = 0
    st = await message.reply_text("📢 Broadcasting…")
    for u in users:
        try:
            await client.send_message(u[0], text)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await st.edit_text(f"✅ Sent to {ok} users. Failed: {fail}")

@music.on_message(filters.command(["ban", "unban"], prefixes=PREFIX))
async def ban_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    if len(message.command) < 2:
        await message.reply_text(f"❌ `{PREFIX}ban <user_id>`")
        return
    try:
        uid = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Invalid id.")
        return
    if message.command[0] == "ban":
        db.ban_user(uid)
        await message.reply_text(f"🚫 Banned `{uid}`.")
    else:
        db.unban_user(uid)
        await message.reply_text(f"✅ Unbanned `{uid}`.")

@music.on_message(filters.command("bio", prefixes=PREFIX) & filters.user(OWNER_ID))
async def bio_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text(f"❌ `{PREFIX}bio <text>`")
        return
    await music.update_profile(bio=" ".join(message.command[1:]))
    await message.reply_text("✅ Bio updated.")

@music.on_message(filters.command("ytupdate", prefixes=PREFIX) & filters.user(OWNER_ID))
async def ytupdate_cmd(client, message):
    st = await message.reply_text("⬇️ yt-dlp update ho raha hai…")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "-U", "--no-cache-dir", "yt-dlp",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _out, err = await asyncio.wait_for(proc.communicate(), timeout=240)
        try:
            import yt_dlp as _ydl
            newver = _ydl.version.__version__
        except Exception:
            newver = "?"
        await st.edit_text(f"✅ yt-dlp updated: `{newver}`")
    except Exception as e:
        await st.edit_text(f"❌ Update failed: `{e}`")
@music.on_message(filters.command("eval", prefixes=PREFIX) & filters.user(OWNER_ID))
async def eval_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text(f"❌ `{PREFIX}eval <code>`")
        return
    code = " ".join(message.command[1:])
    env = {"music": music, "client": client, "vc": vc, "db": db, "message": message, "queues": queues}
    try:
        result = eval(code, {"__builtins__": __builtins__}, env)
        await message.reply_text(f"```\n{result}\n```")
    except Exception as e:
        await message.reply_text(f"```\n{e}\n```")

@music.on_message(filters.new_chat_members)
@music.on_message(filters.service)
async def rjoin_service_handler(client, message):
    if not vc_ready():
        return
    svc = getattr(message, "service", None)
    if svc is None:
        return
    chat_id = message.chat.id
    if chat_id > 0:
        return
    if svc in _CHAT_ENDED:
        try:
            if chat_id in active_calls:
                await vc.leave_call(chat_id)
        except Exception:
            pass
        active_calls.discard(chat_id)
        q = get_queue(chat_id)
        if q.current is not None and q.current.get("rjoin"):
            q.current = None
            q.songs.clear()
            q.repeat = False
            q.loop = False
            q.silent_loop = False
            current_files.pop(chat_id, None)
            PLAY_TIMERS.pop(chat_id, None)
        return
    if svc not in _CHAT_STARTED:
        return
    if get_rjoin_spec(chat_id) is None:
        return
    _rj_now = time.time()
    if hasattr(rjoin_on_call_started, "_last_call"):
        _rj_last = rjoin_on_call_started._last_call.get(chat_id, 0)
        if _rj_now - _rj_last < 15:
            return
    else:
        rjoin_on_call_started._last_call = {}
    rjoin_on_call_started._last_call[chat_id] = _rj_now
    result = await rjoin_on_call_started(chat_id)
    if result:
        try:
            await music.send_message(
                chat_id,
                f"🔁 『{BRAND}』 — {stylish('Auto-Joined!')}"
                + (f"\n🎵 {stylish('repeat playlist ON')}" if result == "playing" else ""),
            )
        except Exception:
            pass

@music.on_message(filters.text)
async def awaiting_handler(client, message):
    if (message.text or "").startswith(PREFIX):
        return
    key = (message.chat.id, message.from_user.id)
    ls = last_search.get(key)
    if ls and (time.time() - ls.get("ts", 0)) < 600:
        spec = (message.text or "").strip()
        if spec:
            results = search_cache.get(ls.get("sid"))
            if results:
                try:
                    if spec.lower() in ("all", "*", "etc"):
                        indices = list(range(len(results)))
                    else:
                        indices = resolve_file_spec(spec, results) or []
                except Exception:
                    indices = []
                if indices:
                    last_search.pop(key, None)
                    natural = ls.get("natural", False)
                    started, queued, first = await _play_picked_songs(
                        message, ls["sid"], indices, natural=natural)
                    if started or queued:
                        tag = "🎧 natural" if natural else "🎵"
                        extra = f" +{queued - 1} more" if queued > 1 else ""
                        await message.reply_text(
                            f"✅ 『{BRAND}』 — {stylish('Selected')}: {queued} {tag}{extra}\n"
                            f"🎵 {first}"
                        )
                    return
    if key not in awaiting:
        return
    purpose = awaiting.pop(key)
    if purpose == "play":
        message.text = f"{PREFIX}play {message.text}"
        message.command = message.text.split()
        await play_cmd(client, message)
    elif purpose == "voice":
        await message.reply_text(f"🎤 Reply to a voice/audio/video and send `{PREFIX}run` or `{PREFIX}play`.")
    elif purpose == "broadcast":
        if not is_core_admin(message.from_user.id):
            return
        text = "📢 **𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄 — Announcement**\n\n" + message.text
        users = db.get_users()
        ok = fail = 0
        st = await message.reply_text("📢 Broadcasting…")
        for u in users:
            try:
                await client.send_message(u[0], text)
                ok += 1
            except Exception:
                fail += 1
            await asyncio.sleep(0.05)
        await st.edit_text(f"✅ Sent to {ok} users. Failed: {fail}", reply_markup=owner_panel())
    elif purpose == "addadmin":
        if message.from_user.id != OWNER_ID:
            return
        if not (message.text or "").strip().lstrip("-").isdigit():
            await message.reply_text("❌ Valid User ID bhejo (digits).")
            return
        uid = int(message.text.strip())
        add_core_admin(uid)
        await message.reply_text(f"✅ 👑 `{uid}` ab **core admin** hai!\n\n" + core_admins_text())
    elif purpose == "deladmin":
        if message.from_user.id != OWNER_ID:
            return
        if not (message.text or "").strip().lstrip("-").isdigit():
            await message.reply_text("❌ Valid User ID bhejo (digits).")
            return
        uid = int(message.text.strip())
        if uid == OWNER_ID:
            await message.reply_text("❌ Owner ko remove nahi kar sakte. 👑")
            return
        del_core_admin(uid)
        await message.reply_text(f"🗑️ 👑 `{uid}` admin list se hata diya.\n\n" + core_admins_text())

GBAN_KEY = "gbans"

def get_gbans():
    raw = db.get_config(GBAN_KEY, "") or ""
    ids = {int(x) for x in raw.split(",") if x.strip().isdigit()}
    ids.discard(OWNER_ID)
    return ids

def gban_user(uid):
    ids = get_gbans()
    ids.add(int(uid))
    db.set_config(GBAN_KEY, ",".join(str(i) for i in sorted(ids)))

def ungban_user(uid):
    ids = get_gbans()
    ids.discard(int(uid))
    db.set_config(GBAN_KEY, ",".join(str(i) for i in sorted(ids)))

def uid_gbanned(uid):
    try:
        return int(uid) in get_gbans()
    except Exception:
        return False

RADIO_STATIONS = {
    "1": {"name": "BBC World Service", "url": "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service"},
    "2": {"name": "Radio City Hindi", "url": "http://prclive1.listenon.in:9960/"},
    "3": {"name": "Radio Mirchi", "url": "http://node-28.zeno.fm/8f4wk1f77gruv"},
    "4": {"name": "SomaFM Groove Salad", "url": "https://ice1.somafm.com/groovesalad-256-mp3"},
    "5": {"name": "Radio Paradise", "url": "https://stream.radioparadise.com/mp3-192"},
    "6": {"name": "Lofi Radio", "url": "http://usa9.fastcast4u.com/proxy/jamz?mp=/1"},
}

@music.on_message(filters.command("lyrics", prefixes=PREFIX))
async def lyrics_cmd(client, message):
    query = _arg(message)
    if not query and message.reply_to_message:
        query = message.reply_to_message.text or ""
    if not query:
        await message.reply_text(f"❌ {stylish('Usage')}: `.lyrics <song name>`")
        return
    st = await message.reply_text(f"🔎 『{BRAND}』 — {stylish('Lyrics dhoond raha hoon')}…")
    artist, title = None, query.strip()
    if " - " in query:
        artist, title = [x.strip() for x in query.split(" - ", 1)]
    else:
        try:
            hits = await _search_guard(deezer_search(query, limit=1), 12)
            if hits:
                artist = hits[0].get("uploader")
                title = hits[0].get("title")
        except Exception:
            pass
    if not artist:
        await st.edit_text(f"❌ {stylish('Artist nahi mila')}. `.lyrics Artist - Song`")
        return
    url = ("https://api.lyrics.ovh/v1/"
           f"{aiohttp.helpers.quote(artist, safe='')}/"
           f"{aiohttp.helpers.quote(title, safe='')}")
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=timeout) as r:
                data = await r.json(content_type=None)
        lyr = (data or {}).get("lyrics")
        if not lyr:
            await st.edit_text(f"❌ {stylish('Lyrics nahi mile')}")
            return
        msg = f"🎤 **{artist} — {title}**\n\n{lyr.strip()}"
        chunks, cur = [], ""
        for ln in msg.split("\n"):
            if len(cur) + len(ln) + 1 > 3900:
                chunks.append(cur)
                cur = ln
            else:
                cur += ln + "\n"
        if cur:
            chunks.append(cur)
        await st.edit_text(chunks[0])
        for c in chunks[1:]:
            await message.reply_text(c)
    except Exception as e:
        await st.edit_text(f"❌ Lyrics fail: `{e}`")

@music.on_message(filters.command("radio", prefixes=PREFIX))
@needs_vc
async def radio_cmd(client, message):
    chat_id = message.chat.id
    if not await can_control(client, chat_id, message.from_user.id):
        await _deny_reply(message)
        return
    arg = _arg(message)
    if not arg:
        body = "\n".join(f"  `{n}.` 📻 {s['name']}" for n, s in RADIO_STATIONS.items())
        await message.reply_text(core_card("live radio 📻", body + "\n\n  `.radio 1` · `.radio off`", stylish("radio streams")))
        return
    if arg.lower() in ("off", "stop", "0"):
        q = get_queue(chat_id)
        q.songs.clear()
        old = q.current
        q.current = None
        if old is not None:
            _delete_temp_song_files(old)
        try:
            await vc.leave_call(chat_id)
        except Exception:
            pass
        active_calls.discard(chat_id)
        PLAY_TIMERS.pop(chat_id, None)
        await message.reply_text(f"📻 {stylish('Radio band')}.")
        return
    stn = RADIO_STATIONS.get(arg.split()[0])
    if not stn:
        await message.reply_text(f"❌ {stylish('Invalid station')}. `.radio`")
        return
    song = {
        "title": f"📻 {stn['name']}",
        "duration": 0,
        "uploader": "Live Radio",
        "direct_url": stn["url"],
        "source": "radio",
        "normal": True,
    }
    q = get_queue(chat_id)
    q.songs.clear()
    q.current = song
    q.loop = False
    q.repeat = False
    active_calls.add(chat_id)
    err_notified.discard(chat_id)
    ok = await play_song(chat_id, song, announce=True)
    if not ok:
        q.current = None
        active_calls.discard(chat_id)

@music.on_message(filters.command("speed", prefixes=PREFIX))
@needs_vc
async def speed_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message)
    if not arg:
        await message.reply_text(f"🎚️ Speed: `{q.speed}x`\n💡 `.speed 1.25` · `.speed 0.75`")
        return
    try:
        v = float(arg)
        if not (0.5 <= v <= 2.5):
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Speed 0.5–2.5")
        return
    q.speed = v
    q.nightcore = False
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"⚡ 『{BRAND}』 — Speed: `{v}x`")

@music.on_message(filters.command("nightcore", prefixes=PREFIX))
@needs_vc
async def nightcore_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    q.nightcore = not q.nightcore
    if q.nightcore:
        q.speed = 1.0
    state = "ON ⚡" if q.nightcore else "OFF"
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"⚡ 『{BRAND}』 — Nightcore: {state}")

@music.on_message(filters.command("bass", prefixes=PREFIX))
@needs_vc
async def bass_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message).lower()
    if arg in ("off", "0", "none", "reset"):
        q.bass = 0
    elif arg.replace(".", "", 1).isdigit():
        q.bass = max(0, min(100, int(float(arg))))
    else:
        q.bass = 0 if q.bass > 0 else 50
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"🔊 『{BRAND}』 — Bass boost: `{q.bass}%`")

@music.on_message(filters.command("treble", prefixes=PREFIX))
@needs_vc
async def treble_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message).lower()
    if arg in ("off", "0", "none", "reset"):
        q.treble = 0
    elif arg.replace(".", "", 1).isdigit():
        q.treble = max(0, min(100, int(float(arg))))
    else:
        q.treble = 0 if q.treble > 0 else 50
    if q.current:
        await reapply_current_effects(message.chat.id)
    await message.reply_text(f"🎼 『{BRAND}』 — Treble boost: `{q.treble}%`")

@music.on_message(filters.command("sound", prefixes=PREFIX))
async def sound_cmd(client, message):
    q = get_queue(message.chat.id)
    body = (
        f"  🔊 {stylish('loud')}     `{q.loud_level}%`\n"
        f"  📢 {stylish('gain')}     `{q.gain_level}%`\n"
        f"  🚀 {stylish('boost')}    `{q.boost_level}%`\n"
        f"  🎤 {stylish('eco')}      `{q.eco_level}%`\n"
        f"  🔊 {stylish('bass')}     `{q.bass}%`\n"
        f"  🎼 {stylish('treble')}   `{q.treble}%`\n"
        f"  🎚️  {stylish('volume')}   `{q.volume}%`\n"
        f"  ⚡ {stylish('speed')}    `{q.speed}x`\n"
        f"  ⚡ {stylish('nightcore')} `{'ON' if q.nightcore else 'OFF'}`\n"
        f"\n  💯 `.max` = sab 100"
    )
    await message.reply_text(core_card("sound control 🔊", body, stylish(".max · .sound")))

@music.on_message(filters.command("max", prefixes=PREFIX))
@needs_vc
async def max_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    q = get_queue(message.chat.id)
    arg = _arg(message).lower()
    if arg in ("off", "0", "none", "reset"):
        q.loud_level = q.gain_level = q.boost_level = q.eco_level = 0
        q.bass = q.treble = 0
        q.volume = 100
        q.speed = 1.0
        q.nightcore = False
        label = "OFF (sab normal)"
    else:
        q.loud_level = q.gain_level = q.boost_level = q.eco_level = 100
        q.bass = q.treble = 100
        q.volume = 200
        _vol_auto[message.chat.id] = False
        label = "MAX LOUD 💯"
    if q.current:
        await reapply_current_effects(message.chat.id)
    try:
        if vc_ready():
            await vc.change_volume_call(message.chat.id, q.volume)
    except Exception:
        pass
    await message.reply_text(f"💯 『{BRAND}』 — {stylish(label)}")

@music.on_message(filters.command("seek", prefixes=PREFIX))
@needs_vc
async def seek_cmd(client, message):
    if not await can_control(client, message.chat.id, message.from_user.id):
        await _deny_reply(message)
        return
    chat_id = message.chat.id
    q = get_queue(chat_id)
    if not q.current:
        await message.reply_text("❌ Kuch play nahi ho raha.")
        return
    arg = _arg(message)
    try:
        delta = int(float(arg))
    except (ValueError, TypeError):
        await message.reply_text("❌ `.seek +30` · `.seek -15` · `.seek 60`")
        return
    cur = int(get_elapsed(chat_id))
    pos = max(0, cur + delta)
    dur = int(q.current.get("duration") or 0)
    if dur and pos >= dur:
        pos = max(0, dur - 2)
    ok = await play_song(chat_id, q.current, announce=False, seek=pos)
    await message.reply_text(f"⏩ Seeked: `{fmt_duration(pos)}`" if ok else "❌ Seek fail")
@music.on_message(filters.command("playlist", prefixes=PREFIX))
@needs_vc
async def playlist_cmd(client, message):
    chat_id = message.chat.id
    args = message.command[1:]
    if not args:
        rows = db.c.execute(
            "SELECT name, created_at FROM playlists WHERE chat_id=? ORDER BY name DESC",
            (chat_id,)).fetchall()
        if not rows:
            await message.reply_text("📭 No playlists.\n`.playlist save <name>` · `.playlist load <name>`")
            return
        body = "\n".join(f"  `{n + 1}.` 🎵 {nm}" for n, (nm, _ts) in enumerate(rows))
        await message.reply_text(core_card("playlists", body, stylish(".playlist load <name>")))
        return
    action = args[0].lower()
    q = get_queue(chat_id)
    if action == "save":
        if len(args) < 2:
            await message.reply_text("❌ `.playlist save <name>`")
            return
        name = " ".join(args[1:])[:40]
        songs = []
        if q.current:
            songs.append(q.current)
        songs.extend(list(q.songs))
        if not songs:
            await message.reply_text("❌ Queue khali hai.")
            return
        clean = []
        for s in songs:
            d = dict(s)
            d.pop("temp", None)
            d.pop("_file", None)
            clean.append(d)
        db.c.execute("DELETE FROM playlists WHERE name=? AND chat_id=?", (name, chat_id))
        db.c.execute(
            "INSERT INTO playlists (name, chat_id, songs, created_at) VALUES (?,?,?,?)",
            (name, chat_id, json.dumps(clean), datetime.now().isoformat()))
        db.conn.commit()
        await message.reply_text(f"✅ Playlist saved: `{name}` · {len(clean)} tracks")
    elif action == "load":
        if len(args) < 2:
            await message.reply_text("❌ `.playlist load <name>`")
            return
        name = " ".join(args[1:])[:40]
        row = db.c.execute(
            "SELECT songs FROM playlists WHERE name=? AND chat_id=?",
            (name, chat_id)).fetchone()
        if not row:
            await message.reply_text(f"❌ Playlist `{name}` nahi mili.")
            return
        try:
            songs = json.loads(row[0])
        except Exception:
            songs = []
        if not songs:
            await message.reply_text("❌ Playlist khali/corrupt hai.")
            return
        q.songs.clear()
        for s in songs:
            s.pop("temp", None)
            s.pop("_file", None)
            q.songs.append(s)
        if not q.current:
            q.current = q.songs.popleft()
            active_calls.add(chat_id)
            await play_song(chat_id, q.current)
        await message.reply_text(f"✅ Playlist loaded: `{name}` · {len(songs)} tracks")
    elif action in ("del", "delete", "rm"):
        if len(args) < 2:
            await message.reply_text("❌ `.playlist del <name>`")
            return
        name = " ".join(args[1:])[:40]
        db.c.execute("DELETE FROM playlists WHERE name=? AND chat_id=?", (name, chat_id))
        db.conn.commit()
        await message.reply_text(f"🗑️ Playlist `{name}` deleted.")
    else:
        await message.reply_text("❌ `.playlist save|load|del <name>`")

@music.on_message(filters.command("gban", prefixes=PREFIX))
async def gban_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text("❌ Sirf OWNER 👑")
        return
    uid = None
    if message.reply_to_message and message.reply_to_message.from_user:
        uid = message.reply_to_message.from_user.id
    elif _arg(message).lstrip("-").isdigit():
        uid = int(_arg(message))
    if not uid or uid == OWNER_ID:
        await message.reply_text("❌ Reply karo ya user id do.")
        return
    gban_user(uid)
    await message.reply_text(f"🚫 Global banned: `{uid}`")

@music.on_message(filters.command("ungban", prefixes=PREFIX))
async def ungban_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text("❌ Sirf OWNER 👑")
        return
    uid = None
    if message.reply_to_message and message.reply_to_message.from_user:
        uid = message.reply_to_message.from_user.id
    elif _arg(message).lstrip("-").isdigit():
        uid = int(_arg(message))
    if not uid:
        await message.reply_text("❌ Reply karo ya user id do.")
        return
    ungban_user(uid)
    await message.reply_text(f"✅ Unbanned: `{uid}`")

@music.on_message(filters.command("gbanlist", prefixes=PREFIX))
async def gbanlist_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    ids = sorted(get_gbans())
    if not ids:
        await message.reply_text("📭 Koi gban nahi.")
        return
    await message.reply_text("🚫 **Global Bans**\n" + "\n".join(f"• `{i}`" for i in ids))

@music.on_message(filters.command("restart", prefixes=PREFIX) & filters.user(OWNER_ID))
async def restart_cmd(client, message):
    try:
        await message.reply_text(f"♻️ 『{BRAND}』 — {stylish('Restarting')}…")
    except Exception:
        pass
    await asyncio.sleep(1)
    try:
        await music.stop()
    except Exception:
        pass
    try:
        await bot.stop()
    except Exception:
        pass
    try:
        db.close()
    except Exception:
        pass
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        os._exit(0)

@music.on_message(filters.command("backup", prefixes=PREFIX) & filters.user(OWNER_ID))
async def backup_cmd(client, message):
    import zipfile
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zp = os.path.join(BACKUPS_DIR, f"devx_backup_{ts}.zip")
    try:
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for fp in ([DB_PATH, SESSION_FILE] if os.path.exists(SESSION_FILE) else [DB_PATH]):
                if os.path.exists(fp):
                    z.write(fp, os.path.basename(fp))
            if os.path.isdir(BANNER_DIR):
                for name in os.listdir(BANNER_DIR):
                    fp = os.path.join(BANNER_DIR, name)
                    if os.path.isfile(fp):
                        z.write(fp, os.path.join("banner", name))
            log = os.path.join(LOGS_DIR, "bot.log")
            if os.path.exists(log):
                z.write(log, "bot.log")
        await message.reply_document(zp, caption=f"📦 Backup: `{os.path.basename(zp)}`")
    except Exception as e:
        await message.reply_text(f"❌ Backup fail: `{e}`")

@music.on_message(filters.command("clean", prefixes=PREFIX))
async def clean_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    playing = playing_paths()
    prefixes = TEMP_PREFIXES + ("tts_", "qr_", "banner_src_")
    removed = 0
    try:
        for name in os.listdir(TEMP_DIR):
            fp = os.path.join(TEMP_DIR, name)
            if os.path.isfile(fp) and fp not in playing and name.startswith(prefixes):
                try:
                    os.remove(fp)
                    removed += 1
                except Exception:
                    pass
    except Exception:
        pass
    await message.reply_text(f"🧹 Temp cleaned: {removed} files")

@music.on_message(filters.command("ytdl", prefixes=PREFIX))
async def ytdl_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    url = _arg(message)
    if not url:
        await message.reply_text("❌ `.ytdl <youtube url>`")
        return
    st = await message.reply_text(f"🎬 Downloading video…")
    try:
        local = await asyncio.to_thread(download_youtube_video, url)
        register_saved_file(local, os.path.basename(local), "youtube", message.chat.id)
        await st.edit_text(f"✅ Video saved: `{os.path.basename(local)}`")
    except Exception as e:
        await st.edit_text(f"❌ Download fail: `{e}`")

@music.on_message(filters.command("save", prefixes=PREFIX))
async def save_cmd(client, message):
    if not is_core_admin(message.from_user.id):
        await message.reply_text("❌ Owner / core admin only.")
        return
    if message.reply_to_message:
        st = await message.reply_text("💾 Saving media…")
        path = await download_reply_media(message)
        if not path:
            await st.edit_text("❌ Reply me audio/video nahi hai.")
            return
        await st.edit_text(f"✅ Saved: `{os.path.basename(path)}`")
        return
    query = _arg(message)
    if not query:
        await message.reply_text("❌ `.save <song|url>` ya reply media")
        return
    st = await message.reply_text("💾 Downloading for save…")
    try:
        title = None
        local = None
        src = "youtube"
        try:
            hits = await _search_guard(saavn_search(query, limit=1), 15)
            if hits and hits[0].get("direct_url"):
                local = await asyncio.wait_for(download_saavn_file(hits[0]["direct_url"]), timeout=120)
                title = hits[0].get("title") or query
                src = "saavn"
        except Exception:
            pass
        if not local:
            if not is_url(query):
                info = await _search_guard(asyncio.to_thread(resolve_song, query), 25)
                qurl = info.get("webpage_url") if info else query
                title = (info or {}).get("title") or title or query
            else:
                qurl = query
            local, via = await _fetch_youtube_audio(qurl, title or query, message.chat.id)
            src = via
        ext = os.path.splitext(local)[1] or ".m4a"
        dest = os.path.join(TEMP_DIR, f"saved_{uuid.uuid4().hex}{ext}")
        os.replace(local, dest)
        register_saved_file(dest, title or os.path.basename(dest), src, message.chat.id)
        await st.edit_text(f"✅ Saved to Vault: `{title or os.path.basename(dest)}`")
    except Exception as e:
        await st.edit_text(f"❌ Save fail: `{e}`")
@music.on_callback_query()
async def cb_handler(client, cb: CallbackQuery):
    data = cb.data
    chat_id = cb.message.chat.id
    q = get_queue(chat_id)
    await cb.answer()

    if data.startswith("hcmd_"):
        cmd = data[5:]
        desc = CMD_HELP.get(cmd, "")
        await cb.answer(desc or "Unknown command", show_alert=True)
        return

    if data.startswith("cb_pick_"):
        _, _, sid, idx = data.split("_")
        results = search_cache.get(int(sid))
        if not results:
            await cb.answer("❌ Session expired. Search again.", show_alert=True)
            return
        try:
            song = results[int(idx)]
        except (IndexError, ValueError):
            await cb.answer("❌ Invalid selection.", show_alert=True)
            return
        if not await can_control(client, chat_id, cb.from_user.id):
            await _deny_answer(cb)
            return
        q.songs.append(song)
        _sync_play_loop(q)
        if not q.current:
            q.current = q.songs.popleft()
            active_calls.add(chat_id)
            ok = await play_song(chat_id, q.current)
            if not ok:
                q.current = None
                try:
                    await cb.message.edit_text(
                        f"❌ Play nahi ho paya → `.diag`",
                        reply_markup=main_menu(),
                    )
                except Exception:
                    pass
        else:
            await cb.message.edit_text(
                f"✅ Added:\n🎵 {song['title']}\n⏱️ {fmt_duration(song['duration'])}",
                reply_markup=player_panel(q),
            )
        return

    if data.startswith("cb_npick_"):
        _, _, sid, idx = data.split("_")
        results = search_cache.get(int(sid))
        if not results:
            await cb.answer("❌ Session expired.", show_alert=True)
            return
        try:
            song = results[int(idx)]
        except (IndexError, ValueError):
            await cb.answer("❌ Invalid selection.", show_alert=True)
            return
        if not await can_control(client, chat_id, cb.from_user.id):
            await _deny_answer(cb)
            return
        song["normal"] = True
        q.songs.append(song)
        _sync_play_loop(q)
        if not q.current:
            q.current = q.songs.popleft()
            active_calls.add(chat_id)
            ok = await play_song(chat_id, q.current)
            if not ok:
                q.current = None
        else:
            await cb.message.edit_text(
                f"✅ Added (natural 🎧):\n🎵 {song['title']}",
                reply_markup=player_panel(q),
            )
        return

    if data.startswith("hpg_"):
        await _show_help_page(cb.message, data)
        return
    if data == "cb_cancel":
        try:
            await cb.message.edit_text("❌ Cancelled.", reply_markup=main_menu())
        except Exception:
            pass
        return
    if data.startswith("cb_qpage_"):
        page = int(data.split("_")[-1])
        text, kb = queue_panel(q, page=page)
        try:
            await cb.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        return
    if data.startswith("cb_fpage_"):
        if not is_core_admin(cb.from_user.id):
            await cb.answer("❌ Owner / core admin only", show_alert=True)
            return
        page = int(data.split("_")[-1])
        text, kb = files_list_text(page=page)
        try:
            await cb.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        return
    if data == "cb_files":
        if not is_core_admin(cb.from_user.id):
            await cb.answer("❌ Owner / core admin only", show_alert=True)
            return
        text, kb = files_list_text(page=0)
        await cb.message.reply_text(text, reply_markup=kb)
        return
    if data == "cb_delall":
        if not is_core_admin(cb.from_user.id):
            await cb.answer("❌ Owner / core admin only", show_alert=True)
            return
        deleted, skipped = delete_all_saved_files()
        text, kb = files_list_text(page=0)
        try:
            await cb.message.edit_text(f"🗑 Deleted {deleted} · skipped {skipped}\n\n{text}", reply_markup=kb)
        except Exception:
            pass
        return
    if data in CONTROL_CALLBACKS and not await can_control(client, chat_id, cb.from_user.id):
        await _deny_answer(cb)
        return
    if data == "cb_play":
        awaiting[(chat_id, cb.from_user.id)] = "play"
        await cb.message.reply_text("▶️ Send me the song name or YouTube URL:")
        return
    if data == "cb_voice":
        awaiting[(chat_id, cb.from_user.id)] = "voice"
        await cb.message.reply_text(f"🎤 Reply to a voice/audio/video, then `{PREFIX}run` or `{PREFIX}play`.")
        return
    if data == "cb_panel":
        await cb.message.reply_text(
            core_card("player deck", stylish("transport  ·  loop  ·  boost  ·  volume")),
            reply_markup=player_panel(q),
        )
        return
    if data == "cb_menu":
        await send_with_banner(cb.message, hub_home_text(), hub_keyboard())
        return
    if data.startswith("hub_"):
        page = data[4:]
        if page == "music":
            await cb.message.reply_text(page_music_text(), reply_markup=hub_keyboard())
        elif page == "files":
            await cb.message.reply_text(page_files_text(), reply_markup=hub_keyboard())
        elif page == "tools":
            await cb.message.reply_text(page_tools_text(), reply_markup=hub_keyboard())
        elif page == "fun":
            await cb.message.reply_text(page_fun_text(), reply_markup=hub_keyboard())
        elif page == "help":
            await help_cmd(client, cb.message)
        elif page == "alive":
            await alive_cmd(client, cb.message)
        elif page == "about":
            await cb.message.reply_text(
                core_card("about", f"  {stylish('version')} `{CORE_VERSION}`", stylish("dev x core")),
                reply_markup=hub_keyboard(),
            )
        return
    if data == "cb_about":
        await cb.message.reply_text(core_card("about", f"  version `{CORE_VERSION}`"), reply_markup=hub_keyboard())
        return
    if data == "cb_admin":
        if not is_core_admin(cb.from_user.id):
            await cb.answer("❌ Owner / core admin only", show_alert=True)
            return
        await cb.message.reply_text(page_admin_text(), reply_markup=owner_panel())
        return
    if data == "cb_addadmin":
        if cb.from_user.id != OWNER_ID:
            await cb.answer("❌ Sirf OWNER", show_alert=True)
            return
        awaiting[(chat_id, cb.from_user.id)] = "addadmin"
        await cb.message.reply_text("👑 User ID bhejo:")
        return
    if data == "cb_deladmin":
        if cb.from_user.id != OWNER_ID:
            await cb.answer("❌ Sirf OWNER", show_alert=True)
            return
        awaiting[(chat_id, cb.from_user.id)] = "deladmin"
        await cb.message.reply_text("🗑️ User ID bhejo:")
        return
    if data == "cb_adminlist":
        if not is_core_admin(cb.from_user.id):
            await cb.answer("❌ Owner / core admin only", show_alert=True)
            return
        await cb.message.reply_text(admin_list_card(), reply_markup=admin_list_kb())
        return
    if data.startswith("alist_del_"):
        if cb.from_user.id != OWNER_ID:
            await cb.answer("❌ Sirf OWNER", show_alert=True)
            return
        try:
            uid = int(data.split("_")[-1])
        except ValueError:
            return
        if uid == OWNER_ID:
            await cb.answer("❌ Owner ko remove nahi", show_alert=True)
            return
        del_core_admin(uid)
        try:
            await cb.message.edit_text(admin_list_card(), reply_markup=admin_list_kb())
        except Exception:
            pass
        return
    if data == "cb_users":
        if not is_core_admin(cb.from_user.id):
            await cb.answer("❌ Owner / core admin only", show_alert=True)
            return
        await users_cmd(client, cb.message)
        return
    if data == "cb_servers":
        if not is_core_admin(cb.from_user.id):
            await cb.answer("❌ Owner / core admin only", show_alert=True)
            return
        await servers_cmd(client, cb.message)
        return
    if data == "cb_broadcast":
        if not is_core_admin(cb.from_user.id):
            await cb.answer("❌ Owner / core admin only", show_alert=True)
            return
        awaiting[(chat_id, cb.from_user.id)] = "broadcast"
        await cb.message.reply_text("📢 Send the broadcast message text:")
        return
    if data == "cb_volume":
        await cb.message.reply_text(f"🎚️ Volume: {fmt_vol(q.volume)}", reply_markup=volume_panel(q))
        return
    if data == "cb_lock":
        if not await is_group_admin(client, chat_id, cb.from_user.id):
            await cb.answer("❌ Group admins only", show_alert=True)
            return
        db.set_config(f"lock:{chat_id}", "1")
        await _deny_answer(cb)
        return
    if data == "cb_unlock":
        if not await is_group_admin(client, chat_id, cb.from_user.id):
            await cb.answer("❌ Group admins only", show_alert=True)
            return
        db.set_config(f"lock:{chat_id}", "0")
        await cb.answer("🔓 Unlocked", show_alert=True)
        return
    if data in CONTROL_CALLBACKS and not vc_ready():
        await cb.answer("❌ Voice engine not running", show_alert=True)
        return

    r = None
    if data == "cb_pause":
        try:
            await vc.pause(chat_id); r = "⏸️ Paused"
            _pause_timer(chat_id)
        except Exception:
            r = "❌ Nothing playing"
    elif data == "cb_resume":
        try:
            await vc.resume(chat_id); r = "▶️ Resumed"
            _resume_timer(chat_id)
        except Exception:
            r = "❌ Nothing paused"
    elif data == "cb_skip":
        if q.songs:
            old = q.current
            q.current = q.songs.popleft()
            await play_song(chat_id, q.current)
            if old is not None:
                _delete_temp_song_files(old)
            r = "⏭️ Skipped"
        else:
            old = q.current
            q.current = None
            if old is not None:
                _delete_temp_song_files(old)
            try:
                await vc.leave_call(chat_id)
            except Exception:
                pass
            active_calls.discard(chat_id)
            PLAY_TIMERS.pop(chat_id, None)
            r = "⏭️ Skipped (empty)"
    elif data == "cb_stop":
        old = q.current
        queued = list(q.songs)
        q.songs.clear(); q.current = None; q.loop = False; q.repeat = False
        q.silent_loop = False
        if old is not None:
            _delete_temp_song_files(old)
        for _s in queued:
            _delete_temp_song_files(_s)
        active_calls.discard(chat_id)
        PLAY_TIMERS.pop(chat_id, None)
        try:
            await vc.leave_call(chat_id); r = "⏹️ Stopped"
        except Exception:
            r = "❌ Not in call"
    elif data == "cb_loop":
        q.loop = not q.loop
        if q.loop:
            q.repeat = False
            q.silent_loop = True
        else:
            q.silent_loop = False
        r = f"🔁 Loop {'ON' if q.loop else 'OFF'}"
    elif data == "cb_repeat":
        q.repeat = not q.repeat
        if q.repeat:
            q.loop = False
            q.silent_loop = True
        else:
            q.silent_loop = False
        if q.current:
            await reapply_current_effects(chat_id)
        r = f"🔂 Repeat {'ON' if q.repeat else 'OFF'}"
    elif data == "cb_boost":
        q.boost_level = 0 if q.boost_level > 0 else 100
        if q.current:
            await reapply_current_effects(chat_id)
        r = f"🚀 Boost {q.boost_level}%"
    elif data == "cb_volup":
        q.volume = min(200, q.volume + 10)
        _vol_auto[chat_id] = False
        try:
            await vc.change_volume_call(chat_id, q.volume)
            _last_vol_applied[chat_id] = q.volume
        except Exception:
            pass
        r = f"🔊 {fmt_vol(q.volume)}"
    elif data == "cb_voldown":
        q.volume = max(0, q.volume - 10)
        _vol_auto[chat_id] = False
        try:
            await vc.change_volume_call(chat_id, q.volume)
            _last_vol_applied[chat_id] = q.volume
        except Exception:
            pass
        r = f"🔉 {fmt_vol(q.volume)}"
    elif data == "cb_vol200":
        q.volume = 200
        _vol_auto[chat_id] = False
        try:
            await vc.change_volume_call(chat_id, 200)
            _last_vol_applied[chat_id] = 200
        except Exception:
            pass
        r = "🔊 200%"
    elif data == "cb_vol_10":
        q.volume = 10; _vol_auto[chat_id] = False
        try:
            await vc.change_volume_call(chat_id, 10); _last_vol_applied[chat_id] = 10
        except Exception:
            pass
        r = "🎚️ 10%"
    elif data == "cb_vol_50":
        q.volume = 50; _vol_auto[chat_id] = False
        try:
            await vc.change_volume_call(chat_id, 50); _last_vol_applied[chat_id] = 50
        except Exception:
            pass
        r = "🎚️ 50%"
    elif data == "cb_vol_100":
        q.volume = 100; _vol_auto[chat_id] = False
        try:
            await vc.change_volume_call(chat_id, 100); _last_vol_applied[chat_id] = 100
        except Exception:
            pass
        r = "🎚️ 100%"
    elif data == "cb_vol_150":
        q.volume = 150; _vol_auto[chat_id] = False
        try:
            await vc.change_volume_call(chat_id, 150); _last_vol_applied[chat_id] = 150
        except Exception:
            pass
        r = "🎚️ 150%"
    elif data == "cb_mute":
        if _muted_state.get(chat_id):
            try:
                await vc.unmute(chat_id); r = "🔊 Unmuted"
            except Exception:
                r = "❌ Not in call"
            _muted_state[chat_id] = False
        else:
            try:
                await vc.mute(chat_id); r = "🔇 Muted"
            except Exception:
                r = "❌ Not in call"
            _muted_state[chat_id] = True
    elif data == "cb_sound":
        await sound_cmd(client, cb.message)
        return
    elif data == "cb_queue":
        text, kb = queue_panel(q, page=0)
        await cb.message.reply_text(text, reply_markup=kb)
        return
    elif data == "cb_now":
        await now_cmd(client, cb.message)
        return
    elif data == "cb_stats":
        await stats_cmd(client, cb.message)
        return
    elif data == "cb_help":
        await help_cmd(client, cb.message)
        return
    else:
        return
    try:
        await cb.message.edit_text("🎛️ **𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄 — Player Panel**\n" + r, reply_markup=player_panel(q))
    except Exception:
        pass
JOKES = [
    "I told my Wi-Fi we needed space. Now it keeps dropping me.",
    "A SQL query walks into a bar, walks up to two tables and asks: can I join you?",
    "I would tell you a UDP joke, but you might not get it.",
    "There are 10 kinds of people: those who get binary and those who don't.",
    "Why did the developer go broke? Because he used up all his cache.",
]
TRUTHS = [
    "What song is stuck in your head right now?",
    "What is a hill you will die on?",
    "Which group member has the best music taste?",
]
DARES = [
    "Send a voice note of your current song — badly.",
    "Change your last name to CORE for 10 minutes.",
    "Play the next track with .boost on.",
]

async def _target_user(client, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    arg = _arg(message)
    if arg.lstrip("-").isdigit():
        try:
            return await client.get_users(int(arg))
        except Exception:
            return None
    if arg:
        try:
            return await client.get_users(arg)
        except Exception:
            return None
    return message.from_user

@music.on_message(filters.command(["alive", "core"], prefixes=PREFIX))
async def alive_cmd(client, message):
    t0 = time.time()
    me = None
    try:
        me = getattr(client, "me", None)
        if me is None:
            me = await client.get_me()
        _ = me.id
    except Exception:
        try:
            me = await client.get_me()
        except Exception:
            me = None
    ping = round((time.time() - t0) * 1000, 1)
    if me and getattr(me, "username", None):
        uname = f"@{me.username}"
    elif me and getattr(me, "first_name", None):
        uname = me.first_name
    else:
        uname = "core"
    sync_saved_files()
    saved = db.get_files()
    body = (
        f"  💚 {stylish('status')}     **ONLINE**\n"
        f"  👤 {stylish('account')}    `{uname}`\n"
        f"  🚀 {stylish('ping')}       `{ping} ms`\n"
        f"  ⏱️  {stylish('uptime')}     `{fmt_uptime()}`\n"
        f"  📦 {stylish('version')}    `{CORE_VERSION}`\n"
        f"  🎛️  {stylish('engine')}     `{'on' if music_started else 'off'}`\n"
        f"  📞 {stylish('live vc')}    `{len(active_calls)}`\n"
        f"  📁 {stylish('vault')}      `{len(saved)}` files\n"
    )
    await send_with_banner(message, core_card("alive", body, stylish("system nominal")), hub_keyboard())

@music.on_message(filters.command("ping", prefixes=PREFIX))
async def ping_cmd(client, message):
    t0 = time.time()
    try:
        msg = await message.reply_text("⌁")
        ms = round((time.time() - t0) * 1000, 1)
        await msg.edit_text(
            core_card("ping ⚡",
                      f"  🚀  `{ms} ms`\n"
                      f"  ⏱️  {stylish('uptime')}  `{fmt_uptime()}`\n"
                      f"  🎛️  {stylish('engine')}   `{'on' if music_started else 'off'}`")
        )
    except Exception:
        try:
            await message.reply_text("🏓 Pong!")
        except Exception:
            pass

@music.on_message(filters.command(["uptime", "status"], prefixes=PREFIX))
async def uptime_cmd(client, message):
    await stats_cmd(client, message)

@music.on_message(filters.command("sysinfo", prefixes=PREFIX))
async def sysinfo_cmd(client, message):
    import platform, shutil
    body = (
        f"  ▸  {stylish('python')}   `{platform.python_version()}`\n"
        f"  ▸  {stylish('system')}   `{platform.system()} {platform.release()}`\n"
        f"  ▸  {stylish('ffmpeg')}   `{'yes' if shutil.which('ffmpeg') else 'missing'}`\n"
        f"  ▸  {stylish('core')}     `{CORE_VERSION}`\n"
        f"  ▸  {stylish('uptime')}   `{fmt_uptime()}`\n"
    )
    await message.reply_text(core_card("sysinfo", body))

@music.on_message(filters.command("id", prefixes=PREFIX))
async def id_cmd(client, message):
    u = await _target_user(client, message)
    if not u:
        await message.reply_text("❌ User not found.")
        return
    body = (
        f"  ▸  {stylish('name')}   {u.first_name}\n"
        f"  ▸  {stylish('user')}   @{u.username or '—'}\n"
        f"  ▸  {stylish('id')}     `{u.id}`\n"
        f"  ▸  {stylish('chat')}   `{message.chat.id}`\n"
    )
    await message.reply_text(core_card("identity", body))

@music.on_message(filters.command("chatid", prefixes=PREFIX))
async def chatid_cmd(client, message):
    c = message.chat
    await message.reply_text(core_card("chat", f"  ▸  {c.title or 'private'}\n  ▸  `{c.id}`\n  ▸  {c.type}"))

@music.on_message(filters.command(["whois", "info"], prefixes=PREFIX))
async def whois_cmd(client, message):
    u = await _target_user(client, message)
    if not u:
        await message.reply_text("❌ User not found.")
        return
    body = (
        f"  ▸  {u.first_name} {u.last_name or ''}\n"
        f"  ▸  @{u.username or '—'}\n"
        f"  ▸  `{u.id}`\n"
        f"  ▸  bot: `{bool(u.is_bot)}`\n"
    )
    await message.reply_text(core_card("whois", body))

@music.on_message(filters.command("setname", prefixes=PREFIX) & filters.user(OWNER_ID))
async def setname_cmd(client, message):
    name = _arg(message)
    if not name:
        await message.reply_text("❌ `.setname Your Name`")
        return
    await client.update_profile(first_name=name[:64])
    await message.reply_text(f"✅ name set → **{name[:64]}**")

@music.on_message(filters.command("setbio", prefixes=PREFIX) & filters.user(OWNER_ID))
async def setbio_ub_cmd(client, message):
    bio = _arg(message)
    if not bio:
        await message.reply_text("❌ `.setbio your bio`")
        return
    await client.update_profile(bio=bio[:70])
    await message.reply_text("✅ bio set")

@music.on_message(filters.command("setpp", prefixes=PREFIX) & filters.user(OWNER_ID))
async def setpp_cmd(client, message):
    r = message.reply_to_message
    if not r or not (r.photo or r.document):
        await message.reply_text("❌ Reply to a photo with `.setpp`")
        return
    path = await r.download()
    try:
        await client.set_profile_photo(photo=path)
        await message.reply_text("✅ profile photo updated")
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

@music.on_message(filters.command("getpp", prefixes=PREFIX))
async def getpp_cmd(client, message):
    u = await _target_user(client, message)
    if not u:
        await message.reply_text("❌ User not found.")
        return
    photos = []
    try:
        async for ph in client.get_chat_photos(u.id, limit=1):
            photos.append(ph)
    except Exception as e:
        await message.reply_text(f"❌ {e}")
        return
    if not photos:
        await message.reply_text("📭 No profile photo.")
        return
    await message.reply_photo(photos[0].file_id, caption=f"{u.first_name} · `{u.id}`")

@music.on_message(filters.command(["time", "date"], prefixes=PREFIX))
async def time_cmd(client, message):
    now = datetime.now()
    await message.reply_text(core_card("clock 🕰️", f"  ⏰  `{now.strftime('%H:%M:%S')}`\n  📅  `{now.strftime('%A, %d %B %Y')}`"))

@music.on_message(filters.command("calc", prefixes=PREFIX))
async def calc_cmd(client, message):
    expr = _arg(message)
    if not expr:
        await message.reply_text("❌ `.calc 2+2*8`")
        return
    if not re.fullmatch(r"[0-9+\-*/().% ]+", expr):
        await message.reply_text("❌ Numbers and + - * / ( ) % only.")
        return
    try:
        val = eval(expr, {"__builtins__": {}}, {})
        await message.reply_text(core_card("calc", f"  `{expr}`\n  = **{val}**"))
    except Exception as e:
        await message.reply_text(f"❌ {e}")

@music.on_message(filters.command("weather", prefixes=PREFIX))
async def weather_cmd(client, message):
    city = _arg(message) or "Delhi"
    url = f"https://wttr.in/{city}?format=j1"
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=timeout, headers={"User-Agent": "devx-core"}) as r:
                data = await r.json(content_type=None)
        cur = (data.get("current_condition") or [{}])[0]
        area = ((data.get("nearest_area") or [{}])[0].get("areaName") or [{}])[0].get("value", city)
        desc = ((cur.get("weatherDesc") or [{}])[0]).get("value", "")
        body = (
            f"  ▸  {area}\n"
            f"  ▸  {desc}\n"
            f"  ▸  {cur.get('temp_C', '?')}°C\n"
        )
        await message.reply_text(core_card("weather", body))
    except Exception as e:
        await message.reply_text(f"❌ Weather failed: {e}")

@music.on_message(filters.command("qr", prefixes=PREFIX))
async def qr_cmd(client, message):
    data = _arg(message)
    if not data and message.reply_to_message:
        data = message.reply_to_message.text or ""
    if not data:
        await message.reply_text("❌ `.qr https://example.com`")
        return
    url = "https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=" + aiohttp.helpers.quote(data[:800], safe="")
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        path = os.path.join(TEMP_DIR, f"qr_{uuid.uuid4().hex}.png")
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=timeout) as r:
                if r.status != 200:
                    raise RuntimeError(r.status)
                with open(path, "wb") as f:
                    f.write(await r.read())
        await message.reply_photo(path, caption=f"QR · `{data[:80]}`")
        try:
            os.remove(path)
        except Exception:
            pass
    except Exception as e:
        await message.reply_text(f"❌ QR failed: {e}")

@music.on_message(filters.command("tts", prefixes=PREFIX))
async def tts_cmd(client, message):
    data = _arg(message)
    if not data and message.reply_to_message:
        data = message.reply_to_message.text or ""
    if not data:
        await message.reply_text("❌ `.tts hello world`")
        return
    try:
        from gtts import gTTS
    except Exception:
        await message.reply_text("❌ gTTS not installed.")
        return
    path = os.path.join(TEMP_DIR, f"tts_{uuid.uuid4().hex}.mp3")
    try:
        await asyncio.to_thread(lambda: gTTS(text=data[:400], lang="en").save(path))
        await message.reply_voice(path, caption=data[:80])
    except Exception as e:
        await message.reply_text(f"❌ TTS failed: {e}")
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

@music.on_message(filters.command("fancy", prefixes=PREFIX))
async def fancy_cmd(client, message):
    data = _arg(message) or (message.reply_to_message.text if message.reply_to_message else "")
    if not data:
        await message.reply_text("❌ `.fancy hello`")
        return
    await message.reply_text(stylish(data)[:4000])

@music.on_message(filters.command(["upper", "lower", "reverse"], prefixes=PREFIX))
async def textcase_cmd(client, message):
    data = _arg(message) or (message.reply_to_message.text if message.reply_to_message else "")
    if not data:
        await message.reply_text("❌ Give text.")
        return
    cmd = message.command[0]
    out = data.upper() if cmd == "upper" else (data.lower() if cmd == "lower" else data[::-1])
    await message.reply_text(f"`{out[:4000]}`")

@music.on_message(filters.command("md5", prefixes=PREFIX))
async def md5_cmd(client, message):
    data = _arg(message)
    if not data:
        await message.reply_text("❌ `.md5 text`")
        return
    await message.reply_text(f"`{hashlib.md5(data.encode()).hexdigest()}`")

@music.on_message(filters.command("password", prefixes=PREFIX))
async def password_cmd(client, message):
    n = 16
    if _arg(message).isdigit():
        n = max(8, min(64, int(_arg(message))))
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%"
    pw = "".join(random.choice(alphabet) for _ in range(n))
    await message.reply_text(core_card("password 🔐", f"  `{pw}`"))

@music.on_message(filters.command("notesadd", prefixes=PREFIX))
async def notesadd_cmd(client, message):
    data = _arg(message)
    if not data:
        await message.reply_text("❌ `.notesadd title | body`")
        return
    if "|" in data:
        title, body = [x.strip() for x in data.split("|", 1)]
    else:
        title, body = data[:40], data
    nid = db.add_note(message.from_user.id, title, body)
    await message.reply_text(f"✅ note `{nid}` saved — **{title}**")

@music.on_message(filters.command("noteslist", prefixes=PREFIX))
async def noteslist_cmd(client, message):
    rows = db.get_notes(message.from_user.id)
    if not rows:
        await message.reply_text("📭 No notes.")
        return
    body = ""
    for nid, title, nb, _ts in rows:
        body += f"  `{nid}`  **{title}**\n      {nb[:80]}\n"
    await message.reply_text(core_card("notes", body, ".notesdel <id>"))

@music.on_message(filters.command(["notesdel", "notesdelete"], prefixes=PREFIX))
async def notesdel_cmd(client, message):
    arg = _arg(message)
    if not arg.isdigit():
        await message.reply_text("❌ `.notesdel 3`")
        return
    ok = db.delete_note(message.from_user.id, int(arg))
    await message.reply_text("✅ deleted" if ok else "❌ not found")

@music.on_message(filters.command("flip", prefixes=PREFIX))
async def flip_cmd(client, message):
    await message.reply_text("🪙  **" + random.choice(["HEADS", "TAILS"]) + "**")

@music.on_message(filters.command("dice", prefixes=PREFIX))
async def dice_cmd(client, message):
    await message.reply_text(f"🎲  **{random.randint(1, 6)}**")

@music.on_message(filters.command(["8ball", "eightball"], prefixes=PREFIX))
async def eightball_cmd(client, message):
    ans = random.choice(["Yes.", "No.", "Ask again later.", "Absolutely.", "Don't count on it.", "Maybe."])
    await message.reply_text(f"🎱  {ans}")

@music.on_message(filters.command("joke", prefixes=PREFIX))
async def joke_cmd(client, message):
    await message.reply_text("😂  " + random.choice(JOKES))

@music.on_message(filters.command("choose", prefixes=PREFIX))
async def choose_cmd(client, message):
    data = _arg(message)
    parts = [x.strip() for x in re.split(r"\||,", data) if x.strip()]
    if len(parts) < 2:
        await message.reply_text("❌ `.choose red | blue | green`")
        return
    await message.reply_text("👉  **" + random.choice(parts) + "**")

@music.on_message(filters.command("rps", prefixes=PREFIX))
async def rps_cmd(client, message):
    you = _arg(message).lower()
    if you not in ("rock", "paper", "scissors"):
        await message.reply_text("❌ `.rps rock|paper|scissors`")
        return
    botc = random.choice(["rock", "paper", "scissors"])
    win = {("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")}
    if you == botc:
        res = "draw"
    elif (you, botc) in win:
        res = "you win"
    else:
        res = "core wins"
    await message.reply_text(f"you `{you}` · core `{botc}`\n**{res}**")

@music.on_message(filters.command("truth", prefixes=PREFIX))
async def truth_cmd(client, message):
    await message.reply_text("🗣  " + random.choice(TRUTHS))

@music.on_message(filters.command("dare", prefixes=PREFIX))
async def dare_cmd(client, message):
    await message.reply_text("⚡  " + random.choice(DARES))

@music.on_message(filters.command("purge", prefixes=PREFIX))
async def purge_cmd(client, message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Admins only.")
        return
    if not message.reply_to_message:
        await message.reply_text("❌ Reply to the first message to purge from.")
        return
    start = message.reply_to_message.id
    end = message.id
    try:
        await client.delete_messages(message.chat.id, list(range(start, end + 1)))
        deleted = end - start + 1
    except Exception as e:
        await message.reply_text(f"❌ {e}")
        return
    msg = await message.reply_text(f"🧹 purged ~{deleted}")
    await asyncio.sleep(2)
    try:
        await msg.delete()
    except Exception:
        pass

@music.on_message(filters.command("pin", prefixes=PREFIX))
async def pin_cmd(client, message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Admins only.")
        return
    if not message.reply_to_message:
        await message.reply_text("❌ Reply to a message with `.pin`")
        return
    await message.reply_to_message.pin()
    await message.reply_text("📌 pinned.")

@music.on_message(filters.command("unpin", prefixes=PREFIX))
async def unpin_cmd(client, message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Admins only.")
        return
    try:
        await client.unpin_chat_message(message.chat.id)
        await message.reply_text("📌 unpinned.")
    except Exception as e:
        await message.reply_text(f"❌ {e}")

@music.on_message(filters.command(["kick"], prefixes=PREFIX))
async def kick_cmd(client, message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Admins only.")
        return
    u = await _target_user(client, message)
    if not u or u.id == message.from_user.id:
        await message.reply_text("❌ Reply to a user or give an id.")
        return
    try:
        await client.ban_chat_member(message.chat.id, u.id)
        await client.unban_chat_member(message.chat.id, u.id)
        await message.reply_text(f"👢 kicked {u.first_name}")
    except Exception as e:
        await message.reply_text(f"❌ {e}")

@music.on_message(filters.command("promote", prefixes=PREFIX))
async def promote_cmd(client, message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Admins only.")
        return
    u = await _target_user(client, message)
    if not u:
        await message.reply_text("❌ Reply to a user.")
        return
    try:
        await client.promote_chat_member(message.chat.id, u.id, can_manage_chat=True, can_delete_messages=True, can_invite_users=True)
        await message.reply_text(f"⬆️ promoted {u.first_name}")
    except Exception as e:
        await message.reply_text(f"❌ {e}")

@music.on_message(filters.command("demote", prefixes=PREFIX))
async def demote_cmd(client, message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Admins only.")
        return
    u = await _target_user(client, message)
    if not u:
        await message.reply_text("❌ Reply to a user.")
        return
    try:
        await client.promote_chat_member(message.chat.id, u.id, can_manage_chat=False)
        await message.reply_text(f"⬇️ demoted {u.first_name}")
    except Exception as e:
        await message.reply_text(f"❌ {e}")
def clean_phone(text):
    return "".join(ch for ch in text if ch.isdigit() or ch == "+")

async def safe_cleanup(client):
    try:
        await client.disconnect()
    except Exception:
        pass

async def start_music():
    global vc, music_started
    if music_started:
        return
    if not SESSION_STRING:
        logger.error("start_music() called but no session string.")
        return
    compat_ok, compat_msg = check_engine_compat()
    if not compat_ok:
        logger.error(compat_msg)
        print("\n  ❌ " + compat_msg.replace("\n", "\n     ") + "\n")
    try:
        music.session_string = SESSION_STRING
        music.storage = MemoryStorage(SESSION_NAME, SESSION_STRING)
        await music.start()
        logger.info("Music userbot started")
        vc = PyTgCalls(music)
        if hasattr(vc, "add_handler"):
            vc.add_handler(on_stream_end)
        else:
            vc.on_stream_end(on_stream_end)
        await vc.start()
        logger.info("PyTgCalls started")
        asyncio.create_task(auto_enforce_loop())
        music_started = True
        logger.info("%s is running…", BOT_NAME)
    except Exception as e:
        import traceback as _tb
        logger.error("Music start error: %s", e)
        _tb.print_exc()
        vc = None
        music_started = False
        if isinstance(e, ImportError) and "GroupcallForbidden" in str(e):
            print("\n  ❌ py-tgcalls version bug — pin 2.2.5 + pyrogram 2.0.106\n")

@bot.on_message(filters.command("start"))
async def bot_start(client, message):
    me = await bot.get_me()
    await message.reply_text(
        f"🤖 **𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄 — Login Bot** (@{me.username})\n\n"
        f"👤 Your User ID: `{message.from_user.id}`\n\n"
        "Commands:\n"
        "/login — log in your user account (for music)\n"
        "/me — see your ID\n"
        "/status — check login/music status\n\n"
        "⚠️ /login can only be used by the owner."
    )

@bot.on_message(filters.command("status"))
async def bot_status(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text("❌ Owner only.")
        return
    try:
        from importlib.metadata import version as _dist_version
        pt_version = _dist_version("py-tgcalls")
    except Exception:
        pt_version = "?"
    compat_ok, compat_msg = check_engine_compat()
    lines = [
        "📊 **𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄 — Status**",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"🔑 Session string: {'✅ EXISTS' if SESSION_STRING else '❌ NOT SET'}",
        f"🎵 Music bot: {'✅ RUNNING' if music_started else '❌ NOT STARTED'}",
        f"💾 Session file: {'✅ FOUND' if os.path.exists(SESSION_FILE) else '❌ NOT FOUND'}",
        f"🔗 pytgcalls: `{pt_version}` · {'✅ compatible' if compat_ok else '❌ INCOMPATIBLE'}",
        f"🎭 Mode: `{get_mode()}`",
        f"📁 Data dir: `{DATA_DIR}`",
    ]
    if not compat_ok:
        lines.append("💊 Fix: pyrogram==2.0.106 + py-tgcalls==2.2.5")
    await message.reply_text("\n".join(lines))

@bot.on_message(filters.command("me"))
async def bot_me(client, message):
    uid = message.from_user.id
    owner = "✅ You ARE the owner!" if uid == OWNER_ID else "❌ You are NOT the owner."
    await message.reply_text(
        f"👤 **Your User ID:** `{uid}`\n"
        f"🔑 **Bot OWNER_ID:** `{OWNER_ID}`\n\n{owner}"
    )

@bot.on_message(filters.command("login"))
async def bot_login(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text(
            f"❌ You are not the owner.\nYour ID: `{message.from_user.id}`\nOwner ID: `{OWNER_ID}`"
        )
        return
    login_state[message.from_user.id] = {"step": "phone"}
    await message.reply_text(
        "📱 **Send your Telegram phone number**\n\n"
        "Format: `+91XXXXXXXXXX`\n\n"
        "This is the SAME account the music bot will use."
    )

@bot.on_message(filters.text & ~filters.command(["start", "login", "me", "status"]))
async def bot_text(client, message):
    global SESSION_STRING
    user_id = message.from_user.id
    st = login_state.get(user_id)
    if not st:
        return
    step = st["step"]
    if step == "phone":
        phone = clean_phone(message.text)
        if not phone.startswith("+") or len(phone) < 8:
            await message.reply_text("❌ Send a valid number. Format: `+91XXXXXXXXXX`")
            return
        user_client = Client(f"tmp_login_{user_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        try:
            await user_client.connect()
            sent = await user_client.send_code(phone)
            st.update({"step": "code", "phone": phone, "hash": sent.phone_code_hash, "user_client": user_client})
            await message.reply_text(
                "🔐 **OTP sent!**\n\n"
                "The code will arrive via Telegram app/SMS.\nNow send the **code here** (digits only)."
            )
        except FloodWait as e:
            await safe_cleanup(user_client); login_state.pop(user_id, None)
            await message.reply_text(f"⏳ FloodWait: wait {e.value} sec, then /login again.")
        except PhoneNumberInvalid:
            await safe_cleanup(user_client); login_state.pop(user_id, None)
            await message.reply_text("❌ Invalid phone number. Format: `+91XXXXXXXXXX`")
        except PhoneNumberUnoccupied:
            await safe_cleanup(user_client); login_state.pop(user_id, None)
            await message.reply_text("❌ This number is NOT registered on Telegram.")
        except PhoneNumberBanned:
            await safe_cleanup(user_client); login_state.pop(user_id, None)
            await message.reply_text("❌ This number is banned by Telegram.")
        except Exception as e:
            logger.error("Login error (phone step): %s", e)
            await safe_cleanup(user_client); login_state.pop(user_id, None)
            await message.reply_text(f"❌ Error: {e}")
        return
    if step == "code":
        user_client = st["user_client"]
        try:
            await user_client.sign_in(st["phone"], st["hash"], message.text.strip())
            ss = await user_client.export_session_string()
            await safe_cleanup(user_client)
            with open(SESSION_FILE, "w") as f:
                f.write(ss)
            SESSION_STRING = ss
            login_state.pop(user_id, None)
            logger.info("Login SUCCESS for user %s", user_id)
            await message.reply_text("✅ **Login successful!**\n\nMusic bot is **starting now**…")
            await start_music()
            await message.reply_text("🎉 **𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄 active!** The music bot is ready!")
        except SessionPasswordNeeded:
            hint = ""
            try:
                hint = await user_client.get_password_hint()
            except Exception:
                pass
            st["step"] = "2fa"
            await message.reply_text(
                "🔒 **2FA password is enabled!**\n\n" + (f"Hint: {hint}\n" if hint else "") + "Send your password."
            )
        except PhoneCodeInvalid:
            await message.reply_text("❌ Invalid code. Send the correct code.")
        except PhoneCodeExpired:
            try:
                sent = await user_client.send_code(st["phone"])
                st["hash"] = sent.phone_code_hash
                await message.reply_text("⏳ Code expired. I sent a **NEW code** — send it quickly.")
            except Exception as e2:
                login_state.pop(user_id, None)
                await message.reply_text(f"❌ Could not resend: {e2}. Use /login again.")
        except FloodWait as e:
            await message.reply_text(f"⏳ FloodWait: {e.value} sec.")
        except Exception as e:
            logger.error("Login error (code step): %s", e)
            login_state.pop(user_id, None)
            await message.reply_text(f"❌ Error: {e}")
        return
    if step == "2fa":
        user_client = st["user_client"]
        try:
            await user_client.check_password(message.text)
            ss = await user_client.export_session_string()
            await safe_cleanup(user_client)
            with open(SESSION_FILE, "w") as f:
                f.write(ss)
            SESSION_STRING = ss
            login_state.pop(user_id, None)
            logger.info("Login SUCCESS (2fa) for user %s", user_id)
            await message.reply_text("✅ **Login successful!**\n\nMusic bot is **starting now**…")
            await start_music()
            await message.reply_text("🎉 **𝐃𝐄𝐕 𝐗 𝐂𝐎𝐑𝐄 active!** The music bot is ready!")
        except PasswordHashInvalid:
            await message.reply_text("❌ Invalid password. Send it again.")
        except FloodWait as e:
            await message.reply_text(f"⏳ FloodWait: {e.value} sec.")
        except Exception as e:
            login_state.pop(user_id, None)
            await message.reply_text(f"❌ Error: {e}")
        return

async def main():
    global SESSION_STRING
    import shutil
    print("=" * 55)
    print(" DEV X CORE  v5.4  —  RAILWAY 24x7")
    print("=" * 55)
    print(f"  📁 DATA_DIR: {DATA_DIR}")
    if shutil.which("ffmpeg") is None:
        print("  ❌ WARNING: ffmpeg NOT FOUND!")
    else:
        print(f"  ✅ ffmpeg: {shutil.which('ffmpeg')}")
    convert_default_logo()
    compat_ok, compat_msg = check_engine_compat()
    if compat_ok:
        print("  ✅ py-tgcalls + pyrogram versions: compatible")
    else:
        print("  ❌ " + compat_msg.replace("\n", "\n     "))
    try:
        await bot.start()
        me = await bot.get_me()
        print(f"  ✅ Login bot started: @{me.username}")
        print(f"  ✅ Owner ID: {OWNER_ID}")
    except Exception as e:
        print(f"  ❌ Login bot start FAILED: {e}")
        await asyncio.sleep(2)
    if SESSION_STRING:
        print("  🔑 Session string found — starting music bot…")
        await start_music()
    else:
        print()
        print("  👉 Now send /login to your bot on Telegram")
        print("     The music bot will start automatically after login!")
    print("=" * 55)
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        LOOP.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    finally:
        try:
            db.close()
        except Exception:
            pass
