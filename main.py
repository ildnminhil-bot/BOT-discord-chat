import os
import base64
import threading
import time
import json
import io
from collections import defaultdict, deque
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from openai import OpenAI

# ==========================================
# 1. WEB SERVER GIỮ BOT SỐNG
# ==========================================
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot đang sống!"

def run_web():
    web_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    threading.Thread(target=run_web, daemon=True).start()

# ==========================================
# 2. CẤU HÌNH TOKEN + CLIENT
# ==========================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

gemini_client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

PROVIDERS = {
    "gemini": {
        "client": gemini_client,
        "text_model": "gemini-3.5-flash",
        "vision_model": "gemini-3.5-flash",
        "version": "Gemini 3.5 Flash"
    },
    "groq": {
        "client": groq_client,
        "text_model": "llama-3.3-70b-versatile",
        "vision_model": "qwen/qwen3.6-27b",
        "version": "Llama 3.3 70B & Qwen 3.6 27B"
    },
}
DEFAULT_PROVIDER = "gemini"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
SAFE_MENTIONS = discord.AllowedMentions(everyone=False, roles=False, users=True)

# Nâng cấp Client lên Bot để dùng Slash Commands
bot = commands.Bot(command_prefix="!", intents=intents, allowed_mentions=SAFE_MENTIONS, help_command=None)

# ==========================================
# 3. BỘ NHỚ & DỮ LIỆU NGƯỜI DÙNG / KÊNH
# ==========================================
HISTORY_LENGTH = 10
MAX_IMAGES_PER_MESSAGE = 4
MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_FILE_BYTES = 1_000_000
MAX_FILE_CHARS = 3000
MAX_MEMBERS_LISTED = 100
TEXT_FILE_EXTENSIONS = ('.txt', '.py', '.json', '.html', '.md', '.csv', '.js', '.cpp')

# Lịch sử chat theo kênh
chat_history = defaultdict(lambda: deque(maxlen=HISTORY_LENGTH))
channel_provider = defaultdict(lambda: DEFAULT_PROVIDER)

# Cài đặt của người dùng
user_settings = defaultdict(lambda: {
    "language": "Tiếng Việt",
    "character": "Bạn là một trợ lý AI thông minh trên Discord, phong cách giống ChatGPT.",
    "data_saved": True
})

start_time = time.time()

# ==========================================
# 4. HÀM TIỆN ÍCH VÀ THÔNG ĐIỆP CHÀO MỪNG
# ==========================================
def get_welcome_embed():
    embed = discord.Embed(
        title="👋 Chào mừng bạn đến với Bot Chat AI!",
        description="Rất vui được hỗ trợ bạn. Dưới đây là thông tin về tôi:",
        color=discord.Color.blue()
    )
    embed.add_field(name="🧠 Mô hình AI", value=f"- **Gemini:** {PROVIDERS['gemini']['version']}\n- **Groq:** {PROVIDERS['groq']['version']}", inline=False)
    embed.add_field(name="👨‍💻 Hỗ trợ", value="Nếu gặp lỗi hoặc cần giải đáp, liên hệ: **@demtrangtron**", inline=False)
    embed.add_field(name="📜 Điều Khoản & Bảo Mật", value="[Điều khoản Dịch vụ](https://sites.google.com/view/botchat-privacy-policy/terms-of-service)\n[Chính sách Bảo mật](https://sites.google.com/view/botchat-privacy-policy/trang-ch%E1%BB%A7)", inline=False)
    embed.set_footer(text="Gõ /help để xem các lệnh hiện có.")
    return embed

def build_context_block(message: discord.Message) -> str:
    if not message.guild:
        return ""
    block = f"\nBạn đang ở server '{message.guild.name}' ({message.guild.member_count} thành viên)."
    members = [m for m in message.guild.members if not m.bot][:MAX_MEMBERS_LISTED]
    if members:
        listed = "\n".join(f"- {m.display_name}: <@{m.id}>" for m in members)
        block += f"\nDanh sách thành viên (muốn @tag ai thì dùng cú pháp <@ID>):\n{listed}"
    others = [m for m in message.mentions if m.id != bot.user.id]
    if others:
        tagged = ", ".join(f"{m.display_name} (<@{m.id}>)" for m in others)
        block += f"\nNgười dùng vừa tag: {tagged}"
    return block

