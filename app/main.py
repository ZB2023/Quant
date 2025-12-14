import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response
from pydantic import BaseModel
from contextlib import contextmanager
from app.core.config import Cfg
import hashlib
import secrets
import logging
from typing import List, Optional, Dict, Tuple
import os
import uuid
import time
import sys
import traceback
import yt_dlp  # Убедитесь, что библиотека установлена

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("QuantServer")

app = FastAPI()

# Папка static больше не используется, файлы хранятся в БД.

typing_status: Dict[str, Tuple[str, float]] = {}

db_pool = None

def hash_pw(password: str) -> str:
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pw_hash.hex()}"

def check_pw(stored: str, provided: str) -> bool:
    try:
        salt, hash_val = stored.split('$')
        check = hashlib.pbkdf2_hmac('sha256', provided.encode(), salt.encode(), 100000)
        return check.hex() == hash_val
    except Exception:
        return False

try:
    print("[SERVER] Connecting to Database...")
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 20, 
        dbname=Cfg.DB_NAME, 
        user=Cfg.DB_USER, 
        password=Cfg.DB_PASS, 
        host=Cfg.DB_HOST, 
        port=Cfg.DB_PORT, 
        cursor_factory=RealDictCursor
    )
    print("[SERVER] Database Connected Successfully.")
except Exception as e:
    logger.critical(f"DB CONNECTION FAILED: {e}")
    db_pool = None

@contextmanager
def get_cursor():
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database Unavailable")
    
    conn = None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            db_pool.putconn(conn)

def check_db_schema():
    if db_pool is None:
        return

    try:
        with get_cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='media_groups' AND column_name='user_id';")
            if not cur.fetchone():
                cur.execute("DELETE FROM media_tracks")
                cur.execute("DELETE FROM media_groups")
                cur.execute("ALTER TABLE media_groups ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
            
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='user_profiles' AND column_name='avatar_url';")
            if not cur.fetchone():
                cur.execute("ALTER TABLE user_profiles ADD COLUMN avatar_url TEXT")

            # Проверка столбца для хранения байтов аватара
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='user_profiles' AND column_name='avatar_data';")
            if not cur.fetchone():
                logger.info("Adding avatar_data column (BYTEA) to user_profiles...")
                cur.execute("ALTER TABLE user_profiles ADD COLUMN avatar_data BYTEA")

    except Exception as e:
        logger.warning(f"Schema check failed: {e}")

check_db_schema()

# --- ФУНКЦИЯ ДЛЯ YOUTUBE-DL (которую потеряли) ---
def get_dl_strategies():
    base_opts = {'quiet': True, 'no_warnings': True, 'nocheckcertificate': True, 'ignoreerrors': True}
    strategies = [
        {'extractor_args': {'youtube': {'player_client': ['ios']}}, 'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)', **base_opts},
        {'extractor_args': {'youtube': {'player_client': ['web']}}, **base_opts},
        base_opts
    ]
    return strategies

# --- МОДЕЛИ ---
class AuthModel(BaseModel):
    login: str
    email: Optional[str] = None
    pw: str

class ActionModel(BaseModel):
    me: str
    target: str

class DelModel(BaseModel):
    username: str
    pw: str

class ProfileUpdateModel(BaseModel):
    username: str
    status_msg: str
    bio: str

class DelAvatarModel(BaseModel):
    username: str

class MsgModel(BaseModel):
    to_user: str
    text: str
    attachment_id: Optional[int] = None
    reply_to: Optional[int] = None

class ClearChatModel(BaseModel):
    me: str
    target: str
    for_all: bool

class DeleteMsgModel(BaseModel):
    id: int
    for_all: bool
    user: str

class EditMsgModel(BaseModel):
    id: int
    new_text: str
    user: str

class ReadMsgModel(BaseModel):
    ids: List[int]
    user: str

class TypingModel(BaseModel):
    user: str
    target: str
    status: bool

class MediaGroupModel(BaseModel):
    title: str
    author: str
    genre: str
    cover_path: str = ""
    username: str  

class MediaGroupUpdateModel(BaseModel):
    id: int
    title: str
    author: str
    genre: str
    cover_path: str = ""

class MediaGroupIDModel(BaseModel):
    id: int

class MediaTrackModel(BaseModel):
    group_id: int
    title: str
    performer: str
    file_path: str
    is_original: bool
    language: str
    rating: int
    parent_id: Optional[int] = None

class MediaTrackUpdateModel(BaseModel):
    id: int
    group_id: int
    title: str
    performer: str
    file_path: str
    is_original: bool
    language: str
    rating: int
    parent_id: Optional[int] = None

class MediaTrackIDModel(BaseModel):
    id: int

class BotAnalyzeModel(BaseModel):
    url: str

class BotDownloadModel(BaseModel):
    url: str
    format_type: str
    quality_id: str

# --- ENDPOINTS ---

@app.post("/register")
def reg(d: AuthModel):
    try:
        with get_cursor() as cur:
            # Проверка: занят ли логин
            cur.execute("SELECT 1 FROM users WHERE username = %s", (d.login,))
            if cur.fetchone():
                # Это НЕ ошибка сервера, это логическая ошибка клиента (400)
                raise HTTPException(status_code=400, detail="User exists")

            # Вставка данных (обрабатываем email если он пуст)
            email_val = d.email if d.email else ""
            
            cur.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (%s, %s, %s, NOW()) RETURNING id", 
                (d.login, email_val, hash_pw(d.pw))
            )
            
            # Получаем ID (поддержка разных типов курсора)
            row = cur.fetchone()
            uid = row['id'] if isinstance(row, dict) else row[0]
            
            # Создаем профиль
            cur.execute("INSERT INTO user_profiles (user_id) VALUES (%s)", (uid,))
            return {"status": "ok", "uid": uid}

    # ВАЖНО: Сначала ловим HTTPException и просто "пробрасываем" его дальше
    except HTTPException:
        raise 

    # Ловим всё остальное (настоящие поломки)
    except Exception as e:
        import traceback
        print("!!! REAL ERROR !!!")
        print(traceback.format_exc())
        logger.error(f"Register error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/login")
