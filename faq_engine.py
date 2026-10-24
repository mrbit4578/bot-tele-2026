"""
BƯỚC 2, BƯỚC 7 & BƯỚC 8: faq_engine.py - Bộ máy trả lời FAQ Đa ngôn ngữ, Tư vấn AI & Chống Spam Nhóm
- Trả lời FAQ đa ngôn ngữ (VI / EN / RU)
- Tư vấn chọn sản phẩm, xem bảng giá, thanh toán (PayPal, USDT, QR Code)
- Lọc keyword & chống spam khi tích hợp Bot vào nhóm Telegram (Bước 8)
"""

import os
import time
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, List, Any, Optional, Tuple
from database import DatabaseManager

logger = logging.getLogger("TelegramBot.FAQEngine")


class AntiSpamFilter:
    """
    Bộ lọc chống spam & kiểm soát tần suất tin nhắn trong nhóm (Bước 8).
    """

    def __init__(self):
        # Lưu lịch sử timestamp tin nhắn theo user_id
        self.user_timestamps: Dict[str, List[float]] = {}

    def check_allowed(self, user_id: str, cooldown_sec: int = 5, max_per_min: int = 6) -> Tuple[bool, str]:
        now = time.time()
        uid = str(user_id)
        history = [t for t in self.user_timestamps.get(uid, []) if now - t < 60.0]

        if history and (now - history[-1]) < cooldown_sec:
            return False, "Cooldown active"

        if len(history) >= max_per_min:
            return False, "Rate limit exceeded (Anti-Spam)"

        history.append(now)
        self.user_timestamps[uid] = history
        return True, "OK"


