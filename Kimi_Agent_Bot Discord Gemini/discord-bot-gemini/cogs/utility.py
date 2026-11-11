"""
Cog Utility: thong tin bot, thong tin server/thanh vien, lenh ho tro.
"""
import time

import discord
from discord import app_commands
from discord.ext import commands

import config


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Kiem tra do tre cua bot.")
    async def ping(self, interaction: discord.Interaction):
        ms = round(self.bot.latency * 1000)
        mood = "Nhanh nhu chop luon ⚡" if ms < 100 else "Tam on, chua chet 😌" if ms < 300 else "Cham nhu rua 🐢"
        await interaction.response.send_message(f"🏓 Pong! **{ms}ms** - {mood}")

    @app_commands.command(name="uptime", description="Thoi gian bot da chay lien tuc.")
    async def uptime(self, interaction: discord.Interaction):
        diff = int(time.time() - self.bot.start_time)
        m, s = divmod(diff, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        await interaction.response.send_message(f"⏱️ Bot da chay lien tuc: **{d} ngay, {h} gio, {m} phut, {s} giay**.")

    @app_commands.command(name="stats", description="Thong ke bot.")
    async def stats(self, interaction: discord.Interaction):
        guilds = len(self.bot.guilds)
        users = sum(g.member_count for g in self.bot.guilds)
        embed = discord.Embed(title="📊 Thống kê bot", color=discord.Color.blurple())
        embed.add_field(name="Server", value=str(guilds), inline=True)
        embed.add_field(name="Tong thanh vien", value=f"~{users}", inline=True)
        embed.add_field(name="Do tre", value=f"{round(self.bot.latency*1000)}ms", inline=True)
        embed.add_field(name="Model AI", value=config.GEMINI_MODEL, inline=True)
        embed.add_field(name="Version", value=config.BOT_VERSION, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Thong tin server hien tai.")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        embed = discord.Embed(title=f"ℹ️ {g.name}", color=discord.Color.gold())
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="ID", value=str(g.id), inline=True)
        embed.add_field(name="Chu so huu", value=g.owner.mention if g.owner else "?", inline=True)
        embed.add_field(name="Thanh vien", value=str(g.member_count), inline=True)
        embed.add_field(name="Kenh", value=str(len(g.channels)), inline=True)
        embed.add_field(name="Role", value=str(len(g.roles)), inline=True)
        embed.add_field(name="Tao ngay", value=g.created_at.strftime("%d/%m/%Y"), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Xem avatar cua thanh vien.")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        embed = discord.Embed(title=f"🖼️ Avatar - {user.display_name}", color=discord.Color.blue())
        embed.set_image(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Thong tin thanh vien.")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        embed = discord.Embed(title=f"👤 {user.display_name}", color=discord.Color.green())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="ID", value=str(user.id), inline=True)
        embed.add_field(name="Ten dang nhap", value=str(user), inline=True)
        embed.add_field(name="Tham gia server", value=user.joined_at.strftime("%d/%m/%Y") if user.joined_at else "?", inline=True)
        embed.add_field(name="Tao tai khoan", value=user.created_at.strftime("%d/%m/%Y"), inline=True)
        roles = [r.mention for r in user.roles if r.name != "@everyone"][:10]
        embed.add_field(name=f"Roles ({len(user.roles)-1})", value=" ".join(roles) or "Khong co", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Danh sach tat ca lenh cua bot.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Hướng dẫn sử dụng bot",
            description=(
                "**Chat với AI:** Nhắc `@tên_bot` + nội dung, nhắn DM, hoặc dùng `/chaton` để bot tự nhập hội thoại.\n"
                "Bot nhớ **12 tin nhắn gần nhất** của bạn trong kênh hiện tại."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="💬 AI Chat",
            value=(
                "`/chaton` `/chatoff` - Bật/tắt chế độ tự chat\n"
                "`/language` - Đổi ngôn ngữ trả lời ngắn\n"
                "`/persona` - Đổi tính cách bot\n"
                "`/history` - Xem bot nhớ gì về bạn\n"
                "`/clear` `/reset` - Xóa lịch sử / xóa dữ liệu"
            ),
            inline=False,
        )
        embed.add_field(
            name="🛡️ Quản lý (Admin/Mod)",
            value=(
                "`/warn` `/warns` `/clearwarns` - Hệ thống cảnh báo (đủ 3 lần tự động mute)\n"
                "`/mute` `/unmute` - Tắt/mở tiếng\n"
                "`/kick` `/ban` `/unban` - Đuổi / cấm / gỡ cấm\n"
                "`/purge` - Xóa hàng loạt tin nhắn\n"
                "`/slowmode` - Chế độ chậm\n"
                "`/dm` - Nhắn tin riêng cho thành viên\n"
                "`/setmodlog` - Đặt kênh nhật ký mod\n"
                "*Bot tự động xóa tin nhắn có từ chửi bậy và cảnh cáo người dùng*"
            ),
            inline=False,
        )
        embed.add_field(
            name="⏰ Nhắc nhở",
            value="`/remind` `/remindlist` `/remindcancel` - Hẹn giờ nhắc việc (hỗ trợ DM)",
            inline=False,
        )
        embed.add_field(
            name="🎲 Giải trí",
            value="`/8ball` `/coinflip` `/dice` `/roast` `/compliment` `/poll` `/say`",
            inline=False,
        )
        embed.add_field(
            name="ℹ️ Thông tin",
            value="`/ping` `/uptime` `/stats` `/serverinfo` `/userinfo` `/avatar`",
            inline=False,
        )
        embed.set_footer(text=f"{config.BOT_VERSION} • Hỗ trợ: {config.SUPPORT_CONTACT}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="version", description="Phiên bản bot.")
    async def version(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"**{config.BOT_VERSION}** - nang cap tu code goc, them mod + reminder + fun 🚀")

    @app_commands.command(name="support", description="Thông tin hỗ trợ.")
    async def support(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🛠️ Cần giúp đỡ? Liên hệ: **{config.SUPPORT_CONTACT}**")


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
