import discord
from discord.ext import commands
from utils.helpers import best_team_partition
from utils.storage import load_player
from config.settings import MATCH_SIZE

class MatchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def match(self, ctx):
        """Finds the most balanced teams from the queue."""
        queue = [...]  # Fetch players from storage
        players = [load_player(ctx.guild.id, user.name) for user in queue]

        if len(players) < MATCH_SIZE:
            await ctx.send("Not enough players for a match!")
            return

        team1, team2, _, _ = best_team_partition(players, MATCH_SIZE)
        await ctx.send(f"Match Created!\n**Team 1:** {team1}\n**Team 2:** {team2}")

def setup(bot):
    bot.add_cog(MatchCog(bot))
