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

-- Bật quyền truy cập cho API (hoặc tùy chỉnh RLS theo nhu cầu)
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pricing ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access products" ON public.products FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access pricing" ON public.pricing FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access faqs" ON public.faqs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access customers" ON public.customers FOR ALL USING (true) WITH CHECK (true);