def login(d: AuthModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (d.login,))
            u = cur.fetchone()
            if not u or not check_pw(u['password_hash'], d.pw):
                time.sleep(0.5) 
                raise HTTPException(401, "Bad credentials")
            return {"status": "ok", "user": u['username']}
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(500, "Internal server error")

@app.get("/user/profile_info")
def get_profile_info(username: str):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            res = cur.fetchone()
            if not res:
                return {"status_msg": "", "bio": "", "avatar_url": ""}
            uid = res['id']
            cur.execute("SELECT status_msg, bio, avatar_url FROM user_profiles WHERE user_id=%s", (uid,))
            prof = cur.fetchone()
            if not prof:
                cur.execute("INSERT INTO user_profiles (user_id) VALUES (%s) RETURNING status_msg, bio, avatar_url", (uid,))
                prof = cur.fetchone()
            
            ava_url = prof.get('avatar_url') or ""
            
            return {"status_msg": prof.get('status_msg') or "", "bio": prof.get('bio') or "", "avatar_url": ava_url}
    except Exception as e:
        logger.error(f"Profile info error: {e}")
        return {"status_msg": "", "bio": "", "avatar_url": ""}

@app.post("/user/profile_update")
def update_profile(d: ProfileUpdateModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.username,))
            u = cur.fetchone()
            if not u:
                raise HTTPException(404, "User not found")
            cur.execute("UPDATE user_profiles SET status_msg = %s, bio = %s WHERE user_id = %s", (d.status_msg, d.bio, u['id']))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(500, "Internal server error")

# --- AVATAR HANDLING (DB STORAGE) ---

