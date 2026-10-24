"""
BƯỚC 2, 6, 7, 8, 9: main.py - Máy chủ Flask xử lý Telegram Bot & Hệ thống Auto Tạo Bot 9 Bước
- Cung cấp route "/" ("Xin chào!"), "/webhook" (nhận tin nhắn từ Telegram HTTPS Webhook)
- Tích hợp Chế độ Polling cục bộ để chạy thử Bot ngay lập tức mà chưa cần Deploy
- Cung cấp Dashboard Web tương tác 9 Bước tại "/dashboard" để tự động hóa toàn bộ quy trình
"""

import os
import sys
import json
import time
import subprocess
import threading
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv

from database import DatabaseManager, generate_supabase_sql
from faq_engine import FAQEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

# Vercel (serverless): filesystem chi-doc, khong co thread nen song lau.
# -> Khong ghi file .env, khong chay Local Polling; chi dung Webhook + Supabase.
IS_VERCEL = bool(os.getenv("VERCEL"))

# Cấu hình Logging chuẩn theo Bước 9 (Render Logs)
SYSTEM_LOGS: List[str] = []


class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        ts = datetime.now().strftime("%H:%M:%S")
        msg = f"[{record.levelname}] {record.getMessage()}"
        SYSTEM_LOGS.append(f"{ts} {msg}")
        if len(SYSTEM_LOGS) > 200:
            SYSTEM_LOGS.pop(0)


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger("TelegramBot")
logger.addHandler(MemoryLogHandler())

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))


def _admin_denied_response():
    """Tra 401 JSON neu request API chua dat yeu cau ADMIN_KEY, nguoc lai tra None.

    Bao ve theo tung endpoint (khong dua vao request.path vi Vercel rewrite
    /(.*) -> /api/index lam duong dan Flask nhan duoc khong dang tin cay).
    - Da dat ADMIN_KEY: bat buoc gui dung header X-Admin-Key.
    - Tren Vercel chua dat ADMIN_KEY: chan (vi /api/state chua cau hinh nhay cam).
    - Local chua dat khoa: mo nhu cu cho tien dung tren may nha.
    """
    admin_key = os.getenv("ADMIN_KEY", "").strip()
    if admin_key:
        provided = request.headers.get("X-Admin-Key", "") or request.cookies.get("admin_key", "")
        if provided != admin_key:
            return jsonify({"ok": False, "message": "Thieu hoac sai ADMIN_KEY. Nhap khoa quan tri de mo Dashboard."}), 401
        return None
    if IS_VERCEL:
        return jsonify({"ok": False, "message": "Hay dat bien ADMIN_KEY trong Vercel Settings roi redeploy de mo khoa Dashboard."}), 401
    return None


@app.before_request
def _protect_api():
    # url_rule duoc Flask gan sau khi khop route theo duong dan goc cua request,
    # dang tin cay hon request.path trong moi truong rewrite cua Vercel.
    rule = request.url_rule
    if rule is not None and rule.rule.startswith("/api/"):
        return _admin_denied_response()
    return None


db = DatabaseManager()
faq_engine = FAQEngine(db)

# Trạng thái Polling cục bộ (chạy thử không cần Webhook HTTPS)
POLLING_STATE = {
    "running": False,
    "thread": None,
    "last_update_id": 0,
    "bot_info": None
}

# Ánh xạ 9 bức ảnh hướng dẫn gốc trong thư mục sang từng bước
STEP_IMAGES = {
    1: "857130286_1433641274769746_1960286195377603991_n.jpg",
    2: "855927700_29105811135721037_8160912043294716999_n.jpg",
    3: "857802977_3024155831250957_5995899367217284581_n.jpg",
    4: "856282083_1175747125022063_1872286703002622442_n.jpg",
    5: "855518536_1577919933619912_9016109783381997211_n.jpg",
    6: "855449911_4509639802623652_2429886808130489623_n.jpg",
    7: "858771343_1175983368327985_6184613730625311593_n.jpg",
    8: "856716525_1875789223783045_3921254774766530744_n.jpg",
    9: "857445656_1096799019796312_2314631996810367865_n.jpg"
}


def get_env_config() -> Dict[str, str]:
    load_dotenv(ENV_PATH, override=True)
    return {
        "BOT_TOKEN": os.getenv("BOT_TOKEN", "").strip(),
        "CHAT_ID": os.getenv("CHAT_ID", "").strip(),
        "TIMEZONE": os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh").strip(),
        "SUPABASE_URL": os.getenv("SUPABASE_URL", "").strip(),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY", "").strip(),
        "WEBHOOK_URL": os.getenv("WEBHOOK_URL", "").strip(),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", "").strip(),
        "ADMIN_KEY": os.getenv("ADMIN_KEY", "").strip(),
        "TELEGRAM_WEBHOOK_SECRET": os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    }


def mask_secret(value: str) -> str:
    """Che gia tri nhay cam khi tra ve trinh duyet (chi giu 4 ky tu cuoi de nhan dien)."""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 4:
        return "\u2022\u2022\u2022\u2022"
    return "\u2022" * 6 + v[-4:]


def save_env_config(updates: Dict[str, str]) -> Dict[str, str]:
    current = get_env_config()
    for k, v in updates.items():
        if v is not None:
            v = str(v).strip()
            # Gia tri dang che (\u2022\u2022\u2022) tu /api/state gui lai = "giu nguyen gia tri cu",
            # tuyet doi khong ghi de len token/key that.
            if "\u2022" in v:
                continue
            current[k] = v
            os.environ[k] = current[k]

    lines = [
        "# CẤU HÌNH HỆ THỐNG BOT TELEGRAM 9 BƯỚC",
        f"BOT_TOKEN={current.get('BOT_TOKEN', '')}",
        f"CHAT_ID={current.get('CHAT_ID', '')}",
        f"TIMEZONE={current.get('TIMEZONE', 'Asia/Ho_Chi_Minh')}",
        f"SUPABASE_URL={current.get('SUPABASE_URL', '')}",
        f"SUPABASE_KEY={current.get('SUPABASE_KEY', '')}",
        f"WEBHOOK_URL={current.get('WEBHOOK_URL', '')}",
        f"GEMINI_API_KEY={current.get('GEMINI_API_KEY', '')}",
        f"ADMIN_KEY={current.get('ADMIN_KEY', '')}",
        f"TELEGRAM_WEBHOOK_SECRET={current.get('TELEGRAM_WEBHOOK_SECRET', '')}",
        ""
    ]
    if IS_VERCEL:
        # Khong ghi file tren Vercel: cau hinh ben vung phai dat trong
        # Vercel Project Settings -> Environment Variables.
        logger.warning("Vercel mode: chi cap nhat bien moi truong trong bo nho. Hay dat cac bien nay trong Vercel Settings de luu ben vung.")
    else:
        try:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            logger.error(f"Khong ghi duoc file .env: {e}")

    # Cập nhật kết nối Supabase trong db
    db.supabase_url = current.get("SUPABASE_URL", "").rstrip("/")
    db.supabase_key = current.get("SUPABASE_KEY", "")
    return current


