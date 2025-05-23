import discord
from discord.ext import commands
from utils.storage import check_profile
from config.settings import MATCH_SIZE


class QueueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []

    @commands.command()
    async def lfg(self, ctx, region, system):
        """Creates a queue for matchmaking."""
        user = ctx.author
        profile = check_profile(ctx.guild.id, user)
        if not profile:
            await ctx.send(f"{user.mention}, you need to set up a profile first!")
            return

        if user not in self.queue:
            self.queue.append(user)
            await ctx.send(f"{user.mention} joined the queue!")

        if len(self.queue) >= MATCH_SIZE:
            await self.start_match(ctx)

    async def start_match(self, ctx):
        """Handles match initiation."""
        await ctx.send("Match found! Creating teams...")
        # Add match logic here


def setup(bot):
    bot.add_cog(QueueCog(bot))
