"""
BƯỚC 2 & BƯỚC 3: database.py - Kết nối và quản lý dữ liệu tập trung (Supabase & Local Fallback)
Quản lý 4 phân hệ dữ liệu chính theo cấu trúc Bước 3:
1. Sản phẩm (products)
2. Bảng giá (pricing)
3. Câu hỏi FAQ đa ngôn ngữ VI/EN/RU (faqs)
4. Khách hàng (customers)
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import urllib.request
import urllib.error
import urllib.parse

logger = logging.getLogger("TelegramBot.Database")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_BUNDLED_DATA_DIR = os.path.join(_BASE_DIR, "data")
# Tren Vercel (serverless) filesystem cua project la chi-doc & tam thoi:
# local DB phai nam o /tmp (mat khi instance tai che) -> Supabase la noi luu ben vung.
# Co the ghi de bang bien moi truong BOT_DATA_DIR.
if os.getenv("BOT_DATA_DIR"):
    DATA_DIR = os.getenv("BOT_DATA_DIR")
elif os.getenv("VERCEL"):
    DATA_DIR = "/tmp/bot-tele-2026-data"
else:
    DATA_DIR = _BUNDLED_DATA_DIR
LOCAL_DB_FILE = os.path.join(DATA_DIR, "bot_database.json")
SCHEMA_SQL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "supabase_schema.sql")

DEFAULT_DATABASE: Dict[str, Any] = {
    "products": [
        {
            "id": "prod_a",
            "name": "Sản phẩm A - Gói AI Pro",
            "code": "SP_A",
            "category": "Phần mềm AI",
            "description": "Giải pháp Chatbot AI tự động hóa chăm sóc khách hàng 24/7 đa kênh.",
            "in_stock": True,
            "stock_qty": 150,
            "order_url": "https://shop.example.com/san-pham-a",
            "features": ["Tự động trả lời 24/7", "Đa ngôn ngữ VI/EN/RU", "Tích hợp nhóm Telegram"]
        },
        {
            "id": "prod_b",
            "name": "Sản phẩm B - Gói Enterprise",
            "code": "SP_B",
            "category": "Giải pháp Doanh nghiệp",
            "description": "Hệ thống Bot AI cao cấp tích hợp Supabase, CRM và cổng thanh toán quốc tế.",
            "in_stock": True,
            "stock_qty": 85,
            "order_url": "https://shop.example.com/san-pham-b",
            "features": ["Lưu trữ Supabase tập trung", "Thanh toán PayPal & USDT", "Chống spam nhóm thông minh"]
        },
        {
            "id": "prod_c",
            "name": "Sản phẩm C - Thiết bị Smart Box",
            "code": "SP_C",
            "category": "Phần cứng",
            "description": "Thiết bị phần cứng thông minh kết nối hệ thống điều khiển qua Telegram.",
            "in_stock": True,
            "stock_qty": 42,
            "order_url": "https://shop.example.com/san-pham-c",
            "features": ["Bảo hành 12 tháng", "Giao hàng toàn quốc", "Hỗ trợ kỹ thuật 1-1"]
        }
    ],
    "pricing": [
        {
            "id": "price_1",
            "product_id": "prod_a",
            "name": "Sản phẩm A",
            "plan": "Gói Cơ Bản (1 Tháng)",
            "price_vnd": "490.000đ",
            "price_usd": "$19.99",
            "price_usdt": "20 USDT",
            "details": "Đầy đủ tính năng tư vấn tự động, FAQ đa ngôn ngữ, hỗ trợ 1 nhóm Telegram."
        },
        {
            "id": "price_2",
            "product_id": "prod_b",
            "name": "Sản phẩm B",
            "plan": "Gói Chuyên Nghiệp (1 Năm)",
            "price_vnd": "2.990.000đ",
            "price_usd": "$119.99",
            "price_usdt": "120 USDT",
            "details": "Không giới hạn nhóm, tích hợp Supabase, cổng thanh toán PayPal & USDT, ưu tiên hỗ trợ VIP."
        },
        {
            "id": "price_3",
            "product_id": "prod_c",
            "name": "Sản phẩm C",
            "plan": "Bộ Thiết Bị Tiêu Chuẩn",
            "price_vnd": "1.250.000đ",
            "price_usd": "$49.99",
            "price_usdt": "50 USDT",
            "details": "Tặng kèm 3 tháng sử dụng Bot AI Pro miễn phí. Phí ship nội thành 20.000đ, tỉnh 30.000đ."
        }
    ],
    "faqs": [
        {
            "id": "faq_ship_vi",
            "lang": "VI",
            "question": "Phí giao hàng tính như thế nào?",
            "keywords": ["phí giao hàng", "giao hàng", "tiền ship", "phí ship", "vận chuyển", "ship"],
            "answer": "Dạ, phí giao hàng tùy khu vực: Nội thành 20.000đ, tỉnh 30.000đ. Bạn có thể dùng /ship để tra cứu chi tiết nhé!"
        },
        {
            "id": "faq_stock_vi",
            "lang": "VI",
            "question": "Sản phẩm này còn hàng không ạ?",
            "keywords": ["còn hàng", "hết hàng", "tồn kho", "mua ngay", "đặt hàng"],
            "answer": "Dạ, sản phẩm vẫn còn hàng. Bạn có thể đặt ngay tại đây: https://shop.example.com"
        },
        {
            "id": "faq_pay_vi",
            "lang": "VI",
            "question": "Shop hỗ trợ những hình thức thanh toán nào?",
            "keywords": ["thanh toán", "chuyển khoản", "paypal", "usdt", "qr", "trả tiền"],
            "answer": "Shop hỗ trợ thanh toán linh hoạt qua PayPal, USDT (TRC20/BEP20) và quét mã QR ngân hàng. Bạn bấm nút 'Thanh toán' hoặc gõ /pay để nhận thông tin nhé!"
        },
        {
            "id": "faq_warranty_vi",
            "lang": "VI",
            "question": "Chế độ bảo hành và hỗ trợ kỹ thuật ra sao?",
            "keywords": ["bảo hành", "đổi trả", "lỗi", "hỗ trợ kỹ thuật"],
            "answer": "Tất cả sản phẩm đều được bảo hành chính hãng 12 tháng, lỗi 1 đổi 1 trong 30 ngày đầu và hỗ trợ kỹ thuật 24/7 qua Telegram."
        },
        {
            "id": "faq_en_1",
            "lang": "EN",
            "question": "What payment methods do you accept?",
            "keywords": ["payment", "pay", "paypal", "usdt", "crypto", "buy"],
            "answer": "We accept PayPal, USDT (TRC20/BEP20), and QR Code instant payment. Use /pay or click the Payment button to proceed!"
        },
        {
            "id": "faq_en_2",
            "lang": "EN",
            "question": "How much is shipping and delivery time?",
            "keywords": ["shipping", "delivery", "ship", "stock", "available"],
            "answer": "All items are in stock! Domestic shipping is 20,000 VND (inner city) or 30,000 VND (provinces). Digital products are delivered instantly via https://shop.example.com"
        },
        {
            "id": "faq_ru_1",
            "lang": "RU",
            "question": "Какие способы оплаты вы принимаете?",
            "keywords": ["оплата", "оплатить", "paypal", "usdt", "купить", "цена"],
            "answer": "Мы принимаем PayPal, USDT (TRC20/BEP20) и оплату по QR-коду. Нажмите кнопку «Оплата» или введите /pay для получения реквизитов!"
        },
        {
            "id": "faq_ru_2",
            "lang": "RU",
            "question": "Есть ли товар в наличии и как оформить заказ?",
            "keywords": ["наличии", "доставка", "заказ", "товар"],
            "answer": "Да, все товары в наличии! Вы можете оформить заказ прямо сейчас на сайте: https://shop.example.com"
        }
    ],
    "customers": [
        {
            "id": "cust_1",
            "telegram_id": "100001",
            "username": "lan_anh",
            "full_name": "Lan Anh",
            "language": "VI",
            "interested_in": "Sản phẩm A",
            "last_message": "Shop ơi, tôi muốn hỏi về phí giao hàng?",
            "created_at": "2026-10-24T10:14:00"
        },
        {
            "id": "cust_2",
            "telegram_id": "100002",
            "username": "minh_duc",
            "full_name": "Minh Đức",
            "language": "VI",
            "interested_in": "Sản phẩm B",
            "last_message": "Sản phẩm này còn hàng không ạ?",
            "created_at": "2026-10-24T10:17:00"
        }
    ],
    "settings": {
        "shop_name": "NexusPilot Pro",
        "shop_url": "https://mt5-mrbit-2026-v2.onrender.com/",
        "fanpage_url": "https://www.facebook.com/profile.php?id=61595736091847",
        "support_username": "@soledadhuong90",
        "shipping_inner_city": "20.000đ",
        "shipping_province": "30.000đ",
        "payment": {
            "paypal_email": "payment@shop.example.com",
            "paypal_link": "https://paypal.me/shopexample",
            "usdt_address": "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE",
            "usdt_network": "TRC20 (Tron) / BEP20 (BSC)",
            "bank_qr_info": "VIETCOMBANK - 0123456789 - SHOP AI AUTOMATION"
        },
        "group_config": {
            "enabled": True,
            "keyword_filter_enabled": True,
            "anti_spam_enabled": True,
            "cooldown_seconds": 5,
            "max_msgs_per_minute": 6,
            "trigger_keywords": [
                "shop ơi", "phí giao hàng", "giao hàng", "ship", "còn hàng",
                "hết hàng", "bảng giá", "giá bao nhiêu", "mua hàng", "đặt hàng",
                "thanh toán", "paypal", "usdt", "bảo hành", "tư vấn"
            ],
            "ignored_keywords": [
                "xem trận tối nay", "đi cà phê", "file báo cáo", "report.pdf"
            ]
        }
    }
}


class DatabaseManager:
    """
    Quản lý kết nối Supabase (REST API) kèm bộ nhớ đệm & fallback JSON cục bộ.
    Đảm bảo hệ thống hoạt động 100% cả khi có hoặc chưa có Supabase.
    """

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.supabase_url = (supabase_url or os.getenv("SUPABASE_URL", "")).strip().rstrip("/")
        self.supabase_key = (supabase_key or os.getenv("SUPABASE_KEY", "")).strip()
        self._remote_cache: Dict[str, Any] = {}
        self._ensure_local_db()

    def _remote_list(self, table: str) -> Optional[List[Dict[str, Any]]]:
        """Doc danh sach tu Supabase co cache TTL 20s.
        Truoc day moi lan bot xu ly 1 tin nhan lai goi HTTP Supabase ~10 lan
        (get_settings/get_products/get_faqs lap lai) -> cham & de vuot quota.
        Cache 20s giu dashboard gan nhu realtime ma giam tai dang ke."""
        now = time.time()
        hit = self._remote_cache.get(table)
        if hit and (now - hit[0]) < 20:
            return hit[1]
        res = self._supabase_request(table, "GET", {"select": "*"})
        if isinstance(res, list):
            self._remote_cache[table] = (now, res)
            return res
        return None

    def _invalidate_cache(self, table: Optional[str] = None) -> None:
        if table:
            self._remote_cache.pop(table, None)
        else:
            self._remote_cache.clear()

    def _ensure_local_db(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(LOCAL_DB_FILE):
            bundled = os.path.join(_BUNDLED_DATA_DIR, "bot_database.json")
            if os.path.abspath(bundled) != os.path.abspath(LOCAL_DB_FILE) and os.path.exists(bundled):
                try:
                    with open(bundled, "r", encoding="utf-8") as f:
                        self.save_local_db(json.load(f))
                    return
                except Exception as e:
                    logger.warning(f"Khong seed duoc tu data kem theo: {e}")
            self.save_local_db(DEFAULT_DATABASE)

    def load_local_db(self) -> Dict[str, Any]:
        self._ensure_local_db()
        try:
            with open(LOCAL_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULT_DATABASE.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception as e:
            logger.error(f"Lỗi đọc local DB: {e}")
            return json.loads(json.dumps(DEFAULT_DATABASE))

    def save_local_db(self, data: Dict[str, Any]) -> bool:
        os.makedirs(DATA_DIR, exist_ok=True)
        try:
            with open(LOCAL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Lỗi lưu local DB: {e}")
            return False

    @property
    def is_supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key and self.supabase_url.startswith("http"))

    def _supabase_request(
        self,
        table: str,
        method: str = "GET",
        query_params: Optional[Dict[str, str]] = None,
        payload: Optional[Any] = None,
        prefer: Optional[str] = None
    ) -> Optional[Any]:
        if not self.is_supabase_configured:
            return None

        url = f"{self.supabase_url}/rest/v1/{table}"
        if query_params:
            url += "?" + urllib.parse.urlencode(query_params)

        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": prefer or "return=representation"
        }

        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else []
        except Exception as e:
            logger.warning(f"Supabase request fallback ({method} {table}): {e}")
            return None

    def test_connection(self) -> Dict[str, Any]:
        """Kiểm tra kết nối Supabase và Local DB (Bước 3 & Bước 9)."""
        local_data = self.load_local_db()
        counts = {
            "products": len(local_data.get("products", [])),
            "pricing": len(local_data.get("pricing", [])),
            "faqs": len(local_data.get("faqs", [])),
            "customers": len(local_data.get("customers", []))
        }

        if not self.is_supabase_configured:
            return {
                "ok": True,
                "mode": "Local Database (JSON Fallback)",
                "supabase_connected": False,
                "message": "Đang sử dụng cơ sở dữ liệu cục bộ (Sẵn sàng). Nhập SUPABASE_URL & SUPABASE_KEY nếu muốn đồng bộ Cloud.",
                "counts": counts
            }

        res = self._supabase_request("products", "GET", {"select": "*", "limit": "5"})
        if res is not None:
            return {
                "ok": True,
                "mode": "Supabase Cloud + Local Sync",
                "supabase_connected": True,
                "message": "Kết nối Supabase thành công!",
                "counts": counts
            }
        return {
            "ok": False,
            "mode": "Local Fallback (Supabase Lỗi/Chưa tạo bảng)",
            "supabase_connected": False,
            "message": "Không thể truy cập bảng trên Supabase. Hãy chạy đoạn mã SQL trong supabase_schema.sql trên Supabase SQL Editor.",
            "counts": counts
        }

    # --- 1. SẢN PHẨM (PRODUCTS) ---
    def get_products(self) -> List[Dict[str, Any]]:
        remote = self._remote_list("products")
        if isinstance(remote, list) and len(remote) > 0:
            return remote
        return self.load_local_db().get("products", [])

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        for p in self.get_products():
            if str(p.get("id")) == str(product_id) or str(p.get("code", "")).lower() == str(product_id).lower():
                return p
        return None

    def upsert_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        db = self.load_local_db()
        products = db.get("products", [])
        if not product.get("id"):
            product["id"] = f"prod_{int(time.time())}"
        updated = False
        for i, p in enumerate(products):
            if p.get("id") == product["id"]:
                products[i] = product
                updated = True
                break
        if not updated:
            products.append(product)
        db["products"] = products
        self.save_local_db(db)
        self._supabase_request("products", "POST", payload=product, prefer="resolution=merge-duplicates,return=representation")
        self._invalidate_cache("products")
        return product

    # --- 2. BẢNG GIÁ (PRICING) ---
    def get_pricing(self) -> List[Dict[str, Any]]:
        remote = self._remote_list("pricing")
        if isinstance(remote, list) and len(remote) > 0:
            return remote
        return self.load_local_db().get("pricing", [])

    def upsert_pricing(self, price_item: Dict[str, Any]) -> Dict[str, Any]:
        db = self.load_local_db()
        pricing = db.get("pricing", [])
        if not price_item.get("id"):
            price_item["id"] = f"price_{int(time.time())}"
        updated = False
        for i, item in enumerate(pricing):
            if item.get("id") == price_item["id"]:
                pricing[i] = price_item
                updated = True
                break
        if not updated:
            pricing.append(price_item)
        db["pricing"] = pricing
        self.save_local_db(db)
        self._supabase_request("pricing", "POST", payload=price_item, prefer="resolution=merge-duplicates,return=representation")
        self._invalidate_cache("pricing")
        return price_item

    # --- 3. CÂU HỎI FAQ (FAQS) ---
    def get_faqs(self, lang: Optional[str] = None) -> List[Dict[str, Any]]:
        remote = self._remote_list("faqs")
        faqs = remote if (isinstance(remote, list) and len(remote) > 0) else self.load_local_db().get("faqs", [])
        if lang:
            lang_upper = lang.upper()
            return [f for f in faqs if str(f.get("lang", "VI")).upper() == lang_upper]
        return faqs

    def upsert_faq(self, faq_item: Dict[str, Any]) -> Dict[str, Any]:
        db = self.load_local_db()
        faqs = db.get("faqs", [])
        if not faq_item.get("id"):
            faq_item["id"] = f"faq_{int(time.time())}"
        if isinstance(faq_item.get("keywords"), str):
            faq_item["keywords"] = [k.strip() for k in faq_item["keywords"].split(",") if k.strip()]
        updated = False
        for i, item in enumerate(faqs):
            if item.get("id") == faq_item["id"]:
                faqs[i] = faq_item
                updated = True
                break
        if not updated:
            faqs.append(faq_item)
        db["faqs"] = faqs
        self.save_local_db(db)
        self._supabase_request("faqs", "POST", payload=faq_item, prefer="resolution=merge-duplicates,return=representation")
        self._invalidate_cache("faqs")
        return faq_item

    # --- 4. KHÁCH HÀNG (CUSTOMERS) ---
    def get_customers(self) -> List[Dict[str, Any]]:
        remote = self._remote_list("customers")
        if isinstance(remote, list) and len(remote) > 0:
            return remote
        return self.load_local_db().get("customers", [])

    def log_customer_interaction(
        self,
        telegram_id: str,
        username: str = "",
        full_name: str = "",
        message: str = "",
        language: str = "VI",
        interested_in: str = ""
    ) -> Dict[str, Any]:
        db = self.load_local_db()
        customers = db.get("customers", [])
        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        existing = None
        for c in customers:
            if str(c.get("telegram_id")) == str(telegram_id):
                existing = c
                break

        if existing:
            existing["username"] = username or existing.get("username", "")
            existing["full_name"] = full_name or existing.get("full_name", "")
            existing["last_message"] = message or existing.get("last_message", "")
            existing["language"] = language or existing.get("language", "VI")
            if interested_in:
                existing["interested_in"] = interested_in
            existing["updated_at"] = now_iso
            record = existing
        else:
            record = {
                "id": f"cust_{telegram_id}",
                "telegram_id": str(telegram_id),
                "username": username,
                "full_name": full_name or "Khách hàng",
                "language": language,
                "interested_in": interested_in or "Tư vấn chung",
                "last_message": message,
                "created_at": now_iso
            }
            customers.append(record)

        db["customers"] = customers
        self.save_local_db(db)
        self._supabase_request("customers", "POST", payload=record, prefer="resolution=merge-duplicates,return=representation")
        self._invalidate_cache("customers")
        return record

    # --- SETTINGS ---
    def get_settings(self) -> Dict[str, Any]:
        db = self.load_local_db()
        return db.get("settings", DEFAULT_DATABASE["settings"])

    def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        db = self.load_local_db()
        current = db.get("settings", DEFAULT_DATABASE["settings"])
        for k, v in new_settings.items():
            if isinstance(v, dict) and isinstance(current.get(k), dict):
                current[k].update(v)
            else:
                current[k] = v
        db["settings"] = current
        self.save_local_db(db)
        return current

    def get_user_lang(self, chat_id: str) -> Optional[str]:
        """Ngôn ngữ đã chọn của user (VI/EN/RU/ZH) hoặc None nếu chưa chọn.

        Ưu tiên bảng Supabase `user_prefs` (tồn tại qua restart Vercel);
        dự phòng file local DATA_DIR/user_prefs.json.
        """
        if self.is_supabase_configured:
            res = self._supabase_request(
                "user_prefs", "GET",
                query_params={"chat_id": f"eq.{chat_id}", "select": "lang"})
            if isinstance(res, list) and res and res[0].get("lang"):
                return str(res[0]["lang"]).upper()
        try:
            prefs_file = os.path.join(DATA_DIR, "user_prefs.json")
            if os.path.exists(prefs_file):
                with open(prefs_file, "r", encoding="utf-8") as f:
                    return json.load(f).get(str(chat_id))
        except Exception:
            pass
        return None

    def set_user_lang(self, chat_id: str, lang: str) -> bool:
        """Lưu ngôn ngữ user chọn. Trả True nếu đã lưu (Supabase hoặc local)."""
        ok = False
        if self.is_supabase_configured:
            res = self._supabase_request(
                "user_prefs", "POST",
                payload=[{"chat_id": str(chat_id), "lang": lang}],
                prefer="resolution=merge-duplicates")
            ok = res is not None
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            prefs_file = os.path.join(DATA_DIR, "user_prefs.json")
            data = {}
            if os.path.exists(prefs_file):
                with open(prefs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[str(chat_id)] = lang
            with open(prefs_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            ok = True
        except Exception as e:
            logger.warning(f"Lưu user_prefs local lỗi: {e}")
        return ok

    def seed_supabase_from_local(self) -> Dict[str, Any]:
        """Đẩy toàn bộ dữ liệu mẫu từ Local lên 4 bảng Supabase."""
        if not self.is_supabase_configured:
            return {"ok": False, "message": "Chưa cấu hình SUPABASE_URL và SUPABASE_KEY."}
        db = self.load_local_db()
        results = {}
        for table in ["products", "pricing", "faqs", "customers"]:
            rows = db.get(table, [])
            res = self._supabase_request(table, "POST", payload=rows)
            results[table] = len(rows) if res is not None else "Lỗi (Kiểm tra đã chạy SQL tạo bảng chưa)"
        return {"ok": True, "seeded": results}


def generate_supabase_sql() -> str:
    """Sinh mã SQL chuẩn để tạo 4 bảng trên Supabase theo Bước 3."""
    sql = """-- ============================================================================