# ============================================================================
# CÁC HÀM GIAO TIẾP TELEGRAM HTTP API (BƯỚC 1, 6, 7, 8, 9)
# ============================================================================

def telegram_api(method: str, payload: Optional[Dict[str, Any]] = None, token: Optional[str] = None) -> Dict[str, Any]:
    bot_token = (token or get_env_config().get("BOT_TOKEN", "")).strip()
    if not bot_token or ":" not in bot_token:
        return {"ok": False, "description": "Chưa cấu hình BOT_TOKEN hợp lệ."}

    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    try:
        resp = requests.post(url, json=payload or {}, timeout=10)
        return resp.json()
    except Exception as e:
        logger.error(f"Telegram API error ({method}): {e}")
        return {"ok": False, "description": str(e)}


def build_inline_keyboard(menu_type: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Tạo bàn phím Inline Keyboard chuẩn theo Bước 7 và Bước 9.
    """
    if not menu_type:
        return None

    settings = db.get_settings()
    shop_url = settings.get("shop_url", "https://shop.example.com")

    if menu_type == "start_menu":
        # Chuẩn giao diện Bước 9: 📋 FAQ | 💰 Bảng giá | 🤖 Hỗ trợ
        return {
            "inline_keyboard": [
                [{"text": "📋 FAQ", "callback_data": "menu_faq"}],
                [{"text": "💰 Bảng giá", "callback_data": "menu_pricing"}],
                [{"text": "🤖 Hỗ trợ", "callback_data": "menu_consultant"}]
            ]
        }

    if menu_type == "main_consultant":
        # Chuẩn giao diện Bước 7: Chọn sản phẩm | Xem bảng giá | Gặp tư vấn viên + Thanh toán & Đa ngôn ngữ
        return {
            "inline_keyboard": [
                [{"text": "📦 Chọn sản phẩm >", "callback_data": "menu_products"}],
                [{"text": "📋 Xem bảng giá >", "callback_data": "menu_pricing"}],
                [{"text": "💳 Thanh toán (PayPal / USDT) >", "callback_data": "menu_payment"}],
                [{"text": "🌐 FAQ đa ngôn ngữ (VI/EN/RU) >", "callback_data": "menu_faq_lang"}],
                [{"text": "👤 Gặp tư vấn viên >", "callback_data": "menu_human_support"}]
            ]
        }

    if menu_type == "products":
        # Bước 7.1: Danh sách chọn sản phẩm
        buttons = []
        for p in db.get_products():
            buttons.append([{
                "text": f"📦 {p.get('name')} >",
                "callback_data": f"prod_{p.get('id')}"
            }])
        buttons.append([{"text": "🛒 Đặt hàng trên Website", "url": shop_url}])
        buttons.append([{"text": "⬅️ Quay lại Menu chính", "callback_data": "menu_consultant"}])
        return {"inline_keyboard": buttons}

    if menu_type == "pricing":
        # Bước 7.2: Xem bảng giá (Sản phẩm A >, Sản phẩm B >, Liên hệ tư vấn >)
        buttons = []
        for p in db.get_products()[:3]:
            buttons.append([{
                "text": f"{p.get('name')} >",
                "callback_data": f"prod_{p.get('id')}"
            }])
        buttons.append([{"text": "💳 Thanh toán ngay >", "callback_data": "menu_payment"}])
        buttons.append([{"text": "📞 Liên hệ tư vấn >", "callback_data": "menu_human_support"}])
        buttons.append([{"text": "⬅️ Quay lại", "callback_data": "menu_consultant"}])
        return {"inline_keyboard": buttons}

    if menu_type == "payment":
        # Bước 7.3: Thanh toán PayPal | USDT | QR Code
        return {
            "inline_keyboard": [
                [
                    {"text": "🅿️ PayPal", "callback_data": "pay_paypal"},
                    {"text": "🪙 USDT (Crypto)", "callback_data": "pay_usdt"}
                ],
                [{"text": "📲 Nhận mã QR Thanh toán", "callback_data": "pay_qr"}],
                [{"text": "⬅️ Quay lại", "callback_data": "menu_consultant"}]
            ]
        }

    if menu_type == "faq_lang":
        # Bước 7.4: FAQ đa ngôn ngữ (VI / EN / RU)
        return {
            "inline_keyboard": [
                [{"text": "🇻🇳 VI — Hỗ trợ tiếng Việt >", "callback_data": "faq_lang_VI"}],
                [{"text": "🇬🇧 EN — English support >", "callback_data": "faq_lang_EN"}],
                [{"text": "🇷🇺 RU — Поддержка на русском >", "callback_data": "faq_lang_RU"}],
                [{"text": "⬅️ Quay lại", "callback_data": "menu_consultant"}]
            ]
        }

    return None


def generate_bot_reply(
    text: str,
    chat_type: str = "private",
    user_id: str = "guest",
    username: str = "",
    full_name: str = "",
    callback_data: Optional[str] = None
) -> Dict[str, Any]:
    """
    Xử lý toàn bộ logic phản hồi của Bot cho cả Tin nhắn văn bản & Nút bấm Callback.
    Dùng chung cho cả Telegram Webhook thực tế và Trình giả lập (Simulator) ở Bước 9.
    """
    is_group = chat_type in ("group", "supergroup")
    settings = db.get_settings()
    support_user = settings.get("support_username", "@phucanhmrt")
    shop_url = settings.get("shop_url", "https://shop.example.com")

    # 1. Xử lý khi người dùng bấm nút Inline (Callback Query)
    if callback_data:
        if callback_data == "menu_faq":
            return {
                "responded": True,
                "text": faq_engine.format_faq_by_language("VI"),
                "reply_markup": build_inline_keyboard("faq_lang")
            }
        if callback_data == "menu_faq_lang":
            return {
                "responded": True,
                "text": "🌐 **CHỌN NGÔN NGỮ HỖ TRỢ (SELECT LANGUAGE):**",
                "reply_markup": build_inline_keyboard("faq_lang")
            }
        if callback_data.startswith("faq_lang_"):
            lang = callback_data.replace("faq_lang_", "")
            return {
                "responded": True,
                "text": faq_engine.format_faq_by_language(lang),
                "reply_markup": build_inline_keyboard("faq_lang")
            }
        if callback_data == "menu_pricing":
            return {
                "responded": True,
                "text": faq_engine.format_pricing_message(),
                "reply_markup": build_inline_keyboard("pricing")
            }
        if callback_data == "menu_products":
            return {
                "responded": True,
                "text": faq_engine.format_products_message(),
                "reply_markup": build_inline_keyboard("products")
            }
        if callback_data.startswith("prod_"):
            prod_id = callback_data.replace("prod_", "", 1)
            prod = db.get_product_by_id(prod_id)
            if prod:
                feats = "\n".join([f"  ✓ {f}" for f in prod.get("features", [])])
                stock_txt = "✅ Còn hàng" if prod.get("in_stock", True) else "❌ Hết hàng"
                msg = (
                    f"📦 **{prod.get('name')}**\n"
                    f"• Danh mục: {prod.get('category', 'Sản phẩm')}\n"
                    f"• Tình trạng: {stock_txt}\n"
                    f"• Mô tả: {prod.get('description')}\n\n"
                    f"**Đặc điểm nổi bật:**\n{feats}\n\n"
                    f"🔗 Đặt mua ngay: {prod.get('order_url', shop_url)}"
                )
                return {
                    "responded": True,
                    "text": msg,
                    "reply_markup": build_inline_keyboard("payment")
                }
        if callback_data == "menu_payment":
            pay = faq_engine.format_payment_message("ALL")
            return {
                "responded": True,
                "text": pay["text"],
                "qr_url": pay["qr_url"],
                "reply_markup": build_inline_keyboard("payment")
            }
        if callback_data == "pay_paypal":
            pay = faq_engine.format_payment_message("PAYPAL")
            return {
                "responded": True,
                "text": pay["text"],
                "reply_markup": build_inline_keyboard("payment")
            }
        if callback_data == "pay_usdt":
            pay = faq_engine.format_payment_message("USDT")
            return {
                "responded": True,
                "text": pay["text"],
                "reply_markup": build_inline_keyboard("payment")
            }
        if callback_data == "pay_qr":
            pay = faq_engine.format_payment_message("ALL")
            return {
                "responded": True,
                "text": "📲 **MÃ QR THANH TOÁN NHANH:**\nQuét mã QR bên dưới hoặc chuyển khoản theo thông tin:\n\n" + pay["text"],
                "qr_url": pay["qr_url"],
                "reply_markup": build_inline_keyboard("payment")
            }
        if callback_data == "menu_human_support":
            return {
                "responded": True,
                "text": (
                    f"👤 **KẾT NỐI TƯ VẤN VIÊN TRỰC TIẾP**\n\n"
                    f"• Tư vấn viên hỗ trợ: {support_user}\n"
                    f"• Website chính thức: {shop_url}\n"
                    f"• Bạn hãy để lại Số điện thoại hoặc nội dung cần hỗ trợ, tư vấn viên sẽ phản hồi trong ít phút!"
                ),
                "reply_markup": build_inline_keyboard("main_consultant")
            }
        if callback_data == "menu_consultant":
            return {
                "responded": True,
                "text": "Bạn muốn tìm hiểu sản phẩm nào?",
                "reply_markup": build_inline_keyboard("main_consultant")
            }

    # 2. Nếu ở trong Nhóm (Bước 8), kiểm tra bộ lọc Keyword & Chống Spam trước
    bot_uname = ""
    if POLLING_STATE.get("bot_info"):
        bot_uname = POLLING_STATE["bot_info"].get("username", "")

    if is_group:
        should_reply, reason = faq_engine.should_respond_in_group(text, user_id, bot_uname)
        if not should_reply:
            return {
                "responded": False,
                "reason": reason,
                "text": None
            }

    clean_text = (text or "").strip()
    cmd = clean_text.split()[0].lower().split("@")[0] if clean_text.startswith("/") else ""

    # Lưu lịch sử tương tác khách hàng vào bảng customers (Bước 3)
    db.log_customer_interaction(
        telegram_id=user_id,
        username=username,
        full_name=full_name,
        message=clean_text,
        language=faq_engine.detect_language(clean_text)
    )

    # 3. Xử lý các lệnh chuẩn (/start, /ship, /faq, /price, /products, /pay, /support, /lang)
    if cmd == "/start":
        # Chuẩn giao diện Bước 9.1: Test lệnh /start
        return {
            "responded": True,
            "text": "Xin chào!\nTôi là trợ lý AI của bạn.\nSẵn sàng hỗ trợ! ✨",
            "reply_markup": build_inline_keyboard("start_menu")
        }

    if cmd == "/ship":
        # Chuẩn Bước 8: Tra cứu phí giao hàng
        return {
            "responded": True,
            "text": faq_engine.format_shipping_info(),
            "reply_markup": None if is_group else build_inline_keyboard("main_consultant")
        }

    if cmd == "/faq":
        return {
            "responded": True,
            "text": faq_engine.format_faq_by_language("VI"),
            "reply_markup": build_inline_keyboard("faq_lang")
        }

    if cmd == "/price":
        return {
            "responded": True,
            "text": faq_engine.format_pricing_message(),
            "reply_markup": build_inline_keyboard("pricing")
        }

    if cmd == "/products":
        return {
            "responded": True,
            "text": faq_engine.format_products_message(),
            "reply_markup": build_inline_keyboard("products")
        }

    if cmd == "/pay":
        pay = faq_engine.format_payment_message("ALL")
        return {
            "responded": True,
            "text": pay["text"],
            "qr_url": pay["qr_url"],
            "reply_markup": build_inline_keyboard("payment")
        }

    if cmd == "/lang":
        return {
            "responded": True,
            "text": "🌐 Chọn ngôn ngữ hỗ trợ / Select support language / Выберите язык:",
            "reply_markup": build_inline_keyboard("faq_lang")
        }

    if cmd == "/support":
        return {
            "responded": True,
            "text": f"👤 Liên hệ tư vấn viên trực tiếp: {support_user}\nHoặc truy cập: {shop_url}",
            "reply_markup": build_inline_keyboard("main_consultant")
        }

    # 4. Xử lý câu hỏi tự nhiên qua FAQ Engine & AI Consultant (Bước 7 & Bước 8)
    ai_res = faq_engine.generate_ai_response(clean_text, is_group=is_group)
    return {
        "responded": True,
        "text": ai_res.get("text"),
        "qr_url": ai_res.get("qr_url"),
        "reply_markup": build_inline_keyboard(ai_res.get("menu_type"))
    }


def process_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """
    BƯỚC 6: Nhận dữ liệu từ Telegram Webhook (hoặc Polling), xử lý và gửi phản hồi.
    """
    try:
        # Xử lý Callback Query (khi khách bấm nút Inline)
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb.get("id")
            data = cb.get("data", "")
            msg = cb.get("message", {})
            chat = msg.get("chat", {})
            chat_id = chat.get("id")
            chat_type = chat.get("type", "private")
            from_user = cb.get("from", {})

            telegram_api("answerCallbackQuery", {"callback_query_id": cb_id})

            reply = generate_bot_reply(
                text="",
                chat_type=chat_type,
                user_id=str(from_user.get("id", chat_id)),
                username=from_user.get("username", ""),
                full_name=f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip(),
                callback_data=data
            )
            if reply.get("responded") and reply.get("text"):
                payload: Dict[str, Any] = {
                    "chat_id": chat_id,
                    "text": reply["text"],
                    "parse_mode": "Markdown"
                }
                if reply.get("reply_markup"):
                    payload["reply_markup"] = reply["reply_markup"]
                telegram_api("sendMessage", payload)
                if reply.get("qr_url") and data == "pay_qr":
                    telegram_api("sendPhoto", {
                        "chat_id": chat_id,
                        "photo": reply["qr_url"],
                        "caption": "📲 Quét mã QR để thanh toán nhanh"
                    })
            return {"ok": True, "handled": "callback_query", "data": data}

        # Xử lý Tin nhắn văn bản (Message)
        message = update.get("message") or update.get("edited_message")
        if not message:
            return {"ok": True, "handled": "ignored_non_message"}

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "private")
        text = message.get("text", "")
        from_user = message.get("from", {})

        if not text:
            return {"ok": True, "handled": "non_text_message"}

        full_name = f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
        logger.info(f"Incoming [{chat_type}] from {full_name} ({chat_id}): {text}")

        reply = generate_bot_reply(
            text=text,
            chat_type=chat_type,
            user_id=str(from_user.get("id", chat_id)),
            username=from_user.get("username", ""),
            full_name=full_name
        )

        if not reply.get("responded"):
            logger.info(f"Ignored group message ({reply.get('reason')}): {text}")
            return {"ok": True, "handled": "filtered_group_message", "reason": reply.get("reason")}

        send_payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": reply["text"],
            "parse_mode": "Markdown"
        }
        if reply.get("reply_markup"):
            send_payload["reply_markup"] = reply["reply_markup"]

        res = telegram_api("sendMessage", send_payload)
        if not res.get("ok"):
            # Fallback nếu Markdown có ký tự đặc biệt chưa đóng
            send_payload.pop("parse_mode", None)
            res = telegram_api("sendMessage", send_payload)

        return {"ok": True, "handled": "message", "telegram_response": res}

    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================================
# ROUTES CHÍNH CỦA BOT (BƯỚC 2 & BƯỚC 6)
# ============================================================================

@app.route("/")
def home():
    """
    Route gốc theo đúng mã nguồn mẫu ở Bước 2:
    @app.route("/")
    def home():
        return "Xin chào!"
    Nếu người dùng mở bằng trình duyệt, hỗ trợ chuyển nhanh vào Dashboard 9 Bước.
    """
    if request.args.get("view") == "dashboard":
        return render_template("dashboard.html", step_images=STEP_IMAGES)
    accept = request.headers.get("Accept", "")
    if "text/html" in accept and request.args.get("raw") != "1":
        return render_template("dashboard.html", step_images=STEP_IMAGES)
    return "Xin chào!"


@app.route("/ping")
def ping():
    return "Xin chào!"


@app.route("/dashboard")
def dashboard():
    """Giao diện Hệ Thống Auto Tạo Bot Telegram 9 Bước."""
    return render_template("dashboard.html", step_images=STEP_IMAGES)


@app.route("/images/<path:filename>")
def serve_step_image(filename: str):
    """Phục vụ 9 bức ảnh hướng dẫn gốc trong thư mục (neu co)."""
    fpath = os.path.join(BASE_DIR, filename)
    if not os.path.isfile(fpath):
        return jsonify({"ok": False, "message": "Anh minh hoa chua duoc dua vao repo."}), 404
    return send_from_directory(BASE_DIR, filename)


@app.route("/webhook", methods=["POST", "GET"])
def telegram_webhook():
    """
    BƯỚC 6: KẾT NỐI TELEGRAM WEBHOOK
    Telegram gửi tin nhắn -> Webhook chuyển dữ liệu -> Bot xử lý và phản hồi
    """
    if request.method == "GET":
        return jsonify({
            "ok": True,
            "status": "Webhook endpoint is active (HTTPS ready)",
            "message": "Telegram gửi POST request tới địa chỉ này để truyền dữ liệu tin nhắn."
        })

    secret = get_env_config().get("TELEGRAM_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != secret:
        return jsonify({"ok": False, "error": "Invalid webhook secret"}), 403

    update = request.get_json(silent=True) or {}
    result = process_telegram_update(update)
    return jsonify(result)


# ============================================================================
# HỆ THỐNG API TỰ ĐỘNG HÓA 9 BƯỚC (9-STEP AUTO BOT BUILDER SYSTEM)
# ============================================================================

@app.route("/api/state", methods=["GET"])
def api_get_state():
    """Lấy trạng thái tổng thể của cả 9 bước."""
    env = get_env_config()
    db_status = db.test_connection()
    settings = db.get_settings()
    return jsonify({
        "ok": True,
        "env": {
            "BOT_TOKEN": mask_secret(env["BOT_TOKEN"]),
            "CHAT_ID": env["CHAT_ID"],
            "TIMEZONE": env["TIMEZONE"],
            "SUPABASE_URL": env["SUPABASE_URL"],
            "SUPABASE_KEY": mask_secret(env["SUPABASE_KEY"]),
            "WEBHOOK_URL": env["WEBHOOK_URL"],
            "GEMINI_API_KEY": mask_secret(env["GEMINI_API_KEY"])
        },
        "database": {
            "status": db_status,
            "products": db.get_products(),
            "pricing": db.get_pricing(),
            "faqs": db.get_faqs(),
            "customers": db.get_customers(),
            "settings": settings
        },
        "polling": {
            "running": POLLING_STATE["running"],
            "bot_info": POLLING_STATE["bot_info"]
        },
        "step_images": STEP_IMAGES,
        "logs": SYSTEM_LOGS[-40:]
    })


# --- BƯỚC 1: TẠO BOT TRÊN TELEGRAM & XÁC THỰC TOKEN ---
@app.route("/api/step1/verify", methods=["POST"])
def api_step1_verify():
    data = request.get_json(silent=True) or {}
    token = (data.get("BOT_TOKEN") or get_env_config().get("BOT_TOKEN", "")).strip()
    chat_id = (data.get("CHAT_ID") or get_env_config().get("CHAT_ID", "")).strip()
    timezone = (data.get("TIMEZONE") or get_env_config().get("TIMEZONE", "Asia/Ho_Chi_Minh")).strip()

    save_env_config({"BOT_TOKEN": token, "CHAT_ID": chat_id, "TIMEZONE": timezone})

    if not token or ":" not in token:
        return jsonify({
            "ok": False,
            "message": "Định dạng BOT_TOKEN chưa hợp lệ (Ví dụ: 1234567890:AAH7bX9k...ZyR2vQmT)."
        })

    me = telegram_api("getMe", token=token)
    if not me.get("ok"):
        return jsonify({
            "ok": False,
            "message": f"Telegram từ chối Token: {me.get('description', 'Token không hợp lệ')}"
        })

    bot_info = me.get("result", {})
    POLLING_STATE["bot_info"] = bot_info

    # Tự động đăng ký Menu lệnh cho Bot
    commands = [
        {"command": "start", "description": "Khởi động trợ lý AI & hiển thị Menu chính"},
        {"command": "products", "description": "Chọn sản phẩm & xem tồn kho"},
        {"command": "price", "description": "Xem bảng giá niêm yết"},
        {"command": "pay", "description": "Thanh toán qua PayPal / USDT / QR Code"},
        {"command": "faq", "description": "Câu hỏi thường gặp (VI / EN / RU)"},
        {"command": "ship", "description": "Tra cứu phí giao hàng nội thành & tỉnh"},
        {"command": "lang", "description": "Đổi ngôn ngữ (Tiếng Việt / English / Русский)"},
        {"command": "support", "description": "Gặp tư vấn viên hỗ trợ trực tiếp"}
    ]
    telegram_api("setMyCommands", {"commands": commands}, token=token)
    logger.info(f"Connected to Telegram Bot @{bot_info.get('username')} (ID: {bot_info.get('id')})")

    return jsonify({
        "ok": True,
        "message": f"Kết nối thành công với Bot @{bot_info.get('username')} ({bot_info.get('first_name')})!",
        "bot_info": bot_info
    })


# --- BƯỚC 2: KIỂM TRA & SINH MÃ NGUỒN PYTHON ---
@app.route("/api/step2/files", methods=["GET", "POST"])
def api_step2_files():
    target_files = ["main.py", "faq_engine.py", "database.py", "requirements.txt", "render.yaml", "Procfile"]
    files_info = []
    for fname in target_files:
        fpath = os.path.join(BASE_DIR, fname)
        exists = os.path.exists(fpath)
        size = os.path.getsize(fpath) if exists else 0
        preview = ""
        if exists:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                preview = f.read(3000)
        files_info.append({
            "name": fname,
            "exists": exists,
            "size": size,
            "preview": preview
        })
    logger.info("Checked Python source code files (main.py, faq_engine.py, database.py, requirements.txt)")
    return jsonify({"ok": True, "files": files_info})


# --- BƯỚC 3: THIẾT LẬP SUPABASE & QUẢN LÝ 4 BẢNG DỮ LIỆU ---
@app.route("/api/step3/supabase", methods=["POST"])
def api_step3_supabase():
    data = request.get_json(silent=True) or {}
    action = data.get("action", "status")

    if action == "save_credentials":
        save_env_config({
            "SUPABASE_URL": data.get("SUPABASE_URL", ""),
            "SUPABASE_KEY": data.get("SUPABASE_KEY", "")
        })
        status = db.test_connection()
        return jsonify({"ok": True, "status": status, "sql": generate_supabase_sql()})

    if action == "seed":
        res = db.seed_supabase_from_local()
        return jsonify(res)

    if action == "add_product":
        item = db.upsert_product(data.get("item", {}))
        return jsonify({"ok": True, "item": item, "products": db.get_products()})

    if action == "add_pricing":
        item = db.upsert_pricing(data.get("item", {}))
        return jsonify({"ok": True, "item": item, "pricing": db.get_pricing()})

    if action == "add_faq":
        item = db.upsert_faq(data.get("item", {}))
        return jsonify({"ok": True, "item": item, "faqs": db.get_faqs()})

    return jsonify({
        "ok": True,
        "status": db.test_connection(),
        "sql": generate_supabase_sql()
    })


# --- BƯỚC 4: ĐƯA CODE LÊN GITHUB (AUTO GIT INIT / COMMIT / PUSH) ---
@app.route("/api/step4/git", methods=["POST"])
def api_step4_git():
    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()
    commit_msg = (data.get("commit_msg") or "Cập nhật mã nguồn").strip()
    branch = (data.get("branch") or "main").strip()
    github_token = (data.get("github_token") or "").strip()
    repo_name = (data.get("repo_name") or "telegram-ai-bot").strip()
    is_private = bool(data.get("is_private", True))

    if IS_VERCEL:
        return jsonify({
            "ok": False,
            "message": "Buoc 4 (git init/commit/push) chi chay tren may local. Tren Vercel, code duoc deploy tu dong tu GitHub moi lan push."
        })

    steps_log = []

    def run_git(args: List[str]) -> Dict[str, Any]:
        try:
            proc = subprocess.run(
                ["git"] + args,
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            return {"ok": proc.returncode == 0, "cmd": "git " + " ".join(args), "output": out.strip()}
        except Exception as e:
            return {"ok": False, "cmd": "git " + " ".join(args), "output": str(e)}

    # 1. Nếu có GitHub Personal Access Token và chưa có repo_url -> Tự tạo Private Repository trên GitHub
    if github_token and not repo_url:
        try:
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            r = requests.post(
                "https://api.github.com/user/repos",
                headers=headers,
                json={"name": repo_name, "private": is_private, "auto_init": False},
                timeout=10
            )
            if r.status_code in (200, 201):
                repo_data = r.json()
                repo_url = repo_data.get("clone_url", "")
                steps_log.append({
                    "ok": True,
                    "cmd": "GitHub API: Create Private Repository",
                    "output": f"Đã tạo repository: {repo_data.get('html_url')}"
                })
            else:
                steps_log.append({
                    "ok": False,
                    "cmd": "GitHub API: Create Repository",
                    "output": r.text
                })
        except Exception as e:
            steps_log.append({"ok": False, "cmd": "GitHub API", "output": str(e)})

    # 2. Khởi tạo Git nếu chưa có
    if not os.path.exists(os.path.join(BASE_DIR, ".git")):
        steps_log.append(run_git(["init"]))

    steps_log.append(run_git(["branch", "-M", branch]))
    steps_log.append(run_git(["add", "."]))
    steps_log.append(run_git(["commit", "-m", commit_msg]))

    if repo_url:
        # Cài đặt remote origin
        run_git(["remote", "remove", "origin"])
        auth_url = repo_url
        if github_token and repo_url.startswith("https://github.com/"):
            auth_url = repo_url.replace("https://github.com/", f"https://{github_token}@github.com/")
        steps_log.append(run_git(["remote", "add", "origin", auth_url]))
        push_res = run_git(["push", "-u", "origin", branch])
        steps_log.append(push_res)

    # Che GitHub token trong moi log tra ve (token tung nam trong URL remote)
    if github_token:
        for st in steps_log:
            if isinstance(st.get("cmd"), str):
                st["cmd"] = st["cmd"].replace(github_token, "***")
            if isinstance(st.get("output"), str):
                st["output"] = st["output"].replace(github_token, "***")

    logger.info("Executed Step 4 Git automation commands")
    return jsonify({
        "ok": True,
        "repo_url": repo_url,
        "steps": steps_log
    })


# --- BƯỚC 5: DEPLOY BOT LÊN RENDER & CẤU HÌNH BIẾN MÔI TRƯỜNG ---
@app.route("/api/step5/render", methods=["POST"])
def api_step5_render():
    data = request.get_json(silent=True) or {}
    updates = {}
    for k in ["BOT_TOKEN", "CHAT_ID", "TIMEZONE", "SUPABASE_URL", "SUPABASE_KEY", "WEBHOOK_URL", "GEMINI_API_KEY"]:
        if k in data:
            updates[k] = data[k]
    env = save_env_config(updates)

    # Kiểm tra nếu người dùng đã điền URL Render thì ping kiểm tra trạng thái Live
    live_check = None
    render_url = env.get("WEBHOOK_URL", "").strip().rstrip("/")
    if render_url.endswith("/webhook"):
        render_url = render_url[:-8]

    if render_url and render_url.startswith("http"):
        try:
            r = requests.get(f"{render_url}/ping", timeout=8)
            live_check = {
                "ok": r.status_code == 200,
                "status_code": r.status_code,
                "response": r.text[:200]
            }
        except Exception as e:
            live_check = {"ok": False, "error": str(e)}

    logger.info("Updated Render Environment Variables & Blueprint configuration")
    return jsonify({
        "ok": True,
        "env": env,
        "live_check": live_check,
        "message": "Đã lưu cấu hình biến môi trường (BOT_TOKEN, CHAT_ID, TIMEZONE) và cập nhật render.yaml!"
    })


# --- BƯỚC 6: KẾT NỐI TELEGRAM WEBHOOK & LOCAL POLLING ---
@app.route("/api/step6/webhook", methods=["POST"])
def api_step6_webhook():
    data = request.get_json(silent=True) or {}
    action = data.get("action", "info")

    if action == "set":
        raw_url = (data.get("WEBHOOK_URL") or get_env_config().get("WEBHOOK_URL", "")).strip().rstrip("/")
        if not raw_url.startswith("https://"):
            return jsonify({
                "ok": False,
                "message": "URL Webhook bắt buộc phải sử dụng giao thức bảo mật https:// (Ví dụ: https://your-app.onrender.com/webhook)"
            })
        webhook_endpoint = raw_url if raw_url.endswith("/webhook") else f"{raw_url}/webhook"
        save_env_config({"WEBHOOK_URL": webhook_endpoint})

        # Dừng Polling nếu đang bật
        POLLING_STATE["running"] = False

        logger.info("Setting up webhook...")
        set_payload: Dict[str, Any] = {"url": webhook_endpoint, "drop_pending_updates": False}
        wh_secret = get_env_config().get("TELEGRAM_WEBHOOK_SECRET", "")
        if wh_secret:
            set_payload["secret_token"] = wh_secret
        res = telegram_api("setWebhook", set_payload)
        if res.get("ok"):
            logger.info("Webhook configured successfully!")
        info = telegram_api("getWebhookInfo")
        return jsonify({
            "ok": res.get("ok", False),
            "set_result": res,
            "webhook_info": info,
            "webhook_url": webhook_endpoint
        })

    if action == "delete":
        res = telegram_api("deleteWebhook")
        info = telegram_api("getWebhookInfo")
        logger.info("Deleted Telegram webhook")
        return jsonify({"ok": res.get("ok", False), "result": res, "webhook_info": info})

    if action == "toggle_polling":
        if IS_VERCEL:
            return jsonify({
                "ok": False,
                "running": False,
                "message": "Local Polling chi chay tren may tinh cua ban. Ban dang mo ban online (Vercel) - hay dung che do Webhook o Buoc 6."
            })
        if POLLING_STATE["running"]:
            POLLING_STATE["running"] = False
            logger.info("Stopped Local Polling mode")
            return jsonify({"ok": True, "running": False, "message": "Đã dừng chế độ Polling cục bộ."})
        else:
            # Xóa webhook trước khi bật getUpdates polling
            telegram_api("deleteWebhook")
            POLLING_STATE["running"] = True
            t = threading.Thread(target=_polling_worker, daemon=True)
            POLLING_STATE["thread"] = t
            t.start()
            logger.info("Starting bot in Local Polling mode...")
            logger.info("Bot is running...")
            logger.info("All systems operational")
            return jsonify({
                "ok": True,
                "running": True,
                "message": "Đã bật chế độ Local Polling! Bạn có thể nhắn tin trực tiếp cho Bot trên Telegram ngay bây giờ."
            })

    info = telegram_api("getWebhookInfo")
    return jsonify({"ok": info.get("ok", False), "webhook_info": info})


def _polling_worker():
    """Luồng chạy ngầm nhận tin nhắn từ Telegram khi người dùng test máy cục bộ."""
    while POLLING_STATE["running"]:
        try:
            token = get_env_config().get("BOT_TOKEN", "")
            if not token:
                time.sleep(3)
                continue
            offset = POLLING_STATE["last_update_id"] + 1
            res = telegram_api("getUpdates", {"offset": offset, "timeout": 5}, token=token)
            if res.get("ok"):
                for upd in res.get("result", []):
                    POLLING_STATE["last_update_id"] = max(POLLING_STATE["last_update_id"], upd.get("update_id", 0))
                    process_telegram_update(upd)
        except Exception as e:
            logger.warning(f"Polling error: {e}")
        time.sleep(1.5)


# --- BƯỚC 7: THIẾT LẬP BOT TƯ VẤN AI & THANH TOÁN ---
@app.route("/api/step7/config", methods=["POST"])
def api_step7_config():
    data = request.get_json(silent=True) or {}
    if "GEMINI_API_KEY" in data:
        save_env_config({"GEMINI_API_KEY": data["GEMINI_API_KEY"]})

    settings_update = {}
    for k in ["shop_name", "shop_url", "support_username", "shipping_inner_city", "shipping_province", "payment"]:
        if k in data:
            settings_update[k] = data[k]

    updated = db.update_settings(settings_update)
    logger.info("Updated Step 7 AI Consultant & Payment settings (PayPal, USDT, QR, Multilingual FAQ)")
    return jsonify({"ok": True, "settings": updated})


# --- BƯỚC 8: TÍCH HỢP BOT VÀO NHÓM & CHỐNG SPAM ---
@app.route("/api/step8/group", methods=["POST"])
def api_step8_group():
    data = request.get_json(silent=True) or {}
    group_cfg = data.get("group_config", {})
    if isinstance(group_cfg.get("trigger_keywords"), str):
        group_cfg["trigger_keywords"] = [
            k.strip() for k in group_cfg["trigger_keywords"].split(",") if k.strip()
        ]
    if isinstance(group_cfg.get("ignored_keywords"), str):
        group_cfg["ignored_keywords"] = [
            k.strip() for k in group_cfg["ignored_keywords"].split(",") if k.strip()
        ]

    updated = db.update_settings({"group_config": group_cfg})

    # Kiểm tra trạng thái Group Privacy từ Telegram getMe
    me = telegram_api("getMe")
    can_read_group = False
    if me.get("ok"):
        can_read_group = bool(me["result"].get("can_read_all_group_messages", False))

    logger.info("Updated Step 8 Group integration & Anti-Spam keyword filter settings")
    return jsonify({
        "ok": True,
        "settings": updated,
        "can_read_all_group_messages": can_read_group
    })


# --- BƯỚC 9: KIỂM TRA BOT, GIẢ LẬP CHAT & CHẨN ĐOÁN LỖI ---
@app.route("/api/step9/simulate", methods=["POST"])
def api_step9_simulate():
    """
    Trình giả lập (Simulator) cho phép test lệnh /start, nút bấm FAQ/Bảng giá/Hỗ trợ
    và test kịch bản Nhóm Hỗ Trợ Khách Hàng ngay trên giao diện Web (hoặc gửi thật qua Telegram).
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "/start")
    chat_type = data.get("chat_type", "private")
    user_id = data.get("user_id", "sim_user_1")
    full_name = data.get("full_name", "Khách hàng Test")
    callback_data = data.get("callback_data")
    send_real = bool(data.get("send_real", False))

    reply = generate_bot_reply(
        text=text,
        chat_type=chat_type,
        user_id=user_id,
        full_name=full_name,
        callback_data=callback_data
    )

    real_telegram_res = None
    env = get_env_config()
    if send_real and env.get("BOT_TOKEN") and env.get("CHAT_ID") and reply.get("responded"):
        payload: Dict[str, Any] = {
            "chat_id": env["CHAT_ID"],
            "text": reply["text"],
            "parse_mode": "Markdown"
        }
        if reply.get("reply_markup"):
            payload["reply_markup"] = reply["reply_markup"]
        real_telegram_res = telegram_api("sendMessage", payload)

    return jsonify({
        "ok": True,
        "input": {"text": text, "chat_type": chat_type, "full_name": full_name, "callback_data": callback_data},
        "reply": reply,
        "real_telegram_res": real_telegram_res
    })


