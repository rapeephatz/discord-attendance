import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, date
import asyncio
import os
import threading
from flask import Flask

# =============== reg.py ===============
import reg

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
checked_in_users = {}
attendance_enabled = True
checkall_enabled = False
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

def get_week_number(dt: date):
    return dt.isocalendar()[1]

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

# ================== MODAL ==================
class CheckinModal(discord.ui.Modal, title="เช็คชื่อ"):
    note = discord.ui.TextInput(
        label="หมายเหตุ",
        placeholder="ชื่อในเกม / ใช้ยืนยันตัวตน",
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        today = datetime.now().date()
        week_number = get_week_number(today)

        if interaction.user.id in checked_in_users and not checkall_enabled:
            if checked_in_users[interaction.user.id].get("week_number") == week_number:
                await interaction.response.send_message(
                    "❌ คุณได้เช็คชื่อแล้วในสัปดาห์นี้",
                    ephemeral=True
                )
                return

        await interaction.response.send_message(
            "📸 กรุณาส่งรูปเล่นกับคนในกิลเพื่อยืนยันภายใน 60 วินาที",
            ephemeral=True
        )

        def check_image(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel and msg.attachments

        try:
            image_msg = await bot.wait_for("message", check=check_image, timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ หมดเวลา กรุณาลองใหม่", ephemeral=True)
            return

        await interaction.followup.send(
            "👥 กรุณาแท็กเพื่อนที่เล่นด้วย (อย่างน้อย 1 คน) ภายใน 60 วินาที",
            ephemeral=True
        )

        def check_tag(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel and msg.mentions

        try:
            tag_msg = await bot.wait_for("message", check=check_tag, timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ ไม่พบการแท็กเพื่อน กรุณาเริ่มใหม่", ephemeral=True)
            return

        log_channel = bot.get_channel(ATTENDANCE_LOG_CHANNEL_ID)

        embed = discord.Embed(title="📸 Attendance Check-in", color=0x2ecc71)
        embed.add_field(name="👤 ผู้ใช้", value=interaction.user.mention, inline=False)
        embed.add_field(name="👥 เล่นกับ", value=", ".join(u.mention for u in tag_msg.mentions), inline=False)
        embed.add_field(name="📅 วันที่", value=str(today))
        embed.add_field(name="⏰ เวลา", value=datetime.now().strftime("%H:%M:%S"))
        embed.add_field(name="📝 หมายเหตุ", value=self.note.value or "-")
        embed.set_image(url=image_msg.attachments[0].url)

        await log_channel.send(embed=embed)

        if interaction.user.id in checked_in_users:
            checked_in_users[interaction.user.id]["count"] += 1
            checked_in_users[interaction.user.id]["week_number"] = week_number
        else:
            checked_in_users[interaction.user.id] = {
                "count": 1,
                "week_number": week_number
            }

        await interaction.followup.send("✅ เช็คชื่อสำเร็จแล้ว", ephemeral=True)

# ================== VIEW ==================
class CheckinView(discord.ui.View):
    @discord.ui.button(label="เช็คชื่อ", style=discord.ButtonStyle.success)
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not attendance_enabled:
            return await interaction.response.send_message("⛔ ระบบเช็คชื่อถูกปิดอยู่", ephemeral=True)

        if interaction.channel.id != ATTENDANCE_CHANNEL_ID:
            return await interaction.response.send_message(
                f"❌ ใช้ได้เฉพาะห้อง <#{ATTENDANCE_CHANNEL_ID}>",
                ephemeral=True
            )

        if REQUIRED_TEXT not in interaction.user.display_name:
            return await interaction.response.send_message(
                f"❌ กรุณาตั้งชื่อให้มีคำว่า {REQUIRED_TEXT}",
                ephemeral=True
            )

        await interaction.response.send_modal(CheckinModal())

# ================== SLASH ==================
@bot.tree.command(name="gmb", description="ระบบเช็คชื่อ", guild=discord.Object(id=GUILD_ID))
async def gmb(interaction: discord.Interaction):
    await interaction.response.send_message("📌 กดปุ่มด้านล่างเพื่อเช็คชื่อ", view=CheckinView())

# ================== READY ==================
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    await reg.setup(bot)
    bot.add_view(reg.ReviewView(None))

    bot.loop.create_task(reset_checked_in_users_weekly())
    print(f"[INFO] Bot ready as {bot.user}")

bot.run(TOKEN)
