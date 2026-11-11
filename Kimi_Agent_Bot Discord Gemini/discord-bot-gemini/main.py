"""
Bot Discord + Gemini - phien ban nang cap v5.0.0
Chay tren Render (web service). Deployee bang: python main.py
"""
import asyncio
import time

import discord
from discord.ext import commands
from aiohttp import web

import config

START_TIME = time.time()


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.moderation = True  # canh bao thanh vien ra/vao cho he thong warn

    safe_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)
    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
        allowed_mentions=safe_mentions,
        help_command=None,
    )
    bot.start_time = START_TIME
    return bot


bot = create_bot()


@bot.event
async def on_ready():
    print(f"[READY] Dang nhap thanh cong: {bot.user} (id={bot.user.id})")
    print(f"[READY] Dang phuc vu {len(bot.guilds)} server")
    # Nap cac module (cogs)
    for ext in ("cogs.ai_chat", "cogs.moderation", "cogs.reminders", "cogs.fun", "cogs.utility"):
        try:
            await bot.load_extension(ext)
            print(f"[COG] Da nap {ext}")
        except Exception as e:
            print(f"[COG LOI] Khong nap duoc {ext}: {e}")
    try:
        synced = await bot.tree.sync()
        print(f"[SYNC] Dong bo {len(synced)} lenh slash (/)")
    except Exception as e:
        print(f"[SYNC LOI] {e}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="chat cua ban | /help de xem lenh",
        )
    )


@bot.event
async def on_guild_join(guild: discord.Guild):
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            embed = discord.Embed(
                title="Chao server! 👋",
                description=(
                    "Minh la bot AI dung Gemini, vua tham gia server nay.\n"
                    "Nhac minh bang cach **@ten_bot** roi chat, hoac dung `/chaton` "
                    "de minh tu nhap hoi chuyen trong kenh nay.\n"
                    "Go `/help` de xem tat ca lenh."
                ),
                color=discord.Color.blurple(),
            )
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass
            break


# ---------------- Web server giup Render thay bot "con song" ----------------
async def handle_health(request: web.Request) -> web.Response:
    uptime = int(time.time() - START_TIME)
    return web.json_response(
        {
            "status": "alive",
            "bot": str(bot.user) if bot.user else "starting",
            "uptime_seconds": uptime,
            "guilds": len(bot.guilds),
            "version": config.BOT_VERSION,
        }
    )


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    print(f"[WEB] Health server chay o port {config.PORT}")


async def main():
    if not config.DISCORD_TOKEN:
        raise RuntimeError("Thieu DISCORD_TOKEN trong bien moi truong!")
    if not config.GEMINI_API_KEY:
        print("[CANH BAO] Thieu GEMINI_API_KEY - chuc nang AI se loi.")
    await start_web_server()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
