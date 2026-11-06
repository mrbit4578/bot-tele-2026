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

Tín hiệu coin Trade.2026 (bot @trademrbit_bot): trạm 24/7 (GitHub Actions)
không gửi thẳng Telegram mà POST về /api/signal-relay của web này (header
X-Signal-Key). Relay định tuyến theo payload kind/bot: kind="coin" ->
ngưỡng 70/100, chống trùng 60 phút cho mỗi coin + chiều, chat + token lấy
từ bảng đăng ký bots (chat_id + tên biến môi trường token_env).
"""

import hmac
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COCKPIT_URL = "https://mt5-mrbit-2026-v2.onrender.com/"
MAX_RECORDS = 50
_LOCK = threading.Lock()

# --- Tín hiệu coin Trade.2026 ---
COIN_MIN_SCORE = 70
COIN_DEDUPE_MINUTES = 60
COIN_BOT_ID = "trademrbit"


def trade2026_url() -> str:
    """Link web Trade.2026 (nút Charts của tín hiệu coin). Đổi bằng biến
    môi trường TRADE2026_URL nếu app có domain riêng."""
    return (os.getenv("TRADE2026_URL", "https://trade-2026-tau.vercel.app").strip().rstrip("/")
            or "https://trade-2026-tau.vercel.app")


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


# --- Định tuyến theo loại tín hiệu (coin Trade.2026 vs forex NexusPilot) ---
def is_coin_signal(sig: Dict[str, Any]) -> bool:
    """Tín hiệu coin Trade.2026: payload có kind='coin' hoặc bot='trademrbit'."""
    return (str(sig.get("kind", "")).strip().lower() == "coin"
            or str(sig.get("bot", "")).strip().lower() == COIN_BOT_ID)


def display_symbol(sig: Dict[str, Any]) -> str:
    """Tên cặp hiển thị: coin -> BTC/USDT, forex -> symbol gốc (XAUUSD)."""
    if sig.get("coin"):
        return f"{sig['coin']}/USDT"
    return sig.get("symbol", "")


def min_score_for(sig: Dict[str, Any]) -> float:
    """Ngưỡng điểm theo loại: coin 70, forex theo SIGNAL_MIN_SCORE (mặc định 80)."""
    if is_coin_signal(sig):
        try:
            return float(os.getenv("COIN_MIN_SCORE", str(COIN_MIN_SCORE)))
        except ValueError:
            return float(COIN_MIN_SCORE)
    return min_score()


def dedupe_minutes_for(sig: Dict[str, Any]) -> int:
    """Cửa sổ chống trùng theo loại: coin 60 phút, forex theo SIGNAL_DEDUPE_MINUTES (30)."""
    if is_coin_signal(sig):
        try:
            return int(os.getenv("COIN_DEDUPE_MINUTES", str(COIN_DEDUPE_MINUTES)))
        except ValueError:
            return COIN_DEDUPE_MINUTES
    return dedupe_minutes()


def dedupe_key_for(sig: Dict[str, Any]) -> str:
    """Khóa chống trùng theo loại: coin -> mỗi coin + chiều; forex -> symbol + chiều + engine."""
    if is_coin_signal(sig):
        return f"coin|{sig.get('coin') or sig['symbol']}|{sig['direction']}"
    return dedupe_key(sig)


def coin_bot() -> Optional[Dict[str, Any]]:
    """Bot coin đang bật trong bảng đăng ký bots (web quản lý nhiều bot).
    Trả None nếu chưa có bảng/chưa bật bot coin nào."""
    try:
        from database import DatabaseManager
        for b in DatabaseManager().get_bots():
            if str(b.get("kind", "")).strip().lower() == "coin" and b.get("enabled"):
                return b
    except Exception:
        return None
    return None


def coin_chat_id() -> str:
    bot = coin_bot()
    if bot and str(bot.get("chat_id", "")).strip():
        return str(bot["chat_id"]).strip()
    return ""


def coin_token() -> str:
    """Token bot coin: lấy từ biến môi trường có TÊN ghi trong bảng bots
    (cột token_env, vd BOT_TOKEN_TRADEMRBIT). Giá trị token không nằm ở đây."""
    bot = coin_bot()
    env_name = str((bot or {}).get("token_env", "") or "BOT_TOKEN_TRADEMRBIT").strip()
    return os.getenv(env_name, "").strip()


def destination_chat_id_for(sig: Dict[str, Any]) -> str:
    """Chat nhận tín hiệu: coin -> chat_id trong bảng bots; forex -> SIGNAL_CHAT_ID/CHAT_ID."""
    if is_coin_signal(sig):
        return coin_chat_id() or destination_chat_id()
    return destination_chat_id()


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
    payload = dict(payload)
    # Bí danh kiểu coin (Trade.2026) -> tên chuẩn của relay.
    if not str(payload.get("symbol", "")).strip() and payload.get("coin"):
        payload["symbol"] = str(payload["coin"]).strip().upper() + "USDT"
    if not str(payload.get("direction", "")).strip() and payload.get("side"):
        payload["direction"] = "BUY" if str(payload["side"]).strip().lower() == "long" else "SELL"
    if payload.get("score") is None and payload.get("diem") is not None:
        payload["score"] = payload["diem"]
    if payload.get("entry_price") is None and payload.get("entry") is None and payload.get("gia_vao") is not None:
        payload["entry"] = payload["gia_vao"]
    symbol = str(payload.get("symbol", "")).strip().upper()
    direction = str(payload.get("direction", "")).strip().upper()
    entry = _num(payload.get("entry_price", payload.get("entry")))
    sl = _num(payload.get("stop_loss", payload.get("sl")))
    tp1 = _num(payload.get("tp1"))
    is_coin = (str(payload.get("kind", "")).strip().lower() == "coin"
               or str(payload.get("bot", "")).strip().lower() == "trademrbit")
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
        "source": str(payload.get("source") or payload.get("nguon") or ("Trade.2026" if is_coin else "cockpit")).strip()[:40],
        "demo": bool(payload.get("demo", False)),
        "change_24h": _num(payload.get("change_24h")),
        "high_24h": _num(payload.get("high_24h")),
        "low_24h": _num(payload.get("low_24h")),
        "volume_24h": str(payload.get("volume_24h", "")).strip()[:30],
        "chart_source": str(payload.get("chart_source", "")).strip()[:60],
        "session": str(payload.get("session", "")).strip()[:60],
        "radar_note": str(payload.get("radar_note", "")).strip()[:300],
        "data_source": str(payload.get("data_source", "")).strip()[:60],
        "last_price": _num(payload.get("last_price", payload.get("price"))),
        "spread": str(payload.get("spread", "")).strip()[:30],
        # Trường riêng của tín hiệu coin Trade.2026 (forex để trống).
        "kind": str(payload.get("kind", "")).strip().lower()[:20],
        "bot": str(payload.get("bot", "")).strip().lower()[:40],
        "coin": str(payload.get("coin", "")).strip().upper()[:20],
        "side": str(payload.get("side", "")).strip().lower()[:10],
        "phase": str(payload.get("phase", "")).strip()[:40],
        "bias_4h": str(payload.get("bias_4h", "")).strip().upper()[:20],
        "phien": str(payload.get("phien", "")).strip()[:20],
        "ts_vao": str(payload.get("ts_vao", "")).strip()[:40],
    }
    bd = []
    if isinstance(payload.get("score_breakdown"), list):
        for f in payload["score_breakdown"][:10]:
            if not isinstance(f, dict):
                continue
            pts = _num(f.get("points"))
            mx = _num(f.get("maxPoints", f.get("max")))
            if pts is None or mx is None:
                continue
            bd.append({"label": str(f.get("label", ""))[:40],
                       "points": pts, "maxPoints": mx,
                       "detail": str(f.get("detail", ""))[:120]})
    sig["score_breakdown"] = bd
    try:
        import chart as _chart
        sig["candles"] = _chart.normalize_candles(payload.get("candles"), cap=120)
    except Exception:
        sig["candles"] = []
    return sig, ""


def dedupe_key(sig: Dict[str, Any]) -> str:
    return f"{sig['symbol']}|{sig['direction']}|{sig.get('engine', '')}"


def find_duplicate(sig: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Tìm tín hiệu đã GỬI gần đây trùng khóa chống trùng (khóa + cửa sổ theo loại tín hiệu)."""
    window = timedelta(minutes=dedupe_minutes_for(sig))
    key = dedupe_key_for(sig)
    now = datetime.now(timezone.utc)
    for rec in load_records():
        if not rec.get("_sent") or rec.get("demo"):
            continue
        if dedupe_key_for(rec) != key:
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
    """Nut duoi tin hieu: Charts | Chat (nick hay) | CHEP MA (copy lenh).
    Coin: Charts mo web Trade.2026. Forex: Charts mo chi tiet trong bot."""
    if is_coin_signal(sig):
        return {"inline_keyboard": [
            [{"text": "📊 Charts", "url": trade2026_url()},
             {"text": "💬 Chat", "url": "https://t.me/soledadhuong90"}],
            [{"text": "📋 CHÉP MÃ", "copy_text": {"text": order_line(sig)}}],
        ]}
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
    coin_sig = is_coin_signal(sig)
    lines = []
    if sig.get("demo"):
        lines.append("🧪 **BẢN TEST THIẾT KẾ — KHÔNG PHẢI TÍN HIỆU THẬT**")
        lines.append(f"Số liệu dưới đây chỉ minh họa bố cục, chưa đủ điều kiện phát thật ({min_score_for(sig):.0f}/100).")
    score_txt = f" · {sig['score']:.0f}/100 điểm" if sig.get("score") is not None else ""
    engine_txt = f" · {sig['engine_name'] or sig['engine']}" if (sig.get("engine_name") or sig.get("engine")) else ""
    lines.append(f"#{display_symbol(sig)} {heart} **{direction}**{score_txt}{engine_txt} ({sig['timeframe']})")
    rows = [f"Entry   {_fmt_price(entry)}"]
    sl = sig.get("stop_loss")
    if sl is not None and entry:
        rows.append(f"SL      {_fmt_price(sl)}  ({_pct(entry, sl, direction):+.2f}%)")
    tp_defs = [("tp1", "50%"), ("tp2", "30%"), ("tp3", "20%")]
    for key, share in tp_defs:
        v = sig.get(key)
        if v is not None and entry:
            # Coin Trade.2026 không chia tỉ trọng vị thế 50/30/20 — TP tính
            # theo RR (TP1 RR 1:2, TP2 RR 1:3). Hiển thị RR thực tế.
            if coin_sig and sl is not None:
                risk = abs(_pct(entry, sl, direction))
                share = f"RR {abs(_pct(entry, v, direction)) / risk:.2f}R" if risk else "RR —"
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
    if is_coin_signal(sig):
        coin_info = []
        if sig.get("bias_4h"):
            coin_info.append(f"Bias 4H: {sig['bias_4h']}")
        if sig.get("phien"):
            coin_info.append(f"Phiên: {sig['phien']}")
        if sig.get("phase"):
            coin_info.append(f"Giai đoạn: {sig['phase']}")
        if coin_info:
            lines.append("🪙 " + " · ".join(coin_info))
    vn_now = datetime.now(timezone.utc) + timedelta(hours=7)
    lines.append(f"⏰ {vn_now.strftime('%d/%m/%Y %H:%M')} (giờ VN)")
    if is_coin_signal(sig):
        lines.append(
            "⚠️ Tín hiệu tham khảo từ trạm 24/7 Trade.2026 — không phải lời khuyên "
            "đầu tư. Mọi quyết định lệnh thật do BẠN xác nhận."
        )
        lines.append(f"📊 Trade.2026: {trade2026_url()}")
    else:
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


