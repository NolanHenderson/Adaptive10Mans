import discord
from discord.ext import commands
from utils.storage import save_profile, load_player

class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def setup_profile(self, ctx, ubi_name: str, system: str):
        """Creates a player profile."""
        user = ctx.author
        profile_data = {
            "ubi_name": ubi_name,
            "dis_name": user.name,
            "elo": 1500,
            "wins": 0,
            "losses": 0,
            "rank": "G1",
            "region": "US East",
            "system": system
        }
        save_profile(ctx.guild.id, user.name, profile_data)
        await ctx.send(f"Profile created for {user.mention}!")

    @commands.command()
    async def profile(self, ctx):
        """Displays a user's profile."""
        user = ctx.author
        profile = load_player(ctx.guild.id, user.name)
        if profile:
            await ctx.send(f"**Profile for {user.name}**\nELO: {profile['elo']}\nRank: {profile['rank']}")
        else:
            await ctx.send("Profile not found!")

def setup(bot):
    bot.add_cog(ProfileCog(bot))