class FAQEngine:
    """
    Bộ máy xử lý ngôn ngữ tự nhiên, đối chiếu FAQ, bảng giá, sản phẩm và tư vấn AI.
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        self.spam_filter = AntiSpamFilter()

    def detect_language(self, text: str) -> str:
        """Nhận diện ngôn ngữ tự động (VI / EN / RU)."""
        text_lower = text.lower()
        # Kiểm tra ký tự Cyrillic (Tiếng Nga - RU)
        if any("\u0400" <= ch <= "\u04FF" for ch in text):
            return "RU"
        # Kiểm tra từ khóa tiếng Anh phổ biến
        en_words = ["hello", "hi ", "price", "shipping", "payment", "product", "support", "buy", "how much"]
        vi_chars = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
        if any(c in text_lower for c in vi_chars):
            return "VI"
        if any(w in text_lower for w in en_words):
            return "EN"
        return "VI"

    def should_respond_in_group(self, text: str, user_id: str, bot_username: str = "") -> Tuple[bool, str]:
        """
        BƯỚC 8: Kiểm tra tin nhắn trong nhóm có cần phản hồi hay không.
        - Bỏ qua các tin nhắn trò chuyện cá nhân không chứa từ khóa (VD: 'Anh em xem trận tối nay nhé!', 'đi cà phê không?', 'report.pdf')
        - Kiểm tra bộ lọc chống spam
        """
        if not text or not text.strip():
            return False, "Empty message"

        settings = self.db.get_settings()
        group_cfg = settings.get("group_config", {})

        if not group_cfg.get("enabled", True):
            return False, "Group bot disabled"

        text_lower = text.strip().lower()

        # Luôn phản hồi nếu là lệnh trực tiếp (/start, /ship, /price, /faq...)
        if text_lower.startswith("/"):
            allowed, reason = self.spam_filter.check_allowed(
                user_id,
                cooldown_sec=int(group_cfg.get("cooldown_seconds", 3)),
                max_per_min=int(group_cfg.get("max_msgs_per_minute", 10))
            )
            return allowed, reason

        # Kiểm tra danh sách từ khóa bị loại trừ (chat phiếm/báo cáo nội bộ)
        ignored = group_cfg.get("ignored_keywords", [])
        for ig in ignored:
            if ig.lower() in text_lower:
                return False, f"Ignored keyword matched: {ig}"

        # Kiểm tra danh sách từ khóa kích hoạt (Bước 8.3: Bật lọc keyword & chống spam)
        if group_cfg.get("keyword_filter_enabled", True):
            triggers = group_cfg.get("trigger_keywords", [])
            matched_trigger = False
            if bot_username and f"@{bot_username.lower().lstrip('@')}" in text_lower:
                matched_trigger = True
            else:
                for kw in triggers:
                    if kw.lower() in text_lower:
                        matched_trigger = True
                        break
                # Kiểm tra thêm trong keywords của bảng FAQs
                if not matched_trigger:
                    for faq in self.db.get_faqs():
                        for fkw in faq.get("keywords", []):
                            if fkw.lower() in text_lower:
                                matched_trigger = True
                                break
                        if matched_trigger:
                            break

            if not matched_trigger:
                return False, "No trigger keyword matched in group message"

        # Kiểm tra chống spam
        if group_cfg.get("anti_spam_enabled", True):
            allowed, reason = self.spam_filter.check_allowed(
                user_id,
                cooldown_sec=int(group_cfg.get("cooldown_seconds", 5)),
                max_per_min=int(group_cfg.get("max_msgs_per_minute", 6))
            )
            if not allowed:
                return False, reason

        return True, "Matched keyword & passed anti-spam"

    def match_faq(self, query: str, lang: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Tìm câu trả lời phù hợp nhất trong cơ sở dữ liệu FAQ."""
        if not query:
            return None
        q_lower = query.lower().strip()
        detected_lang = lang or self.detect_language(query)

        # Lấy danh sách FAQ ưu tiên theo ngôn ngữ trước, sau đó toàn bộ
        faqs_lang = self.db.get_faqs(detected_lang)
        all_faqs = faqs_lang + [f for f in self.db.get_faqs() if f not in faqs_lang]

        best_faq = None
        best_score = 0

        for faq in all_faqs:
            score = 0
            question_lower = str(faq.get("question", "")).lower()
            if q_lower == question_lower:
                return faq
            if q_lower in question_lower or question_lower in q_lower:
                score += 5

            for kw in faq.get("keywords", []):
                kw_lower = str(kw).lower().strip()
                if kw_lower and kw_lower in q_lower:
                    # Ưu tiên cụm từ khóa dài và chính xác hơn
                    score += 3 + len(kw_lower.split())

            if score > best_score:
                best_score = score
                best_faq = faq

        return best_faq if best_score >= 3 else None

    def format_shipping_info(self) -> str:
        """Thông tin phí giao hàng chuẩn theo Bước 8 (/ship)."""
        settings = self.db.get_settings()
        inner = settings.get("shipping_inner_city", "20.000đ")
        prov = settings.get("shipping_province", "30.000đ")
        return (
            f"Dạ, phí giao hàng tùy khu vực:\n"
            f"• Nội thành: {inner}\n"
            f"• Tỉnh: {prov}\n"
            f"Bạn có thể dùng /ship để tra cứu chi tiết nhé!"
        )

    def format_products_message(self) -> str:
        """Danh sách sản phẩm theo Bước 7 (1. Chọn sản phẩm)."""
        products = self.db.get_products()
        settings = self.db.get_settings()
        shop_url = settings.get("shop_url", "https://shop.example.com")
        lines = ["📦 **DANH MỤC SẢN PHẨM HIỆN CÓ:**\n"]
        for idx, p in enumerate(products, 1):
            status = "✅ Còn hàng" if p.get("in_stock", True) else "❌ Tạm hết"
            lines.append(
                f"{idx}. **{p.get('name')}** ({status})\n"
                f"   • Mô tả: {p.get('description')}\n"
                f"   • Đặt hàng: {p.get('order_url', shop_url)}"
            )
        lines.append("\n👉 Bấm vào từng sản phẩm bên dưới để xem chi tiết hoặc đặt mua!")
        return "\n".join(lines)

    def format_pricing_message(self) -> str:
        """Bảng giá niêm yết theo Bước 7 (2. Xem bảng giá) & Bước 9 (3. Đối chiếu bảng giá)."""
        pricing = self.db.get_pricing()
        lines = ["💰 **BẢNG GIÁ NIÊM YẾT CHÍNH THỨC:**\n"]
        for item in pricing:
            lines.append(
                f"🔹 **{item.get('name')}** — *{item.get('plan', '')}*\n"
                f"   • Giá VNĐ: `{item.get('price_vnd')}`\n"
                f"   • Quốc tế: `{item.get('price_usd')}` | `{item.get('price_usdt')}`\n"
                f"   • Quyền lợi: {item.get('details')}\n"
            )
        lines.append("📞 Cần tư vấn gói riêng? Hãy chọn **Liên hệ tư vấn** bên dưới!")
        return "\n".join(lines)

    def format_payment_message(self, method: str = "ALL") -> Dict[str, Any]:
        """Thông tin thanh toán theo Bước 7 (3. Thanh toán: PayPal | USDT | QR Code)."""
        settings = self.db.get_settings()
        pay = settings.get("payment", {})
        paypal_email = pay.get("paypal_email", "payment@shop.example.com")
        paypal_link = pay.get("paypal_link", "https://paypal.me/shopexample")
        usdt_addr = pay.get("usdt_address", "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE")
        usdt_net = pay.get("usdt_network", "TRC20 / BEP20")
        bank_qr = pay.get("bank_qr_info", "VIETCOMBANK - 0123456789 - SHOP AI")

        qr_data = urllib.parse.quote(f"USDT:{usdt_addr}|PAYPAL:{paypal_email}|{bank_qr}")
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_data}"

        if method.upper() == "PAYPAL":
            text = (
                "💳 **THANH TOÁN QUA PAYPAL**\n\n"
                f"• Email PayPal: `{paypal_email}`\n"
                f"• Link thanh toán nhanh: {paypal_link}\n"
                "• Nội dung: `[Tên Telegram] + [Mã Sản Phẩm]`"
            )
        elif method.upper() == "USDT":
            text = (
                "🪙 **THANH TOÁN QUA CRYPTO (USDT)**\n\n"
                f"• Mạng lưới (Network): **{usdt_net}**\n"
                f"• Địa chỉ ví (Wallet): `{usdt_addr}`\n"
                "• Sau khi chuyển khoản, vui lòng gửi TxID để Bot xác nhận tự động!"
            )
        else:
            text = (
                "💠 **HƯỚNG DẪN THANH TOÁN ĐA KÊNH**\n\n"
                f"1️⃣ **PayPal**: `{paypal_email}` ({paypal_link})\n"
                f"2️⃣ **USDT ({usdt_net})**: `{usdt_addr}`\n"
                f"3️⃣ **QR Ngân hàng**: `{bank_qr}`\n\n"
                "📲 Bạn có thể quét mã QR hoặc chọn phương thức bên dưới:"
            )

        return {"text": text, "qr_url": qr_url}

    def format_faq_by_language(self, lang: str = "VI") -> str:
        """Hiển thị danh sách FAQ theo ngôn ngữ VI / EN / RU (Bước 7.4)."""
        lang = lang.upper()
        faqs = self.db.get_faqs(lang)
        titles = {
            "VI": "🇻🇳 **CÂU HỎI THƯỜNG GẶP (TIẾNG VIỆT)**\n",
            "EN": "🇬🇧 **FREQUENTLY ASKED QUESTIONS (ENGLISH)**\n",
            "RU": "🇷🇺 **ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ (РУССКИЙ)**\n"
        }
        header = titles.get(lang, titles["VI"])
        lines = [header]
        for idx, f in enumerate(faqs, 1):
            lines.append(f"❓ **Q{idx}: {f.get('question')}**\n💡 {f.get('answer')}\n")
        return "\n".join(lines)

    def generate_ai_response(self, user_message: str, is_group: bool = False) -> Dict[str, Any]:
        """
        Tạo câu trả lời thông minh kết hợp FAQ, Kịch bản Tư vấn AI (Bước 7) và Kịch bản Nhóm (Bước 8).
        Trả về dict: {'text': ..., 'reply_markup': ...}
        """
        msg_lower = user_message.strip().lower()
        settings = self.db.get_settings()
        shop_url = settings.get("shop_url", "https://shop.example.com")

        # 1. Kịch bản chính xác trong hình Bước 8: Hỏi phí giao hàng
        if any(k in msg_lower for k in ["phí giao hàng", "phí ship", "tiền ship", "giao hàng"]):
            inner = settings.get("shipping_inner_city", "20.000đ")
            prov = settings.get("shipping_province", "30.000đ")
            return {
                "text": (
                    f"Dạ, phí giao hàng tùy khu vực:\n"
                    f"Nội thành {inner}, tỉnh {prov}.\n"
                    f"Bạn có thể dùng /ship để tra cứu chi tiết nhé!"
                ),
                "menu_type": None if is_group else "main_consultant"
            }

        # 2. Kịch bản chính xác trong hình Bước 8: Hỏi còn hàng không
        if any(k in msg_lower for k in ["còn hàng không", "còn hàng", "hết hàng", "tồn kho"]):
            return {
                "text": f"Dạ, sản phẩm vẫn còn hàng.\nBạn có thể đặt ngay tại đây:\n{shop_url}",
                "menu_type": None if is_group else "products"
            }

        # 3. Kịch bản chính xác trong hình Bước 7: "Mình cần tư vấn sản phẩm"
        if any(k in msg_lower for k in ["tư vấn sản phẩm", "cần tư vấn", "tư vấn", "mua sản phẩm", "chọn sản phẩm"]):
            return {
                "text": "Bạn muốn tìm hiểu sản phẩm nào?",
                "menu_type": "main_consultant"
            }

        # 4. Hỏi bảng giá
        if any(k in msg_lower for k in ["bảng giá", "giá bao nhiêu", "báo giá", "price", "цена"]):
            return {
                "text": self.format_pricing_message(),
                "menu_type": "pricing"
            }

        # 5. Hỏi thanh toán
        if any(k in msg_lower for k in ["thanh toán", "paypal", "usdt", "payment", "оплата"]):
            pay_info = self.format_payment_message("ALL")
            return {
                "text": pay_info["text"],
                "menu_type": "payment",
                "qr_url": pay_info["qr_url"]
            }

        # 6. Đối chiếu trong bảng FAQ đa ngôn ngữ
        faq_match = self.match_faq(user_message)
        if faq_match:
            return {
                "text": faq_match.get("answer", ""),
                "menu_type": None if is_group else "main_consultant"
            }

        # 7. Nếu cấu hình GEMINI_API_KEY hoặc OPENAI_API_KEY thì gọi AI sinh câu trả lời tự nhiên
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        if gemini_key:
            ai_reply = self._call_gemini_api(user_message, gemini_key)
            if ai_reply:
                return {"text": ai_reply, "menu_type": "main_consultant"}

        # 8. Phản hồi mặc định thân thiện kèm menu điều hướng
        lang = self.detect_language(user_message)
        if lang == "EN":
            return {
                "text": "Hello! How can I help you today? Please choose an option below:",
                "menu_type": "main_consultant"
            }
        elif lang == "RU":
            return {
                "text": "Здравствуйте! Чем я могу вам помочь? Выберите нужный раздел ниже:",
                "menu_type": "main_consultant"
            }

        return {
            "text": "Bạn muốn tìm hiểu sản phẩm nào? Hãy chọn một mục bên dưới để mình hỗ trợ nhanh nhất nhé! ✨",
            "menu_type": "main_consultant"
        }

    def _call_gemini_api(self, prompt: str, api_key: str) -> Optional[str]:
        """Tích hợp Gemini AI tùy chọn cho tư vấn nâng cao."""
        try:
            products = self.db.get_products()
            pricing = self.db.get_pricing()
            context = (
                "Bạn là trợ lý AI chăm sóc khách hàng chuyên nghiệp trên Telegram.\n"
                f"Danh sách sản phẩm: {json.dumps(products, ensure_ascii=False)}\n"
                f"Bảng giá: {json.dumps(pricing, ensure_ascii=False)}\n"
                "Hãy trả lời ngắn gọn, lịch sự, chính xác."
            )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{context}\n\nKhách hàng hỏi: {prompt}"}]}]
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.warning(f"Gemini API fallback: {e}")
            return None
