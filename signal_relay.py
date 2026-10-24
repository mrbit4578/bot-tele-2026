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


def recent_signals(limit: int = 10, only_sent: bool = False,
                   include_demo: bool = False) -> List[Dict[str, Any]]:
    records = load_records()
    if only_sent:
        records = [r for r in records if r.get("_sent")]
    if not include_demo:
        records = [r for r in records if not r.get("demo")]
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
        "demo": bool(payload.get("demo", False)),
        "change_24h": _num(payload.get("change_24h")),
        "high_24h": _num(payload.get("high_24h")),
        "low_24h": _num(payload.get("low_24h")),
        "volume_24h": str(payload.get("volume_24h", "")).strip()[:30],
        "chart_source": str(payload.get("chart_source", "")).strip()[:60],
    }
    try:
        import chart as _chart
        sig["candles"] = _chart.normalize_candles(payload.get("candles"), cap=120)
    except Exception:
        sig["candles"] = []
    return sig, ""


def dedupe_key(sig: Dict[str, Any]) -> str:
    return f"{sig['symbol']}|{sig['direction']}|{sig.get('engine', '')}"


def find_duplicate(sig: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Tìm tín hiệu đã GỬI gần đây trùng khóa chống trùng."""
    window = timedelta(minutes=dedupe_minutes())
    now = datetime.now(timezone.utc)
    for rec in load_records():
        if not rec.get("_sent") or rec.get("demo"):
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


def _pct(entry: float, level: float, direction: str) -> float:
    """% cach Entry, quy uoc: SL luon am, TP luon duong."""
    if direction == "BUY":
        return (level - entry) / entry * 100
    return (entry - level) / entry * 100


def order_line(sig: Dict[str, Any]) -> str:
    """Dong lenh 1 dong, copy-paste duoc ngay."""
    parts = [sig["symbol"], sig["direction"], _fmt_price(sig.get("entry_price")),
             "SL", _fmt_price(sig.get("stop_loss"))]
    for k in ("tp1", "tp2", "tp3"):
        if sig.get(k) is not None:
            parts += [k.upper(), _fmt_price(sig[k])]
    return " ".join(parts)


def signal_keyboard(sig: Dict[str, Any]) -> Dict[str, Any]:
    """Nut duoi tin hieu: Charts (xem chi tiet) | Chat (nick hay) | CHEP MA (copy lenh)."""
    return {"inline_keyboard": [
        [{"text": "📊 Charts", "callback_data": "signal_chart"},
         {"text": "💬 Chat", "url": "https://t.me/soledadhuong90"}],
        [{"text": "📋 CHÉP MÃ", "copy_text": {"text": order_line(sig)}}],
    ]}


def format_signal_message(sig: Dict[str, Any]) -> str:
    """Bố cục kiểu kênh mẫu: headline + khối số liệu + dòng lệnh copy + miễn trừ."""
    entry = sig.get("entry_price")
    direction = sig["direction"]
    heart = "💚" if direction == "BUY" else "❤️"
    lines = []
    if sig.get("demo"):
        lines.append("🧪 **BẢN TEST THIẾT KẾ — KHÔNG PHẢI TÍN HIỆU THẬT**")
        lines.append("Số liệu dưới đây chỉ minh họa bố cục, chưa đủ điều kiện phát thật (80/100).")
    score_txt = f" · {sig['score']:.0f}/100 điểm" if sig.get("score") is not None else ""
    engine_txt = f" · {sig['engine_name'] or sig['engine']}" if (sig.get("engine_name") or sig.get("engine")) else ""
    lines.append(f"#{sig['symbol']} {heart} **{direction}**{score_txt}{engine_txt} ({sig['timeframe']})")
    rows = [f"Entry   {_fmt_price(entry)}"]
    sl = sig.get("stop_loss")
    if sl is not None and entry:
        rows.append(f"SL      {_fmt_price(sl)}  ({_pct(entry, sl, direction):+.2f}%)")
    tp_defs = [("tp1", "50%"), ("tp2", "30%"), ("tp3", "20%")]
    for key, share in tp_defs:
        v = sig.get(key)
        if v is not None and entry:
            rows.append(f"{key.upper()} {share}  {_fmt_price(v)}  ({_pct(entry, v, direction):+.2f}%)")
    lines.append("```\n" + "\n".join(rows) + "\n```")
    lines.append(f"`{order_line(sig)}`")
    stats = []
    if sig.get("change_24h") is not None:
        stats.append(f"24h {sig['change_24h']:+.2f}%")
    if sig.get("high_24h") is not None:
        stats.append(f"High {_fmt_price(sig['high_24h'])}")
    if sig.get("low_24h") is not None:
        stats.append(f"Low {_fmt_price(sig['low_24h'])}")
    if sig.get("volume_24h"):
        stats.append(f"Vol {sig['volume_24h']}")
    if stats:
        lines.append("📊 " + " · ".join(stats))
    if sig.get("suggested_lot") is not None:
        lines.append(f"Lot gợi ý {sig['suggested_lot']:.2f} · Tối đa 0.02 theo guardrail")
    if sig.get("rationale"):
        lines.append(f"📝 {sig['rationale'][:160]}")
    vn_now = datetime.now(timezone.utc) + timedelta(hours=7)
    lines.append(f"⏰ {vn_now.strftime('%d/%m/%Y %H:%M')} (giờ VN)")
    lines.append(
        "⚠️ Tín hiệu tham khảo từ hệ thống NexusPilot Pro — không phải lời khuyên "
        "đầu tư. Hãy tự kiểm tra và quản trị rủi ro trước khi vào lệnh."
    )
    lines.append(f"🖥 Cockpit: {COCKPIT_URL}")
    return "\n".join(lines)


def detail_text(sig: Dict[str, Any]) -> str:
    """Bản chi tiết khi bấm Charts: thêm risk/reward, engine, lý do đầy đủ."""
    base = format_signal_message(sig)
    entry = sig.get("entry_price")
    sl = sig.get("stop_loss")
    extra = []
    if entry and sl:
        risk = abs(_pct(entry, sl, sig["direction"]))
        rewards = []
        for k in ("tp1", "tp2", "tp3"):
            v = sig.get(k)
            if v is not None:
                rewards.append(abs(_pct(entry, v, sig["direction"])) / risk if risk else 0)
        if rewards:
            extra.append(f"📐 Rủi ro {risk:.2f}% · Tỉ lệ R: {' / '.join(f'{r:.2f}R' for r in rewards)}")
    if sig.get("engine_name") or sig.get("engine"):
        extra.append(f"🧠 Engine: {sig['engine_name'] or sig['engine']}")
    if sig.get("quality"):
        extra.append(f"🏅 Chất lượng: {sig['quality']}")
    if extra:
        base += "\n" + "\n".join(extra)
    return base


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
