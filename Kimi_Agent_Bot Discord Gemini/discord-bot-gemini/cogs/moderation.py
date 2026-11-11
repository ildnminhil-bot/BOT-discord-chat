"""
Cog Quan ly: loc tu chui bay, he thong canh bao (warn), mute, kick, ban,
nhac nho rieng (DM), don tin nhan, slowmode, nhat ky mod.
"""
import asyncio
import re
import time
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

import config

# ---------------- Tu cam: chui bay thong dung (khong dau + co dau) ----------------
BAD_WORDS = {
    # Viet khong dau (luu y: bo cac tu de ban oan nhu "dm"=direct message,
    # "dien"=giao dien, "du"=du lich, "lon"=lon nuoc, "thoi", "hoi", "khung")
    "vcl", "vl", "vkl", "dkm", "dcm", "dit", "đjt", "cak",
    "lol", "loz", "cmn", "cc", "cl", "ngu", "oc",
    "sida", "xaml", "con di", "concho", "thang cho", "me may",
    "bo may", "chung may", "fuckyou", "ditme", "ditba", "lonte",
    # Viet co dau
    "địt", "đm", "đéo", "cặc", "lồn", "đĩ", "điếm", "chó", "chết tiệt",
    "khốn", "khốn nạn", "súc vật", "thằng ngu", "con điên", "bẩn",
    # Anh
    "fuck", "shit", "bitch", "bastard", "asshole", "dick", "pussy",
    "whore", "slut", "cunt", "nigger", "faggot", "retard",
}

# Lenh co ban khong can quyen (phan biet admin/member)
MOD_PERMISSIONS = {
    "warn": "moderate_members",
    "mute": "moderate_members",
    "unmute": "moderate_members",
    "kick": "kick_members",
    "ban": "ban_members",
    "unban": "ban_members",
    "purge": "manage_messages",
    "slowmode": "manage_channels",
}

SCOLD_MESSAGES = [
    "🧼 **{user}** oi, mieng nha binh lafm chut di! Kem nay coi nhu chua thay gi.",
    "😤 **{user}** vua thot ra tu cam day. Lan nay canh cao, lan sau la co kem day nhe!",
    "🚫 **{user}**! Tu nay khong duoc phep o day. Uong nuoc loc mieng di roi quay lai.",
    "🧹 **{user}** bi don dep loi noi boc mui. Lan sau gio cai mieng ra ma noi nhe.",
]

WARN_JOKES = [
    "Mot lan canh cao danh cho **{user}**. Tich luy du 3 lan la co phan thuong dac biet~ 🎁",
    "**{user}** nhan them 1 vet den. {count}/3 roi day, co gang them chut nua! 😏",
    "Canh cao thu {count} cho **{user}**. Server nay co luat, deu co kem het.",
]


