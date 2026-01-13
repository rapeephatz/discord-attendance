import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, date
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
checked_in_users = {}  # {user_id: {"last_date": "YYYY-MM-DD", "week_number": int, "count": int}}
attendance_enabled = True
checkall_enabled = False  # ใช้สำหรับ /gmb_checkall
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

# ================== HELPER ==================
def get_week_number(dt: date):
    return dt.isocalendar()[1]
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
        today = datetime.now().date()
        week_number = get_week_number(today)
        member_roles = [role.id for role in interaction.user.roles]
        allowed = any(role_id in ALLOWED_ROLE_IDS for role_id in member_roles)

        # กันคนเช็คซ้ำรายสัปดาห์
        if interaction.user.id in checked_in_users:
            if not checkall_enabled and checked_in_users[interaction.user.id].get("week_number") == week_number:
                await interaction.response.send_message(
                    "❌ คุณได้เช็คชื่อแล้วในสัปดาห์นี้",
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
        embed.add_field(name="📅 วันที่", value=str(today))
        embed.add_field(name="⏰ เวลา", value=datetime.now().strftime("%H:%M:%S"))
        embed.add_field(name="📝 หมายเหตุ", value=self.note.value or "-")
        embed.set_image(url=image_msg.attachments[0].url)

        await log_channel.send(embed=embed)

        # บันทึกผู้ใช้
        if interaction.user.id in checked_in_users:
            checked_in_users[interaction.user.id]["count"] += 1
            checked_in_users[interaction.user.id]["week_number"] = week_number
            checked_in_users[interaction.user.id]["last_date"] = str(today)
        else:
            checked_in_users[interaction.user.id] = {
                "count": 1,
                "week_number": week_number,
                "last_date": str(today)
            }

        await interaction.followup.send("✅ เช็คชื่อสำเร็จแล้ว", ephemeral=True)

# ================== VIEW ==================
class CheckinView(discord.ui.View):
    @discord.ui.button(label="เช็คชื่อ", style=discord.ButtonStyle.success)
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):
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

        today = datetime.now().date()
        week_number = get_week_number(today)
        if interaction.user.id in checked_in_users and not checkall_enabled:
            if checked_in_users[interaction.user.id].get("week_number") == week_number:
                await interaction.response.send_message(
                    "❌ คุณได้เช็คชื่อแล้วในสัปดาห์นี้",
                    ephemeral=True
                )
                return

        await interaction.response.send_modal(CheckinModal())

# ================== SLASH COMMANDS ==================
@bot.tree.command(name="gmb", description="ระบบเช็คชื่อ")
async def gmb(interaction: discord.Interaction):
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

@bot.tree.command(
    name="gmb_toggle",
    description="เปิด/ปิดรับเช็คชื่อ",
    guild=discord.Object(id=GUILD_ID)
)
async def gmb_toggle(interaction: discord.Interaction):
    global attendance_enabled

    if not any(role.id in TOGGLE_ROLE_IDS for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้",
            ephemeral=True
        )
        return

    attendance_enabled = not attendance_enabled

    await interaction.response.send_message(
        "🟢 เปิดรับเช็คชื่อแล้ว"
        if attendance_enabled
        else "🔴 ปิดรับเช็คชื่อแล้ว",
        ephemeral=True
    )

@bot.tree.command(
    name="gmb_list",
    description="ดูรายชื่อคนที่เช็คชื่อแล้วตอนนี้",
    guild=discord.Object(id=GUILD_ID)
)
async def gmb_list(interaction: discord.Interaction):
    if not checked_in_users:
        await interaction.response.send_message(
            "📭 ตอนนี้ยังไม่มีใครเช็คชื่อ",
            ephemeral=True
        )
        return

    members_info = []
    for user_id, data in checked_in_users.items():
        member = interaction.guild.get_member(user_id)
        if member:
            members_info.append(
                f"{member.mention} — วันที่ล่าสุด: {data['last_date']} — เช็ค {data['count']} ครั้ง"
            )

    embed = discord.Embed(
        title="📋 รายชื่อผู้เช็คชื่อแล้ว",
        color=0x3498db
    )
    embed.add_field(
        name=f"ทั้งหมด {len(members_info)} คน",
        value="\n".join(members_info),
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(
    name="gmb_reset",
    description="รีเซ็ตการเช็คชื่อของผู้ใช้",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(member="เลือกผู้ใช้ที่จะรีเซ็ต")
async def gmb_reset(interaction: discord.Interaction, member: discord.Member):
    if not any(role.id in TOGGLE_ROLE_IDS for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้",
            ephemeral=True
        )
        return

    if member.id in checked_in_users:
        del checked_in_users[member.id]
        await interaction.response.send_message(
            f"✅ รีเซ็ตการเช็คชื่อของ {member.mention} เรียบร้อยแล้ว",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"ℹ️ {member.mention} ยังไม่ได้เช็คชื่อ",
            ephemeral=True
        )

# ================== NEW COMMANDS ==================
@bot.tree.command(
    name="gmb_checksum",
    description="ให้ผู้ใช้เช็คชื่อซ้ำ",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(member="เลือกผู้ใช้ที่จะเช็คชื่อซ้ำ")
async def gmb_checksum(interaction: discord.Interaction, member: discord.Member):
    if not any(role.id in TOGGLE_ROLE_IDS for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้",
            ephemeral=True
        )
        return

    today = datetime.now().date()
    week_number = get_week_number(today)

    # เพิ่ม count โดยไม่ตรวจซ้ำ
    if member.id in checked_in_users:
        checked_in_users[member.id]["count"] += 1
        checked_in_users[member.id]["last_date"] = str(today)
        checked_in_users[member.id]["week_number"] = week_number
    else:
        checked_in_users[member.id] = {
            "count": 1,
            "last_date": str(today),
            "week_number": week_number
        }

    await interaction.response.send_message(
        f"✅ {member.mention} สามารถเช็คชื่อซ้ำได้แล้ว",
        ephemeral=True
    )

@bot.tree.command(
    name="gmb_checkall",
    description="เปิดให้ผู้ใช้เช็คชื่อซ้ำทุกคน",
    guild=discord.Object(id=GUILD_ID)
)
async def gmb_checkall(interaction: discord.Interaction):
    global checkall_enabled
    if not any(role.id in TOGGLE_ROLE_IDS for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้",
            ephemeral=True
        )
        return

    checkall_enabled = True
    await interaction.response.send_message(
        "✅ เปิดให้ผู้ใช้ที่มี role เช็คชื่อซ้ำได้แล้ว",
        ephemeral=True
    )

@bot.tree.command(
    name="gmb_check",
    description="ดูจำนวนครั้งที่ผู้ใช้เช็คชื่อ",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(member="เลือกผู้ใช้เพื่อตรวจสอบ")
async def gmb_check(interaction: discord.Interaction, member: discord.Member):
    if member.id not in checked_in_users:
        await interaction.response.send_message(
            f"ℹ️ {member.mention} ยังไม่ได้เช็คชื่อ",
            ephemeral=True
        )
        return

    data = checked_in_users[member.id]
    await interaction.response.send_message(
        f"📌 {member.mention} เช็คชื่อไปแล้ว {data['count']} ครั้ง ล่าสุด: {data['last_date']}",
        ephemeral=True
    )

# ================== READY ==================
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    bot.loop.create_task(reset_checked_in_users_weekly())
    print(f"[INFO] Bot ready as {bot.user}")

# ==========================================

bot.run(TOKEN)
