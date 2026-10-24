"""
users.py — Theo dõi người dùng bot + ID tin nhắn bot đã gửi.

Mục đích: tính năng "Xóa nhật ký" và bảng quản trị "Người dùng" trên Dashboard.
- Người dùng bấm xóa -> bot gọi deleteMessage cho các tin NHẮN CỦA BOT đã gửi
  cho họ (giới hạn của Telegram: bot chỉ xóa được tin do chính nó gửi; tin do
  người dùng tự gõ thì họ phải tự xóa trong app; tin bot quá cũ có thể bị từ chối).
- Dữ liệu vận hành (file này, user_prefs, signals, Supabase) KHÔNG bị xóa khi
  người dùng xóa nhật ký — máy chủ vẫn giữ để quản trị.
"""

import json
import logging
import os
from datetime import datetime, timezone

from database import DATA_DIR

logger = logging.getLogger(__name__)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
MSGS_FILE = os.path.join(DATA_DIR, "bot_messages.json")
MAX_MSGS_PER_USER = 300


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


def track_user(chat_id: str, name: str = "", username: str = "",
               lang: str = "") -> None:
    """Ghi nhận / cập nhật 1 người dùng bot (mỗi lần họ nhắn hoặc bấm nút)."""
    chat_id = str(chat_id)
    if not chat_id or chat_id == "guest":
        return
    users = _load(USERS_FILE)
    rec = users.get(chat_id, {})
    now = _now_iso()
    rec.setdefault("first_seen", now)
    rec["last_seen"] = now
    rec["interactions"] = int(rec.get("interactions", 0)) + 1
    if name:
        rec["name"] = name[:100]
    if username:
        rec["username"] = username[:100]
    if lang:
        rec["lang"] = lang[:10]
    users[chat_id] = rec
    _save(USERS_FILE, users)


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


def get_bot_message_ids(chat_id: str) -> list:
    msgs = _load(MSGS_FILE)
    return [int(m) for m in msgs.get(str(chat_id), []) if str(m).isdigit()]


def clear_bot_messages(chat_id: str) -> None:
    msgs = _load(MSGS_FILE)
    msgs.pop(str(chat_id), None)
    _save(MSGS_FILE, msgs)


def list_users() -> list:
    """Danh sách người dùng cho bảng quản trị: mới tương tác nhất lên trước."""
    users = _load(USERS_FILE)
    msgs = _load(MSGS_FILE)
    out = []
    for chat_id, rec in users.items():
        out.append({
            "chat_id": chat_id,
            "name": rec.get("name", ""),
            "username": rec.get("username", ""),
            "lang": rec.get("lang", ""),
            "first_seen": rec.get("first_seen", ""),
            "last_seen": rec.get("last_seen", ""),
            "interactions": rec.get("interactions", 0),
            "tracked_bot_messages": len(msgs.get(chat_id, [])),
        })
    out.sort(key=lambda r: r["last_seen"], reverse=True)
    return out
