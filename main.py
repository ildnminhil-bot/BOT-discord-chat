import os
import base64
import threading
import time
import json
import io
import datetime
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
    return "Bot is alive!"

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

chat_history = defaultdict(lambda: deque(maxlen=HISTORY_LENGTH))
channel_provider = defaultdict(lambda: DEFAULT_PROVIDER)

# ĐỔI MẶC ĐỊNH SANG TIẾNG ANH
user_settings = defaultdict(lambda: {
    "language": "English",
    "character": "You are a smart, helpful AI assistant on Discord, similar to ChatGPT.",
    "data_saved": True
})

start_time = time.time()

# ==========================================
# 4. HÀM TIỆN ÍCH VÀ THÔNG ĐIỆP CHÀO MỪNG (TIẾNG ANH)
# ==========================================
def get_welcome_embed():
    embed = discord.Embed(
        title="👋 Welcome to AI Chat Bot!",
        description="I'm here to assist you. Below is some information about me:",
        color=discord.Color.blue()
    )
    embed.add_field(name="🧠 AI Models", value=f"- **Gemini:** {PROVIDERS['gemini']['version']}\n- **Groq:** {PROVIDERS['groq']['version']}", inline=False)
    embed.add_field(name="👨‍💻 Support", value="If you encounter any issues, please contact: **@demtrangtron**", inline=False)
    embed.add_field(name="📜 Terms & Privacy", value="[Terms of Service](https://sites.google.com/view/botchat-privacy-policy/terms-of-service)\n[Privacy Policy](https://sites.google.com/view/botchat-privacy-policy/trang-ch%E1%BB%A7)", inline=False)
    embed.set_footer(text="Type /help to see all available commands.")
    return embed

def build_context_block(message: discord.Message) -> str:
    if not message.guild:
        return ""
    block = f"\nYou are currently in the server '{message.guild.name}' ({message.guild.member_count} members)."
    members = [m for m in message.guild.members if not m.bot][:MAX_MEMBERS_LISTED]
    if members:
        listed = "\n".join(f"- {m.display_name}: <@{m.id}>" for m in members)
        block += f"\nServer member list (use <@ID> syntax to tag someone):\n{listed}"
    others = [m for m in message.mentions if m.id != bot.user.id]
    if others:
        tagged = ", ".join(f"{m.display_name} (<@{m.id}>)" for m in others)
        block += f"\nUsers mentioned in this message: {tagged}"
    return block

