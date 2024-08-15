import asyncio
import json
import os
import random
import time
from itertools import combinations
from typing import Optional

import discord
from discord.ext import commands
from discord.utils import get
from replit.object_storage import Client

client = Client()  # Create a client instance
#queue_pc = {}
#queue_console = {}
#queue_dict = {}

role_dict = {}
full_queue = None
match_size = 10
members = []
list_of_regions = [
    "Asia East", "Asia South East", "Japan East", "South Africa North",
    "UAE North", "EU West", "EU North", "US East", "US Central", "US West",
    "US South Central", "Brazil South", "Australia East"
]
list_of_ranks = [
    "C1", "C2", "C3", "C4", "C5", "B1", "B2", "B3", "B4", "B5", "S1", "S2",
    "S3", "S4", "S5", "G1", "G2", "G3", "G4", "G5", "P1", "P2", "P3", "P4",
    "P5", "E1", "E2", "E3", "E4", "E5", "D1", "D2", "D3", "D4", "D5", "F"
]
list_of_systems = ["PC", "PS", "Xbox"]

list_of_major_regions = ["ja", "so", "ua", "eu", "us", "br", "au", "af"]
queue_regions = {region: {'pc': {}, 'console': {}} for region in list_of_major_regions}

intents = discord.Intents.default()
intents.members = True  # Enable member intents (to see members in guilds)
intents.message_content = True
bot = commands.Bot(command_prefix="!", case_insensitive=True, intents=intents)


