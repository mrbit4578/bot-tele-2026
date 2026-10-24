"""
users.py — Theo dõi người dùng bot + ID tin nhắn bot đã gửi.

Mục đích: tính năng "Xóa nhật ký" và bảng quản trị "Người dùng" trên Dashboard.
- Người dùng bấm xóa -> bot gọi deleteMessage cho các tin NHẮN CỦA BOT đã gửi
  cho họ (giới hạn của Telegram: bot chỉ xóa được tin do chính nó gửi; tin do
  người dùng tự gõ thì họ phải tự xóa trong app; tin bot quá cũ có thể bị từ chối).
- Dữ liệu vận hành (file này, user_prefs, signals, Supabase) KHÔNG bị xóa khi
  người dùng xóa nhật ký — máy chủ vẫn giữ để quản trị.
- Lưu trữ 2 lớp: file local (dự phòng, nhanh) + Supabase (vĩnh viễn, mọi
  instance Vercel đều đọc chung — khắc phục lỗi bảng lúc ẩn lúc hiện do /tmp
  mỗi instance khác nhau). Khi Supabase chưa có bảng, code vẫn chạy bằng local.
"""

import json
import logging
import os
from datetime import datetime, timezone

from database import DATA_DIR, DatabaseManager

logger = logging.getLogger(__name__)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
MSGS_FILE = os.path.join(DATA_DIR, "bot_messages.json")
MAX_MSGS_PER_USER = 300

_DB = None


def _get_db():
    global _DB
    if _DB is None:
        try:
            _DB = DatabaseManager()
        except Exception as e:
            logger.warning(f"Không khởi tạo được DatabaseManager: {e}")
            _DB = False
    return _DB or None


def _supa():
    db = _get_db()
    if db is None or not db.is_supabase_configured:
        return None
    return db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Đọc {path} lỗi: {e}")
    return {}