def detail_view(sig: Dict[str, Any]) -> str:
    """Bản CHI TIẾT khi bấm Charts — KHÁC hẳn tin gốc: không lặp lại khối số liệu,
    mà mở thành phần điểm, cảnh báo radar, phiên, nguồn + độ tươi dữ liệu."""
    direction = sig["direction"]
    heart = "💚" if direction == "BUY" else "❤️"
    lines = [f"🔍 **CHI TIẾT TÍN HIỆU — #{display_symbol(sig)} {heart} {direction} ({sig['timeframe']})**"]
    score_txt = f"{sig['score']:.0f}/100" if sig.get("score") is not None else "?"
    lines.append(f"Điểm: **{score_txt}**" + (f" · Chất lượng: {sig['quality']}" if sig.get("quality") else ""))
    lines.append(f"Engine: {sig['engine_name'] or sig['engine'] or '-'}")
    bd = sig.get("score_breakdown") or []
    if bd:
        lines.append("━━━ **Thành phần điểm** ━━━")
        for f in bd:
            mark = "✓" if f["points"] >= f["maxPoints"] * 0.6 else "○"
            line = f"{mark} {f['label']} — {f['points']:.0f}/{f['maxPoints']:.0f}"
            if f.get("detail"):
                line += f" · {f['detail']}"
            lines.append(line)
    elif is_coin_signal(sig):
        lines.append("_(Tín hiệu coin không kèm breakdown thành phần điểm.)_")
    else:
        lines.append("_(Chi tiết điểm thành phần sẽ hiện khi Cockpit gửi kèm breakdown — xem bản vá v2.)_")
    entry = sig.get("entry_price")
    sl = sig.get("stop_loss")
    if entry and sl:
        risk = abs(_pct(entry, sl, direction))
        tps = [sig.get(k) for k in ("tp1", "tp2", "tp3") if sig.get(k) is not None]
        rr = " / ".join(f"{abs(_pct(entry, t, direction)) / risk:.2f}R" for t in tps) if risk else "-"
        lines.append(f"📐 Rủi ro {risk:.2f}% · Tỉ lệ R: {rr}")
    if sig.get("session"):
        lines.append(f"🕐 Phiên: {sig['session']}")
    if sig.get("radar_note"):
        lines.append(f"⚠️ Radar: {sig['radar_note'][:200]}")
    if sig.get("rationale"):
        lines.append(f"📝 {sig['rationale'][:200]}")
    src = sig.get("data_source") or sig.get("source") or ("Trade.2026" if is_coin_signal(sig) else "NexusPilot")
    vn_now = datetime.now(timezone.utc) + timedelta(hours=7)
    lines.append(f"Nguồn: {src} · Xem lúc {vn_now.strftime('%H:%M %d/%m')} (giờ VN)")
    lines.append("⚠️ Tham khảo, không phải lời khuyên đầu tư.")
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


