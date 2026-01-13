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
checked_in_users = set()

# ✅ เพิ่มแค่นี้
attendance_enabled = True
# ==============================

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
        member_roles = [role.id for role in interaction.user.roles]
        allowed = any(role_id in ALLOWED_ROLE_IDS for role_id in member_roles)

        if not allowed and interaction.user.id in checked_in_users:
            await interaction.response.send_message(
                "❌ คุณได้เช็คชื่อแล้วในสัปดาห์นี้",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "📸 กรุณาส่งรูปเล่นกับคนในกิลเพื่อยืนยันภายใน 60 วินาที",
            ephemeral=True
        )

        def check(msg: discord.Message):
            return (
                msg.author == interaction.user
                and msg.channel == interaction.channel
                and msg.attachments
            )

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ หมดเวลา กรุณาลองใหม่", ephemeral=True)
            return

        log_channel = bot.get_channel(ATTENDANCE_LOG_CHANNEL_ID)
        if not log_channel:
            await interaction.followup.send("❌ ไม่พบห้องเก็บข้อมูล", ephemeral=True)
            return

        embed = discord.Embed(title="📸 Attendance Check-in", color=0x2ecc71)
        embed.add_field(name="👤 ผู้ใช้", value=interaction.user.mention, inline=False)
        embed.add_field(name="📅 วันที่", value=datetime.now().strftime("%Y-%m-%d"))
        embed.add_field(name="⏰ เวลา", value=datetime.now().strftime("%H:%M:%S"))
        embed.add_field(name="📝 หมายเหตุ", value=self.note.value or "-")
        embed.set_image(url=msg.attachments[0].url)

        await log_channel.send(embed=embed)

        if not allowed:
            checked_in_users.add(interaction.user.id)

        await interaction.followup.send("✅ เช็คชื่อสำเร็จแล้ว", ephemeral=True)
# ==========================================

# ================== VIEW ==================
class CheckinView(discord.ui.View):
    @discord.ui.button(label="เช็คชื่อ", style=discord.ButtonStyle.success)
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ✅ เพิ่มเช็คเปิด/ปิด
        if not attendance_enabled:
            await interaction.response.send_message(
                "⛔ ระบบเช็คชื่อถูกปิดอยู่",
                ephemeral=True
            )
            return

        if interaction.channel.id != ATTENDANCE_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ ใช้ได้เฉพาะห้อง <#{ATTENDANCE_CHANNEL_ID}>",
                ephemeral=True
            )
            return

        if REQUIRED_TEXT not in interaction.user.display_name:
            await interaction.response.send_message(
                f"❌ กรุณาตั้งชื่อให้มีคำว่า {REQUIRED_TEXT}",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(CheckinModal())
# ==========================================

# ================== SLASH COMMAND ==================
@bot.tree.command(name="gmb", description="ระบบเช็คชื่อ")
async def gmb(interaction: discord.Interaction):
    # ✅ เพิ่มเช็คเปิด/ปิด
    if not attendance_enabled:
        await interaction.response.send_message(
            "⛔ ระบบเช็คชื่อถูกปิดอยู่",
            ephemeral=True
        )
        return

    if interaction.channel.id != ATTENDANCE_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ ใช้ได้เฉพาะห้อง <#{ATTENDANCE_CHANNEL_ID}>",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "📌 กดปุ่มด้านล่างเพื่อเช็คชื่อ",
        view=CheckinView()
    )


# ✅ คำสั่งเดียวที่เพิ่ม
@bot.tree.command(
    name="gmb_toggle",
    description="เปิด/ปิดรับเช็คชื่อ",
    guild=discord.Object(id=GUILD_ID)
)
async def gmb_toggle(interaction: discord.Interaction):
    global attendance_open

    # เช็ค role
    if not any(role.id in TOGGLE_ROLE_IDS for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้",
            ephemeral=True
        )
        return

    attendance_open = not attendance_open

    await interaction.response.send_message(
        "🟢 เปิดรับเช็คชื่อแล้ว"
        if attendance_open
        else "🔴 ปิดรับเช็คชื่อแล้ว",
        ephemeral=True
    )

# ================================================

# ================== READY ==================
@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.loop.create_task(reset_checked_in_users_weekly())
    print(f"[INFO] Bot ready as {bot.user}")
# ==========================================

bot.run(TOKEN)