@app.post("/user/avatar/upload")
async def upload_avatar(username: str = Form(...), file: UploadFile = File(...)):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            res = cur.fetchone()
            if not res:
                raise HTTPException(404, "User not found")
            uid = res['id']

        file_bytes = await file.read()
        
        # Определяем mime type
        media_type = "image/png"
        header = file_bytes[:4]
        if header == b'GIF8': 
            media_type = 'image/gif'
        elif header.startswith(b'\xff\xd8'): 
            media_type = 'image/jpeg'
        
        ts = int(time.time())
        # Ссылка, которую клиент использует для запроса файла
        virtual_url = f"/user/content/avatar/{uid}?t={ts}"
        
        with get_cursor() as cur:
            # Сохраняем байты и ссылку
            cur.execute(
                "UPDATE user_profiles SET avatar_data=%s, avatar_url=%s WHERE user_id=%s", 
                (file_bytes, virtual_url, uid)
            )
        
        return {"status": "ok", "url": virtual_url}
    except Exception as e:
        logger.error(f"Avatar upload error: {e}")
        raise HTTPException(500, "Internal server error")

@app.get("/user/content/avatar/{user_id}")
def get_avatar_content(user_id: int):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT avatar_data FROM user_profiles WHERE user_id=%s", (user_id,))
            res = cur.fetchone()
            
            if not res or not res['avatar_data']:
                return Response(content=b"", status_code=404)
            
            data = bytes(res['avatar_data'])
            
            media_type = "image/png"
            if data[:4] == b'GIF8':
                media_type = "image/gif"
            elif data[:2] == b'\xff\xd8':
                media_type = "image/jpeg"
                
            return Response(content=data, media_type=media_type)
    except Exception as e:
        logger.error(f"Get avatar error: {e}")
        return Response(content=b"", status_code=500)

@app.post("/user/avatar/delete")
def delete_avatar_endpoint(d: DelAvatarModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.username,))
            u = cur.fetchone()
            if not u:
                raise HTTPException(404)
            
            cur.execute("UPDATE user_profiles SET avatar_url=NULL, avatar_data=NULL WHERE user_id=%s", (u['id'],))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Avatar delete error: {e}")
        raise HTTPException(500, "Internal server error")

# --- OTHER OPERATIONS ---

@app.delete("/user/delete")
def delete_user(d: DelModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE username=%s", (d.username,))
            user = cur.fetchone()
            if not user or not check_pw(user['password_hash'], d.pw):
                raise HTTPException(401, "Bad password")
            uid = user['id']
            
            cur.execute("DELETE FROM messages WHERE sender_id=%s OR receiver_id=%s", (uid, uid))
            cur.execute("DELETE FROM user_profiles WHERE user_id=%s", (uid,))
            cur.execute("DELETE FROM friends WHERE user_id=%s OR friend_id=%s", (uid, uid))
            cur.execute("DELETE FROM blacklist WHERE user_id=%s OR blocked_id=%s", (uid, uid))
            cur.execute("DELETE FROM users WHERE id=%s", (uid,))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"User delete error: {e}")
        raise HTTPException(500, "Internal server error")

@app.get("/users/search")
def search_user(query: str):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT username FROM users WHERE username ILIKE %s LIMIT 5", (f"{query}%",))
            return {"users": [r['username'] for r in cur.fetchall()]}
    except Exception as e:
        logger.error(f"User search error: {e}")
        return {"users": []}

@app.get("/contacts/list")
def get_contacts(username: str):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            res = cur.fetchone()
            if not res:
                return {"contacts": []}
            uid = res['id']
            
            query = """
                WITH LastMsgs AS (
                    SELECT 
                        CASE 
                            WHEN sender_id = %s THEN receiver_id 
                            ELSE sender_id 
                        END as contact_id,
                        MAX(id) as last_msg_id
                    FROM messages 
                    WHERE sender_id = %s OR receiver_id = %s
                    GROUP BY 1
                )
                SELECT 
                    u.id as user_id,
                    u.username,
                    up.avatar_url,
                    m.content as last_message,
                    m.created_at,
                    m.sender_id
                FROM LastMsgs lm
                JOIN users u ON u.id = lm.contact_id
                LEFT JOIN user_profiles up ON up.user_id = u.id
                JOIN messages m ON m.id = lm.last_msg_id
                ORDER BY m.id DESC
            """
            cur.execute(query, (uid, uid, uid))
            rows = cur.fetchall()
            
            contacts = []
            for r in rows:
                av = r['avatar_url'] or ""
                contacts.append({
                    "username": r['username'],
                    "avatar_url": av,
                    "last_message": r['last_message'],
                    "last_sender_id": r['sender_id'],
                    "timestamp": r['created_at'].isoformat() if r['created_at'] else ""
                })
                
            return {"contacts": contacts}
    except Exception as e:
        logger.error(f"Contacts list error: {e}")
        return {"contacts": []}