def normalize(text: str) -> str:
    """Chuan hoa chuoi: thuong, bo dau cau, gom khoang trang."""
    t = text.lower()
    t = re.sub(r"[.,!?;:'\"\(\)\[\]\{\}@#$%^&*~`<>/\\|_+=-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def find_bad_words(text: str):
    """Tra ve danh sach tu cam tim thay (khop theo cum tu)."""
    t = normalize(text)
    found = []
    for w in BAD_WORDS:
        w_norm = normalize(w)
        if re.search(r"\b" + re.escape(w_norm) + r"\b", t):
            found.append(w)
    return found


def is_owner(user_id: int) -> bool:
    return user_id in config.OWNER_IDS


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> {user_id: {"count": int, "reasons": [...] }}
        self.warns: dict = defaultdict(lambda: defaultdict(lambda: {"count": 0, "reasons": []}))
        # guild_id -> channel_id nhat ky mod (dat bang /setmodlog)
        self.modlog: dict = {}

    # ---------------- Nhat ky ----------------
    async def log(self, guild: discord.Guild, embed: discord.Embed):
        cid = self.modlog.get(guild.id)
        channel = guild.get_channel(cid) if cid else None
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

    # ---------------- Bo loc tu chui ----------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if is_owner(message.author.id):
            return
        # Bot va admin duoc mien (co quyen quan ly kenh)
        perms = message.channel.permissions_for(message.author)
        if perms.manage_messages:
            return

        found = find_bad_words(message.content)
        if not found:
            return
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            return
        scold = SCOLD_MESSAGES[hash(message.author.id) % len(SCOLD_MESSAGES)]
        await message.channel.send(scold.format(user=message.author.mention), delete_after=15)
        # Tu dong canh cao
        await self._add_warn(message.guild, message.author, f"Tu cam: {', '.join(found)}")
        embed = discord.Embed(
            title="🧼 Tu dong loc tu cam",
            description=f"{message.author.mention} vua bi xoa tin nhan vi su dung tu cam.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Tu phat hien", value=", ".join(f"`{w}`" for w in found))
        await self.log(message.guild, embed)

    # ---------------- He thong warn ----------------
    async def _add_warn(self, guild: discord.Guild, member: discord.Member, reason: str):
        data = self.warns[guild.id][member.id]
        data["count"] += 1
        data["reasons"].append(f"[{time.strftime('%d/%m %H:%M')}] {reason}")
        return data["count"]

    @app_commands.command(name="warn", description="Canh cao mot thanh vien.")
    @app_commands.describe(user="Nguoi canh cao", ly_do="Ly do")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, ly_do: str = "Khong ro"):
        if not (interaction.user.guild_permissions.moderate_members or is_owner(interaction.user.id)):
            await interaction.response.send_message("Ban khong co quyen canh cao nguoi khac 😑", ephemeral=True)
            return
        if user.id == self.bot.user.id:
            await interaction.response.send_message("Canh cao minh a? Cam on, minh van dep trai. 😌", ephemeral=True)
            return
        count = await self._add_warn(interaction.guild, user, ly_do)
        joke = WARN_JOKES[count % len(WARN_JOKES)]
        await interaction.response.send_message(
            f"⚠️ {joke.format(user=user.mention, count=count)}\n📋 Ly do: *{ly_do}*"
        )
        embed = discord.Embed(title="⚠️ Cảnh báo", color=discord.Color.yellow())
        embed.add_field(name="Nguoi bi canh cao", value=user.mention, inline=True)
        embed.add_field(name="Boi", value=interaction.user.mention, inline=True)
        embed.add_field(name="Ly do", value=ly_do, inline=False)
        embed.add_field(name="Tong so canh cao", value=str(count), inline=True)
        await self.log(interaction.guild, embed)
        # Du 3 lan -> mute 10 phut
        if count >= 3 and count % 3 == 0:
            try:
                await user.timeout(discord.utils.utcnow() + __import__("datetime").timedelta(minutes=10),
                                   reason="Du 3 lan canh cao")
                await interaction.channel.send(f"🔇 **{user.mention}** du 3 canh cao, bi tat tieng 10 phut. Ngoi suy ngam di!")
            except (discord.Forbidden, discord.HTTPException):
                pass

    @app_commands.command(name="warns", description="Xem so canh cao cua thanh vien.")
    async def warns(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        data = self.warns[interaction.guild.id].get(user.id)
        if not data or data["count"] == 0:
            await interaction.response.send_message(f"✨ **{user.display_name}** trong veo nhu pha le, chua co canh cao nao.")
            return
        embed = discord.Embed(title=f"⚠️ Hồ sơ cảnh báo - {user.display_name}", color=discord.Color.orange())
        embed.add_field(name="Tong so", value=str(data["count"]), inline=True)
        reasons = "\n".join(data["reasons"][-10:]) or "Khong co"
        embed.add_field(name="Lich su", value=reasons[:1000], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarns", description="Xoa het canh cao cua thanh vien.")
    async def clearwarns(self, interaction: discord.Interaction, user: discord.Member):
        if not (interaction.user.guild_permissions.moderate_members or is_owner(interaction.user.id)):
            await interaction.response.send_message("Khong co quyen nhe ban oi 🙅", ephemeral=True)
            return
        self.warns[interaction.guild.id].pop(user.id, None)
        await interaction.response.send_message(f"🧹 Da xoa sach vet nham cua **{user.display_name}**. Song tot nhe!")

    # ---------------- Mute / Kick / Ban ----------------
    @app_commands.command(name="mute", description="Tat tieng thanh vien (phut).")
    @app_commands.describe(user="Nguoi bi mute", phut="So phut (mac dinh 10)", ly_do="Ly do")
    async def mute(self, interaction: discord.Interaction, user: discord.Member, phut: int = 10, ly_do: str = "Khong ro"):
        if not (interaction.user.guild_permissions.moderate_members or is_owner(interaction.user.id)):
            await interaction.response.send_message("Ban khong co quyen mute ai het 😑", ephemeral=True)
            return
        if phut < 1 or phut > 40320:
            await interaction.response.send_message("So phut hop le: 1 - 40320 (28 ngay).", ephemeral=True)
            return
        try:
            import datetime
            until = discord.utils.utcnow() + datetime.timedelta(minutes=phut)
            await user.timeout(until, reason=ly_do)
            await interaction.response.send_message(f"🔇 **{user.mention}** bi tat tieng **{phut} phut**. Ly do: *{ly_do}*")
        except discord.Forbidden:
            await interaction.response.send_message("Minh khong du quyen de mute nguoi nay (hoac vi tri role cao hon minh).", ephemeral=True)

    @app_commands.command(name="unmute", description="Mo tat tieng cho thanh vien.")
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        if not (interaction.user.guild_permissions.moderate_members or is_owner(interaction.user.id)):
            await interaction.response.send_message("Khong co quyen 🙅", ephemeral=True)
            return
        try:
            await user.timeout(None)
            await interaction.response.send_message(f"🔊 **{user.mention}** duoc noi lai roi. Noi nhe thoi nhe!")
        except discord.Forbidden:
            await interaction.response.send_message("Khong du quyen.", ephemeral=True)

    @app_commands.command(name="kick", description="Duoi thanh vien ra khoi server.")
    @app_commands.describe(user="Nguoi bi kick", ly_do="Ly do")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, ly_do: str = "Khong ro"):
        if not (interaction.user.guild_permissions.kick_members or is_owner(interaction.user.id)):
            await interaction.response.send_message("Ban khong co quyen kick 😑", ephemeral=True)
            return
        try:
            await user.send(f"👢 Ban da bi duoi khoi server **{interaction.guild.name}**. Ly do: *{ly_do}*")
        except discord.Forbidden:
            pass
        try:
            await user.kick(reason=ly_do)
            await interaction.response.send_message(f"👢 **{user.display_name}** da bay mau khoi server. Ly do: *{ly_do}*")
        except discord.Forbidden:
            await interaction.response.send_message("Khong du quyen kick (co the role ho cao hon minh).", ephemeral=True)

    @app_commands.command(name="ban", description="Cam thanh vien vinh vien.")
    @app_commands.describe(user="Nguoi bi ban", ly_do="Ly do", xoa_tin_nhan_ngay="Xoa tin nhan bao nhieu ngay (0-7)")
    async def ban(self, interaction: discord.Interaction, user: discord.Member, ly_do: str = "Khong ro",
                  xoa_tin_nhan_ngay: int = 0):
        if not (interaction.user.guild_permissions.ban_members or is_owner(interaction.user.id)):
            await interaction.response.send_message("Ban khong co quyen ban 😑", ephemeral=True)
            return
        try:
            await user.send(f"🔨 Ban da bi cam khoi server **{interaction.guild.name}**. Ly do: *{ly_do}*")
        except discord.Forbidden:
            pass
        try:
            await user.ban(reason=ly_do, delete_message_days=max(0, min(7, xoa_tin_nhan_ngay)))
            await interaction.response.send_message(f"🔨 **{user.display_name}** da nhan banh mi chien. Ly do: *{ly_do}*")
        except discord.Forbidden:
            await interaction.response.send_message("Khong du quyen ban.", ephemeral=True)

    @app_commands.command(name="unban", description="Go cam cho nguoi dung (theo ID hoac ten).")
    async def unban(self, interaction: discord.Interaction, user_id: str):
        if not (interaction.user.guild_permissions.ban_members or is_owner(interaction.user.id)):
            await interaction.response.send_message("Khong co quyen 🙅", ephemeral=True)
            return
        try:
            uid = int(user_id)
            await interaction.guild.unban(discord.Object(id=uid))
            await interaction.response.send_message(f"🔓 Da go cam cho user ID `{uid}`. Lan sau deo nha di nhe!")
        except ValueError:
            await interaction.response.send_message("User ID phai la mot con so.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("Nguoi nay khong co trong danh sach cam.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Khong du quyen.", ephemeral=True)

    # ---------------- Tien ich quan ly ----------------
    @app_commands.command(name="purge", description="Xoa so luong tin nhan gan day trong kenh.")
    @app_commands.describe(so_luong="So tin nhan can xoa (1-100)")
    async def purge(self, interaction: discord.Interaction, so_luong: int):
        if not (interaction.user.guild_permissions.manage_messages or is_owner(interaction.user.id)):
            await interaction.response.send_message("Khong co quyen don dep 🧹❌", ephemeral=True)
            return
        if so_luong < 1 or so_luong > 100:
            await interaction.response.send_message("So luong hop le: 1 - 100.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=so_luong)
        await interaction.followup.send(f"🧹 Da don **{len(deleted)}** tin nhan. Sach bong luon!")

    @app_commands.command(name="slowmode", description="Dat che do cham cho kenh (giay).")
    @app_commands.describe(giay="So giay (0 = tat)")
    async def slowmode(self, interaction: discord.Interaction, giay: int):
        if not (interaction.user.guild_permissions.manage_channels or is_owner(interaction.user.id)):
            await interaction.response.send_message("Khong co quyen 🙅", ephemeral=True)
            return
        giay = max(0, min(21600, giay))
        await interaction.channel.edit(slowmode_delay=giay)
        msg = f"🐌 Slowmode: **{giay} giay**/tin nhan." if giay else "🚀 Da tat slowmode."
        await interaction.response.send_message(msg)

    @app_commands.command(name="dm", description="Nhan tin rieng den thanh vien (Admin/Mod).")
    @app_commands.describe(user="Nguoi nhan", noi_dung="Noi dung tin nhan")
    async def dm(self, interaction: discord.Interaction, user: discord.Member, noi_dung: str):
        if not (interaction.user.guild_permissions.manage_messages or is_owner(interaction.user.id)):
            await interaction.response.send_message("Lenh nay danh cho admin/mod thoi nhe 😉", ephemeral=True)
            return
        try:
            await user.send(f"📩 **Tin nhan tu {interaction.guild.name}** (tu {interaction.user.display_name}):\n{noi_dung}")
            await interaction.response.send_message(f"📨 Da gui tin nhan rieng cho **{user.display_name}**.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Nguoi nay tat DM, khong gui duoc.", ephemeral=True)

    @app_commands.command(name="setmodlog", description="Dat kenh nhat ky dieu hanh (mod log).")
    async def setmodlog(self, interaction: discord.Interaction, kenh: discord.TextChannel):
        if not (interaction.user.guild_permissions.manage_guild or is_owner(interaction.user.id)):
            await interaction.response.send_message("Can quyen quan ly server 🙅", ephemeral=True)
            return
        self.modlog[interaction.guild.id] = kenh.id
        await interaction.response.send_message(f"📋 Mod log se duoc gui vao {kenh.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