-- BƯỚC 3: THIẾT LẬP SUPABASE - LƯU TRỮ VÀ QUẢN LÝ DỮ LIỆU TẬP TRUNG
-- Chạy script này trong mục SQL Editor của Supabase Dashboard
-- ============================================================================

-- 1. Bảng Sản phẩm (products)
CREATE TABLE IF NOT EXISTS public.products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT,
    category TEXT,
    description TEXT,
    in_stock BOOLEAN DEFAULT TRUE,
    stock_qty INTEGER DEFAULT 100,
    order_url TEXT,
    features JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Bảng giá (pricing)
CREATE TABLE IF NOT EXISTS public.pricing (
    id TEXT PRIMARY KEY,
    product_id TEXT REFERENCES public.products(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    plan TEXT,
    price_vnd TEXT,
    price_usd TEXT,
    price_usdt TEXT,
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Bảng Câu hỏi FAQ đa ngôn ngữ VI / EN / RU (faqs)
CREATE TABLE IF NOT EXISTS public.faqs (
    id TEXT PRIMARY KEY,
    lang TEXT DEFAULT 'VI',
    question TEXT NOT NULL,
    keywords JSONB DEFAULT '[]'::jsonb,
    answer TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Bảng Khách hàng (customers)
CREATE TABLE IF NOT EXISTS public.customers (
    id TEXT PRIMARY KEY,
    telegram_id TEXT UNIQUE NOT NULL,
    username TEXT,
    full_name TEXT,
    language TEXT DEFAULT 'VI',
    interested_in TEXT,
    last_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Bảng ngôn ngữ đã chọn của user (user_prefs) — lưu lựa chọn từ menu
-- ngôn ngữ để bot trả lời đúng ngôn ngữ đó ở mọi lần sau (không bị ghi đè
-- bởi cột language của bảng customers, vốn cập nhật theo từng tin nhắn).
CREATE TABLE IF NOT EXISTS public.user_prefs (
    chat_id TEXT PRIMARY KEY,
    lang TEXT NOT NULL DEFAULT 'VI',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Bảng người dùng bot (bot_users) — bảng quản trị "Người dùng" trên Dashboard:
-- ghi nhận ai đã nhắn/bấm nút (tên, ID, username, ngôn ngữ, lần tương tác).
-- Dùng Supabase thay cho file /tmp để mọi instance Vercel đọc chung một bảng,
-- tránh lỗi bảng lúc ẩn lúc hiện theo từng instance.
CREATE TABLE IF NOT EXISTS public.bot_users (
    chat_id TEXT PRIMARY KEY,
    name TEXT,
    username TEXT,
    lang TEXT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    interactions INTEGER DEFAULT 0
);

-- 7. Bảng ID tin nhắn bot đã gửi (bot_messages) — phục vụ "Xóa nhật ký":
-- bot chỉ xóa được tin do chính nó gửi nên cần lưu lại ID từng tin.
CREATE TABLE IF NOT EXISTS public.bot_messages (
    chat_id TEXT NOT NULL,
    message_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, message_id)
);

-- Bật quyền truy cập cho API (hoặc tùy chỉnh RLS theo nhu cầu)
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pricing ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access products" ON public.products FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access pricing" ON public.pricing FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access faqs" ON public.faqs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access customers" ON public.customers FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE public.bot_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bot_messages ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "Allow all access bot_users" ON public.bot_users FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    CREATE POLICY "Allow all access bot_messages" ON public.bot_messages FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
"""
    try:
        with open(SCHEMA_SQL_FILE, "w", encoding="utf-8") as f:
            f.write(sql)
    except Exception:
        pass
    return sql
