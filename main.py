import os
import discord
from openai import OpenAI

# 1. Cấu hình GitHub AI Key
GITHUB_TOKEN = "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"

# 2. Cấu hình Discord Bot Token (Dán token Discord bạn lấy ở bước trước vào đây)
DISCORD_TOKEN = "DÁN_DISCORD_BOT_TOKEN_CỦA_BẠN_VÀO_ĐÂY"

# Khởi tạo OpenAI Client
ai_client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

# Cấu hình Discord Client
intents = discord.Intents.default()
intents.message_content = True
bot_client = discord.Client(intents=intents)

@bot_client.event
async def on_ready():
    print(f'Bot đã đăng nhập thành công với tên: {bot_client.user}')

@bot_client.event
async def on_message(message):
    # Bỏ qua tin nhắn do chính bot gửi
    if message.author == bot_client.user:
        return

    # Chỉ trả lời khi có người nhắn tin hoặc tag bot
    # Trả lời tin nhắn
    async with message.channel.typing():
        try:
            response = ai_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Bạn là bot Discord cực bựa, hài hước và xì teen."},
                    {"role": "user", "content": message.content},
                ],
                model="gpt-4o",
                temperature=0.8,
            )
            bot_reply = response.choices[0].message.content
            await message.channel.send(bot_reply)
        except Exception as e:
            await message.channel.send(f"Lỗi rồi ông ơi: {e}")

# Chạy bot
bot_client.run(DISCORD_TOKEN)