@app.post("/friends/request")
def send_req(d: ActionModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.me,))
            mid_row = cur.fetchone()
            if not mid_row: raise HTTPException(404, "User ME not found")
            mid = mid_row['id']
            
            cur.execute("SELECT id FROM users WHERE username=%s", (d.target,))
            tgt = cur.fetchone()
            if not tgt:
                raise HTTPException(404, "Target not found")
            if mid == tgt['id']:
                raise HTTPException(400, "Same user")
                
            cur.execute("SELECT 1 FROM blacklist WHERE user_id=%s AND blocked_id=%s", (tgt['id'], mid))
            if cur.fetchone():
                raise HTTPException(403, "Blocked")
                
            cur.execute("SELECT status FROM friends WHERE user_id=%s AND friend_id=%s", (mid, tgt['id']))
            if not cur.fetchone():
                cur.execute("INSERT INTO friends (user_id, friend_id, status) VALUES (%s, %s, 'pending')", (mid, tgt['id']))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Friend request error: {e}")
        raise HTTPException(500, "Internal server error")

@app.post("/friends/accept")
def accept_req(d: ActionModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.me,))
            mid = cur.fetchone()['id']
            cur.execute("SELECT id FROM users WHERE username=%s", (d.target,))
            tid = cur.fetchone()['id']
            cur.execute("UPDATE friends SET status='accepted' WHERE user_id=%s AND friend_id=%s", (tid, mid))
            cur.execute("SELECT 1 FROM friends WHERE user_id=%s AND friend_id=%s", (mid, tid))
            if cur.fetchone():
                cur.execute("UPDATE friends SET status='accepted' WHERE user_id=%s AND friend_id=%s", (mid, tid))
            else:
                cur.execute("INSERT INTO friends (user_id, friend_id, status) VALUES (%s, %s, 'accepted')", (mid, tid))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Friend accept error: {e}")
        raise HTTPException(500, "Internal server error")

@app.post("/friends/remove")
def rem_friend(d: ActionModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.me,))
            mid = cur.fetchone()['id']
            cur.execute("SELECT id FROM users WHERE username=%s", (d.target,))
            tid = cur.fetchone()['id']
            cur.execute("DELETE FROM friends WHERE (user_id=%s AND friend_id=%s) OR (user_id=%s AND friend_id=%s)", (mid, tid, tid, mid))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Friend remove error: {e}")
        raise HTTPException(500, "Internal server error")

@app.get("/friends/list")
def list_friends(user: str):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (user,))
            u = cur.fetchone()
            if not u:
                return {"friends": []}
            
            q = """
                SELECT u.id as user_id, u.username, p.avatar_url
                FROM friends f 
                JOIN users u ON f.friend_id = u.id 
                LEFT JOIN user_profiles p ON u.id = p.user_id 
                WHERE f.user_id = %s AND f.status = 'accepted'
            """
            cur.execute(q, (u['id'],))
            
            res = []
            for r in cur.fetchall():
                av = r['avatar_url'] or ""
                res.append({'username': r['username'], 'avatar_url': av})
                
            return {"friends": res}
    except Exception as e:
        logger.error(f"Friends list error: {e}")
        return {"friends": []}

