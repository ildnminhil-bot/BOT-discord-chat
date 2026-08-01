import os
import base64
import threading
from collections import defaultdict, deque

import discord
from flask import Flask
from openai import OpenAI

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
    threading.Thread(target=run_web, daemon=True).start()


# ==========================================
# 2. CẤU HÌNH TOKEN + 2 CLIENT: GEMINI VÀ GROQ (ĐÃ BỎ HẲN GITHUB)
# ==========================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GEMINI_API_KEY:
    print("⚠️  Thiếu biến môi trường GEMINI_API_KEY - lệnh !gemini sẽ báo lỗi.")
if not GROQ_API_KEY:
    print("⚠️  Thiếu biến môi trường GROQ_API_KEY - lệnh !groq sẽ báo lỗi.")

# Lý do lỗi 410: endpoint cũ models.inference.ai.azure.com (GitHub Models) đã bị
# GitHub khai tử HẲN từ 17/10/2025, gọi vào chỉ nhận lỗi 410 vĩnh viễn, không có
# cách sửa nào khác ngoài chuyển sang nhà cung cấp khác -> đây là lý do đổi sang
# Gemini + Groq bên dưới, cả hai đều tương thích thư viện "openai" nên code gọi
# API gần như giữ nguyên, chỉ đổi base_url/model.
gemini_client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# Model dùng cho từng hãng - đổi ở đây nếu sau này muốn dùng bản khác
PROVIDERS = {
    "gemini": {
        "client": gemini_client,
        "text_model": "gemini-3.5-flash",
        "vision_model": "gemini-3.5-flash",  # Gemini tự đọc được ảnh, khỏi cần đổi model
    },
    "groq": {
        "client": groq_client,
        "text_model": "llama-3.3-70b-versatile",
        "vision_model": "qwen/qwen3.6-27b",  # model DUY NHẤT bên Groq đọc được ảnh hiện tại
    },
}
DEFAULT_PROVIDER = "gemini"  # đổi thành "groq" nếu muốn Groq làm mặc định lúc bot khởi động

# Bật intents để bot lấy được thông tin Server/Thành viên (phục vụ việc @tag người khác)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Chặn AI vô tình ping @everyone/@role dù danh sách thành viên có trong prompt;
# vẫn cho phép @tag từng người cụ thể (đúng tính năng yêu cầu).
SAFE_MENTIONS = discord.AllowedMentions(everyone=False, roles=False, users=True)

bot_client = discord.Client(intents=intents, allowed_mentions=SAFE_MENTIONS)

# ==========================================
# 3. BỘ NHỚ SIÊU NHẸ: LỊCH SỬ CHAT + API ĐANG DÙNG CHO MỖI KÊNH
# ==========================================
HISTORY_LENGTH = 10                 # số dòng hội thoại nhớ được mỗi kênh (~5 lượt hỏi-đáp)
MAX_IMAGES_PER_MESSAGE = 4           # Groq vision tối đa 5 ảnh/lượt, chừa dư 1
MAX_IMAGE_BYTES = 6 * 1024 * 1024    # bỏ qua ảnh > 6MB để khỏi phình RAM
MAX_FILE_BYTES = 1_000_000
MAX_FILE_CHARS = 3000
MAX_MEMBERS_LISTED = 100             # chỉ liệt kê tối đa 100 thành viên để prompt khỏi quá to
TEXT_FILE_EXTENSIONS = ('.txt', '.py', '.json', '.html', '.md', '.csv', '.js', '.cpp')

chat_history = defaultdict(lambda: deque(maxlen=HISTORY_LENGTH))
channel_provider = defaultdict(lambda: DEFAULT_PROVIDER)


@bot_client.event
async def on_ready():
    print(f'Bot đã đăng nhập thành công với tên: {bot_client.user}')


def strip_mention(text: str) -> str:
    """Bỏ phần tag bot (<@ID> hoặc <@!ID>) khỏi đầu câu."""
    return (text.replace(f'<@{bot_client.user.id}>', '')
                .replace(f'<@!{bot_client.user.id}>', '')
                .strip())


