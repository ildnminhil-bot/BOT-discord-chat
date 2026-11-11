"""
Cog Nhac nho: /remind - dat lich nhac viec, bot se nhac trong kenh hoac nhan DM.
Luu y: du lieu nhac nho luu trong RAM, mat khi bot restart (Render free hoi
phai chiu, muon ben lau hon co the noi them database sau).
"""
import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks


class Reminders(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # [ {id, user_id, channel_id, guild_id, message, dm, fire_at} ]
        self.reminders: list = []
        self._next_id = 1
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    # ---------------- Vong lap kiem tra ----------------
    @tasks.loop(seconds=15)
    async def check_reminders(self):
        now = time.time()
        due = [r for r in self.reminders if r["fire_at"] <= now]
        for r in due:
            self.reminders.remove(r)
            asyncio.create_task(self._fire(r))

    @check_reminders.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def _fire(self, r: dict):
        try:
            user = self.bot.get_user(r["user_id"]) or await self.bot.fetch_user(r["user_id"])
            text = f"⏰ **Nhac nho:** {r['message']}"
            if r["dm"]:
                await user.send(text)
                return
            channel = self.bot.get_channel(r["channel_id"])
            if channel:
                await channel.send(f"{user.mention} {text}")
            else:
                await user.send(text)
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[REMIND LOI] {e}")

    # ---------------- Lenh ----------------
    @app_commands.command(name="remind", description="Dat loi nhac nho sau mot khoang thoi gian.")
    @app_commands.describe(
        thoi_gian="VD: 10m, 2h, 1d, 30s",
        noi_dung="Noi dung can nhac",
        dm="True = nhan qua tin nhan rieng",
    )
    async def remind(self, interaction: discord.Interaction, thoi_gian: str, noi_dung: str, dm: bool = False):
        seconds = self.parse_time(thoi_gian)
        if seconds is None or seconds <= 0 or seconds > 30 * 24 * 3600:
            await interaction.response.send_message(
                "Dinh dang thoi gian khong hop le. Dung: `30s`, `10m`, `2h`, `1d` (toi da 30 ngay).",
                ephemeral=True,
            )
            return
        if not noi_dung.strip():
            await interaction.response.send_message("Noi dung nhac nho dang trong kia ban oi.", ephemeral=True)
            return
        r = {
            "id": self._next_id,
            "user_id": interaction.user.id,
            "channel_id": interaction.channel_id,
            "guild_id": interaction.guild_id,
            "message": noi_dung.strip(),
            "dm": dm,
            "fire_at": time.time() + seconds,
        }
        self._next_id += 1
        self.reminders.append(r)
        when = time.strftime("%H:%M:%S %d/%m", time.localtime(r["fire_at"]))
        mode = "qua DM" if dm else f"tai {interaction.channel.mention}"
        await interaction.response.send_message(
            f"⏰ Da hen gio! **{noi_dung.strip()}** - se nhac ban **{when}** {mode}."
        )

    @app_commands.command(name="remindlist", description="Xem danh sach nhac nho cua ban.")
    async def remindlist(self, interaction: discord.Interaction):
        mine = [r for r in self.reminders if r["user_id"] == interaction.user.id]
        if not mine:
            await interaction.response.send_message("Ban khong co loi nhac nho nao het. That su quen lam~ 😴")
            return
        lines = []
        for r in mine[:15]:
            when = time.strftime("%H:%M %d/%m", time.localtime(r["fire_at"]))
            mode = "DM" if r["dm"] else "Kenh"
            lines.append(f"`#{r['id']}` [{when}] ({mode}) - {r['message'][:60]}")
        await interaction.response.send_message("📋 **Danh sach nhac nho:**\n" + "\n".join(lines))

    @app_commands.command(name="remindcancel", description="Huy mot loi nhac nho theo ID.")
    async def remindcancel(self, interaction: discord.Interaction, remind_id: int):
        for r in list(self.reminders):
            if r["id"] == remind_id and r["user_id"] == interaction.user.id:
                self.reminders.remove(r)
                await interaction.response.send_message(f"❌ Da huy nhac nho `#{remind_id}`.")
                return
        await interaction.response.send_message("Khong tim thay nhac nho nay (hoac khong phai cua ban).", ephemeral=True)

    # ---------------- Tien ich ----------------
    @staticmethod
    def parse_time(text: str):
        """'10m' -> 600, '2h' -> 7200, '1d' -> 86400, '30s' -> 30."""
        text = text.strip().lower()
        if len(text) < 2:
            return None
        unit = text[-1]
        try:
            num = float(text[:-1])
        except ValueError:
            return None
        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        if unit not in mult:
            return None
        return int(num * mult[unit])


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminders(bot))