# Classes:
class Player:

    def __init__(self, ubi_name, dis_name, elo, wins, losses, rank, region,
                 system):
        self.ubi_name = ubi_name  # Ubisoft account Name
        self.dis_name = dis_name  # Discord account Name
        self.elo = elo  # Elo
        self.wins = wins  # Number of wins
        self.losses = losses  # Number of losses
        self.rank = rank  # Rank
        self.region = region  # Region
        self.system = system

    def to_dict(self):
        """Convert the Player instance to a dictionary."""
        return {
            'ubi_name': self.ubi_name,
            'dis_name': self.dis_name,
            'elo': self.elo,
            'wins': self.wins,
            'losses': self.losses,
            'rank': self.rank,
            'region': self.region,
            'system': self.system
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Player instance from a dictionary."""
        return cls(ubi_name=data['ubi_name'],
                   dis_name=data['dis_name'],
                   elo=data['elo'],
                   wins=data['wins'],
                   losses=data['losses'],
                   rank=data['rank'],
                   region=data['region'],
                   system=data['system'])

    @classmethod
    def sanitize_filename(cls, filename):
        # Remove leading/trailing whitespace and replace spaces with underscores
        if type(filename) != str:
            filename = filename.name
        return filename.strip().replace(" ", "_").replace(".", "_")

    def save_to_json(self, filename):
        file_safe_name = self.sanitize_filename(self.dis_name)
        key = f"player_data/{filename}/{file_safe_name}.json"
        client.upload_from_text(key, json.dumps(self.to_dict()))
        print(f"Saved player data to object storage as {key}")

    @classmethod
    def load_from_json(cls, filename, username):
        file_safe_name = cls.sanitize_filename(username)
        key = f"player_data/{filename}/{file_safe_name}.json"
        try:
            data = client.download_as_text(key)
            return cls.from_dict(json.loads(data))
        except FileNotFoundError:
            print(f"No data found for {key}")
            return None


# Functions:
def check_profile(filename, user):
    try:
        # Try to load the player profile from the JSON file
        player = Player.load_from_json(filename, user)

        # Check if the player profile exists
        if player.dis_name == user.name:
            print("Player exists:", player.to_dict())
            return player
        else:
            print("Player does not match")
            return None
    except FileNotFoundError:
        return None


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
        try:
            player = Player.load_from_json(server_id, dis)
            players.append(player)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Error loading player data for {dis}.")

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


# Bot Commands


@bot.command(name='setup_profile', aliases=['setup profile', 'setup'])
async def setup_profiles(ctx):
    guild = ctx.guild
    new_user = ctx.author

    async def ask_user_for_input(member, question, input_type=str, timeout=60):
        await member.send(question)
        print(f"Sent question to {member.name}: {question}")

        def check(m):
            return m.author == member and isinstance(m.channel,
                                                     discord.DMChannel)

        try:
            msg = await bot.wait_for('message', check=check, timeout=timeout)
            print(f"Received response from {member.name}: {msg.content}")
            return input_type(msg.content)
        except asyncio.TimeoutError:
            await member.send("You took too long to respond! Please try again."
                              )
            print(f"Timeout waiting for response from {member.name}")
            return None

    try:
        await new_user.send(
            f"Hello {new_user}, I am a bot from {guild}. Let's set up your player profile!"
        )
        print(f"Greeting message sent to {new_user.name}")

        ubi_name = await ask_user_for_input(
            new_user, "Please enter your Ubisoft account name:")
        if ubi_name is None: return
        dis_name = new_user.name
        print(f"Collected Ubisoft name: {ubi_name}")

        region = await ask_user_for_input(
            new_user, "Please enter your region from this list:\n"
            "(Asia East, Asia South East, Japan East, South Africa North, "
            "UAE North, EU West, EU North, US East, US Central, US West, "
            "US South Central, Brazil South, Australia East)")
        if region.lower() in [r.lower() for r in list_of_regions]:
            print(f"Collected region: {region}")
        else:
            await new_user.send(
                "Invalid region. Please use !setup profile again.")
            return

        system = await ask_user_for_input(
            new_user, "Please enter your system:\n"
            '(PC, Xbox, PS. if you play on multiple, say: "PC PS")')
        if system.lower() in [stm.lower() for stm in list_of_systems]:
            pass
        else:
            await new_user.send(
                "Invalid system. Please use !setup profile again.")
            return

        rank = await ask_user_for_input(
            new_user, "Please enter your rank:\n"
            "(Use the form G1 for Gold 1, P3 for Plat 3, etc... Use D1 for champ.)"
        )
        if rank.lower() in [rnk.lower() for rnk in list_of_ranks]:
            print(f"Collected rank: {rank}")
        else:
            await new_user.send(
                "Invalid rank. Please use !setup profile again.")
            return

        elo = 1500
        wins = 0
        losses = 0

        player = Player(ubi_name, dis_name, elo, wins, losses, rank, region,
                        system)
        player.save_to_json(ctx.guild.id)
        print(f"Saved player profile for {new_user.name}")

        await new_user.send(
            "Your profile has been successfully created and saved!")
    except Exception as e:
        print(f"An error occurred: {e}")
        await new_user.send(
            f"An error occurred: {e}\n\nPlease reach out to a moderator")


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

    # Fetch player's system and region
    player = check_profile(server_id, user)
    if not player:
        await ctx.send("No user profile, make one with !setup_profile")
        return

    system = player.system.lower()
    major_region = player.region[:2].lower()
    if major_region not in list_of_major_regions:
        await ctx.send("Invalid region in profile. Please update your profile with a valid region.")
        return

    # Determine the correct queue
    queues = queue_regions[major_region]
    queue = queues['pc'] if 'pc' in system else queues['console']

    # Create the queue if it doesn't exist
    if server_id not in queue:
        queue[server_id] = []

    # Add user to the queue if not already in it
    if user not in queue[server_id]:
        queue[server_id].append(user)
        await ctx.send(f"{user.mention} has joined the queue for {system} players in {major_region.upper()} region!")
    else:
        await ctx.send(f"{user.mention}, you're already in the queue for {player.region} region.")

    # Try to make a match
    if len(queue[server_id]) >= match_size:
        await ctx.send('making a match')
        members = make_a_match(ctx, queue[server_id], server_id)
        if members:
            bot.loop.create_task(
                create_lobby(ctx, "Blue Team DEF", "Orange Team ATK", members))
        queue[server_id] = [
            user for user in queue.get(server_id, []) if user not in members
        ]

# Subcommand for leaving the queue
@Queue.command(name="Leave", aliases=['leave', 'l', 'L', 'LEAVE'])
async def Leave(ctx):
    server_id = ctx.guild.id
    user = ctx.author

    # Fetch player's region
    player = check_profile(server_id, user)
    if not player:
        await ctx.send("No user profile, make one with !setup_profile")
        return

    major_region = player.region[:2].lower()
    if major_region not in list_of_major_regions:
        await ctx.send("Invalid region in profile. Please update your profile with a valid region.")
        return

    left_queue = False

    # Check which queue the player is in and remove them
    for system in ['pc', 'console']:
        queue = queue_regions[major_region][system]
        if server_id in queue and user in queue[server_id]:
            queue[server_id].remove(user)
            await ctx.send(f"{user.mention} has left the {system.upper()} queue for the {player.region} region.")
            left_queue = True

    if not left_queue:
        await ctx.send(f"{user.mention}, you are not in any queue for the {player.region} region.")

# Subcommand for listing the queue
@Queue.command(name="List", aliases=['list', 'LIST'])
async def ListQ(ctx):
    server_id = ctx.guild.id
    response = ""

    queues_with_players = []
    for region, systems in queue_regions.items():
        for system, queue in systems.items():
            if server_id in queue and queue[server_id]:
                queue_list = "\n".join([str(item) for item in queue[server_id]])
                response += f"{system.upper()} Queue for {region}:\n{queue_list}\n{len(queue[server_id])}/{match_size}\n\n"
                queues_with_players.append(f"{region} - {system.upper()}")

    if not queues_with_players:
        response = "All queues are empty."

    await ctx.send(response)


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
        f"🔵{members[1].mention}\n"
        f"🔵{members[2].mention}\n"
        f"🔵{members[3].mention}\n"
        f"🔵{members[4].mention}\n\n"
        f"🟠{team_b}\n"
        f"🟠{members[5].mention}\n"
        f"🟠{members[6].mention}\n"
        f"🟠{members[7].mention}\n"
        f"🟠{members[8].mention}\n"
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


@bot.command(name='assign_system_roles')
@commands.has_permissions(administrator=True)
async def assign_system_roles(ctx):
    print("command called")
    server_id = ctx.guild.id
    guild = ctx.guild

    for member in guild.members:
        print("checking member:", member)
        if not member.bot:
            print("checking profile")
            player = check_profile(server_id, member)
            if player:
                print("player found")
                system = player.system
                print(system)
                if system:
                    roles = system.split()  # In case multiple systems are provided (e.g., "PC PS")
                    for role_name in roles:
                        role = get(guild.roles, name=role_name)
                        if role:
                            await member.add_roles(role)
                            await ctx.send(f"Assigned role {role_name} to {member.name}")
                        else:
                            await ctx.send(f"Role {role_name} not found on the server.")
            else:
                await ctx.send(f"No profile found for {member.name}")


# Run the bot with your token
bot.run(os.environ['DISCORD_KEY'])
