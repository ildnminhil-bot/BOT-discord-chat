import os
import threading
import discord
from flask import Flask
from openai import OpenAI
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

# Web server giả để Render không tắt bot
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot đang sống!"

def run_web():
    web_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = threading.Thread(target=run_web, daemon=True)
    t.start()

# ==================== CONVERSATION MANAGER ====================
class ConversationManager:
    """Quản lý lịch sử chat tiết kiệm RAM"""
    def __init__(self, max_messages=15, max_age_minutes=60):
        self.conversations = defaultdict(list)
        self.max_messages = max_messages  # Giới hạn message mỗi cuộc chat
        self.max_age_minutes = max_age_minutes  # Xóa tin cũ hơn 60 phút
    
    def add_message(self, channel_id: int, role: str, content: str):
        """Thêm message vào lịch sử"""
        self.conversations[channel_id].append({
            "role": role,
            "content": content[:500],  # Giới hạn 500 chars mỗi message
            "timestamp": datetime.now()
        })
        
        # Xóa message cũ
        self._cleanup(channel_id)
    
    def _cleanup(self, channel_id: int):
        """Xóa message cũ và giới hạn số lượng"""
        now = datetime.now()
        cutoff_time = now - timedelta(minutes=self.max_age_minutes)
        
        # Xóa message cũ hơn cutoff_time
        self.conversations[channel_id] = [
            msg for msg in self.conversations[channel_id]
            if msg["timestamp"] > cutoff_time
        ]
        
        # Giữ chỉ max_messages message gần nhất
        if len(self.conversations[channel_id]) > self.max_messages:
            self.conversations[channel_id] = self.conversations[channel_id][-self.max_messages:]
    
    def get_history(self, channel_id: int) -> list:
        """Lấy lịch sử chat (không kể timestamp)"""
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversations[channel_id]
        ]
    
    def clear_old_conversations(self):
        """Xóa các cuộc chat không còn sử dụng"""
        to_delete = []
        for channel_id, messages in self.conversations.items():
            if messages and (datetime.now() - messages[-1]["timestamp"]).total_seconds() > 3600:
                to_delete.append(channel_id)
        
        for channel_id in to_delete:
            del self.conversations[channel_id]

# ==================== GITHUB AI CLIENT ====================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

ai_client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=GITHUB_TOKEN,
)

# ==================== DISCORD BOT ====================
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# Khởi tạo conversation manager
conv_manager = ConversationManager(max_messages=15, max_age_minutes=60)

SYSTEM_PROMPT = """Bạn là một trợ lý AI vui vẻ, thông minh và rất hữu ích trên Discord.
- Trả lời ngắn gọn, dễ hiểu (tối đa 2000 characters)
- Dùng emoji thích hợp
- Có tính cách vui tính, thân thiện
- Nếu bị tag (@), bắt đầu bằng "Hey!" để chỉ ra bạn nhận thấy
- Nhớ context cuộc trò chuyện trước để trả lời logic hơn"""

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} đã đăng nhập!')
    
    # Cleanup lịch sử cũ mỗi 30 phút
    async def cleanup_task():
        while True:
            await asyncio.sleep(1800)  # 30 phút
            conv_manager.clear_old_conversations()
            print("🧹 Dọn dẹp lịch sử chat cũ")
    
    bot.loop.create_task(cleanup_task())

@bot.event
async def on_message(message):
    # Bỏ qua tin nhắn của bot
    if message.author == bot.user:
        return
    
    # Kiểm tra bot có được tag hay không
    is_mentioned = bot.user in message.mentions
    
    # Chỉ trả lời nếu:
    # 1. Có tag bot
    # 2. Hoặc trả lời message của bot
    # 3. Hoặc là DM
    if not (is_mentioned or (message.reference and await check_reply_to_bot(message)) or isinstance(message.channel, discord.DMChannel)):
        return
    
    # Xóa mention từ content nếu có
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()
    
    if not content:
        await message.reply("Bạn gọi mình nhưng không hỏi gì cả 😅")
        return
    
    async with message.channel.typing():
        try:
            # Thêm message của user vào lịch sử
            conv_manager.add_message(message.channel.id, "user", content)
            
            # Lấy lịch sử cuộc trò chuyện
            history = conv_manager.get_history(message.channel.id)
            
            # Gọi AI API
            response = ai_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *history,  # Thêm lịch sử
                ],
                model="gpt-4o",
                temperature=0.8,
                max_tokens=800,  # Giới hạn output
            )
            
            bot_reply = response.choices[0].message.content
            
            # Thêm reply của bot vào lịch sử
            conv_manager.add_message(message.channel.id, "assistant", bot_reply)
            
            # Chia nhỏ message nếu quá dài
            if len(bot_reply) > 2000:
                chunks = [bot_reply[i:i+2000] for i in range(0, len(bot_reply), 2000)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await message.reply(chunk, mention_author=False)
                    else:
                        await message.channel.send(chunk)
            else:
                await message.reply(bot_reply, mention_author=False)
                
        except Exception as e:
            error_msg = str(e)
            if "API" in error_msg or "quota" in error_msg.lower():
                await message.reply("⚠️ API đang bận, thử lại lát nữa!")
            else:
                await message.reply(f"❌ Lỗi: {error_msg[:100]}")

async def check_reply_to_bot(message):
    """Kiểm tra message có phải reply cho bot không"""
    if message.reference:
        try:
            replied_to = await message.channel.fetch_message(message.reference.message_id)
            return replied_to.author == bot.user
        except:
            return False
    return False

# ==================== START BOT ====================
keep_alive()
print("🚀 Khởi động bot...")
bot.run(DISCORD_TOKEN)

