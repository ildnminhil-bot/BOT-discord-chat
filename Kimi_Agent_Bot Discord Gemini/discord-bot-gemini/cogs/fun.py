"""
Cog Fun: mini-games, tro choi, lenh vui nham giai tri cho server.
"""
import random

import discord
from discord import app_commands
from discord.ext import commands

BALL_ANSWERS = [
    "Chac chan roi! Minh ma noi sai minh nhay xuong song 🌊",
    "Co ve nhu dung day... hoac ban bi lua, ai biet duoc 🤷",
    "Khong dau ban oi. Dung hoi nua, hoi mai cung the thoi.",
    "Rat co the! Nhung dung trach minh neu sai nhe.",
    "Minh dang ban xem phim, hoi lai sau di... ok thi **DUNG**.",
    "Sao khong? Cu thu di, doi khong giu giay to ma.",
    "Xac suat 50/50. Tung dong xu di cho nhanh.",
    "Hoi thang Google di, minh chi la bot nho bet thoi 😤",
    "Tra loi nam trong trai tim ban. Minh khong dam doc.",
    "Thien co! (Khong biet nghia la gi nhung nghe hay).",
]

ROASTS = [
    "Ban oi, WiFi nha ban manh hon guong mat ban nhieu 😌",
    "Neu su ngu ngoc la diem, ban da pha ky luc the gioi roi.",
    "Ban khong xau, chi la hinh thu ban dang thay doi theo thoi tian thoi.",
    "IQ ban cao den muc... khiem ton qua nen giau di a?",
    "Ban la ly do nguoi ta phat minh ra nut 'block'.",
    "Nhin ban minh hieu tai sao me ban hay thang mat ca dem roi.",
]

COMPLIMENTS = [
    "Hom nay ban trong that tuyet voi! A, xin loi, minh bi lo mat khau de lai tu may chu cu~ 😇",
    "Ban la nguoi thu vi day! That day, khong dua dau. Ok hoi dua chut.",
    "Neu server nay la lop hoc, ban la ban duoc phat hong hoa ay.",
    "Nu cuoi ban sang hon ca den neon cua ca quan net.",
]


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="8ball", description="Hoi qua cau than ky (tra loi chan that 100%).")
    async def eightball(self, interaction: discord.Interaction, cau_hoi: str):
        ans = random.choice(BALL_ANSWERS)
        await interaction.response.send_message(f"🎱 **Cau hoi:** {cau_hoi}\n**Tra loi:** {ans}")

    @app_commands.command(name="coinflip", description="Tung dong xu.")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["🪙 Mat SAP!", "🪙 Mat NGUA!"])
        await interaction.response.send_message(result)

    @app_commands.command(name="dice", description="Tung xuc xac (1-6, co the nhieu vien).")
    async def dice(self, interaction: discord.Interaction, so_vien: int = 1):
        so_vien = max(1, min(10, so_vien))
        rolls = [random.randint(1, 6) for _ in range(so_vien)]
        total = sum(rolls)
        await interaction.response.send_message(f"🎲 Ket qua: {rolls} (tong: **{total}**)")

    @app_commands.command(name="roast", description="Xin bot ca khia mot chut nhe.")
    @app_commands.describe(user="Nguoi muon bi ca khia (khong de trong = ca khia ban)")
    async def roast(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        roast = random.choice(ROASTS)
        await interaction.response.send_message(f"{target.mention} {roast}")

    @app_commands.command(name="compliment", description="Bot khen nguoi khac (hoac khen ban).")
    async def compliment(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        comp = random.choice(COMPLIMENTS)
        await interaction.response.send_message(f"{target.mention} {comp}")

    @app_commands.command(name="poll", description="Tao binh chon nhanh trong kenh.")
    @app_commands.describe(cau_hoi="Cau hoi binh chon", lua_chon_1="Lua chon 1", lua_chon_2="Lua chon 2",
                           lua_chon_3="Lua chon 3 (tuy chon)", lua_chon_4="Lua chon 4 (tuy chon)")
    async def poll(self, interaction: discord.Interaction, cau_hoi: str, lua_chon_1: str, lua_chon_2: str,
                   lua_chon_3: str = None, lua_chon_4: str = None):
        options = [o for o in (lua_chon_1, lua_chon_2, lua_chon_3, lua_chon_4) if o]
        if len(options) < 2:
            await interaction.response.send_message("Can it nhat 2 lua chon.", ephemeral=True)
            return
        letters = ["🅰️", "🅱️", "🌟", "🔥"]
        desc = "\n".join(f"{letters[i]} {opt}" for i, opt in enumerate(options))
        embed = discord.Embed(
            title=f"📊 {cau_hoi}",
            description=desc + "\n\n*Bam reaction phia duoi de binh chon!*",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Tao boi {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(options)):
            await msg.add_reaction(letters[i])

    @app_commands.command(name="say", description="Bot noi thay loi ban (co the ca khia ho).")
    async def say(self, interaction: discord.Interaction, noi_dung: str):
        await interaction.response.send_message("Da ghi nhan~", ephemeral=True)
        await interaction.channel.send(noi_dung)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