# ==========================================
# 5. CÁC SỰ KIỆN BOT
# ==========================================
@bot.event
async def on_ready():
    print(f'Bot logged in successfully as: {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} Slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_guild_join(guild):
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send(embed=get_welcome_embed())
            break

# ==========================================
# 6. SLASH COMMANDS (/) - TIẾNG ANH
# ==========================================
@bot.tree.command(name="reset", description="Clear all your saved data and chat memory.")
async def reset(interaction: discord.Interaction):
    chat_history[interaction.channel_id].clear()
    if interaction.user.id in user_settings:
        del user_settings[interaction.user.id]
    await interaction.response.send_message("🧹 Your data and chat history have been completely cleared.\n\n*Use `/language` if you want to change your default language.*", embed=get_welcome_embed())

@bot.tree.command(name="language", description="Change the bot's default language.")
async def language(interaction: discord.Interaction, lang: str):
    user_settings[interaction.user.id]["language"] = lang
    await interaction.response.send_message(f"✅ Default language has been changed to: **{lang}**")

@bot.tree.command(name="character", description="Set the bot's persona/character.")
async def character(interaction: discord.Interaction, description: str):
    user_settings[interaction.user.id]["character"] = description
    await interaction.response.send_message(f"🎭 Bot persona updated to:\n> {description}")

@bot.tree.command(name="clear", description="Clear the current chat history (keeps settings).")
async def clear(interaction: discord.Interaction):
    chat_history[interaction.channel_id].clear()
    await interaction.response.send_message("🧹 Chat history cleared. Language and persona settings are kept intact.")

@bot.tree.command(name="settings", description="Display your current settings.")
async def settings(interaction: discord.Interaction):
    prefs = user_settings[interaction.user.id]
    embed = discord.Embed(title="⚙️ Your Settings", color=discord.Color.green())
    embed.add_field(name="Language", value=prefs['language'], inline=True)
    embed.add_field(name="Bot Version", value="v4.2.0", inline=True)
    embed.add_field(name="Data Status", value="Saved locally" if prefs['data_saved'] else "Not saved", inline=True)
    embed.add_field(name="Persona", value=prefs['character'], inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="export", description="Export your saved data as a file.")
async def export(interaction: discord.Interaction):
    prefs = user_settings[interaction.user.id]
    history = list(chat_history[interaction.channel_id])
    export_data = {
        "settings": prefs,
        "chat_memory": history
    }
    file_bytes = io.BytesIO(json.dumps(export_data, ensure_ascii=False, indent=4).encode('utf-8'))
    file = discord.File(file_bytes, filename=f"export_{interaction.user.id}.json")
    await interaction.response.send_message("📦 Here is your exported data file:", file=file)

@bot.tree.command(name="version", description="Show the current bot version.")
async def version(interaction: discord.Interaction):
    await interaction.response.send_message("**Version:** v4.2.0\n**Last Updated:** 02/08/2026")

@bot.tree.command(name="about", description="Show detailed information about the bot.")
async def about(interaction: discord.Interaction):
    embed = discord.Embed(title="ℹ️ About Bot", color=discord.Color.gold())
    embed.add_field(name="Version", value="v4.2.0", inline=True)
    embed.add_field(name="Last Updated", value="01/08/2026", inline=True)
    embed.add_field(name="Developer", value="**@demtrangtron**", inline=False)
    embed.add_field(name="Key Features", value="- Reads images, text files, and source code.\n- Flexible AI switching (Gemini/Groq).\n- Customizable persona & language.\n- Highly optimized & lightweight (<1GB).", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="support", description="Show support information.")
async def support(interaction: discord.Interaction):
    await interaction.response.send_message("🛠️ **Technical Support**\nIf you encounter any issues or have questions, please contact: **@demtrangtron**.")

@bot.tree.command(name="ping", description="Check the bot's current latency (ping).")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Latency: **{round(bot.latency * 1000)}ms**")

@bot.tree.command(name="terms", description="Show Terms of Service.")
async def terms(interaction: discord.Interaction):
    await interaction.response.send_message("📜 **Terms of Service:**\nhttps://sites.google.com/view/botchat-privacy-policy/terms-of-service")

@bot.tree.command(name="privacy", description="Show Privacy Policy.")
async def privacy(interaction: discord.Interaction):
    await interaction.response.send_message("🔒 **Privacy Policy:**\nhttps://sites.google.com/view/botchat-privacy-policy/trang-ch%E1%BB%A7")

@bot.tree.command(name="uptime", description="Show how long the bot has been running.")
async def uptime(interaction: discord.Interaction):
    current_time = time.time()
    difference = int(round(current_time - start_time))
    mins, secs = divmod(difference, 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    await interaction.response.send_message(f"⏱️ Bot has been continuously running for: **{days} days, {hours} hours, {mins} minutes**.")

@bot.tree.command(name="stats", description="Show bot statistics.")
async def stats(interaction: discord.Interaction):
    guilds = len(bot.guilds)
    users = sum(g.member_count for g in bot.guilds)
    await interaction.response.send_message(f"📊 **Bot Stats:**\n- Servers: {guilds}\n- Total Users: ~{users}")

@bot.tree.command(name="help", description="List of all available commands.")
async def help_cmd(interaction: discord.Interaction):
    help_text = (
        "**List of Slash Commands (/)**\n"
        "`/reset` - Clear all your data & memory.\n"
        "`/language <lang>` - Change default language.\n"
        "`/character <desc>` - Set the bot's persona.\n"
        "`/clear` - Clear current chat history.\n"
        "`/settings` - View your current settings.\n"
        "`/export` - Download your data file.\n"
        "`/about`, `/version`, `/ping`, `/uptime`, `/stats` - Bot info.\n"
        "`/support`, `/privacy`, `/terms` - Support and policies."
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
    await bot.process_commands(message)

    if message.author == bot.user:
        return
    is_dm = isinstance(message.channel, discord.DMChannel)
    if bot.user not in message.mentions and not is_dm:
        return

    channel_id = message.channel.id
    user_text = strip_mention(message.content)
    command = user_text.lower()

    if command in ("!gemini", "!groq"):
        provider_name = command.lstrip("!")
        channel_provider[channel_id] = provider_name
        await message.reply(f"✅ This channel has switched to **{provider_name.upper()}**.")
        return

    provider_name = channel_provider[channel_id]
    provider = PROVIDERS[provider_name]
    prefs = user_settings[message.author.id]

    try:
        await message.add_reaction("⏳")
    except Exception:
        pass

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
                print(f"Failed to read image: {e}")
        elif attachment.size < MAX_FILE_BYTES and attachment.filename.endswith(TEXT_FILE_EXTENSIONS):
            try:
                file_bytes = await attachment.read()
                text_files_content += f"\n\n--- Content of {attachment.filename} ---\n"
                text_files_content += file_bytes.decode('utf-8', errors='ignore')[:MAX_FILE_CHARS]
            except Exception as e:
                print(f"Failed to read file: {e}")

    final_prompt = (user_text + text_files_content).strip()
    if not final_prompt:
        final_prompt = "Please analyze this for me." if image_parts else "Hello!"

    api_content = ([{"type": "text", "text": final_prompt}] + image_parts) if image_parts else final_prompt
    
    history_text = final_prompt
    if image_parts:
        history_text += f"\n[Sent {len(image_parts)} images - not saved to memory to save RAM]"

    system_prompt = (
        f"{prefs['character']}\n"
        f"- YOU MUST ALWAYS ANSWER IN THIS LANGUAGE (UNLESS REQUESTED OTHERWISE): **{prefs['language']}**.\n"
        f"- The user chatting with you is: '{message.author.display_name}'.\n"
        "- Keep answers CONCISE, get straight to the point.\n"
        "- Format code and text clearly using Markdown."
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
            await message.channel.send(f"⚠️ Error from **{provider_name.upper()}**: {e}")
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
