import discord
from discord.ext import commands
from discord import app_commands
import asyncio

GUILD_REVIEW_CHANNEL_ID = 1459577266194612224
ADMIN_ROLE_IDS = [
    1265593210399490058 #CEO ROLE
    1461210572589891757 #POLICY
    1460590568370606122 #CODE
    1461209644826497105 #COMMUNITYADMIN
    1452731313512779849 #BOT
    ]  

class GuildRegister(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reg_guild", description="สมัครเข้ากิล")
    async def reg_guild(self, interaction: discord.Interaction):

        await interaction.response.send_message(
            "📋 **ตัวอย่างการกรอก**\n"
            "ชื่อเล่น: แจ่มใส\n"
            "ชื่อในเกม: แจ่มใสxgmb\n"
            "อายุ: 25\n"
            "ช่วงเวลาที่เล่น: 18:00 - 23:00\n"
            "สาเหตุที่อยากเข้ากิล: อยากหาทีมจริงจัง\n"
            "ตำแหน่งที่จะเทส: เมจ-แครี่\n"
            "Facebook: Arabit\n\n"
            "พิมพ์ `เริ่ม` เพื่อสมัคร",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            return await interaction.followup.send("❌ หมดเวลา", ephemeral=True)

        if msg.content != "เริ่ม":
            return await interaction.followup.send("ยกเลิกการสมัคร ❌", ephemeral=True)

        questions = [
            "ชื่อเล่น",
            "ชื่อในเกม",
            "อายุ",
            "ช่วงเวลาที่เล่น",
            "สาเหตุที่อยากเข้ากิล",
            "ตำแหน่งที่จะเทส",
            "Facebook"
        ]

        answers = {}

        for q in questions:
            await interaction.followup.send(f"📝 {q}:", ephemeral=True)
            reply = await self.bot.wait_for("message", check=check, timeout=120)
            answers[q] = reply.content

        await interaction.followup.send("📸 กรุณาส่งรูปโปรไฟล์ในเกม", ephemeral=True)

        def check_img(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.attachments

        try:
            img_msg = await self.bot.wait_for("message", check=check_img, timeout=120)
        except asyncio.TimeoutError:
            return await interaction.followup.send("❌ ไม่พบรูป", ephemeral=True)

        channel = self.bot.get_channel(GUILD_REVIEW_CHANNEL_ID)

        embed = discord.Embed(title="📥 ใบสมัครกิลใหม่", color=discord.Color.gold())
        for k, v in answers.items():
            embed.add_field(name=k, value=v, inline=False)

        embed.set_image(url=img_msg.attachments[0].url)
        embed.set_footer(text=f"ผู้สมัคร: {interaction.user}")

        await channel.send(embed=embed, view=ReviewView(interaction.user))
        await interaction.followup.send("✅ ส่งใบสมัครเรียบร้อย รอทีมงานตรวจสอบ", ephemeral=True)


class ReviewView(discord.ui.View):
    def __init__(self, applicant: discord.Member):
        super().__init__(timeout=None)
        self.applicant = applicant

    async def interaction_check(self, interaction: discord.Interaction):
        if not any(r.id in ADMIN_ROLE_IDS for r in interaction.user.roles):
            await interaction.response.send_message("❌ คุณไม่มีสิทธิ์", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ อนุมัติ", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        old_name = self.applicant.display_name
        if not old_name.startswith("รอเทส |"):
            new_name = f"รอเทส | {old_name}"
            await self.applicant.edit(nick=new_name)

        await interaction.response.send_message(
            f"🎉 อนุมัติ {self.applicant.mention}\nเปลี่ยนชื่อเป็น `{new_name}`",
            ephemeral=True
        )
        await interaction.message.edit(view=None)

    @discord.ui.button(label="❌ ปฏิเสธ", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"🚫 ปฏิเสธ {self.applicant.mention}",
            ephemeral=True
        )
        await interaction.message.edit(view=None)


async def setup(bot):
    await bot.add_cog(GuildRegister(bot))
