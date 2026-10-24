# HƯỚNG DẪN TẠO BOT TELEGRAM MỚI THEO HỆ THỐNG 9 BƯỚC

Tài liệu này đúc kết từ lần dựng bot `@Nexuspilot90_bot` (chạy live tại https://bot-tele-2026.vercel.app ngày 24/10/2026). Cứ làm đúng thứ tự dưới đây là tạo được một bot mới hoàn chỉnh: có Dashboard quản trị, dữ liệu Supabase, chạy 24/7 trên Vercel miễn phí.

Mã nguồn mẫu: https://github.com/mrbit4578/bot-tele-2026

---

## PHẦN 0 — CHUẨN BỊ (làm 1 lần, dùng mãi)

Cần 4 tài khoản miễn phí:

1. **Telegram** — để tạo bot qua @BotFather.
2. **GitHub** — để chứa mã nguồn.
3. **Vercel** — để chạy bot online (đăng nhập bằng GitHub cho nhanh).
4. **Supabase** — để lưu dữ liệu bền vững (đăng nhập bằng GitHub).

Khái niệm cần nắm trước khi bắt đầu:

- **BOT_TOKEN**: "chìa khóa" của bot do @BotFather cấp, dạng `1234567890:AAH7bX...`. Ai có token là điều khiển được bot — **tuyệt đối không gửi token qua chat, không chụp màn hình chứa token, không đưa vào code**.
- **ADMIN_KEY**: mật khẩu mở Dashboard do **bạn tự nghĩ ra** (ví dụ một chuỗi chữ + số dài 12 ký tự trở lên). Mỗi bot một khóa riêng, ghi lại vào nơi lưu mật khẩu của bạn.
- **Webhook**: cách Telegram "đẩy" tin nhắn của khách về server của bạn qua một địa chỉ HTTPS. Bot online trên Vercel **chỉ chạy bằng webhook** (không dùng Polling — Polling chỉ để test trên máy nhà).

---

## PHẦN A — TẠO BOT MỚI (khoảng 20 phút)

### Bước A1. Tạo bot trên Telegram

1. Mở Telegram, tìm **@BotFather** (có tích xanh), bấm Start.
2. Gõ `/newbot`.
3. Nhập **tên hiển thị** của bot (ví dụ: `Shop Giày MrBit Bot`).
4. Nhập **username** cho bot: phải kết thúc bằng `bot` (ví dụ: `mrbit_shop_bot`). Nếu bị báo trùng, đổi tên khác.
5. BotFather trả về **BOT_TOKEN** — copy và lưu ngay vào nơi an toàn. **Không chụp màn hình có token.**

### Bước A2. Lấy mã nguồn về repo GitHub mới

Cách dễ nhất: dùng lại nguyên bộ mã nguồn mẫu.

1. Vào repo mẫu: https://github.com/mrbit4578/bot-tele-2026
2. Bấm **Use this template** (hoặc **Fork**) → đặt tên repo mới (ví dụ: `bot-shop-giay`) → Create.
   Nếu không thấy nút template: bấm **Code → Download ZIP**, rồi tạo repo mới trống trên GitHub và upload các file lên (giữ nguyên cấu trúc thư mục).
3. Kiểm tra repo mới có đủ: `main.py`, `database.py`, `faq_engine.py`, `requirements.txt`, `api/index.py`, `vercel.json`, thư mục `templates/`, thư mục `data/`, file `supabase_schema.sql`.
   **Không bao giờ upload file `.env` lên GitHub.**

### Bước A3. Tạo project Supabase và chạy SQL tạo 4 bảng

1. Vào https://supabase.com → **New project** → đặt tên (ví dụ: `bot-shop-giay`), đặt mật khẩu database và lưu lại, chọn region **Singapore** cho gần Việt Nam → Create.
2. Chờ project khởi tạo xong (1–2 phút), vào mục **SQL Editor** (menu trái) → **New query**.
3. Mở file `supabase_schema.sql` trong repo của bạn, copy **toàn bộ** nội dung, dán vào ô SQL → bấm **Run**. Thấy báo thành công là 4 bảng `products`, `pricing`, `faqs`, `customers` đã được tạo.
4. Lấy 2 thông tin để dành cho Bước A4:
   - **SUPABASE_URL**: chính là `https://<mã-project>.supabase.co` (mã project nằm trong địa chỉ trang Supabase của bạn, hoặc xem ở Settings → General).
   - **SUPABASE_KEY**: vào **Settings → API Keys** → tab **Legacy anon, service_role API keys** → hàng **service_role** → bấm **Reveal** rồi copy.
     Không dùng khóa `anon` (khóa yếu, dành cho trình duyệt) và không dùng khóa ở tab Publishable/Secret (định dạng mới, hệ thống này chưa dùng).

### Bước A4. Deploy lên Vercel và đặt biến môi trường

1. Vào https://vercel.com → **Add New → Project** → chọn repo GitHub vừa tạo → **Import**. Không cần chỉnh Build Settings (Vercel tự nhận `api/index.py` và `vercel.json`) → bấm **Deploy**, chờ báo **Ready**.
2. Vào project trên Vercel → **Settings → Environment Variables** → thêm lần lượt các biến sau, môi trường **Production**:

| Tên biến | Giá trị điền |
| :--- | :--- |
| `BOT_TOKEN` | Token lấy ở Bước A1 |
| `ADMIN_KEY` | Chuỗi bí mật bạn tự đặt (khóa mở Dashboard) |
| `SUPABASE_URL` | Địa chỉ project Supabase ở Bước A3 |
| `SUPABASE_KEY` | Khóa **service_role** ở Bước A3 |
| `TIMEZONE` | `Asia/Ho_Chi_Minh` |
| `CHAT_ID` | Không bắt buộc — chỉ cần nếu muốn nhận tin test gửi thật từ Bước 9 (lấy ID của bạn qua bot @userinfobot) |
| `GEMINI_API_KEY` | Không bắt buộc — có thì bot trả lời được cả câu hỏi ngoài danh sách FAQ |
| `TELEGRAM_WEBHOOK_SECRET` | Không bắt buộc — một chuỗi bí mật tự đặt để tăng bảo mật webhook |

3. Sau khi thêm biến, bắt buộc **Redeploy** để biến có hiệu lực: thẻ **Deployments** → dấu **⋯** ở bản mới nhất → **Redeploy**.

### Bước A5. Mở Dashboard và kiểm tra Bước 1 + Bước 3

1. Mở `https://<tên-project>.vercel.app/dashboard` → trình duyệt hỏi **ADMIN_KEY** → nhập đúng khóa bạn đặt ở Bước A4.
2. Vào **Bước 1**: các ô token đã được điền sẵn dạng che (chỉ thấy 4 ký tự cuối) là bình thường. Bấm **Xác thực / Kết nối** → thấy báo "Kết nối thành công với Bot @username_của_bạn" là đạt. (Giá trị đang che không bao giờ ghi đè lên khóa thật — hệ thống đã chặn sẵn.)
3. Vào **Bước 3**: ô SUPABASE_URL đã có địa chỉ, khóa hiện dạng che. Bấm **Lưu & Kiểm Tra Kết Nối** → đạt khi hiện **"Kết nối Supabase thành công!"**.
   - Nếu báo **lỗi 404 / chưa tạo bảng**: bạn chưa chạy SQL ở Bước A3 — quay lại chạy SQL, xong quay lại đây bấm **Đẩy Dữ Liệu Mẫu Lên Supabase (Auto-Seed)** để nạp dữ liệu mẫu.

### Bước A6. Gắn Webhook ở Bước 6 (bước quyết định bot sống hay không)

1. Trong Dashboard, vào **Bước 6**.
2. Ô Webhook URL điền: `https://<tên-project>.vercel.app/webhook`
3. Bấm **Set Webhook** → đạt khi kết quả `getWebhookInfo` hiện đúng URL đó và `pending_update_count` bằng 0.
4. Mở Telegram, nhắn cho bot: `/start`. Bot trả lời kèm menu nút bấm là **hoàn thành**. Thử tiếp: "phí giao hàng bao nhiêu?" và bấm các nút FAQ / Bảng giá / Thanh toán.

---

## PHẦN B — THAY NỘI DUNG THÀNH CỦA SHOP BẠN

Bot mẫu đang chứa dữ liệu demo (Sản phẩm A/B/C, shop.example.com...). Thay bằng nội dung thật theo 1 trong 2 cách:

**Cách 1 — sửa ngay trên Dashboard (nhanh, không cần code):**
- Bước 3: thêm sản phẩm, bảng giá, câu FAQ mới bằng các ô nhập sẵn có.
- Bước 7: điền tên shop, link website, username tư vấn viên, thông tin thanh toán thật (email PayPal, địa chỉ ví USDT + mạng lưới, thông tin QR ngân hàng), phí ship nội thành / tỉnh.
- Bước 8: chỉnh danh sách từ khóa kích hoạt và từ khóa bỏ qua cho nhóm.

**Cách 2 — sửa file dữ liệu trong repo (sạch cho lâu dài):**
- Mở file `data/bot_database.json` trong repo, sửa các mục `products`, `pricing`, `faqs`, `settings` (đặc biệt: `shop_url`, `support_username`, `payment.usdt_address`, `payment.bank_qr_info` — **đây là thông tin nhận tiền, phải thay bằng của bạn**, dữ liệu mẫu đang là ví dụ).
- Commit + push lên GitHub → Vercel tự deploy lại. Sau đó vào Dashboard Bước 3 bấm **Auto-Seed** để đẩy nội dung mới lên Supabase.

**Thêm ngôn ngữ FAQ:** hiện có sẵn VI / EN / RU. Muốn bot trả lời đúng câu hỏi của khách, hãy bổ sung FAQ theo đúng từ khóa khách hay gõ (mục `keywords` trong từng câu FAQ).

---

## PHẦN C — ĐƯA BOT VÀO NHÓM TELEGRAM

1. Chat với @BotFather → `/mybots` → chọn bot → **Bot Settings → Group Privacy → Turn off**. (Không tắt thì bot không đọc được tin nhắn trong nhóm, chỉ thấy lệnh `/`.)
2. Thêm bot vào nhóm của bạn. Nếu muốn bot xóa được tin rác của người khác, cấp quyền **Admin** cho bot trong nhóm.
3. Trong Dashboard **Bước 8**: bật lọc từ khóa và chống spam, chỉnh thời gian chờ (mặc định 5 giây) và số tin tối đa mỗi phút (mặc định 6).
4. Test trong nhóm: nhắn "shop ơi, phí giao hàng bao nhiêu?" → bot trả lời. Nhắn câu tán gẫu (ví dụ "đi cà phê không?") → bot im lặng là đúng.

---

## PHẦN D — VẬN HÀNH VÀ XỬ LÝ LỖI THƯỜNG GẶP

| Hiện tượng | Nguyên nhân | Cách xử lý |
| :--- | :--- | :--- |
| Mở Dashboard bị báo 401 "Thiếu hoặc sai ADMIN_KEY" | Chưa đặt biến `ADMIN_KEY`, hoặc nhập sai, hoặc chưa Redeploy sau khi đặt | Đặt biến ở Vercel Settings → Redeploy → nhập lại đúng khóa |
| Trang hiện câu "Hãy đặt biến ADMIN_KEY..." | Biến chưa có trên môi trường Production | Kiểm tra biến có tick đúng **Production** chưa, rồi Redeploy |
| Bước 3 báo lỗi 404 khi đọc bảng | Chưa chạy SQL tạo bảng trên Supabase | Chạy file `supabase_schema.sql` ở SQL Editor (Bước A3), rồi Auto-Seed |
| Bước 3 báo "Local Fallback" | URL hoặc khóa Supabase sai | Đối chiếu lại `SUPABASE_URL` và khóa **service_role** ở tab Legacy |
| Bot không trả lời tin nhắn | Chưa gắn webhook, hoặc webhook trỏ sai địa chỉ, hoặc đang bật Polling ở máy nhà | Vào Bước 6 kiểm tra `getWebhookInfo` — URL phải là `https://<project>.vercel.app/webhook`; nếu từng bật Polling local thì tắt đi rồi Set Webhook lại |
| Bot trả lời nhưng nội dung là dữ liệu mẫu | Chưa thay dữ liệu | Làm theo Phần B rồi Auto-Seed lại |
| Nghi ngờ lộ BOT_TOKEN | Token từng bị chụp màn hình / gửi qua chat | Vào @BotFather → `/revoke` → chọn bot → nhận token mới → cập nhật biến `BOT_TOKEN` trên Vercel → Redeploy → Set Webhook lại ở Bước 6 |
| Muốn đổi ADMIN_KEY | Đổi biến trên Vercel | Settings → Environment Variables → sửa `ADMIN_KEY` → Redeploy |

**Xem log khi có lỗi lạ:** Vercel → project → **Logs** (hoặc Deployments → bản deploy → Runtime Logs). Dashboard Bước 9 cũng có nút chẩn đoán 4 nhóm lỗi và trình giả lập chat để test mà không cần mở Telegram.

---

## PHẦN E — CHECKLIST TRƯỚC KHI COI LÀ XONG

- [ ] `getWebhookInfo` hiện đúng URL webhook, `pending_update_count` = 0
- [ ] Nhắn `/start` cho bot trên Telegram, bot trả lời kèm menu
- [ ] Hỏi thử 1 câu FAQ bằng tiếng Việt và 1 câu tiếng Anh, bot trả lời đúng
- [ ] Bước 3 hiện "Kết nối Supabase thành công", dữ liệu là của shop thật (không còn shop.example.com)
- [ ] Thông tin thanh toán ở Bước 7 là **của bạn** (PayPal / ví USDT / QR ngân hàng)
- [ ] Đã tắt Group Privacy nếu dùng bot trong nhóm, test bot trả lời đúng chủ đề và im lặng trước tin tán gẫu
- [ ] File `.env` **không** có trong repo GitHub; BOT_TOKEN và service_role key không xuất hiện trong bất kỳ ảnh chụp hay đoạn chat nào
- [ ] Đã lưu ADMIN_KEY và BOT_TOKEN vào nơi lưu mật khẩu của bạn

---

## GHI CHÚ KỸ THUẬT (để hiểu hệ thống, không bắt buộc đọc)

- Kiến trúc: Flask app (`main.py` + `faq_engine.py` + `database.py`) chạy serverless trên Vercel qua `api/index.py` và rewrite trong `vercel.json`. Mọi request bị rewrite về `/api/index/<đường-gốc>` nên `main.py` có sẵn WSGI middleware cắt tiền tố này khỏi `PATH_INFO` — **đừng xóa middleware đó**, xóa là toàn bộ trang 404.
- Trên Vercel, hệ thống tập tin chỉ ghi được vào `/tmp` (mất khi instance tái chế) nên dữ liệu bền vững phải nằm ở Supabase. Local DB JSON chỉ là tầng dự phòng.
- Toàn bộ `/api/*` của Dashboard được khóa bằng `ADMIN_KEY` (header `X-Admin-Key`), và `/api/state` luôn che token/key chỉ còn 4 ký tự cuối trước khi gửi ra trình duyệt.
- Muốn chạy thử trên máy nhà: `python main.py` rồi mở `http://127.0.0.1:5000/dashboard`, bật **Local Polling** ở Bước 6. Khi đã gắn webhook online thì không bật Polling nữa (hai chế độ xung đột nhau).
- Muốn đổi nhà cung cấp: bộ mã nguồn có sẵn `render.yaml` và `Procfile` để deploy lên Render với cùng bộ biến môi trường.