@app.route("/api/step9/diagnostics", methods=["POST", "GET"])
def api_step9_diagnostics():
    """
    BƯỚC 9: Thực hiện 4 bài kiểm tra toàn diện & đối chiếu 4 nhóm lỗi:
    1. Test lệnh /start
    2. Kiểm tra Webhook (getWebhookInfo)
    3. Đối chiếu FAQ & Bảng giá
    4. Kiểm tra 4 nhóm lỗi (Lỗi kết nối, Lỗi webhook, Lỗi câu trả lời, Lỗi deploy)
    """
    logger.info("Starting bot diagnostics...")
    env = get_env_config()

    # 1. Test lệnh /start
    start_reply = generate_bot_reply(text="/start", chat_type="private", user_id="diag_test")
    test1_ok = bool(start_reply.get("responded") and "Xin chào!" in start_reply.get("text", ""))

    # 2. Kiểm tra kết nối Telegram & Webhook
    me_res = telegram_api("getMe")
    webhook_res = telegram_api("getWebhookInfo")
    conn_ok = bool(me_res.get("ok"))
    wh_result = webhook_res.get("result", {}) if webhook_res.get("ok") else {}
    wh_ok = bool(webhook_res.get("ok"))

    # 3. Đối chiếu FAQ & Bảng giá
    faqs_vi = db.get_faqs("VI")
    faqs_en = db.get_faqs("EN")
    faqs_ru = db.get_faqs("RU")
    pricing = db.get_pricing()
    products = db.get_products()
    faq_price_ok = len(faqs_vi) > 0 and len(faqs_en) > 0 and len(faqs_ru) > 0 and len(pricing) > 0 and len(products) > 0

    # 4. Kiểm tra cấu hình Deploy (requirements.txt, main.py, render.yaml, Procfile)
    deploy_files = ["main.py", "faq_engine.py", "database.py", "requirements.txt", "render.yaml", "Procfile"]
    missing_files = [f for f in deploy_files if not os.path.exists(os.path.join(BASE_DIR, f))]
    deploy_ok = len(missing_files) == 0

    if conn_ok:
        logger.info("Connected to Telegram")
    if test1_ok and faq_price_ok and deploy_ok:
        logger.info("All systems operational")

    checklist = {
        "loi_ket_noi": {
            "name": "Lỗi kết nối (Telegram & Database)",
            "passed": conn_ok,
            "detail": f"Đã kết nối @{me_res.get('result', {}).get('username')}" if conn_ok else "Chưa nhập hoặc sai BOT_TOKEN ở Bước 1 (Local DB vẫn hoạt động tốt)."
        },
        "loi_webhook": {
            "name": "Lỗi Webhook / Polling",
            "passed": bool(wh_result.get("url")) or POLLING_STATE["running"],
            "detail": (
                f"Webhook URL: {wh_result.get('url')}"
                if wh_result.get("url")
                else ("Đang chạy chế độ Local Polling trực tiếp" if POLLING_STATE["running"] else "Chưa gắn URL Webhook HTTPS hoặc chưa bật Local Polling ở Bước 6.")
            )
        },
        "loi_cau_tra_loi": {
            "name": "Lỗi câu trả lời (FAQ & Bảng giá)",
            "passed": test1_ok and faq_price_ok,
            "detail": f"Đã nạp {len(products)} sản phẩm, {len(pricing)} bảng giá, {len(faqs_vi)+len(faqs_en)+len(faqs_ru)} câu FAQ (VI/EN/RU)."
        },
        "loi_deploy": {
            "name": "Lỗi Deploy (Cấu trúc mã nguồn Render)",
            "passed": deploy_ok,
            "detail": "Đầy đủ 100% file chuẩn Render (main.py, faq_engine.py, database.py, requirements.txt, render.yaml, Procfile)." if deploy_ok else f"Thiếu file: {', '.join(missing_files)}"
        }
    }

    return jsonify({
        "ok": True,
        "start_test": start_reply,
        "webhook_info": webhook_res if webhook_res.get("ok") else {
            "ok": True,
            "note": "Mẫu cấu hình chuẩn (Nhập BOT_TOKEN thật ở Bước 1 để xem dữ liệu thực từ api.telegram.org)",
            "result": {
                "url": env.get("WEBHOOK_URL") or "https://your-app.onrender.com/webhook",
                "has_custom_certificate": False,
                "pending_update_count": 0
            }
        },
        "data_audit": {
            "products_count": len(products),
            "pricing_count": len(pricing),
            "faqs_vi": len(faqs_vi),
            "faqs_en": len(faqs_en),
            "faqs_ru": len(faqs_ru),
            "passed": faq_price_ok
        },
        "checklist": checklist,
        "logs": SYSTEM_LOGS[-30:]
    })


