import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio
import os

# ================== CONFIG ==================
TOKEN = os.getenv("DISCORD_TOKEN")  # ตั้งค่าใน Render environment variable
ATTENDANCE_CHANNEL_ID = 1458496060543733928  # ห้องที่บอททำงาน
REQUIRED_TEXT = "˚₊‧ ɢᴍʙ ‧₊˚"
ALLOWED_ROLE_IDS = [1265593210399490058, 1452731313512779849]  # role ที่สามารถเช็คชื่อซ้ำได้
# ============================================

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not found in environment variables")

# ================== GLOBAL ==================
checked_in_users = set()  # เก็บ user.id ของคนที่เช็คชื่อแล้ว

# ================== BOT ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== MODAL ==================
class CheckinModal(discord.ui.Modal, title="เช็คชื่อ"):
    note = discord.ui.TextInput(
        label="หมายเหตุ",
        placeholder="ชื่อภายในเกม / ใช้เพื่อยืนยันตัวตน",
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        # ตรวจสอบ role ก่อนจำกัดเช็คชื่อซ้ำ
        member_roles = [role.id for role in interaction.user.roles]
        allowed = any(role_id in ALLOWED_ROLE_IDS for role_id in member_roles)

        if not allowed and interaction.user.id in checked_in_users:
            await interaction.response.send_message(
                "❌ คุณได้เช็คชื่อแล้ววันนี้", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "📸 กรุณาส่งรูปเล่นกับคนในกิลภายในเกม เพื่อยืนยันภายใน 60 วินาที",
            ephemeral=True
        )

        def check(msg: discord.Message):
            return (
                msg.author == interaction.user
                and msg.channel == interaction.channel
                and len(msg.attachments) > 0
            )

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ หมดเวลา กรุณาลองใหม่", ephemeral=True)
            return

        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%H:%M:%S")

        log_channel = bot.get_channel(ATTENDANCE_CHANNEL_ID)
        if log_channel is None:
            await interaction.followup.send("❌ ไม่พบห้องเก็บข้อมูล", ephemeral=True)
            return

        embed = discord.Embed(
            title="📸 Attendance Check-in",
            color=0x2ecc71
        )
        embed.add_field(name="👤 ผู้ใช้", value=interaction.user.mention, inline=False)
        embed.add_field(name="📅 วันที่", value=today, inline=True)
        embed.add_field(name="⏰ เวลา", value=now, inline=True)
        embed.add_field(name="📝 หมายเหตุ", value=self.note.value or "-", inline=False)
        embed.set_image(url=msg.attachments[0].url)

        await log_channel.send(embed=embed)

        if not allowed:
            checked_in_users.add(interaction.user.id)

        await interaction.followup.send("✅ เช็คชื่อสำเร็จแล้ว", ephemeral=True)

# ================== VIEW / BUTTON ==================
class CheckinView(discord.ui.View):
    @discord.ui.button(label="เช็คชื่อ", style=discord.ButtonStyle.success)
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ใช้เฉพาะห้องที่กำหนด
        if interaction.channel.id != ATTENDANCE_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ คำสั่งนี้ใช้ได้เฉพาะห้อง <#{ATTENDANCE_CHANNEL_ID}> เท่านั้น",
                ephemeral=True
            )
            return

        display_name = interaction.user.display_name

        if REQUIRED_TEXT not in display_name:
            await interaction.response.send_message(
                f"❌ กรุณาตั้งชื่อให้มีคำว่า `{REQUIRED_TEXT}` ก่อนเช็คชื่อ\n"
                f"ตัวอย่าง: `001 ˚₊‧ ɢᴍʙ ‧₊˚ BANANA`",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(CheckinModal())

# ================== SLASH COMMAND ==================
@bot.tree.command(name="gmb", description="ระบบเช็คชื่อ")
async def gmb(interaction: discord.Interaction):
    # ใช้เฉพาะห้องที่กำหนด
    if interaction.channel.id != ATTENDANCE_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ คำสั่งนี้ใช้ได้เฉพาะห้อง <#{ATTENDANCE_CHANNEL_ID}> เท่านั้น",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "📌 กดปุ่มด้านล่างเพื่อเช็คชื่อ",
        view=CheckinView()
    )

# ================== READY ==================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot ready as {bot.user}")

# ================== KEEP ALIVE ==================
bot.run(TOKEN)
