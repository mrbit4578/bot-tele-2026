# 🤖 HỆ THỐNG AUTO TẠO BOT TELEGRAM THEO CẤU TRÚC 9 BƯỚC

Hệ thống tự động hóa trọn gói quy trình khởi tạo, cấu hình, quản trị dữ liệu, triển khai (Deploy) và kiểm thử Bot Telegram AI theo đúng chuẩn **9 Bước**:

| Bước | Tên Bước | Tính năng Tự động hóa trong Tool |
| :--- | :--- | :--- |
| **Bước 1** | **Tạo Bot trên Telegram** | Xác thực `BOT_TOKEN` từ `@BotFather`, tự động cài đặt Menu lệnh (`/start`, `/products`, `/price`, `/pay`, `/faq`, `/ship`, `/lang`, `/support`). |
| **Bước 2** | **Viết Mã Nguồn Python** | Tự động tạo & quản lý 4 file cốt lõi: `main.py` (Flask & xử lý tin nhắn), `faq_engine.py` (Trả lời FAQ & AI), `database.py` (Kết nối dữ liệu), `requirements.txt`. |
| **Bước 3** | **Thiết Lập Supabase** | Quản lý tập trung 4 bảng: **Sản phẩm (`products`)**, **Bảng giá (`pricing`)**, **Câu hỏi FAQ (`faqs`)**, **Khách hàng (`customers`)** kèm `supabase_schema.sql` và Local Database Fallback tự động. |
| **Bước 4** | **Đưa Code Lên GitHub** | Tự động khởi tạo Git (`git init`), tạo Private Repo qua GitHub API, `git add .`, `git commit -m "Cập nhật mã nguồn"`, `git push origin main`. |
| **Bước 5** | **Deploy Bot Lên Render** | Tạo sẵn `render.yaml` (Render Blueprint) & `Procfile`, cấu hình biến môi trường (`BOT_TOKEN`, `CHAT_ID`, `TIMEZONE`) và kiểm tra trạng thái **LIVE**. |
| **Bước 6** | **Kết Nối Telegram Webhook** | Tự động gắn HTTPS Webhook (`setWebhook`) hoặc bật **Chế độ Local Polling** để chạy Bot ngay trên máy tính mà chưa cần server HTTPS. |
| **Bước 7** | **Thiết Lập Bot Tư Vấn AI** | 1. Chọn sản phẩm → 2. Xem bảng giá → 3. Thanh toán (`PayPal`, `USDT`, `QR Code`) → 4. FAQ đa ngôn ngữ (`VI` / `EN` / `RU`). |
| **Bước 8** | **Tích Hợp Bot Vào Nhóm** | Kiểm tra `Group Privacy`, bật **Bộ lọc Keyword & Chống Spam** (chỉ phản hồi câu hỏi phù hợp như phí ship `/ship`, tồn kho; tự động bỏ qua tin nhắn tán gẫu trong nhóm). |
| **Bước 9** | **Kiểm Tra Bot & Sửa Lỗi** | Tích hợp **Máy Giả Lập Chat Telegram (Simulator)**, kiểm tra `/start`, kiểm tra JSON `getWebhookInfo`, đối chiếu FAQ & bảng giá, xem Render Logs trực tiếp. |

---

## 🚀 Cách Khởi Chạy Nhanh (1-Click)

1. Nhấp đúp vào file **[`CHAY_HE_THONG_9_BUOC.bat`](CHAY_HE_THONG_9_BUOC.bat)**
2. Hoặc chạy lệnh trong Terminal:
   ```bash
   python main.py
   ```
3. Mở trình duyệt truy cập: **`http://127.0.0.1:5000/dashboard`**

---

## ☁️ Deploy Online Trên Vercel (khuyên dùng từ 2026-10-24)

1. Đẩy code lên GitHub (repo `bot-tele-2026`) → vào [vercel.com](https://vercel.com) → **Add New Project** → chọn repo → **Import** (không cần chỉnh Build Settings, Vercel tự nhận `api/index.py` + `vercel.json`).
2. Trong **Project Settings → Environment Variables**, đặt tối thiểu:
   - `BOT_TOKEN` — token từ @BotFather
   - `ADMIN_KEY` — tự đặt một chuỗi bí mật (khóa mở Dashboard online; **bắt buộc**, thiếu là toàn bộ `/api/*` bị chặn 401)
   - `SUPABASE_URL`, `SUPABASE_KEY` — để dữ liệu bền vững (không có Supabase, dữ liệu local trên Vercel nằm ở `/tmp` và mất khi instance tái chế)
   - `CHAT_ID`, `TIMEZONE=Asia/Ho_Chi_Minh`, `GEMINI_API_KEY` (tùy chọn), `TELEGRAM_WEBHOOK_SECRET` (tùy chọn, tăng bảo mật webhook)
3. **Deploy** → mở URL Vercel → vào `/dashboard`, nhập `ADMIN_KEY` khi được hỏi.
4. Sang **Bước 6** → đặt Webhook URL = `https://<ten-du-an>.vercel.app/webhook` → **Set Webhook**. Xong — bot trả lời 24/7 qua Webhook.
   - *Local Polling không chạy trên Vercel* (serverless không có tiến trình nền) — Polling chỉ dùng khi chạy `python main.py` trên máy nhà.
   - *Bước 4 (git push tự động) cũng chỉ chạy local* — trên Vercel, code deploy tự động từ GitHub.

### Khác biệt đã xử lý khi đưa lên Vercel

| Vấn đề bản gốc | Cách xử lý |
| :--- | :--- |
| Local DB ghi file trong thư mục project (Vercel chỉ-đọc) | Tự chuyển sang `/tmp` khi có biến `VERCEL`; ưu tiên Supabase làm nơi lưu bền |
| `/api/state` trả token/key dạng rõ cho bất kỳ ai mở trang | Token/key được che (chỉ hiện 4 ký tự cuối) + toàn bộ `/api/*` khóa bằng `ADMIN_KEY` |
| Giá trị đã che bị lưu đè lên token thật khi bấm Lưu ở Dashboard | Server tự bỏ qua mọi giá trị chứa ký tự che `•` khi lưu cấu hình |
| Bot xử lý 1 tin nhắn gọi Supabase ~10 lần | Thêm cache đọc Supabase TTL 20 giây trong `database.py` |
| Upsert lên Supabase bằng POST thường (trùng khóa chính bị lỗi 409) | Dùng `Prefer: resolution=merge-duplicates` đúng ngữ nghĩa upsert |
| Webhook ai cũng gọi giả mạo được | Hỗ trợ `TELEGRAM_WEBHOOK_SECRET` (header `X-Telegram-Bot-Api-Secret-Token`) |
| Log khởi động báo "đã kết nối/đang chạy" dù chưa cấu hình | Log khởi động trung thực theo trạng thái thật |
| GitHub token ở Bước 4 có thể lộ qua log lệnh git | Tự che token trong mọi log trả về của Bước 4 |

## ⚠️ An toàn thông tin

- **Không bao giờ commit file `.env`** (đã có trong `.gitignore`). File zip dự án từng chứa `BOT_TOKEN` và `GEMINI_API_KEY` dạng thật — nếu đã từng gửi zip/file đó cho người khác, hãy thu hồi token bot qua @BotFather (`/revoke`) và tạo khóa Gemini mới.
- Dùng `SUPABASE_KEY` loại **service_role** chỉ ở phía server (biến môi trường), không dán vào code/HTML phía trình duyệt.
