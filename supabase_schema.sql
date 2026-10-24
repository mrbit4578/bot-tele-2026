-- ============================================================================
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
