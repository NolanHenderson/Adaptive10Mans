import discord
from discord.ext import commands

bot = commands.Bot(command_prefix="!")  # You can customize the command prefix

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Create a group of commands under !Queue
@bot.group()
async def Queue(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send("Please use a valid subcommand: Join, Leave, or List")

# Subcommand for joining the queue
@Queue.command()
async def Join(ctx):
    server_id = ctx.guild.id
    user = ctx.author

    # Create the queue if it doesn't exist
    if server_id not in queue_dict:
        queue_dict[server_id] = []

    # Add user to the queue if not already in it
    if user not in queue_dict[server_id]:
        queue_dict[server_id].append(user)
        await ctx.send(f"{user.mention} has joined the queue!")
    else:
        await ctx.send(f"{user.mention}, you're already in the queue.")

# Subcommand for leaving the queue
@Queue.command()
async def Leave(ctx):
    server_id = ctx.guild.id
    user = ctx.author

    # Remove user from the queue if they are in it
    if server_id in queue_dict and user in queue_dict[server_id]:
        queue_dict[server_id].remove(user)
        await ctx.send(f"{user.mention} has left the queue.")
    else:
        await ctx.send(f"{user.mention}, you are not in the queue.")

# Subcommand for listing the queue
@Queue.command()
async def List(ctx):
    server_id = ctx.guild.id

    # Check if the queue exists and is not empty
    if server_id in queue_dict and queue_dict[server_id]:
        queue_list = "\n".join([user.mention for user in queue_dict[server_id]])
        await ctx.send(f"Queue:\n{queue_list}")
    else:
        await ctx.send("The queue is empty.")

# Run the bot with your token
bot.run('YOUR_BOT_TOKEN')