# --- /tin_hieu cho bot coin: đọc tín hiệu mới nhất từ Supabase Trade.2026 ---
TRADE2026_SUPABASE_URL_DEFAULT = "https://fagveiomuwuyuzzeepvk.supabase.co"
COIN_SIGNAL_MAX_AGE_HOURS = 24


def _coin_empty_state_text() -> str:
    """Văn bản khi chưa có tín hiệu coin đạt chuẩn trong 24h qua (cũng là
    fallback khi Supabase chưa cấu hình hoặc lỗi)."""
    return (
        "📡 Chưa có tín hiệu coin đạt chuẩn nào được phát.\n"
        "Trạm 24/7 Trade.2026 chỉ phát tín hiệu coin có điểm từ 70/100 trở lên "
        "(giai đoạn alert_ready hoặc retest_in_progress). "
        "Khi trạm phát hiện tín hiệu coin đạt chuẩn, bot sẽ tự gửi về đây.\n\n"
        "Top coin theo dõi: BTC, ETH, SOL, BNB, DOGE, DYDX, WIF, OP, RUNE, INJ, SUI, XAUT."
    )


def _trade2026_supabase() -> Tuple[Optional[str], Optional[str]]:
    """(base_url, anon_key) cho dự án Supabase Trade.2026 (almond-fence).
    Key chỉ đọc từ biến môi trường — KHÔNG hardcode giá trị key vào code."""
    base = (os.getenv("TRADE2026_SUPABASE_URL", TRADE2026_SUPABASE_URL_DEFAULT) or "").strip().rstrip("/")
    key = (os.getenv("TRADE2026_SUPABASE_ANON_KEY", "") or "").strip()
    if not base or not key:
        return None, None
    return base, key


