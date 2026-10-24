"""
news_feed.py — Lịch kinh tế ForexFactory cho bot tín hiệu NexusPilot.

Nguồn dữ liệu (cùng kiến trúc với dự án NexusPilot của chủ bot):
1. Upstream trực tiếp: https://nfs.faireconomy.media/ff_calendar_thisweek.json
2. Dự phòng: kho cache trên nhánh `data` của repo GitHub dự án
   (research/ff-calendar/latest.json) — dùng khi upstream lỗi/429.

Giới hạn của nguồn (nói rõ trong tin nhắn gửi người dùng):
- Feed chỉ có lịch TUẦN HIỆN TẠI (Chủ nhật → Thứ bảy). "7 ngày tới" và
  "7 ngày qua" hiển thị phần nằm trong tuần hiện tại và ghi chú rõ.
- Feed KHÔNG có số "thực tế" (actual) sau khi tin ra — giống cột Thực tế
  trên tab NEWS của Cockpit (đang để trống). Chỉ có dự báo & kỳ trước.

Cache trong bộ nhớ 15 phút để tránh gọi upstream liên tục.
"""

import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

UPSTREAM_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_URL = ("https://raw.githubusercontent.com/hayhahen-ui/mt5-mrbit-2026/"
             "data/research/ff-calendar/latest.json")
CACHE_TTL_SECONDS = 900
VN_TZ = timezone(timedelta(hours=7))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}

_cache: Dict[str, Any] = {"at": None, "events": [], "source": ""}
_lock = threading.Lock()

WEEKDAYS_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
IMPACT_ICON = {"High": "🔴", "Medium": "🟠", "Low": "🟡", "Holiday": "⚪"}


