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

ATTENDANCE_CHANNEL_ID = 1458496060543733928
ATTENDANCE_LOG_CHANNEL_ID = 1459577266194612224

REQUIRED_TEXT = "˚₊‧ ɢᴍʙ ‧₊˚"

ALLOWED_ROLE_IDS = [1265593210399490058, 1452731313512779849]
TOGGLE_ROLE_IDS = [1265593210399490058]  # 🔥 role ที่สั่ง /gmb_toggle ได้

RESET_WEEKDAY = 0  # Monday
RESET_HOUR = 5     # 05:00
# ============================================

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not found")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== GLOBAL STATE ==================
checked_in_users = set()
attendance_open = True

# ================== FLASK (Render keep alive) ==================
app = Flask("")

@app.route("/")
def home():
    return "Bot is running"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_flask, daemon=True).start()

# ================== WEEKLY RESET ==================
async def reset_checked_in_users_weekly():
    await bot.wait_until_ready()
    while True:
        now = datetime.now()
        days = RESET_WEEKDAY - now.weekday()
        if days <= 0:
            days += 7

        next_reset = now.replace(
            hour=RESET_HOUR, minute=0, second=0, microsecond=0
        ) + timedelta(days=days)

        await asyncio.sleep((next_reset - now).total_seconds())
        checked_in_users.clear()

        ch = bot.get_channel(ATTENDANCE_LOG_CHANNEL_ID)
        if ch:
            await ch.send("🔔 เริ่มสัปดาห์ใหม่ สามารถเช็คชื่อได้อีกครั้ง!")

# ================== MODAL ==================
class CheckinModal(discord.ui.Modal, title="เช็คชื่อ"):
    note = discord.ui.TextInput(
        label="หมายเหตุ",
        placeholder="ชื่อในเกม / ใช้ยืนยันตัวตน",
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        roles = [r.id for r in interaction.user.roles]
        allowed = any(r in ALLOWED_ROLE_IDS for r in roles)

        if not allowed and interaction.user.id in checked_in_users:
            await interaction.response.send_message(
                "❌ คุณเช็คชื่อไปแล้วในสัปดาห์นี้",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "📸 ส่งรูปเล่นกับคนในกิลภายใน 60 วินาที",
            ephemeral=True
        )

        def check(msg: discord.Message):
            return (
                msg.author == interaction.user
                and msg.channel == interaction.channel
                and msg.attachments
            )

        try:
            msg = await bot.wait_for("message", timeout=60, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ หมดเวลา", ephemeral=True)
            return

        log = bot.get_channel(ATTENDANCE_LOG_CHANNEL_ID)
        if not log:
            return

        embed = discord.Embed(
            title="📸 Attendance Check-in",
            color=0x2ecc71
        )
        embed.add_field(name="👤 ผู้ใช้", value=interaction.user.mention, inline=False)
        embed.add_field(name="📅 วันที่", value=datetime.now().strftime("%Y-%m-%d"))
        embed.add_field(name="⏰ เวลา", value=datetime.now().strftime("%H:%M:%S"))
        embed.add_field(name="📝 หมายเหตุ", value=self.note.value or "-")
        embed.set_image(url=msg.attachments[0].url)

        await log.send(embed=embed)

        if not allowed:
            checked_in_users.add(interaction.user.id)

        await interaction.followup.send("✅ เช็คชื่อสำเร็จ", ephemeral=True)

# ================== VIEW ==================
class CheckinView(discord.ui.View):
    @discord.ui.button(label="เช็คชื่อ", style=discord.ButtonStyle.success)
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):
        global attendance_open

        if not attendance_open:
            await interaction.response.send_message(
                "🔴 ปิดรับเช็คชื่อชั่วคราว",
                ephemeral=True
            )
            return

        if interaction.channel.id != ATTENDANCE_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ ใช้คำสั่งนี้ในห้องที่กำหนดเท่านั้น",
                ephemeral=True
            )
            return

        if REQUIRED_TEXT not in interaction.user.display_name:
            await interaction.response.send_message(
                f"❌ กรุณาตั้งชื่อให้มี `{REQUIRED_TEXT}`",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(CheckinModal())

# ================== SLASH COMMANDS ==================
@bot.tree.command(name="gmb", description="ระบบเช็คชื่อ")
async def gmb(interaction: discord.Interaction):
    if interaction.channel.id != ATTENDANCE_CHANNEL_ID:
        await interaction.response.send_message(
            "❌ ใช้ได้เฉพาะห้องที่กำหนด",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "📌 กดปุ่มเพื่อเช็คชื่อ",
        view=CheckinView()
    )

@bot.tree.command(name="gmb_toggle", description="เปิด/ปิดรับเช็คชื่อ")
async def gmb_toggle(interaction: discord.Interaction):
    global attendance_open

    if not any(r.id in TOGGLE_ROLE_IDS for r in interaction.user.roles):
        await interaction.response.send_message(
            "❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้",
            ephemeral=True
        )
        return

    attendance_open = not attendance_open
    status = "🟢 เปิดรับเช็คชื่อแล้ว" if attendance_open else "🔴 ปิดรับเช็คชื่อแล้ว"
    await interaction.response.send_message(status)

# ================== READY ==================
@bot.event
async def on_ready():
    await bot.tree.clear_commands(guild=None)  # 🔥 สำคัญที่สุด
    await bot.tree.sync()
    bot.loop.create_task(reset_checked_in_users_weekly())
    print(f"[READY] Logged in as {bot.user}")

# ================== RUN ==================
bot.run(TOKEN)
