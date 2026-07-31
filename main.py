import os
import threading
import discord
from flask import Flask
from openai import OpenAI
from collections import defaultdict, deque
# ==========================================
# 1. WEB SERVER GIỮ BOT SỐNG (DÀNH CHO RENDER/RAILWAY)
# ==========================================
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot đang sống!"

def run_web():
    web_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()

# ==========================================
# 2. CẤU HÌNH TOKEN VÀ CLIENT
# ==========================================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Đã cập nhật Endpoint mới của GitHub để tránh lỗi 410
ai_client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

# Bật intents để bot lấy được thông tin Server/Thành viên
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot_client = discord.Client(intents=intents)

# ==========================================
# 3. QUẢN LÝ BỘ NHỚ SIÊU NHẸ (CHỐNG TRÀN RAM)
# ==========================================
chat_history = defaultdict(lambda: deque(maxlen=10))

@bot_client.event
async def on_ready():
    print(f'Bot đã đăng nhập thành công với tên: {bot_client.user}')

@bot_client.event
async def on_message(message):
    # Bỏ qua tin nhắn do chính bot gửi
    if message.author == bot_client.user:
        return

    # Chỉ phản hồi khi được tag HOẶC chat trong mục DM (nhắn tin riêng)
    if bot_client.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        
        # Lọc bỏ phần tag bot khỏi câu hỏi
        user_text = message.content.replace(f'<@{bot_client.user.id}>', '').strip()
        
        # --- TÍNH NĂNG 1: LỆNH "!RESET" GIẢI PHÓNG RAM ---
        if user_text.lower() == "!reset":
            chat_history[message.channel.id].clear()
            return await message.reply("🧹 Bíp bíp! Đã xóa sạch trí nhớ cuộc trò chuyện này. RAM trống trơn!")

        # --- TÍNH NĂNG 2: THẢ EMOJI "ĐANG SUY NGHĨ" ---
        try:
            await message.add_reaction("⏳")
        except:
            pass # Bỏ qua nếu bot chưa có quyền thả reaction

        # --- TÍNH NĂNG 3: ĐỌC ẢNH & ĐỌC FILE TÀI LIỆU ---
        image_urls = []
        text_files_content = ""

        for attachment in message.attachments:
            # Lọc ảnh (Vision)
            if attachment.content_type and attachment.content_type.startswith('image/'):
                image_urls.append(attachment.url)
            
            # Lọc file văn bản/code, giới hạn dung lượng và số chữ
            elif attachment.size < 1000000 and attachment.filename.endswith(('.txt', '.py', '.json', '.html', '.md', '.csv', '.js', '.cpp')):
                try:
                    file_bytes = await attachment.read()
                    text_files_content += f"\n\n--- Nội dung file {attachment.filename} ---\n"
                    text_files_content += file_bytes.decode('utf-8', errors='ignore')[:3000]
                except Exception as e:
                    print(f"Không thể đọc file: {e}")

        # Gắn text từ file vào cuối lời nhắn
        final_prompt = user_text + text_files_content
        if not final_prompt.strip():
            final_prompt = "Hãy phân tích bức ảnh này giúp tôi." if image_urls else "Chào bạn"

        # Định dạng dữ liệu cho API
        if image_urls:
            api_content = [{"type": "text", "text": final_prompt}]
            for img_url in image_urls:
                api_content.append({"type": "image_url", "image_url": {"url": img_url}})
        else:
            api_content = final_prompt

        # Thêm câu hỏi vào bộ nhớ (Deque)
        chat_history[message.channel.id].append({"role": "user", "content": api_content})

        # --- TẠO NGỮ CẢNH SERVER ---
        server_info = ""
        if message.guild:
            server_info = (f"Bạn đang ở trong server Discord tên '{message.guild.name}'. "
                           f"Server có {message.guild.member_count} thành viên. ")

        system_prompt = f"""Bạn là một trợ lý AI thông minh trên Discord, phong cách giống ChatGPT.
        - {server_info}
        - Người chat: '{message.author.display_name}' (ID: {message.author.id}). Để tag, dùng cú pháp <@{message.author.id}>.
        - Trình bày mã nguồn (code) và văn bản rõ ràng bằng Markdown.
        - Bạn có thể đọc ảnh và file code người dùng gửi.
        """

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(list(chat_history[message.channel.id]))

        async with message.channel.typing():
            try:
                response = ai_client.chat.completions.create(
                    messages=messages,
                    model="gpt-4o",
                    temperature=0.7,
                )
                
                bot_reply = response.choices[0].message.content
                chat_history[message.channel.id].append({"role": "assistant", "content": bot_reply})
                
                # Cắt nhỏ tin nhắn nếu dài hơn 2000 ký tự
                if len(bot_reply) > 2000:
                    for i in range(0, len(bot_reply), 2000):
                        await message.channel.send(bot_reply[i:i+2000])
                else:
                    await message.reply(bot_reply)

                # --- HOÀN TẤT: XÓA ⏳ VÀ THAY BẰNG ✅ ---
                try:
                    await message.remove_reaction("⏳", bot_client.user)
                    await message.add_reaction("✅")
                except:
                    pass

            except Exception as e:
                await message.channel.send(f"Lỗi hệ thống rồi ông ơi: {e}")
                # Nếu lỗi, đổi reaction thành dấu ❌
                try:
                    await message.remove_reaction("⏳", bot_client.user)
                    await message.add_reaction("❌")
                except:
                    pass

# ==========================================
# 4. CHẠY BOT
# ==========================================
keep_alive()
bot_client.run(DISCORD_TOKEN)