@app.get("/friends/incoming")
def incoming(user: str):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (user,))
            u = cur.fetchone()
            if not u:
                return {"requests": []}
            
            q = """
                SELECT u.id as user_id, u.username, p.avatar_url
                FROM friends f 
                JOIN users u ON f.user_id = u.id 
                LEFT JOIN user_profiles p ON u.id = p.user_id 
                WHERE f.friend_id = %s AND f.status = 'pending'
            """
            cur.execute(q, (u['id'],))
            
            res = []
            for r in cur.fetchall():
                av = r['avatar_url'] or ""
                res.append({'username': r['username'], 'avatar_url': av})
                
            return {"requests": res}
    except Exception as e:
        logger.error(f"Incoming friends error: {e}")
        return {"requests": []}

@app.get("/blacklist/list")
def get_bl(user: str):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (user,))
            u = cur.fetchone()
            if not u:
                return {"blocked": []}
            q = """
                SELECT u.id as user_id, u.username, p.avatar_url
                FROM blacklist b 
                JOIN users u ON b.blocked_id=u.id 
                LEFT JOIN user_profiles p ON u.id = p.user_id 
                WHERE b.user_id=%s
            """
            cur.execute(q, (u['id'],))
            res = []
            for r in cur.fetchall():
                av = r['avatar_url'] or ""
                res.append({'username': r['username'], 'avatar_url': av})
            return {"blocked": res}
    except Exception as e:
        logger.error(f"Blacklist error: {e}")
        return {"blocked": []}

@app.post("/blacklist/block")
def block_u(d: ActionModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.me,))
            mid = cur.fetchone()['id']
            cur.execute("SELECT id FROM users WHERE username=%s", (d.target,))
            tid = cur.fetchone()['id']
            cur.execute("DELETE FROM friends WHERE (user_id=%s AND friend_id=%s) OR (user_id=%s AND friend_id=%s)", (mid, tid, tid, mid))
            if not cur.execute("SELECT 1 FROM blacklist WHERE user_id=%s AND blocked_id=%s", (mid, tid)):
                cur.execute("INSERT INTO blacklist (user_id, blocked_id) VALUES (%s, %s)", (mid, tid))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Block user error: {e}")
        raise HTTPException(500, "Internal server error")

@app.post("/blacklist/unblock")
def unblock_u(d: ActionModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.me,))
            mid = cur.fetchone()['id']
            cur.execute("SELECT id FROM users WHERE username=%s", (d.target,))
            tid = cur.fetchone()['id']
            cur.execute("DELETE FROM blacklist WHERE user_id=%s AND blocked_id=%s", (mid, tid))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Unblock user error: {e}")
        raise HTTPException(500, "Internal server error")

@app.post("/messages/send")
def send_m(sender: str, msg: MsgModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (sender,))
            sid = cur.fetchone()['id']
            cur.execute("SELECT id FROM users WHERE username=%s", (msg.to_user,))
            rid = cur.fetchone()['id']
            cur.execute("INSERT INTO messages (sender_id, receiver_id, content, attachment_id, reply_to_id, created_at, is_read, deleted_for_sender, deleted_for_receiver) VALUES (%s, %s, %s, %s, %s, NOW(), FALSE, FALSE, FALSE)", (sid, rid, msg.text, msg.attachment_id, msg.reply_to))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(500, "Internal server error")

