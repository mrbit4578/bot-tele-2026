"""
signal_relay.py — Cầu nối tín hiệu NexusPilot Pro -> Telegram.

Cockpit NexusPilot (trình duyệt) POST tín hiệu đạt chuẩn về endpoint
/api/signal-relay của hệ thống bot này. Module này chịu trách nhiệm:

- Kiểm tra khóa chia sẻ SIGNAL_KEY (header X-Signal-Key, so sánh hmac).
- Chuẩn hóa + kiểm tra payload tín hiệu (symbol, direction, entry, SL, TP).
- Lọc theo ngưỡng điểm SIGNAL_MIN_SCORE (mặc định 80/100 — khớp guardrail
  của NexusPilot: tín hiệu yếu KHÔNG được phát).
- Chống trùng: cùng symbol + direction + engine trong SIGNAL_DEDUPE_MINUTES
  (mặc định 30 phút) chỉ gửi 1 lần.
- Định dạng tin nhắn tín hiệu tiếng Việt kèm miễn trừ trách nhiệm.
- Lưu lịch sử tín hiệu đã nhận vào DATA_DIR/signals.json (tối đa 50 bản ghi)
  để lệnh /tin_hieu đọc lại tín hiệu mới nhất.

Nơi nhận tin: biến môi trường SIGNAL_CHAT_ID, không có thì dùng CHAT_ID.
"""

import hmac
import json
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COCKPIT_URL = "https://mt5-mrbit-2026-v2.onrender.com/"
MAX_RECORDS = 50
_LOCK = threading.Lock()


def _data_dir() -> Path:
    custom = os.getenv("BOT_DATA_DIR", "").strip()
    if custom:
        p = Path(custom)
    elif os.getenv("VERCEL"):
        p = Path("/tmp/bot_tele_data")
    else:
        p = Path(__file__).resolve().parent / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _store_path() -> Path:
    return _data_dir() / "signals.json"


def signal_key() -> str:
    return os.getenv("SIGNAL_KEY", "").strip()


def min_score() -> float:
    try:
        return float(os.getenv("SIGNAL_MIN_SCORE", "80"))
    except ValueError:
        return 80.0


def dedupe_minutes() -> int:
    try:
        return int(os.getenv("SIGNAL_DEDUPE_MINUTES", "30"))
    except ValueError:
        return 30


def destination_chat_id() -> str:
    return (os.getenv("SIGNAL_CHAT_ID", "").strip()
            or os.getenv("CHAT_ID", "").strip())


def check_key(provided: Optional[str]) -> bool:
    expected = signal_key()
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided.strip(), expected)


