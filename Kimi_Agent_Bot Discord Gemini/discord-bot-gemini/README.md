# 🤖 Discord Bot AI (Gemini) v5.0.0

Bot Discord dùng **Google Gemini** làm não, nâng cấp từ code gốc (v4.4.0). Bot chat **thân thiện, vui vẻ, hơi chế diễu** một chút cho vui 😏 — đồng thời ngắn có bộ **quản lý server** khá tay: lọc từ chửi bậy tự động, hệ thống cảnh báo, mute/kick/ban, nhắc nhở, và một đống lệnh giải trí.

## ✨ Tính năng chính

### 💬 Chat AI (Gemini)
- Trả lời ngắn khi được **@mention**, khi **nhắn DM**, hoặc khi bật `/chaton` trong kênh
- **Nhớ 12 tin nhắn gần nhất** của từng người trong từng kênh → trả lời ngắn đúng ngữ cảnh
- Đọc được **ảnh** (mô tả, giải đề, OCR sơ bộ) và **file text/code**
- Đổi ngôn ngữ (`/language`), đổi tính cách (`/persona`), xem bot nhớ gì (`/history`)
- Trả lời ngắn dài tự động **chia tin** để không bị lỗi 2000 ký tự

### 🛡️ Quản lý server
- **Tự động xóa** tin nhắn có từ chửi bậy (Việt + Anh, có dấu + không dấu) và cảnh cáo người gửi
- **Hệ thống warn**: `/warn` `/warns` `/clearwarns` — đủ **3 lần tự động mute 10 phút**
- `/mute` `/unmute` `/kick` `/ban` `/unban` `/purge` `/slowmode`
- **Nhắn riêng (DM)** cho thành viên bằng `/dm`
- **Nhật ký mod** (`/setmodlog`): mọi hành động quản lý đều được ghi lại

### ⏰ Nhắc nhở
- `/remind 10m uống nước` — bot sẽ nhắc trong kênh hoặc **qua DM**
- `/remindlist`, `/remindcancel`

### 🎲 Giải trí
- `/8ball` `/coinflip` `/dice` `/roast` (xin bị cà khịa) `/compliment` `/poll` `/say`

### ℹ️ Thông tin
- `/ping` `/uptime` `/stats` `/serverinfo` `/userinfo` `/avatar` `/help`

## 🚀 Cài đặt & chạy

### 1. Lấy Discord Token
1. Vào [Discord Developer Portal](https://discord.com/developers/applications) → New Application
2. **Bot → Add Bot** → copy **Token**
3. Bật các **Privileged Gateway Intents**: `MESSAGE CONTENT INTENT`, `SERVER MEMBERS INTENT`
4. OAuth2 → URL Generator: scope `bot` + `applications.commands`, quyền gợi ý: *Send Messages, Manage Messages, Moderate Members, Kick, Ban, Read Message History, Embed Links, Add Reactions, View Channels*

### 2. Lấy Gemini API Key
Vào [Google AI Studio](https://aistudio.google.com/apikey) → tạo API key.

### 3. Deploy lên Render
1. Push code này lên **GitHub**
2. Render → **New → Blueprint** → chọn repo (file `render.yaml` tự tạo service)
3. Vào **Environment Variables** điền:
   | Key | Giá trị |
   |---|---|
   | `DISCORD_TOKEN` | token bước 1 |
   | `GEMINI_API_KEY` | key bước 2 |
   | `OWNER_IDS` | Discord ID của bạn (bật Developer Mode, chuột phải avatar → Copy ID) |
   | `GEMINI_MODEL` | `gemini-2.5-flash` (mặc định) |
4. Deploy → mở log xem dòng `[READY] Dang nhap thanh cong`

> Render free ngủ sau 15 phút không traffic → bot offline. Cách khắc phục: dùng UptimeRobot ping endpoint `/` mỗi 5 phút, hoặc nâng gói paid.

### Chạy local
```bash
pip install -r requirements.txt
cp .env.example .env   # điền token
# (cài python-dotenv nếu muốn nạp .env tự động, hoặc export biến môi trường)
python main.py
```

## 📁 Cấu trúc
```
├── main.py            # Khoi dong bot + web server (health check cho Render)
├── config.py          # Cau hinh tap trung (lay tu env)
├── cogs/
│   ├── ai_chat.py     # Chat AI, bo nho, doc anh/file
│   ├── moderation.py  # Loc tu cam, warn, mute, kick, ban, DM, modlog
│   ├── reminders.py   # Nhac nho hen gio
│   ├── fun.py         # Mini-games, poll, roast
│   └── utility.py     # Thong tin + /help
├── requirements.txt
├── render.yaml
└── .env.example
```

## ⚠️ Lưu ý
- Bộ nhớ chat & warn lưu **trong RAM** → mất khi bot restart (giới hạn gói Render free). Muốn lâu dài thì nối thêm SQLite/PostgreSQL.
- Danh sách từ cấm ở `cogs/moderation.py` (`BAD_WORDS`) — tự thêm/bớt tuỳ server.
- Bot phải có **role cao hơn** người bị mute/ban thì mới thao tác được.