def _parse_ts(ts: Any) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _row_to_signal(row: Dict[str, Any]) -> Dict[str, Any]:
    """Chuyển 1 dòng bảng signals (Supabase) thành signal chuẩn của relay."""
    coin = str(row.get("coin", "")).strip().upper()
    side = str(row.get("side", "")).strip().lower()
    direction = "BUY" if side == "long" else "SELL"
    return {
        "coin": coin,
        "bot": "trademrbit",
        "kind": "coin",
        "symbol": coin + "USDT" if coin else "",
        "side": side,
        "direction": direction,
        "timeframe": "M15",
        "entry_price": _num(row.get("gia_vao")),
        "stop_loss": _num(row.get("sl")),
        "tp1": _num(row.get("tp1")),
        "tp2": _num(row.get("tp2")),
        "tp3": None,
        "score": _num(row.get("diem")),
        "engine": "Trade.2026 Crypto",
        "engine_name": "Trade.2026 Crypto",
        "source": "Trade.2026",
        "bias_4h": str(row.get("bias_4h") or "").strip().upper(),
        "phien": str(row.get("phien") or "").strip(),
        "phase": str(row.get("phase") or "").strip(),
        "ts_vao": str(row.get("ts_vao") or "").strip(),
        "demo": False,
        "score_breakdown": [],
        "candles": [],
    }


