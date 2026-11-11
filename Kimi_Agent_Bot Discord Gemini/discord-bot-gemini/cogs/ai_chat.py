"""
Cog AI Chat: nho lich su hoi thoai, doc anh/file, persona vui ve hoi che dieu.
Bot tra loi khi: duoc @mention, nhan tin rieng (DM), hoac kenh da bat /chaton.
"""
import asyncio
import base64
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands
from openai import OpenAI

import config


def _build_gemini_client() -> OpenAI:
    return OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_BASE_URL)


class AIChat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gemini = _build_gemini_client()
        # Lich su chat: key = (channel_id, user_id) -> deque cac tin nhan
        self.history: dict = defaultdict(lambda: deque(maxlen=config.HISTORY_LENGTH))
        # Kenh dang o che do chat tu dong
        self.active_channels: set = set()
        # Cai dat nguoi dung
        self.user_settings: dict = defaultdict(
            lambda: {
                "language": config.DEFAULT_LANGUAGE,
                "persona": config.DEFAULT_PERSONA,
            }
        )

    # --------------------- Tien ich ---------------------
    def strip_mention(self, text: str) -> str:
        uid = self.bot.user.id if self.bot.user else 0
        return text.replace(f"<@{uid}>", "").replace(f"<@!{uid}>", "").strip()

    def context_block(self, message: discord.Message) -> str:
        if not message.guild:
            return ""
        block = (
            f"\nBan dang o trong server '{message.guild.name}' "
            f"({message.guild.member_count} thanh vien)."
        )
        members = [m for m in message.guild.members if not m.bot][: config.MAX_MEMBERS_LISTED]
        if members:
            listed = "\n".join(f"- {m.display_name}: <@{m.id}>" for m in members)
            block += f"\nDanh sach thanh vien (dung <@ID> de nhan ai do):\n{listed}"
        others = [m for m in message.mentions if m.id != self.bot.user.id]
        if others:
            tagged = ", ".join(f"{m.display_name} (<@{m.id}>)" for m in others)
            block += f"\nNhung nguoi duoc nhan trong tin nhan nay: {tagged}"
        return block

    async def split_and_send(self, target, text: str, reference=None):
        """Gui tin nhan dai bang cach chia nho, tranh loi 2000 ky tu."""
        if len(text) <= config.MAX_DISCORD_MSG:
            if reference is not None:
                await reference.reply(text)
            else:
                await target.send(text)
            return
        chunks = [text[i : i + config.MAX_DISCORD_MSG] for i in range(0, len(text), config.MAX_DISCORD_MSG)]
        for i, chunk in enumerate(chunks):
            if i == 0 and reference is not None:
                await reference.reply(chunk)
            else:
                await target.send(chunk)

    # --------------------- Lenh slash ---------------------
    @app_commands.command(name="chaton", description="Bat che do bot tu chat trong kenh nay (khong can @bot).")
    async def chat_on(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid in self.active_channels:
            await interaction.response.send_message("Minh da ngoi san trong kenh nay roi, cu tro chuyen thoai mai~ 😎")
        else:
            self.active_channels.add(cid)
            await interaction.response.send_message(
                "🚀 **Bat che do tu dong!** Tu gio minh se nhap hoi chuyen trong kenh nay, "
                "khong can nhan @ nua. Dung `/chatoff` neu thay minh noi nhieu qua."
            )

    @app_commands.command(name="chatoff", description="Tat che do tu dong, can @bot de chat lai.")
    async def chat_off(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid in self.active_channels:
            self.active_channels.discard(cid)
            await interaction.response.send_message("🛑 **Tat che do tu dong.** Muon tro chuyen lai thi nhan @minh nhe.")
        else:
            await interaction.response.send_message("Minh dau co dang tu nhap hoi dau 🤷")

    @app_commands.command(name="reset", description="Xoa sach du lieu va tri nho chat cua ban.")
    async def reset(self, interaction: discord.Interaction):
        self.history.pop((interaction.channel_id, interaction.user.id), None)
        self.user_settings.pop(interaction.user.id, None)
        await interaction.response.send_message("🧹 Xoa sach tri nho ve ban roi. Nhu chua tung gap nhau... *xoa nuoc mat*")

    @app_commands.command(name="clear", description="Xoa lich su chat hien tai (giu nguyen cai dat).")
    async def clear(self, interaction: discord.Interaction):
        self.history.pop((interaction.channel_id, interaction.user.id), None)
        await interaction.response.send_message("🧹 Don sach lich su chat. Bat dau mot cuoc tinh moi~")

    @app_commands.command(name="language", description="Doi ngon ngu mac dinh cua bot.")
    @app_commands.describe(lang="Vi du: Tieng Viet, English, 日本語...")
    async def language(self, interaction: discord.Interaction, lang: str):
        self.user_settings[interaction.user.id]["language"] = lang
        await interaction.response.send_message(f"✅ Ngôn ngữ mac dinh da doi sang: **{lang}**")

    @app_commands.command(name="persona", description="Thay doi tinh cach nhan vat cua bot.")
    @app_commands.describe(mo_ta="Vi du: mot ong gia kho tinh, thich ca khia nhung tam tot")
    async def persona(self, interaction: discord.Interaction, mo_ta: str):
        self.user_settings[interaction.user.id]["persona"] = mo_ta
        await interaction.response.send_message(f"🎭 Ok, gio minh se dong vai:\n> {mo_ta}")

    @app_commands.command(name="settings", description="Xem cai dat hien tai cua ban.")
    async def settings(self, interaction: discord.Interaction):
        prefs = self.user_settings[interaction.user.id]
        embed = discord.Embed(title="⚙️ Cài đặt của bạn", color=discord.Color.green())
        embed.add_field(name="Ngôn ngữ", value=prefs["language"], inline=True)
        embed.add_field(name="Version", value=config.BOT_VERSION, inline=True)
        embed.add_field(name="Persona", value=prefs["persona"][:300], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="history", description="Xem lai doan hoi thoai gan day ma bot nho ve ban.")
    async def history(self, interaction: discord.Interaction):
        key = (interaction.channel_id, interaction.user.id)
        msgs = list(self.history.get(key, []))
        if not msgs:
            await interaction.response.send_message("Minh chua nho gi ve ban ca. Chat voi minh da nao~")
            return
        lines = []
        for m in msgs[-8:]:
            role = "🧑 Bạn" if m["role"] == "user" else "🤖 Bot"
            content = m["content"] if isinstance(m["content"], str) else "[ảnh/file]"
            lines.append(f"**{role}:** {content[:250]}")
        embed = discord.Embed(
            title="🧠 Đoạn hội thoại bot nhớ",
            description="\n\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed)

    # --------------------- Xu ly tin nhan ---------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.bot.user in message.mentions
        in_active = message.channel.id in self.active_channels
        if not (is_dm or is_mentioned or in_active):
            return

        user_text = self.strip_mention(message.content)
        if not user_text and not message.attachments:
            await message.add_reaction("👀")
            return

        try:
            await message.add_reaction("⏳")
        except discord.Forbidden:
            pass

        # Doc dinh kem: anh + file text
        image_parts = []
        file_content = ""
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                if len(image_parts) >= config.MAX_IMAGES_PER_MESSAGE or att.size > config.MAX_IMAGE_BYTES:
                    continue
                try:
                    raw = await att.read()
                    b64 = base64.b64encode(raw).decode("utf-8")
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{att.content_type};base64,{b64}"},
                    })
                except Exception as e:
                    print(f"[LOI DOC ANH] {e}")
            elif att.size < config.MAX_FILE_BYTES and att.filename.endswith(config.TEXT_FILE_EXTENSIONS):
                try:
                    raw = await att.read()
                    file_content += f"\n\n--- Noi dung file {att.filename} ---\n"
                    file_content += raw.decode("utf-8", errors="ignore")[: config.MAX_FILE_CHARS]
                except Exception as e:
                    print(f"[LOI DOC FILE] {e}")

        prompt = (user_text + file_content).strip()
        if not prompt:
            prompt = "Mo ta giup minh noi dung nay." if image_parts else "Chao ban!"

        api_content = ([{"type": "text", "text": prompt}] + image_parts) if image_parts else prompt

        history_text = prompt
        if image_parts:
            history_text += f"\n[Gui {len(image_parts)} anh - khong luu vao bo nho]"

        prefs = self.user_settings[message.author.id]
        system_prompt = (
            f"{prefs['persona']}\n"
            f"- LUON tra loi bang ngon ngu nay (tru khi nguoi dung yeu cau khac): **{prefs['language']}**.\n"
            f"- Nguoi dang noi chuyen voi ban la: '{message.author.display_name}'.\n"
            "- Tra loi ngan gon, di thang van de, dinh dang Markdown khi can.\n"
            "- Co the tha emoji Discord (:smile:...) cho sinh dong."
            + self.context_block(message)
        )

        key = (message.channel.id, message.author.id)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(list(self.history[key]))
        messages.append({"role": "user", "content": api_content})

        async with message.channel.typing():
            try:
                resp = await asyncio.to_thread(
                    self.gemini.chat.completions.create,
                    messages=messages,
                    model=config.GEMINI_MODEL,
                    temperature=0.8,
                    max_tokens=1500,
                )
                reply = resp.choices[0].message.content or "..."
                self.history[key].append({"role": "user", "content": history_text})
                self.history[key].append({"role": "assistant", "content": reply})
                await self.split_and_send(message.channel, reply, reference=message)
                try:
                    await message.remove_reaction("⏳", self.bot.user)
                    await message.add_reaction("✅")
                except discord.Forbidden:
                    pass
            except Exception as e:
                err = str(e)
                print(f"[GEMINI LOI] {err}")
                await message.channel.send(f"⚠️ **Loi tu Gemini:** `{err[:400]}`")
                try:
                    await message.remove_reaction("⏳", self.bot.user)
                    await message.add_reaction("❌")
                except discord.Forbidden:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AIChat(bot))