def _save(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Ghi {path} lỗi: {e}")


def _local_user(chat_id: str) -> dict:
    return _load(USERS_FILE).get(str(chat_id), {})


def get_local_user(chat_id: str) -> dict:
    """Bản ghi local của 1 user (kèm trường nội bộ _username_checked_at)."""
    return _local_user(chat_id)


def mark_username_checked(chat_id: str) -> None:
    """Đánh dấu đã thử lấy username qua getChat (chống gọi API lặp)."""
    users = _load(USERS_FILE)
    rec = users.get(str(chat_id), {})
    rec["_username_checked_at"] = _now_iso()
    users[str(chat_id)] = rec
    _save(USERS_FILE, users)


def _supa_user(chat_id: str):
    db = _supa()
    if db is None:
        return None
    res = db._supabase_request("bot_users", "GET",
                               {"chat_id": f"eq.{chat_id}", "select": "*"})
    if isinstance(res, list) and res:
        return res[0]
    return None


def track_user(chat_id: str, name: str = "", username: str = "",
               lang: str = "", count_interaction: bool = True) -> None:
    """Ghi nhận / cập nhật 1 người dùng bot (mỗi lần họ nhắn hoặc bấm nút).
    count_interaction=False: chỉ bổ sung thông tin (vd username qua getChat),
    KHÔNG tính thêm lượt tương tác, KHÔNG đổi last_seen."""
    chat_id = str(chat_id)
    if not chat_id or chat_id == "guest":
        return
    users = _load(USERS_FILE)
    rec = users.get(chat_id, {})
    now = _now_iso()
    if count_interaction:
        rec.setdefault("first_seen", now)
        rec["last_seen"] = now
        rec["interactions"] = int(rec.get("interactions", 0)) + 1
    else:
        rec.setdefault("first_seen", now)
    if name:
        rec["name"] = name[:100]
    if username:
        rec["username"] = username[:100]
    if lang:
        rec["lang"] = lang[:10]
    users[chat_id] = rec
    _save(USERS_FILE, users)
    # Lớp Supabase: đọc trước để giữ first_seen + cộng dồn interactions
    db = _supa()
    if db is not None:
        try:
            old = _supa_user(chat_id) or {}
            payload = [{
                "chat_id": chat_id,
                "name": rec.get("name", old.get("name", "")),
                "username": rec.get("username", old.get("username", "")),
                "lang": rec.get("lang", old.get("lang", "")),
                "first_seen": old.get("first_seen") or rec.get("first_seen", now),
                "last_seen": now if count_interaction else old.get("last_seen", now),
                "interactions": int(old.get("interactions", 0)) + (1 if count_interaction else 0),
            }]
            db._supabase_request("bot_users", "POST", payload=payload,
                                 prefer="resolution=merge-duplicates")
        except Exception as e:
            logger.warning(f"Ghi bot_users Supabase lỗi: {e}")


def track_bot_message(chat_id: str, message_id: int) -> None:
    """Lưu ID 1 tin nhắn bot đã gửi (để xóa lại khi người dùng yêu cầu)."""
    chat_id = str(chat_id)
    try:
        mid = int(message_id)
    except (TypeError, ValueError):
        return
    msgs = _load(MSGS_FILE)
    lst = [int(m) for m in msgs.get(chat_id, []) if str(m).isdigit()]
    if mid not in lst:
        lst.append(mid)
    msgs[chat_id] = lst[-MAX_MSGS_PER_USER:]
    _save(MSGS_FILE, msgs)
    db = _supa()
    if db is not None:
        try:
            db._supabase_request("bot_messages", "POST",
                                 payload=[{"chat_id": chat_id, "message_id": mid}],
                                 prefer="resolution=merge-duplicates")
        except Exception as e:
            logger.warning(f"Ghi bot_messages Supabase lỗi: {e}")


def get_bot_message_ids(chat_id: str) -> list:
    """Hợp nhất ID tin bot từ Supabase + local (khử trùng)."""
    chat_id = str(chat_id)
    ids = set()
    db = _supa()
    if db is not None:
        try:
            res = db._supabase_request(
                "bot_messages", "GET",
                {"chat_id": f"eq.{chat_id}", "select": "message_id"})
            if isinstance(res, list):
                for row in res:
                    try:
                        ids.add(int(row.get("message_id")))
                    except (TypeError, ValueError):
                        pass
        except Exception as e:
            logger.warning(f"Đọc bot_messages Supabase lỗi: {e}")
    msgs = _load(MSGS_FILE)
    for m in msgs.get(chat_id, []):
        if str(m).isdigit():
            ids.add(int(m))
    return sorted(ids)


def clear_bot_messages(chat_id: str) -> None:
    msgs = _load(MSGS_FILE)
    msgs.pop(str(chat_id), None)
    _save(MSGS_FILE, msgs)
    db = _supa()
    if db is not None:
        try:
            db._supabase_request("bot_messages", "DELETE",
                                 {"chat_id": f"eq.{chat_id}"})
        except Exception as e:
            logger.warning(f"Xóa bot_messages Supabase lỗi: {e}")


def get_user(chat_id: str):
    """1 user đã hợp nhất (ưu tiên Supabase, dự phòng local)."""
    supa = _supa_user(str(chat_id))
    if supa:
        return supa
    local = _local_user(chat_id)
    if local:
        return {"chat_id": str(chat_id), **{k: v for k, v in local.items()
                                            if not k.startswith("_")}}
    return None


def list_users() -> list:
    """Danh sách người dùng cho bảng quản trị: mới tương tác nhất lên trước.
    Hợp nhất Supabase + local: user có ở Supabase lấy bản Supabase; user chỉ
    có ở local (ghi trước khi chạy SQL tạo bảng) vẫn hiện thêm."""
    users = _load(USERS_FILE)
    msgs = _load(MSGS_FILE)
    merged = {}
    for chat_id, rec in users.items():
        merged[str(chat_id)] = {
            "chat_id": str(chat_id),
            "name": rec.get("name", ""),
            "username": rec.get("username", ""),
            "lang": rec.get("lang", ""),
            "first_seen": rec.get("first_seen", ""),
            "last_seen": rec.get("last_seen", ""),
            "interactions": rec.get("interactions", 0),
        }
    db = _supa()
    if db is not None:
        try:
            res = db._supabase_request("bot_users", "GET", {"select": "*"})
            if isinstance(res, list):
                for row in res:
                    cid = str(row.get("chat_id", ""))
                    if not cid:
                        continue
                    merged[cid] = {
                        "chat_id": cid,
                        "name": row.get("name", ""),
                        "username": row.get("username", ""),
                        "lang": row.get("lang", ""),
                        "first_seen": row.get("first_seen", ""),
                        "last_seen": row.get("last_seen", ""),
                        "interactions": row.get("interactions", 0),
                    }
        except Exception as e:
            logger.warning(f"Đọc bot_users Supabase lỗi: {e}")
    out = []
    for cid, rec in merged.items():
        out.append(rec)
    # Đếm tin bot đã gửi: dùng hợp nhất (Supabase + local) theo từng user
    for rec in out:
        try:
            rec["tracked_bot_messages"] = len(get_bot_message_ids(rec["chat_id"]))
        except Exception:
            rec["tracked_bot_messages"] = 0
    out.sort(key=lambda r: r["last_seen"], reverse=True)
    return out