# ==========================================
# 5. CÁC SỰ KIỆN BOT
# ==========================================
@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập thành công với tên: {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Đã đồng bộ {len(synced)} lệnh Slash.")
    except Exception as e:
        print(f"Lỗi đồng bộ lệnh: {e}")

@bot.event
async def on_guild_join(guild):
    # Gửi lời chào khi vào server mới
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send(embed=get_welcome_embed())
            break

# ==========================================
# 6. SLASH COMMANDS (/)
# ==========================================
@bot.tree.command(name="reset", description="Xóa toàn bộ dữ liệu lưu trữ và bộ nhớ trò chuyện.")
async def reset(interaction: discord.Interaction):
    chat_history[interaction.channel_id].clear()
    if interaction.user.id in user_settings:
        del user_settings[interaction.user.id]
    
    await interaction.response.send_message("🧹 Dữ liệu của bạn và lịch sử trò chuyện đã được xóa sạch.\n\n*Vui lòng chọn ngôn ngữ mặc định bằng lệnh `/language` nếu cần.*", embed=get_welcome_embed())

@bot.tree.command(name="language", description="Thay đổi ngôn ngữ mặc định của bot.")
async def language(interaction: discord.Interaction, lang: str):
    user_settings[interaction.user.id]["language"] = lang
    await interaction.response.send_message(f"✅ Đã đổi ngôn ngữ mặc định của bạn thành: **{lang}**")

@bot.tree.command(name="character", description="Thiết lập tính cách của bot.")
async def character(interaction: discord.Interaction, mo_ta: str):
    user_settings[interaction.user.id]["character"] = mo_ta
    await interaction.response.send_message(f"🎭 Đã cập nhật tính cách bot thành:\n> {mo_ta}")

@bot.tree.command(name="clear", description="Xóa lịch sử cuộc trò chuyện (giữ nguyên cài đặt).")
async def clear(interaction: discord.Interaction):
    chat_history[interaction.channel_id].clear()
    await interaction.response.send_message("🧹 Đã xóa lịch sử cuộc trò chuyện hiện tại. Các cài đặt ngôn ngữ/tính cách vẫn được giữ nguyên.")

@bot.tree.command(name="settings", description="Hiển thị các cài đặt hiện tại của bạn.")
async def settings(interaction: discord.Interaction):
    prefs = user_settings[interaction.user.id]
    embed = discord.Embed(title="⚙️ Cài đặt của bạn", color=discord.Color.green())
    embed.add_field(name="Ngôn ngữ", value=prefs['language'], inline=True)
    embed.add_field(name="Phiên bản Bot", value="v4.2.0", inline=True)
    embed.add_field(name="Trạng thái lưu dữ liệu", value="Đang lưu cục bộ" if prefs['data_saved'] else "Không lưu", inline=True)
    embed.add_field(name="Tính cách", value=prefs['character'], inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="export", description="Xuất dữ liệu lưu trữ của bạn dưới dạng file.")
async def export(interaction: discord.Interaction):
    prefs = user_settings[interaction.user.id]
    history = list(chat_history[interaction.channel_id])
    export_data = {
        "settings": prefs,
        "chat_memory": history
    }
    file_bytes = io.BytesIO(json.dumps(export_data, ensure_ascii=False, indent=4).encode('utf-8'))
    file = discord.File(file_bytes, filename=f"export_{interaction.user.id}.json")
    await interaction.response.send_message("📦 Đây là file xuất dữ liệu của bạn:", file=file)

@bot.tree.command(name="version", description="Hiển thị phiên bản bot hiện tại.")
async def version(interaction: discord.Interaction):
    await interaction.response.send_message("**Version:** v4.2.0\n**Last Updated:** 02/08/2026")

@bot.tree.command(name="about", description="Hiển thị thông tin chi tiết về bot.")
async def about(interaction: discord.Interaction):
    embed = discord.Embed(title="ℹ️ Về Bot", color=discord.Color.gold())
    embed.add_field(name="Phiên bản", value="v4.2.0", inline=True)
    embed.add_field(name="Ngày cập nhật", value="01/08/2026", inline=True) # Theo yêu cầu Source 2
    embed.add_field(name="Nhà phát triển", value="**@demtrangtron**", inline=False)
    embed.add_field(name="Tính năng nổi bật", value="- Đọc ảnh, file văn bản, mã nguồn.\n- Đổi AI linh hoạt (Gemini/Groq).\n- Tùy chỉnh tính cách & ngôn ngữ.\n- Dung lượng tối ưu siêu nhẹ (<1GB).", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="support", description="Hiển thị thông tin hỗ trợ.")
async def support(interaction: discord.Interaction):
    await interaction.response.send_message("🛠️ **Hỗ trợ kỹ thuật**\nNếu gặp lỗi hoặc cần giải đáp thắc mắc, vui lòng liên hệ: **@demtrangtron**.")

@bot.tree.command(name="ping", description="Kiểm tra độ trễ (ping) hiện tại của bot.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Độ trễ: **{round(bot.latency * 1000)}ms**")

@bot.tree.command(name="terms", description="Hiển thị Điều khoản dịch vụ.")
async def terms(interaction: discord.Interaction):
    await interaction.response.send_message("📜 **Điều Khoản Dịch Vụ:**\nhttps://sites.google.com/view/botchat-privacy-policy/terms-of-service")

@bot.tree.command(name="privacy", description="Hiển thị Chính sách bảo mật.")
async def privacy(interaction: discord.Interaction):
    await interaction.response.send_message("🔒 **Chính Sách Bảo Mật:**\nhttps://sites.google.com/view/botchat-privacy-policy/trang-ch%E1%BB%A7")

@bot.tree.command(name="uptime", description="Hiển thị thời gian bot đã hoạt động.")
async def uptime(interaction: discord.Interaction):
    current_time = time.time()
    difference = int(round(current_time - start_time))
    text = str(datetime.timedelta(seconds=difference)) if 'datetime' in globals() else f"{difference} giây"
    # Fallback to simple math if datetime not imported
    mins, secs = divmod(difference, 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    await interaction.response.send_message(f"⏱️ Bot đã hoạt động liên tục trong: **{days} ngày, {hours} giờ, {mins} phút**.")

@bot.tree.command(name="stats", description="Hiển thị thống kê của bot.")
async def stats(interaction: discord.Interaction):
    guilds = len(bot.guilds)
    users = sum(g.member_count for g in bot.guilds)
    await interaction.response.send_message(f"📊 **Thống kê Bot:**\n- Số máy chủ: {guilds}\n- Tổng người dùng: ~{users}")

@bot.tree.command(name="help", description="Danh sách các câu lệnh.")
async def help_cmd(interaction: discord.Interaction):
    help_text = (
        "**Danh sách các câu lệnh Slash (/)**\n"
        "`/reset` - Đặt lại toàn bộ dữ liệu & bộ nhớ.\n"
        "`/language <ngôn_ngữ>` - Đổi ngôn ngữ mặc định.\n"
        "`/character <mô_tả>` - Cài đặt tính cách bot.\n"
        "`/clear` - Xóa lịch sử chat hiện tại.\n"
        "`/settings` - Xem cấu hình hiện tại của bạn.\n"
        "`/export` - Tải xuống file dữ liệu của bạn.\n"
        "`/about`, `/version`, `/ping`, `/uptime`, `/stats` - Thông tin bot.\n"
        "`/support`, `/privacy`, `/terms` - Hỗ trợ và chính sách."
    )
    await interaction.response.send_message(help_text)


# ==========================================
# 7. XỬ LÝ TIN NHẮN (CHAT VỚI AI)
# ==========================================
def strip_mention(text: str) -> str:
    return (text.replace(f'<@{bot.user.id}>', '')
                .replace(f'<@!{bot.user.id}>', '')
                .strip())

@bot.event
async def on_message(message: discord.Message):
    # Cho phép bot process các lệnh prefix cũ (như !gemini, !groq)
    await bot.process_commands(message)

    if message.author == bot.user:
        return
    is_dm = isinstance(message.channel, discord.DMChannel)
    if bot.user not in message.mentions and not is_dm:
        return

    channel_id = message.channel.id
    user_text = strip_mention(message.content)
    command = user_text.lower()

    # Hỗ trợ chuyển đổi nhanh qua prefix
    if command in ("!gemini", "!groq"):
        provider_name = command.lstrip("!")
        channel_provider[channel_id] = provider_name
        await message.reply(f"✅ Kênh này chuyển sang dùng **{provider_name.upper()}** để trả lời.")
        return

    provider_name = channel_provider[channel_id]
    provider = PROVIDERS[provider_name]
    prefs = user_settings[message.author.id]

    try:
        await message.add_reaction("⏳")
    except Exception:
        pass

    # Đọc ảnh và file
    image_parts = []
    text_files_content = ""
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith('image/'):
            if len(image_parts) >= MAX_IMAGES_PER_MESSAGE or attachment.size > MAX_IMAGE_BYTES:
                continue
            try:
                img_bytes = await attachment.read()
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{attachment.content_type};base64,{b64}"},
                })
            except Exception as e:
                print(f"Không đọc được ảnh: {e}")
        elif attachment.size < MAX_FILE_BYTES and attachment.filename.endswith(TEXT_FILE_EXTENSIONS):
            try:
                file_bytes = await attachment.read()
                text_files_content += f"\n\n--- Nội dung file {attachment.filename} ---\n"
                text_files_content += file_bytes.decode('utf-8', errors='ignore')[:MAX_FILE_CHARS]
            except Exception as e:
                print(f"Không thể đọc file: {e}")

    final_prompt = (user_text + text_files_content).strip()
    if not final_prompt:
        final_prompt = "Hãy phân tích giúp tôi." if image_parts else "Chào bạn"

    api_content = ([{"type": "text", "text": final_prompt}] + image_parts) if image_parts else final_prompt
    
    history_text = final_prompt
    if image_parts:
        history_text += f"\n[Đã gửi kèm {len(image_parts)} ảnh - không lưu ảnh lại để tiết kiệm RAM]"

    # Tích hợp tính cách và ngôn ngữ người dùng vào Prompt Hệ Thống
    system_prompt = (
        f"{prefs['character']}\n"
        f"- BẠN LUÔN PHẢI TRẢ LỜI BẰNG NGÔN NGỮ NÀY (TRỪ KHI ĐƯỢC YÊU CẦU KHÁC): **{prefs['language']}**.\n"
        f"- Người đang chat với bạn: '{message.author.display_name}'.\n"
        "- Trả lời NGẮN GỌN, đi thẳng vào trọng tâm.\n"
        "- Trình bày code/văn bản rõ ràng bằng Markdown."
        + build_context_block(message)
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(list(chat_history[channel_id]))
    messages.append({"role": "user", "content": api_content})
    model_to_use = provider["vision_model"] if image_parts else provider["text_model"]

    async with message.channel.typing():
        try:
            response = provider["client"].chat.completions.create(
                messages=messages,
                model=model_to_use,
                temperature=0.7,
            )
            bot_reply = response.choices[0].message.content

            chat_history[channel_id].append({"role": "user", "content": history_text})
            chat_history[channel_id].append({"role": "assistant", "content": bot_reply})

            if len(bot_reply) > 2000:
                for i in range(0, len(bot_reply), 2000):
                    await message.channel.send(bot_reply[i:i + 2000])
            else:
                await message.reply(bot_reply)
                
            try:
                await message.remove_reaction("⏳", bot.user)
                await message.add_reaction("✅")
            except Exception:
                pass
        except Exception as e:
            await message.channel.send(f"⚠️ Lỗi từ **{provider_name.upper()}**: {e}")
            try:
                await message.remove_reaction("⏳", bot.user)
                await message.add_reaction("❌")
            except Exception:
                pass

# ==========================================
# 8. CHẠY BOT
# ==========================================
keep_alive()
bot.run(DISCORD_TOKEN)