def _fetch_json(url: str, timeout: int = 12) -> Any:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _normalize(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events = []
    for e in raw_events:
        try:
            dt = datetime.fromisoformat(str(e.get("date", "")))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        events.append({
            "title": str(e.get("title", "")).strip(),
            "country": str(e.get("country", "")).strip().upper(),
            "dt": dt,
            "impact": str(e.get("impact", "")).strip() or "Low",
            "forecast": str(e.get("forecast", "")).strip(),
            "previous": str(e.get("previous", "")).strip(),
        })
    events.sort(key=lambda x: x["dt"])
    return events


def get_events(force: bool = False) -> Tuple[List[Dict[str, Any]], str]:
    """Trả về (events đã chuẩn hóa, nhãn nguồn). Rỗng + '' nếu mọi nguồn lỗi."""
    now = datetime.now(timezone.utc)
    with _lock:
        if (not force and _cache["at"] is not None
                and (now - _cache["at"]).total_seconds() < CACHE_TTL_SECONDS):
            return list(_cache["events"]), _cache["source"]
    events: List[Dict[str, Any]] = []
    source = ""
    # 1) Upstream trực tiếp
    try:
        raw = _fetch_json(UPSTREAM_URL)
        if isinstance(raw, list) and raw:
            events = _normalize(raw)
            source = "ForexFactory (trực tiếp)"
    except Exception:
        events = []
    # 2) Kho cache của dự án trên GitHub
    if not events:
        try:
            raw = _fetch_json(CACHE_URL)
            if isinstance(raw, dict) and isinstance(raw.get("events"), list) and raw["events"]:
                events = _normalize(raw["events"])
                fetched = str(raw.get("fetchedAt", ""))[:10]
                source = f"kho dự án NexusPilot (cập nhật {fetched})" if fetched else "kho dự án NexusPilot"
        except Exception:
            events = []
    if events:
        with _lock:
            _cache.update({"at": now, "events": events, "source": source})
    return events, source


def _now(now: Optional[datetime]) -> datetime:
    return now or datetime.now(timezone.utc)


def upcoming_events(days: int = 7, impacts: Tuple[str, ...] = ("High", "Medium"),
                    now: Optional[datetime] = None) -> Tuple[List[Dict[str, Any]], str]:
    events, source = get_events()
    n = _now(now)
    end = n + timedelta(days=days)
    return [e for e in events if e["impact"] in impacts and n <= e["dt"] <= end], source


def past_events(days: int = 7, impacts: Tuple[str, ...] = ("High", "Medium"),
                now: Optional[datetime] = None) -> Tuple[List[Dict[str, Any]], str]:
    events, source = get_events()
    n = _now(now)
    start = n - timedelta(days=days)
    return [e for e in events if e["impact"] in impacts and start <= e["dt"] < n], source


def _fmt_event_line(e: Dict[str, Any]) -> str:
    vn = e["dt"].astimezone(VN_TZ)
    icon = IMPACT_ICON.get(e["impact"], "⚪")
    parts = [f"🕖 {vn.strftime('%H:%M')} {icon} **{e['country']}** — {e['title']}"]
    meta = []
    if e.get("forecast"):
        meta.append(f"Dự báo {e['forecast']}")
    if e.get("previous"):
        meta.append(f"Kỳ trước {e['previous']}")
    if meta:
        parts.append(" · ".join(meta))
    return "\n   ".join(parts) if len(parts) > 1 else parts[0]


def _group_by_day(events: List[Dict[str, Any]], reverse: bool = False) -> str:
    ordered = sorted(events, key=lambda x: x["dt"], reverse=reverse)
    lines: List[str] = []
    current_day = None
    for e in ordered:
        vn = e["dt"].astimezone(VN_TZ)
        day_key = vn.strftime("%Y-%m-%d")
        if day_key != current_day:
            current_day = day_key
            lines.append(f"\n📅 **{WEEKDAYS_VI[vn.weekday()]} {vn.strftime('%d/%m')}**")
        lines.append(_fmt_event_line(e))
    return "\n".join(lines).strip()


MAX_EVENTS = 30


def format_upcoming(now: Optional[datetime] = None) -> str:
    events, source = upcoming_events(now=now)
    if not events:
        return ("📰 **LỊCH KINH TẾ 7 NGÀY TỚI**\n\n"
                "Chưa lấy được dữ liệu lịch (nguồn đang lỗi) hoặc không có tin "
                "mạnh/trung bình nào trong phần còn lại của tuần này. "
                "Lịch tuần mới được ForexFactory cập nhật vào Chủ nhật.")
    shown = events[:MAX_EVENTS]
    text = "📰 **LỊCH KINH TẾ SẮP RA — 7 NGÀY TỚI (tin mạnh & trung bình)**\n"
    text += _group_by_day(shown)
    if len(events) > MAX_EVENTS:
        text += f"\n\n… và {len(events) - MAX_EVENTS} sự kiện nữa — xem đầy đủ ở tab NEWS trên Cockpit."
    text += (f"\n\n📌 Nguồn: {source}. Lịch ForexFactory theo tuần hiện tại — "
             "phần vượt sang tuần sau sẽ có sau Chủ nhật.")
    return text


def format_past(now: Optional[datetime] = None) -> str:
    events, source = past_events(now=now)
    if not events:
        return ("📰 **TIN KINH TẾ ĐÃ RA — 7 NGÀY QUA**\n\n"
                "Không có tin mạnh/trung bình nào đã ra trong phần tuần này "
                "mà bot lấy được. Thử lại sau ít phút.")
    shown = list(reversed(events))[:MAX_EVENTS]
    text = "📰 **TIN KINH TẾ ĐÃ RA — 7 NGÀY QUA (tin mạnh & trung bình)**\n"
    text += _group_by_day(shown, reverse=True)
    text += ("\n\n📌 Nguồn: " + source + ". Lưu ý: nguồn ForexFactory không kèm "
             "số “thực tế” sau khi tin ra (giống cột Thực tế trên Cockpit) — "
             "tra số thực tế tại trang ForexFactory.")
    return text


def format_latest(now: Optional[datetime] = None) -> str:
    n = _now(now)
    past, source = past_events(days=1, now=n)
    upcoming, _ = upcoming_events(days=1, now=n)
    lines = ["📰 **TIN KINH TẾ MỚI NHẤT (24 giờ qua & 24 giờ tới)**"]
    if past:
        lines.append("\n⏪ **Vừa ra (24h qua):**")
        lines.append(_group_by_day(list(reversed(past))[:8], reverse=True))
    if upcoming:
        lines.append("\n⏩ **Sắp ra (24h tới):**")
        lines.append(_group_by_day(upcoming[:8]))
    if not past and not upcoming:
        lines.append("\nKhông có tin mạnh/trung bình nào trong 48 giờ quanh hiện tại. "
                     "Dùng /tin_sap_ra để xem cả tuần.")
    lines.append(f"\n📌 Nguồn: {source or 'ForexFactory'}. Gõ /tin_sap_ra (7 ngày tới) "
                 "hoặc /tin_da_ra (7 ngày qua) để xem đầy đủ.")
    return "\n".join(lines)
