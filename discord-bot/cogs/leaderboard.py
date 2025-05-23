import discord
from discord.ext import commands
from utils.storage import get_sorted_leaderboard


class LeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def leaderboard(self, ctx):
        """Displays the leaderboard sorted by ELO."""
        leaderboard = get_sorted_leaderboard()
        embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())

        for rank, (name, elo) in enumerate(leaderboard.items(), start=1):
            embed.add_field(name=f"{rank}. {name}", value=f"ELO: {elo}", inline=False)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(LeaderboardCog(bot))
