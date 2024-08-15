import asyncio
import json
import os
import random
import time
from itertools import combinations
from threading import Thread
from typing import Optional

import discord
from discord.ext import commands

queue_dict = {}
role_dict = {}
full_queue = None
match_size = 10
members = []

intents = discord.Intents.default()
intents.members = True  # Enable member intents (to see members in guilds)
intents.message_content = True
bot = commands.Bot(command_prefix="!", case_insensitive=True, intents=intents)


# Classes:
class Player:

    def __init__(self, ubi_name, dis_name, elo, wins, losses, rank):
        self.ubi_name = ubi_name  # Ubisoft account Name
        self.dis_name = dis_name  # Discord account Name
        self.elo = elo  # Elo
        self.wins = wins  # Number of wins
        self.losses = losses  # Number of losses
        self.rank = rank  # Rank

    def to_dict(self):
        """Convert the Player instance to a dictionary."""
        return {
            'ubi_name': self.ubi_name,
            'dis_name': self.dis_name,
            'elo': self.elo,
            'wins': self.wins,
            'losses': self.losses,
            'rank': self.rank
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Player instance from a dictionary."""
        return cls(ubi_name=data['ubi_name'],
                   dis_name=data['dis_name'],
                   elo=data['elo'],
                   wins=data['wins'],
                   losses=data['losses'],
                   rank=data['rank'])

    def save_to_json(self, filename, user):
        """Save player data to a JSON file."""
        with open("./player_data/" + str(filename) + "/" + str(user.name),
                  'w') as file:
            json.dump(self.to_dict(), file)

    @classmethod
    def load_from_json(cls, filename, user):
        """Load player data from a JSON file."""
        with open("./player_data/" + str(filename) + "/" + str(user.name),
                  'r') as file:
            data = json.load(file)
            return cls.from_dict(data)


# Functions:
def check_and_create_profile(ubi_name, dis_name, elo, wins, losses, rank,
                             filename, user):
    try:
        # Try to load the player profile from the JSON file
        player = Player.load_from_json(filename, user)

        # Check if the player profile exists
        if player.ubi_name == ubi_name:
            print("Player exists:", player.to_dict())
            return player
        else:
            print("Player does not match. Creating a new profile.")
            raise FileNotFoundError
    except (FileNotFoundError, json.JSONDecodeError):
        # Create a new player profile
        new_player = Player(ubi_name, dis_name, elo, wins, losses, rank)
        new_player.save_to_json(filename, user)
        print("New player profile created and saved.")
        return new_player


def generate_match_id():
    return f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"


def best_team_partition(players, match_size):
    n = len(players)
    k = int(match_size / 2)
    if n < 2 * k:
        raise ValueError(
            "Number of players must be at least twice the team size.")

    all_indices = set(range(n))
    min_diff = float('inf')
    best_team1 = None
    best_team2 = None
    best_discarded = None

    # Generate all combinations of k players from n
    for team1_indices in combinations(range(n), k):
        team1_indices_set = set(team1_indices)
        remaining_indices = all_indices - team1_indices_set

        # Generate all combinations of k players from the remaining n - k
        for team2_indices in combinations(remaining_indices, k):
            team2_indices_set = set(team2_indices)

            team1 = [players[i] for i in team1_indices]
            team2 = [players[i] for i in team2_indices_set]

            discarded = [
                players[i] for i in remaining_indices - team2_indices_set
            ]

            score1 = sum(player.elo for player in team1)
            score2 = sum(player.elo for player in team2)

            diff = abs(score1 - score2)
            if diff < min_diff:
                min_diff = diff
                best_team1 = team1
                best_team2 = team2
                best_discarded = discarded

    return best_team1, best_team2, best_discarded


def make_a_match(cxt, roster, server_id):
    Match_Made = True
    #roster is a list of discord users
    players = []
    for dis in roster:
        if os.path.exists("./player_data/" + str(server_id) + "/" + dis.name):
            try:
                player = Player.load_from_json(server_id, dis)
                players.append(player)
            except (FileNotFoundError, json.JSONDecodeError):
                print(f"Error loading player data for {dis}.")
        else:
            print(f"No file found for {dis}.")

    Team_1, Team_2, Discarded = best_team_partition(players, match_size)

    for user in roster:
        members.append(user)

    if len(members) < match_size:
        missing = match_size - len(members)
        for _ in range(missing):
            members.append(members[0])

    if Match_Made:
        return members
    else:
        return []


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


# Create a group of commands under !Queue
@bot.group()
async def Queue(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send("Please use a valid subcommand: Join, Leave, or List")


# Subcommand for joining the queue
@Queue.command(name='Join', aliases=['join', 'j', 'J', 'JOIN'])
async def Join(ctx, role: Optional[str] = "Flex"):
    server_id = ctx.guild.id
    user = ctx.author
    role_dict[user] = role
    print(role)
    # Create the queue if it doesn't exist
    if server_id not in queue_dict:
        queue_dict[server_id] = []

    # Add user to the queue if not already in it
    if user not in queue_dict[server_id]:
        queue_dict[server_id].append(user)
        check_and_create_profile(user.name, user.name, 1500, 0, 0, "Unranked",
                                 server_id, user)
        await ctx.send(f"{user.mention} has joined the queue!")
    else:
        await ctx.send(f"{user.mention}, you're already in the queue.")

    # Try to make a match
    if len(queue_dict[server_id]) >= match_size:
        await ctx.send('making a match')
        members = make_a_match(ctx, queue_dict[server_id], server_id)
        if members:
            bot.loop.create_task(
                create_lobby(ctx, "Blue Team DEF", "Orange Team ATK", members))
        queue_dict[server_id] = [
            user for user in queue_dict.get(server_id, [])
            if user not in members
        ]


#
#
#
#


# Subcommand for leaving the queue
@Queue.command(name="Leave", aliases=['leave', 'l', 'L', 'LEAVE'])
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
@Queue.command(name="List", aliases=['list', 'LIST'])
async def List(ctx):
    server_id = ctx.guild.id

    # Check if the queue exists and is not empty
    if server_id in queue_dict and queue_dict[server_id]:
        queue_list = "\n".join([str(item) for item in queue_dict[server_id]])
        await ctx.send(
            f"Queue for {ctx.guild.name}:\n{queue_list}\n{len(queue_dict)}/{match_size}"
        )
    else:
        await ctx.send("The queue is empty.")


# Match Reporting
@bot.command()
async def create_lobby(ctx, team_a: str, team_b: str, members: list):
    # Create the poll message
    players = []
    for member in members:
        players.append(member.name)
    match_ID = generate_match_id()
    poll_message = await ctx.send(
        "Match ID: " + match_ID + "\n"
        f"🔵{team_a}\n"
        f"🔵{members[0].mention}\n"
        #f"🔵{members[1].mention}\n"
        #f"🔵{members[2].mention}\n"
        #f"🔵{members[3].mention}\n"
        #f"🔵{members[4].mention}\n\n"
        f"🟠{team_b}\n"
        #f"🟠{members[5].mention}\n"
        #f"🟠{members[6].mention}\n"
        #f"🟠{members[7].mention}\n"
        #f"🟠{members[8].mention}\n"
        f"🟠{members[1].mention}\n\n"
        f"Indicate the winner!\n🔵 {team_a} vs. 🟠 {team_b}\n\n"
        "React with 🔵 or 🟠")

    # Add reactions for voting
    await poll_message.add_reaction("🔵")
    await poll_message.add_reaction("🟠")

    def check(reaction, user):
        return (
            user != bot.user and str(reaction.emoji) in ["🔵", "🟠"]
            and reaction.message.id == poll_message.id and
            True  #user.id in members  # Check if the user is in the allowed voters list
        )

    try:
        # Wait for a certain amount of time (e.g., 60 seconds) or until one team has 6 votes
        while True:
            reaction, user = await bot.wait_for("reaction_add",
                                                timeout=7200.0,
                                                check=check)

            # Fetch the message again to get updated reaction counts
            poll_message = await ctx.fetch_message(poll_message.id)
            votes_a = discord.utils.get(poll_message.reactions,
                                        emoji="🔵").count - 1
            votes_b = discord.utils.get(poll_message.reactions,
                                        emoji="🟠").count - 1

            if votes_a > match_size / 2:
                await ctx.send(
                    f"{team_a} wins match {match_ID} with {votes_a} votes! 🎉")
                break
            elif votes_b > match_size / 2:
                await ctx.send(
                    f"{team_b} wins match {match_ID} with {votes_b} votes! 🎉")
                break
    except discord.ext.commands.errors.CommandInvokeError:
        # Handle the case where no one votes or the command is cancelled
        await ctx.send("No winner was decided.")


# Everything surrounding player data
player_data_dir = "player_data"
os.makedirs(player_data_dir, exist_ok=True)


def get_player_file_path(user_id):
    return os.path.join(player_data_dir, f"{user_id}.json")


# Function to load player data
def load_player_data(user_id):
    file_path = get_player_file_path(user_id)
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    else:
        # Return default data if no file exists
        return {"elo": 1000, "wins": 0, "losses": 0}


# Function to save player data
def save_player_data(user_id, data):
    file_path = get_player_file_path(user_id)
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


# Run the bot with your token
bot.run(os.environ['DISCORD_KEY'])