def latest_coin_signal_text() -> str:
    """Văn bản cho lệnh /tin_hieu của bot coin: tín hiệu coin đạt chuẩn
    mới nhất (trong 24h qua) từ bảng signals của Supabase Trade.2026.
    Lỗi/mất cấu hình -> về trạng thái trống, KHÔNG bao giờ làm vỡ reply."""
    empty = _coin_empty_state_text()
    base, key = _trade2026_supabase()
    if not base or not key:
        return empty
    url = (f"{base}/rest/v1/signals"
           "?select=coin,side,diem,gia_vao,sl,tp1,tp2,rr,phase,bias_4h,phien,ts_vao"
           "&loai=eq.that&diem=gte.70&order=ts_vao.desc&limit=5")
    try:
        # Chỉ gửi header apikey (key sb_ là opaque, không phải JWT — KHÔNG
        # gửi Authorization: Bearer, sẽ bị Supabase trả 401 PGRST301).
        req = urllib.request.Request(url, headers={"apikey": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return empty
    if not isinstance(rows, list):
        return empty
    now = datetime.now(timezone.utc)
    fresh = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_ts(row.get("ts_vao"))
        if dt is None:
            continue  # ts không đọc được -> coi như dữ liệu lỗi, bỏ qua
        if (now - dt).total_seconds() <= COIN_SIGNAL_MAX_AGE_HOURS * 3600:
            fresh.append((dt, row))
    if not fresh:
        return empty
    dt, row = fresh[0]
    sig = _row_to_signal(row)
    vn = dt.astimezone(timezone(timedelta(hours=7)))
    return ("📡 **TÍN HIỆU COIN GẦN NHẤT:**\n\n"
            + format_signal_message(sig)
            + f"\n🕐 Tín hiệu lúc {vn.strftime('%H:%M %d/%m/%Y')} (giờ VN)")