@app.get("/messages/history")
def get_history(u1: str, u2: str, offset: int = 0, limit: int = 50):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (u1,))
            res1 = cur.fetchone()
            cur.execute("SELECT id FROM users WHERE username=%s", (u2,))
            res2 = cur.fetchone()
            if not res1 or not res2:
                return {"messages": []}
            id1, id2 = res1['id'], res2['id']
            query = """
                SELECT m.id, m.content, u.id as sender_uid, u.username as sender_name, up.avatar_url, m.created_at, m.sender_id, m.is_read, m.reply_to_id, m.attachment_id
                FROM messages m 
                JOIN users u ON m.sender_id = u.id 
                LEFT JOIN user_profiles up ON u.id = up.user_id
                WHERE 
                (
                    (sender_id=%s AND receiver_id=%s AND deleted_for_sender = FALSE) 
                    OR 
                    (sender_id=%s AND receiver_id=%s AND deleted_for_receiver = FALSE)
                )
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(query, (id1, id2, id2, id1, limit, offset))
            
            msgs = []
            for r in cur.fetchall():
                msg_dict = {
                    'id': r['id'],
                    'content': r['content'],
                    'sender_uid': r['sender_uid'],
                    'sender_name': r['sender_name'],
                    'avatar_url': r['avatar_url'] or "",
                    'created_at': r['created_at'].isoformat() if r['created_at'] else "",
                    'sender_id': r['sender_id'],
                    'is_read': r['is_read'],
                    'reply_to_id': r['reply_to_id'],
                    'attachment_id': r['attachment_id']
                }
                msgs.append(msg_dict)
            return {"messages": list(reversed(msgs))}
    except Exception as e:
        logger.error(f"Message history error: {e}")
        return {"messages": []}

@app.get("/messages/load")
def load_m(u1: str, u2: str, last_id: int = 0):
    try:
        if not u1 or not u2:
            raise HTTPException(400, "Both u1 and u2 parameters are required")
            
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (u1,))
            res1 = cur.fetchone()
            cur.execute("SELECT id FROM users WHERE username=%s", (u2,))
            res2 = cur.fetchone()
            if not res1 or not res2:
                return {"messages": []}
            id1, id2 = res1['id'], res2['id']
            query = """
                SELECT m.id, m.content, u.id as sender_uid, u.username as sender_name, up.avatar_url, m.created_at, m.sender_id, m.is_read, m.reply_to_id, m.attachment_id
                FROM messages m 
                JOIN users u ON m.sender_id = u.id 
                LEFT JOIN user_profiles up ON u.id = up.user_id
                WHERE 
                (
                    ((sender_id=%s AND receiver_id=%s AND deleted_for_sender = FALSE) 
                    OR 
                    (sender_id=%s AND receiver_id=%s AND deleted_for_receiver = FALSE))
                    AND m.id > %s
                )
                ORDER BY m.created_at ASC, m.id ASC
            """
            cur.execute(query, (id1, id2, id2, id1, last_id))
            
            msgs = []
            for r in cur.fetchall():
                msg_dict = {
                    'id': r['id'],
                    'content': r['content'],
                    'sender_uid': r['sender_uid'],
                    'sender_name': r['sender_name'],
                    'avatar_url': r['avatar_url'] or "",
                    'created_at': r['created_at'].isoformat() if r['created_at'] else "",
                    'sender_id': r['sender_id'],
                    'is_read': r['is_read'],
                    'reply_to_id': r['reply_to_id'],
                    'attachment_id': r['attachment_id']
                }
                msgs.append(msg_dict)
            return {"messages": msgs}
    except Exception as e:
        logger.error(f"Load messages error: {e}")
        return {"messages": []}

@app.post("/messages/clear")
def clear_chat(d: ClearChatModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.me,))
            mid = cur.fetchone()['id']
            cur.execute("SELECT id FROM users WHERE username=%s", (d.target,))
            tid = cur.fetchone()['id']
            if d.for_all:
                cur.execute("DELETE FROM messages WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)", (mid, tid, tid, mid))
            else:
                cur.execute("UPDATE messages SET deleted_for_sender=TRUE WHERE sender_id=%s AND receiver_id=%s", (mid, tid))
                cur.execute("UPDATE messages SET deleted_for_receiver=TRUE WHERE sender_id=%s AND receiver_id=%s", (tid, mid))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Clear chat error: {e}")
        raise HTTPException(500, "Internal server error")

@app.post("/messages/delete_one")
def delete_one_msg(d: DeleteMsgModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.user,))
            uid = cur.fetchone()['id']
            cur.execute("SELECT sender_id, receiver_id FROM messages WHERE id=%s", (d.id,))
            m = cur.fetchone()
            if not m:
                raise HTTPException(404)
            is_sender = (m['sender_id'] == uid)
            if d.for_all and is_sender:
                cur.execute("DELETE FROM messages WHERE id=%s", (d.id,))
            else:
                if is_sender:
                    cur.execute("UPDATE messages SET deleted_for_sender=TRUE WHERE id=%s", (d.id,))
                else:
                    cur.execute("UPDATE messages SET deleted_for_receiver=TRUE WHERE id=%s", (d.id,))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Delete message error: {e}")
        raise HTTPException(500, "Internal server error")

@app.post("/messages/read")
def read_msgs(d: ReadMsgModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.user,))
            uid = cur.fetchone()['id']
            if d.ids:
                cur.execute("UPDATE messages SET is_read=TRUE WHERE receiver_id=%s AND id = ANY(%s)", (uid, d.ids))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Read messages error: {e}")
        raise HTTPException(500, "Internal server error")

@app.post("/messages/edit")
def edit_msg(d: EditMsgModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (d.user,))
            uid = cur.fetchone()['id']
            cur.execute("SELECT sender_id FROM messages WHERE id=%s", (d.id,))
            m = cur.fetchone()
            if m and m['sender_id'] == uid:
                cur.execute("UPDATE messages SET content=%s WHERE id=%s", (d.new_text, d.id))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Edit message error: {e}")
        raise HTTPException(500, "Internal server error")

@app.post("/messages/typing")
def set_typing(d: TypingModel):
    try:
        if d.status:
            typing_status[d.user] = (d.target, time.time())
        else:
            if d.user in typing_status:
                del typing_status[d.user]
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Typing error: {e}")
        raise HTTPException(500, "Internal server error")

@app.get("/messages/typing")
def get_typing(user: str, me: str):
    try:
        if user in typing_status:
            target, ts = typing_status[user]
            if target == me and (time.time() - ts) < 5.0:
                return {"is_typing": True}
        return {"is_typing": False}
    except Exception as e:
        logger.error(f"Get typing error: {e}")
        return {"is_typing": False}

@app.post("/media/group")
def create_group(m: MediaGroupModel):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (m.username,))
            u = cur.fetchone()
            if not u:
                raise HTTPException(404, "User not found")
            
            cur.execute("""
                INSERT INTO media_groups (user_id, title, author, genre, cover_path) 
                VALUES (%s, %s, %s, %s, %s) 
                RETURNING id
            """, (u['id'], m.title, m.author, m.genre, m.cover_path))
            return {"id": cur.fetchone()['id']}
    except Exception as e:
        logger.error(f"Create group error: {e}")
        raise HTTPException(500, "Internal server error")

@app.put("/media/group/update")
def update_group(m: MediaGroupUpdateModel):
    try:
        with get_cursor() as cur:
            cur.execute("UPDATE media_groups SET title=%s, author=%s, genre=%s, cover_path=%s WHERE id=%s", (m.title, m.author, m.genre, m.cover_path, m.id))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Update group error: {e}")
        raise HTTPException(500, "Internal server error")

@app.delete("/media/group/delete")
def delete_group(d: MediaGroupIDModel):
    try:
        with get_cursor() as cur:
            cur.execute("DELETE FROM media_tracks WHERE group_id=%s", (d.id,))
            cur.execute("DELETE FROM media_groups WHERE id=%s", (d.id,))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Delete group error: {e}")
        raise HTTPException(500, "Internal server error")

@app.get("/media/groups")
def get_groups(username: Optional[str] = None):
    try:
        with get_cursor() as cur:
            if username:
                cur.execute("SELECT id FROM users WHERE username=%s", (username,))
                u = cur.fetchone()
                if not u:
                    return {"groups": []}
                cur.execute("""
                    SELECT * FROM media_groups 
                    WHERE user_id = %s
                    ORDER BY is_downloaded ASC, created_at DESC
                """, (u['id'],))
            else:
                return {"groups": []}
                
            groups = []
            for r in cur.fetchall():
                group_dict = {
                    'id': r['id'],
                    'user_id': r['user_id'],
                    'title': r['title'],
                    'author': r['author'],
                    'genre': r['genre'],
                    'cover_path': r['cover_path'],
                    'created_at': r['created_at'].isoformat() if r['created_at'] else "",
                    'is_downloaded': r['is_downloaded']
                }
                groups.append(group_dict)
            return {"groups": groups}
    except Exception as e:
        logger.error(f"Get groups error: {e}")
        return {"groups": []}

@app.post("/media/track")
def add_track(t: MediaTrackModel):
    try:
        with get_cursor() as cur:
            cur.execute("INSERT INTO media_tracks (group_id, title, performer, file_path, is_original, language, rating, parent_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", (t.group_id, t.title, t.performer, t.file_path, t.is_original, t.language, t.rating, t.parent_id))
            return {"id": cur.fetchone()['id']}
    except Exception as e:
        logger.error(f"Add track error: {e}")
        raise HTTPException(500, "Internal server error")

@app.put("/media/track/update")
def update_track(t: MediaTrackUpdateModel):
    try:
        with get_cursor() as cur:
            cur.execute("UPDATE media_tracks SET title=%s, performer=%s, file_path=%s, is_original=%s, language=%s, rating=%s, parent_id=%s WHERE id=%s", (t.title, t.performer, t.file_path, t.is_original, t.language, t.rating, t.parent_id, t.id))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Update track error: {e}")
        raise HTTPException(500, "Internal server error")

@app.delete("/media/track/delete")
def delete_track(d: MediaTrackIDModel):
    try:
        with get_cursor() as cur:
            cur.execute("DELETE FROM media_tracks WHERE id=%s", (d.id,))
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Delete track error: {e}")
        raise HTTPException(500, "Internal server error")

@app.get("/media/tracks")
def get_tracks(group_id: int):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM media_tracks WHERE group_id = %s ORDER BY is_original DESC, rating DESC", (group_id,))
            tracks = []
            for r in cur.fetchall():
                track_dict = {
                    'id': r['id'],
                    'group_id': r['group_id'],
                    'title': r['title'],
                    'performer': r['performer'],
                    'file_path': r['file_path'],
                    'is_original': r['is_original'],
                    'language': r['language'],
                    'rating': r['rating'],
                    'parent_id': r['parent_id']
                }
                tracks.append(track_dict)
            return {"tracks": tracks}
    except Exception as e:
        logger.error(f"Get tracks error: {e}")
        return {"tracks": []}

@app.get("/media/videos")
def get_videos_list():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM media_videos ORDER BY created_at DESC")
            videos = []
            for r in cur.fetchall():
                video_dict = {
                    'id': r['id'],
                    'title': r['title'],
                    'url': r['url'],
                    'duration': r['duration'],
                    'created_at': r['created_at'].isoformat() if r['created_at'] else ""
                }
                videos.append(video_dict)
            return {"videos": videos}
    except Exception as e:
        logger.error(f"Get videos error: {e}")
        return {"videos": []}

@app.post("/bot/analyze")
def analyze_url(d: BotAnalyzeModel):
    try:
        s = get_dl_strategies()
        for opts in s:
            try:
                opts.update({'skip_download': True, 'extract_flat': False})
                with yt_dlp.YoutubeDL(opts) as ydl:
                    i = ydl.extract_info(d.url, download=False)
                    if not i:
                        continue
                    return {
                        "status": "ok",
                        "title": i.get('title'),
                        "channel": i.get('uploader'),
                        "thumb": i.get('thumbnail'),
                        "duration": i.get('duration_string'),
                        "can_video": True,
                        "has_1080": False,
                        "has_720": False
                    }
            except:
                continue
        return {"status": "error", "msg": "Content unavailable"}
    except Exception as e:
        logger.error(f"Analyze URL error: {e}")
        return {"status": "error", "msg": "Internal server error"}

@app.post("/bot/download")
def download_media(d: BotDownloadModel):
    return {"status": "error", "msg": "Downloads disabled in DB mode for simplicity"}