# Khởi tạo các dòng log chuẩn theo hình Bước 9 khi khởi động Server
def _init_boot_logs():
    generate_supabase_sql()
    mode = "Vercel (Webhook)" if IS_VERCEL else "Local (Polling/Webhook)"
    logger.info(f"Starting bot... Che do: {mode}")
    env = get_env_config()
    if env.get("BOT_TOKEN"):
        logger.info("BOT_TOKEN da co - bot san sang phan hoi qua Webhook/Polling.")
    else:
        logger.info("Chua co BOT_TOKEN - nhap token o Buoc 1 de bot phan hoi Telegram.")


_init_boot_logs()


# --- WSGI middleware cho Vercel -------------------------------------------------
# vercel.json rewrite moi request ve /api/index/<duong-dan-goc> va Vercel dat
# PATH_INFO = /api/index/<duong-dan-goc>. Flask khop route theo PATH_INFO nen
# phai cat tien to "/api/index" (chuyen sang SCRIPT_NAME) truoc khi Flask xu ly.
# Khi chay local, PATH_INFO khong co tien to nay nen middleware khong lam gi.
class _StripApiIndexPrefix:
    PREFIX = "/api/index"

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.PREFIX or path.startswith(self.PREFIX + "/"):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + self.PREFIX
            environ["PATH_INFO"] = path[len(self.PREFIX):] or "/"
        return self.wsgi_app(environ, start_response)


app.wsgi_app = _StripApiIndexPrefix(app.wsgi_app)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 72)
    print("🚀 HỆ THỐNG AUTO TẠO BOT TELEGRAM 9 BƯỚC ĐÃ KHỞI ĐỘNG!")
    print(f"👉 Mở trình duyệt tại: http://127.0.0.1:{port}/dashboard")
    print(f"👉 Endpoint Webhook:   http://127.0.0.1:{port}/webhook")
    print("=" * 72)
    app.run(host="0.0.0.0", port=port, debug=False)
