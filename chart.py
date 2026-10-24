"""
chart.py — Vẽ chart nến cho tín hiệu NexusPilot (Pillow, không cần matplotlib).

Nguồn nến (theo thứ tự ưu tiên):
1. Nến kèm trong payload relay từ Cockpit (TwelveData, đủ mọi cặp).
2. CoinGecko OHLC miễn phí cho BTCUSD (không cần key).
3. Binance klines cho BTCUSD (thử, lỗi thì bỏ qua).
Không có nến thật -> không vẽ chart (không bao giờ vẽ nến giả).
"""

import io
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BG = (13, 18, 32)
GRID = (30, 40, 60)
TEXT = (220, 228, 240)
UP = (34, 197, 94)
DOWN = (239, 68, 68)
ENTRY_C = (250, 204, 21)
SL_C = (239, 68, 68)
TP_C = (34, 197, 94)


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
        return f if f == f and abs(f) != float("inf") else None
    except (TypeError, ValueError):
        return None


def normalize_candles(raw: Any, cap: int = 120) -> List[Dict[str, float]]:
    """Chuẩn hóa nến từ payload: [{t,o,h,l,c}] hoặc [[t,o,h,l,c]]."""
    out: List[Dict[str, float]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        try:
            if isinstance(item, dict):
                o, h, l, c = (_num(item.get(k)) for k in ("o", "h", "l", "c"))
                t = _num(item.get("t"))
            elif isinstance(item, (list, tuple)) and len(item) >= 5:
                t, o, h, l, c = (_num(v) for v in item[:5])
            else:
                continue
        except (TypeError, ValueError):
            continue
        if None in (o, h, l, c) or h < max(o, c) or l > min(o, c):
            continue
        out.append({"t": t or 0, "o": o, "h": h, "l": l, "c": c})
    out.sort(key=lambda x: x["t"])
    return out[-cap:]


def fetch_btc_candles(limit: int = 48) -> List[Dict[str, float]]:
    """Nến BTC/USD thật, không cần key. CoinGecko trước, Binance dự phòng."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc",
            params={"vs_currency": "usd", "days": 1}, timeout=12,
            headers={"User-Agent": "NexusPilotBot/1.0"})
        r.raise_for_status()
        rows = r.json()
        candles = normalize_candles(rows)
        if len(candles) >= 10:
            return candles[-limit:]
    except Exception as e:
        logger.warning(f"CoinGecko OHLC lỗi: {e}")
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "15m", "limit": limit},
            timeout=12, headers={"User-Agent": "NexusPilotBot/1.0"})
        r.raise_for_status()
        return normalize_candles(r.json())
    except Exception as e:
        logger.warning(f"Binance klines lỗi: {e}")
    return []


def _fmt(v: float) -> str:
    if v >= 1000:
        return f"{v:,.2f}"
    if v >= 100:
        return f"{v:,.3f}"
    return f"{v:.5f}".rstrip("0").rstrip(".")


def draw_chart(candles: List[Dict[str, float]], levels: Dict[str, Optional[float]],
               symbol: str, direction: str, title_note: str = "",
               width: int = 1080, height: int = 600) -> Optional[bytes]:
    """Vẽ chart nến nền tối, kèm đường Entry/SL/TP. Trả PNG bytes hoặc None."""
    if len(candles) < 5:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Chưa cài Pillow, không vẽ được chart.")
        return None
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
        font_sm = font
    pad_l, pad_r, pad_t, pad_b = 110, 130, 60, 40
    w, h = width, height
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    lo = min(min(c["l"] for c in candles),
             *[v for v in levels.values() if v is not None])
    hi = max(max(c["h"] for c in candles),
             *[v for v in levels.values() if v is not None])
    span = (hi - lo) or 1
    lo -= span * 0.05
    hi += span * 0.05
    span = hi - lo
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    def y(price: float) -> float:
        return pad_t + (hi - price) / span * plot_h

    for i in range(5):
        yy = pad_t + plot_h * i / 4
        d.line([(pad_l, yy), (w - pad_r, yy)], fill=GRID, width=1)
        d.text((8, yy - 12), _fmt(hi - span * i / 4), fill=TEXT, font=font_sm)
    n = len(candles)
    step = plot_w / n
    bw = max(2, step * 0.6)
    for i, c in enumerate(candles):
        x = pad_l + step * i + step / 2
        col = UP if c["c"] >= c["o"] else DOWN
        d.line([(x, y(c["h"])), (x, y(c["l"]))], fill=col, width=2)
        d.rectangle([x - bw / 2, y(max(c["o"], c["c"])),
                     x + bw / 2, y(min(c["o"], c["c"]))], fill=col)
    arrow = "▲ BUY" if direction == "BUY" else "▼ SELL"
    d.text((pad_l, 12), f"{symbol}  {arrow}", fill=TEXT, font=font)
    if title_note:
        d.text((pad_l + 330, 16), title_note, fill=(150, 165, 185), font=font_sm)
    level_style = [("entry", ENTRY_C, "Entry"), ("stop_loss", SL_C, "SL"),
                   ("tp1", TP_C, "TP1"), ("tp2", TP_C, "TP2"), ("tp3", TP_C, "TP3")]
    for key, col, label in level_style:
        v = levels.get(key)
        if v is None:
            continue
        yy = y(v)
        x0, x1 = pad_l, w - pad_r
        x = x0
        while x < x1:
            d.line([(x, yy), (min(x + 14, x1), yy)], fill=col, width=2)
            x += 24
        d.text((w - pad_r + 8, yy - 12), f"{label} {_fmt(v)}", fill=col, font=font_sm)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