def load_records() -> List[Dict[str, Any]]:
    try:
        raw = _store_path().read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_records(records: List[Dict[str, Any]]) -> None:
    path = _store_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(records[:MAX_RECORDS], ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(path)


def record_signal(sig: Dict[str, Any], sent: bool, reason: str = "") -> Dict[str, Any]:
    rec = dict(sig)
    rec["_received_at"] = datetime.now(timezone.utc).isoformat()
    rec["_sent"] = bool(sent)
    if reason:
        rec["_reason"] = reason
    with _LOCK:
        records = load_records()
        records.insert(0, rec)
        _save_records(records)
    return rec


def recent_signals(limit: int = 10, only_sent: bool = False) -> List[Dict[str, Any]]:
    records = load_records()
    if only_sent:
        records = [r for r in records if r.get("_sent")]
    return records[:limit]


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_signal(payload: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """Trả về (signal đã chuẩn hóa, '') hoặc (None, lý do lỗi)."""
    if not isinstance(payload, dict):
        return None, "Payload phai la JSON object."
    symbol = str(payload.get("symbol", "")).strip().upper()
    direction = str(payload.get("direction", "")).strip().upper()
    entry = _num(payload.get("entry_price", payload.get("entry")))
    sl = _num(payload.get("stop_loss", payload.get("sl")))
    tp1 = _num(payload.get("tp1"))
    if not symbol:
        return None, "Thieu symbol."
    if direction not in ("BUY", "SELL"):
        return None, "direction phai la BUY hoac SELL."
    if entry is None or sl is None or tp1 is None:
        return None, "Thieu entry_price / stop_loss / tp1 dang so."
    if direction == "BUY" and not (sl < entry < tp1):
        return None, "Gia khong hop le cho lenh BUY (can SL < Entry < TP1)."
    if direction == "SELL" and not (tp1 < entry < sl):
        return None, "Gia khong hop le cho lenh SELL (can TP1 < Entry < SL)."
    score = _num(payload.get("score"))
    sig: Dict[str, Any] = {
        "symbol": symbol,
        "direction": direction,
        "timeframe": str(payload.get("timeframe", "M15")).strip() or "M15",
        "engine": str(payload.get("engine", "")).strip(),
        "engine_name": str(payload.get("engine_name", payload.get("engine", ""))).strip(),
        "entry_price": entry,
        "stop_loss": sl,
        "tp1": tp1,
        "tp2": _num(payload.get("tp2")),
        "tp3": _num(payload.get("tp3")),
        "score": score,
        "quality": str(payload.get("quality", "")).strip(),
        "suggested_lot": _num(payload.get("suggested_lot", payload.get("lot"))),
        "rationale": str(payload.get("rationale", "")).strip()[:400],
        "source": str(payload.get("source", "cockpit")).strip()[:40],
    }
    return sig, ""


def dedupe_key(sig: Dict[str, Any]) -> str:
    return f"{sig['symbol']}|{sig['direction']}|{sig.get('engine', '')}"


def find_duplicate(sig: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Tìm tín hiệu đã GỬI gần đây trùng khóa chống trùng."""
    window = timedelta(minutes=dedupe_minutes())
    now = datetime.now(timezone.utc)
    for rec in load_records():
        if not rec.get("_sent"):
            continue
        if dedupe_key(rec) != dedupe_key(sig):
            continue
        try:
            ts = datetime.fromisoformat(rec.get("_received_at", ""))
        except ValueError:
            continue
        if now - ts <= window:
            return rec
    return None


def _fmt_price(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if value >= 1000:
        return f"{value:,.2f}"
    if value >= 10:
        return f"{value:.2f}"
    return f"{value:.4f}"


def format_signal_message(sig: Dict[str, Any]) -> str:
    """Định dạng tin nhắn tín hiệu gửi lên Telegram (Markdown an toàn cơ bản)."""
    arrow = "🟢" if sig["direction"] == "BUY" else "🔴"
    tps = [f"TP1 {_fmt_price(sig.get('tp1'))}"]
    if sig.get("tp2") is not None:
        tps.append(f"TP2 {_fmt_price(sig['tp2'])}")
    if sig.get("tp3") is not None:
        tps.append(f"TP3 {_fmt_price(sig['tp3'])}")
    lines = [
        f"🚀 **TÍN HIỆU MỚI — {sig['symbol']} ({sig['timeframe']})**",
        f"{arrow} **{sig['direction']}** @ {_fmt_price(sig.get('entry_price'))}",
        f"🎯 {' · '.join(tps)}",
        f"🛡 SL {_fmt_price(sig.get('stop_loss'))}",
    ]
    meta = []
    if sig.get("score") is not None:
        meta.append(f"Điểm {sig['score']:.0f}/100")
    if sig.get("quality"):
        meta.append(f"Chất lượng {sig['quality']}")
    if sig.get("engine_name") or sig.get("engine"):
        meta.append(f"Engine {sig.get('engine_name') or sig.get('engine')}")
    if sig.get("suggested_lot") is not None:
        meta.append(f"Lot gợi ý {sig['suggested_lot']:.2f}")
    if meta:
        lines.append("📊 " + " · ".join(meta))
    if sig.get("rationale"):
        lines.append(f"📝 {sig['rationale']}")
    vn_now = datetime.now(timezone.utc) + timedelta(hours=7)
    lines.append(f"⏰ {vn_now.strftime('%d/%m/%Y %H:%M')} (giờ VN)")
    lines.append(
        "⚠️ Tín hiệu tham khảo từ hệ thống NexusPilot Pro — không phải lời khuyên "
        "đầu tư. Hãy tự kiểm tra và quản trị rủi ro trước khi vào lệnh."
    )
    lines.append(f"🖥 Cockpit: {COCKPIT_URL}")
    return "\n".join(lines)


def latest_signal_text() -> str:
    """Văn bản cho lệnh /tin_hieu: tín hiệu đã gửi mới nhất."""
    sent = recent_signals(limit=1, only_sent=True)
    if not sent:
        return (
            "📡 Chưa có tín hiệu đạt chuẩn nào được phát.\n"
            f"Hệ thống chỉ phát tín hiệu có điểm từ {min_score():.0f}/100 trở lên "
            "để tránh nhiễu. Khi Cockpit NexusPilot xuất hiện tín hiệu đạt chuẩn, "
            "bot sẽ tự gửi về đây."
        )
    sig = sent[0]
    return "📡 **TÍN HIỆU GẦN NHẤT:**\n\n" + format_signal_message(sig)
