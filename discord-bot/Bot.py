import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv('DISCORD_KEY')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="$", case_insensitive=True, intents=intents)

# Load Cogs
COGS = ["queue", "match", "profile", "leaderboard"]

for cog in COGS:
    bot.load_extension(f"cogs.{cog}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="Now with ranks!"))

bot.run(TOKEN)
