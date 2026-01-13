import discord
from discord.ext import commands
import os

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1265593210269339782  # server ID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    bot.tree.clear_commands(guild=guild)
    await bot.tree.sync(guild=guild)

    print("✅ CLEARED ALL SLASH COMMANDS")
    await bot.close()

bot.run(TOKEN)
