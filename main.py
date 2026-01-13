import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import os
import threading
from flask import Flask

# ================== CONFIG ==================
TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1265593210269339782

ATTENDANCE_CHANNEL_ID = 1458496060543733928
ATTENDANCE_LOG_CHANNEL_ID = 1459577266194612224

REQUIRED_TEXT = "˚₊‧ ɢᴍʙ ‧₊˚"
ALLOWED_ROLE_IDS = [1265593210399490058, 1452731313512779849]
TOGGLE_ROLE_IDS = [1265593210399490058, 1452731313512779849, 1265593210269339787]

RESET_WEEKDAY = 0
RESET_HOUR = 5
# ============================================

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not found in environment variables")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== STATE ==================
checked_in_users = {}  # {user_id: {"last_date": "YYYY-MM-DD", "count": int}}
attendance_enabled = True
# ==========================================

# ================== FLASK ==================
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_flask).start()
# ===========================================

# ================== RESET WEEKLY ==================
async def reset_checked_in_users_weekly():
    await bot.wait_until_ready()
    while True:
        now = datetime.now()
        days_ahead = RESET_WEEKDAY - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7

        next_reset = now.replace(
            hour=RESET_HOUR, minute=0, second=0, microsecond=0
        ) + timedelta(days=days_ahead)

        await asyncio.sleep((next_reset - now).total_seconds())

        checked_in_users.clear()
        log_channel = bot.get_channel(ATTENDANCE_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send("🔔 เริ่มสัปดาห์ใหม่ สามารถเช็คชื่อได้อีกครั้ง!")
# ================================================

# ================== MODAL ==================
class CheckinModal(discord.ui.Modal, title="เช็คชื่อ"):
    note = discord.ui.TextInput(
        label="หมายเหตุ",
        placeholder="ชื่อในเกม / ใช้ยืนยันตัวตน",
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        today_str = datetime.now().strftime("%Y-%m-%d")
        member_roles = [role.id for role in interaction.user.roles]
        allowed = any(role_id in ALLOWED_ROLE_IDS for role_id in member_roles)

        # กันคนเช็คซ้ำ
        if interaction.user.id in checked_in_users and checked_in_users[interaction.user.id]["last_date"] == today_str:
            await interaction.response.send_message(
                "❌ คุณได้เช็คชื่อแล้ววันนี้",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "📸 กรุณาส่งรูปเล่นกับคนในกิลเพื่อยืนยันภายใน 60 วินาที",
            ephemeral=True
        )

        def check_image(msg: discord.Message):
            return (
                msg.author == interaction.user
                and msg.channel == interaction.channel
                and msg.attachments
            )

        try:
            image_msg = await bot.wait_for("message", check=check_image, timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ หมดเวลา กรุณาลองใหม่", ephemeral=True)
            return

        await interaction.followup.send(
            "👥 กรุณาแท็กเพื่อนที่เล่นด้วย (อย่างน้อย 1 คน) ภายใน 60 วินาที",
            ephemeral=True
        )

        def check_tag(msg: discord.Message):
            return (
                msg.author == interaction.user
                and msg.channel == interaction.channel
                and msg.mentions
            )

        try:
            tag_msg = await bot.wait_for("message", check=check_tag, timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "❌ ไม่พบการแท็กเพื่อน กรุณาเริ่มใหม่",
                ephemeral=True
            )
            return

        log_channel = bot.get_channel(ATTENDANCE_LOG_CHANNEL_ID)
        if not log_channel:
            await interaction.followup.send("❌ ไม่พบห้องเก็บข้อมูล", ephemeral=True)
            return

        tagged_users = ", ".join(user.mention for user in tag_msg.mentions)

        embed = discord.Embed(title="📸 Attendance Check-in", color=0x2ecc71)
        embed.add_field(name="👤 ผู้ใช้", value=interaction.user.mention, inline=False)
        embed.add_field(name="👥 เล่นกับ", value=tagged_users, inline=False)
        embed.add_field(name="📅 วันที่", value=today_str)
        embed.add_field(name="⏰ เวลา", value=datetime.now().strftime("%H:%M:%S"))
        embed.add_field(name="📝 หมายเหตุ", value=self.note.value or "-")
        embed.set_image(url=image_msg.attachments[0].url)

        await log_channel.send(embed=embed)

        # บันทึกผู้ใช้ลง checked_in_users
        if interaction.user.id in checked_in_users:
            checked_in_users[interaction.user.id]["last_date"] = today_str
            checked_in_users[interaction.user.id]["count"] += 1
        else:
            checked_in_users[interaction.user.id] = {"last_date": today_str, "count": 1}

        await inte