def build_context_block(message: discord.Message) -> str:
    """Ghép thông tin server + danh sách thành viên để bot @tag đúng người khi cần."""
    if not message.guild:
        return ""

    block = (f"\nBạn đang ở server '{message.guild.name}' "
             f"({message.guild.member_count} thành viên).")

    members = [m for m in message.guild.members if not m.bot][:MAX_MEMBERS_LISTED]
    if members:
        listed = "\n".join(f"- {m.display_name}: <@{m.id}>" for m in members)
        block += (f"\nDanh sách thành viên (tối đa {MAX_MEMBERS_LISTED} người đầu), muốn "
                  f"@tag ai thì dùng ĐÚNG cú pháp <@ID> tương ứng bên dưới:\n{listed}")

    others = [m for m in message.mentions if m.id != bot_client.user.id]
    if others:
        tagged = ", ".join(f"{m.display_name} (<@{m.id}>)" for m in others)
        block += f"\nNgười dùng vừa tag sẵn trong tin nhắn: {tagged}"

    return block


@bot_client.event
async def on_message(message: discord.Message):
    if message.author == bot_client.user:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    if bot_client.user not in message.mentions and not is_dm:
        return

    channel_id = message.channel.id
    user_text = strip_mention(message.content)
    command = user_text.lower()

    # --- LỆNH "!RESET": XÓA TRÍ NHỚ CUỘC TRÒ CHUYỆN ---
    if command == "!reset":
        chat_history[channel_id].clear()
        await message.reply("🧹 Đã xóa sạch trí nhớ cuộc trò chuyện này. RAM trống trơn!")
        return

    # --- LỆNH ĐỔI API: !gemini hoặc !groq, áp dụng đến khi đổi lệnh khác ---
    if command in ("!gemini", "!groq"):
        provider_name = command.lstrip("!")
        channel_provider[channel_id] = provider_name
        await message.reply(f"✅ Kênh này chuyển sang dùng **{provider_name.upper()}** để "
                             f"trả lời, cho đến khi bạn gõ lệnh đổi API khác.")
        return

    provider_name = channel_provider[channel_id]
    provider = PROVIDERS[provider_name]

    try:
        await message.add_reaction("⏳")
    except Exception:
        pass

    # --- ĐỌC ẢNH (đổi sang base64 thay vì gửi thẳng link Discord CDN, vì link có
    #     thể hết hạn hoặc bị AI provider chặn fetch -> lỗi khó hiểu) VÀ FILE ---
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

    # Nội dung gửi API NGAY LƯỢT NÀY - có thể kèm ảnh thật (base64)
    api_content = ([{"type": "text", "text": final_prompt}] + image_parts) if image_parts else final_prompt

    # Nội dung LƯU VÀO LỊCH SỬ: không bao giờ chứa base64 ảnh, để RAM không phình to
    # theo thời gian và để khỏi gửi lại ảnh/link cũ đã hết hạn ở lượt chat sau.
    history_text = final_prompt
    if image_parts:
        history_text += f"\n[Đã gửi kèm {len(image_parts)} ảnh - không lưu ảnh lại để tiết kiệm RAM]"

    system_prompt = (
        "Bạn là một trợ lý AI thông minh trên Discord, phong cách giống ChatGPT.\n"
        f"- Người đang chat với bạn: '{message.author.display_name}' "
        f"(muốn nhắc lại người này thì dùng <@{message.author.id}>).\n"
        "- Trả lời NGẮN GỌN, đi thẳng vào trọng tâm, tối đa vài câu trừ khi được yêu cầu "
        "giải thích dài hơn.\n"
        "- Trình bày code/văn bản rõ ràng bằng Markdown.\n"
        "- Có thể đọc ảnh, đọc file người dùng gửi, và @tag bất kỳ ai trong danh sách "
        "thành viên bằng đúng cú pháp <@ID> khi được yêu cầu."
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

            # Chỉ lưu vào lịch sử SAU KHI gọi API thành công, tránh để lại một lượt
            # "user" mồ côi (không có "assistant" đi kèm) mỗi khi API bị lỗi.
            chat_history[channel_id].append({"role": "user", "content": history_text})
            chat_history[channel_id].append({"role": "assistant", "content": bot_reply})

            if len(bot_reply) > 2000:
                for i in range(0, len(bot_reply), 2000):
                    await message.channel.send(bot_reply[i:i + 2000])
            else:
                await message.reply(bot_reply)

            try:
                await message.remove_reaction("⏳", bot_client.user)
                await message.add_reaction("✅")
            except Exception:
                pass

        except Exception as e:
            await message.channel.send(f"⚠️ Lỗi từ **{provider_name.upper()}**: {e}")
            try:
                await message.remove_reaction("⏳", bot_client.user)
                await message.add_reaction("❌")
            except Exception:
                pass


# ==========================================
# 4. CHẠY BOT
# ==========================================
keep_alive()
bot_client.run(DISCORD_TOKEN)
