import asyncio
from asyncio import sleep
import datetime
import json
import os
import random
import re
import time
from itertools import combinations
from typing import Optional

import discord
from discord import team
import requests
from discord import file
from discord.ext import commands, tasks
from discord.ui import Button, View
from discord.utils import get
from replit.object_storage import Client
from replit.object_storage.errors import ObjectNotFoundError

client = Client()  # Create a client instance
EU_QUEUE_CHANNEL_ID = 1274045870223921262
US_QUEUE_CHANNEL_ID = 1274045870568112243
text_channel_id = 00000
channel_id_flag = False

last_update_time = {"us": time.time(), "eu": time.time()}
RATE_LIMIT_PERIOD = 10  # 10 seconds
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
queue_regions = {
    region: {
        'pc': {},
        'console': {}
    }
    for region in list_of_major_regions
}

maps = ["bank", "border", "Chalet", "Clubhouse", "Consulate", "kafe", "Lair", "Night Haven", "Skyscraper"]

intents = discord.Intents.default()
intents.members = True  # Enable member intents (to see members in guilds)
intents.message_content = True
bot = commands.Bot(command_prefix="$", case_insensitive=True, intents=intents)


# Classes:
class QView(View):

    def __init__(self, ctx, embed_message, server_id, region, system, GID):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.embed_message = embed_message
        self.server_id = server_id
        self.player_list = []  # This will store Discord user objects
        self.region = region
        self.system = system
        self.GID = GID

    def get_player_list(self):
        # Return the list of players in a formatted string
        displayed_players = self.player_list[:
                                             15]  # Only display first 15 players
        more_players_count = len(self.player_list) - 15

        players_text = "\n".join(
            [player.mention for player in displayed_players])
        if more_players_count > 0:
            players_text += f"\n+ {more_players_count} more"

        return players_text

    @discord.ui.button(label="Join Queue",
                       style=discord.ButtonStyle.green,
                       custom_id="join_game")
    async def join_game(self, interaction: discord.Interaction,
                        button: Button):
        try:
            embed = self.embed_message.embeds[0]
            user = interaction.user
            player = check_profile(self.server_id, user)

            if player is not None and player != "NUP":
                rank_emoji = get(interaction.guild.emojis, name=player.rank)
                player_entry = f"{rank_emoji} @{user.display_name} ({user.display_name})" if rank_emoji else f"@{user.display_name} ({user.display_name})"
            else:
                player_entry = f"@{user.display_name} ({user.display_name})"

            if user not in self.player_list:
                self.player_list.append(user)

            self.update_players_field(embed)
            await self.embed_message.edit(embed=embed)
            await interaction.response.send_message(
                "You have joined the queue!", ephemeral=True)
            # For testing
            print(f"length of player list: {len(self.player_list)}")
            # while len(self.player_list) < match_size:
            #    self.player_list.append(user)
            if len(self.player_list) >= match_size:
                print(self.player_list)
                roster = [
                    Player.load_from_json(self.server_id, p.name)
                    for p in self.player_list
                ]
                print(roster)
                members, Team_1, Team_2, Discarded = make_a_match(
                    self.ctx, roster, self.server_id)
                for mem in range(len(Team_1)):
                    Team_1[mem] = discord.utils.get(
                        self.ctx.guild.members,
                        name=Team_1[mem].dis_name)
                for mem in range(len(Team_2)):
                    Team_2[mem] = discord.utils.get(
                        self.ctx.guild.members,
                        name=Team_2[mem].dis_name)
                asyncio.create_task(match_info(self.ctx, self.GID,
                                               Team_1, Team_2))
                self.player_list = []
                self.update_players_field(embed)
                await self.embed_message.edit(embed=embed)
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Leave Queue",
                       style=discord.ButtonStyle.red,
                       custom_id="leave_queue")
    async def leave_queue(self, interaction: discord.Interaction,
                          button: Button):
        embed = self.embed_message.embeds[0]
        user = interaction.user

        while user in self.player_list:
            self.player_list.remove(user)  # Remove the actual user object

        self.update_players_field(embed)
        await self.embed_message.edit(embed=embed)
        await interaction.response.send_message(
            "You have left the game queue.", ephemeral=True)

    def update_players_field(self, embed):
        # Show only the first 15 players
        displayed_players = self.player_list[:15]
        more_players_count = len(self.player_list) - 15

        players_text = "\n".join(
            [player.mention for player in displayed_players])
        if more_players_count > 0:
            players_text += f"\n+ {more_players_count} more"

        for field in embed.fields:
            if field.name == "Players":
                embed.set_field_at(index=embed.fields.index(field),
                                   name="Players",
                                   value=players_text,
                                   inline=False)
                break


class MapButton(View):
    def __init__(self):
        super().__init__(timeout=300)
        self.used = False

    @discord.ui.button(label="Get Random Map", style=discord.ButtonStyle.primary)
    async def random_map_button(self, interaction: discord.Interaction, button: Button):
        random_map = random.choice(maps)
        if not self.used:
            await interaction.response.send_message(f"The random map is: {random_map}")
            self.used = True


class VoteButton(View):
    def __init__(self):
        super().__init__(timeout=60)  # Set a timeout of 60 seconds for the button
        self.blue_votes = 0
        self.orange_votes = 0

    @discord.ui.button(label="Vote for Blue Team", style=discord.ButtonStyle.primary, custom_id="vote_blue")
    async def blue_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.blue_votes += 1
        await interaction.response.send_message(f"Blue Team now has {self.blue_votes} votes.", ephemeral=True)
        if self.blue_votes >= 6:
            await interaction.channel.send("Blue Team wins with 6 votes!")

    @discord.ui.button(label="Vote for Orange Team", style=discord.ButtonStyle.secondary, custom_id="vote_orange")
    async def orange_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.orange_votes += 1
        await interaction.response.send_message(f"Orange Team now has {self.orange_votes} votes.", ephemeral=True)
        if self.orange_votes >= 6:
            await interaction.channel.send("Orange Team wins with 6 votes!")

    async def on_timeout(self):
        # Handle timeout if needed
        await self.message.edit(content="Voting has ended.", view=None)


async def match_info(ctx, match_id, Team_1, Team_2):
    team_1_members = Team_1
    team_2_members = Team_2

    match_id = generate_match_id()
    url = 'https://www.mapban.gg/en/ban/r6s/competitive/bo1'
    # Send a GET request to the webpage
    response = requests.get(url)
    response.raise_for_status()  # Ensure we notice bad responses

    # Use regex to find all URLs in input fields
    links = re.findall(r'>([^<]+)<', response.text)

    # Filter out any strings that are just whitespace
    links = [s.strip() for s in links if s.strip()]
    team1Link = links[30]
    team2Link = links[33]

    # Create the embed
    embed = discord.Embed(title="Match Information", color=0x00ff00)
    embed.add_field(name="Match ID", value=match_id, inline=False)

    # Add Team 1 and Team 2 columns
    team_1_str = "\n".join(mem.mention for mem in team_1_members)
    team_2_str = "\n".join(mem.mention for mem in team_2_members)
    embed.add_field(name="Blue Team", value=team_1_str, inline=True)
    embed.add_field(name="Orange Team", value=team_2_str, inline=True)

    embed.add_field(name="Blue Team Bans:", value=team1Link, inline=False)
    embed.add_field(name="Orange Team Bans:", value=team2Link, inline=False)
    embed.add_field(name="Or, click below to recieve a random map", value=" ", inline=False)

    # Optionally, add a footer or other information
    embed.set_footer(text="Good luck to both teams!")

    # for mem in range(5):
    #    Team_1_usrs[mem] = discord.utils.get(ctx.guild.members,name=Team_1[mem].dis_name)
    #    Team_2_usrs[mem] = discord.utils.get(ctx.guild.members,name=Team_2[mem].dis_name)
    view = MapButton()
    await create_match_channels(ctx, Team_1, Team_2, match_id[-4:], 10, embed, view)
    # Send the embed to the channel


# Command to create a new LFG queue with the updated QView
@bot.command()
@commands.has_permissions(administrator=True)
async def lfg(ctx, region, system):
    GID = generate_match_id()
    if system.upper() == "PC":
        syscolor = discord.Color.dark_red()
    else:
        syscolor = discord.Color.dark_blue()
    embed = discord.Embed(title=f" Queue for {str(region).upper()}",
                          color=syscolor)

    embed.add_field(name="Players", value="", inline=False)
    embed.add_field(name="System", value=str(system).upper(), inline=True)
    embed.add_field(
        name="Started at",
        value=datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"),
        inline=True)
    embed.set_footer(text=f"Game ID: {GID}")

    message = await ctx.send(embed=embed)
    view = QView(ctx, message, ctx.guild.id, region, system, GID)
    await message.edit(view=view)


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
        if not isinstance(filename, str):
            filename = filename.dis_name
            # raise ValueError("filename must be a string")
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

        print(f"Attempting to download player data for key: {key}")

        try:
            data = client.download_as_text(key)
            return cls.from_dict(json.loads(data))
        except client.ObjectNotFoundError:
            print(f"No data found for {key}")
            return None
        except Exception as e:
            print(f"Error downloading player data for {key}: {str(e)}")
            return None


# Functions:
def check_profile(filename, user):
    try:
        player = Player.load_from_json(filename, user.name)

        if player and player.dis_name == user.name:
            print("Player exists:", player.to_dict())
            return player
        else:
            print("Player does not match")
            return None
    except FileNotFoundError:
        return "NUP"


def generate_match_id():
    return f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"


# Function to get the queue based on region
def get_queue(region, server_id):
    queues = queue_regions[region]
    if region == 'eu':
        queue = queues['pc'] if 'pc' in system else queues['console']
    elif region == 'us':
        queue = queues['pc'] if 'pc' in system else queues['console']
    return queue


def best_team_partition(players, match_size):
    print(players)
    n = len(players)
    k = int(match_size / 2)
    # if n < 2 * k:
    #    raise ValueError(
    #        "Number of players must be at least twice the team size.")

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
    players = []
    for dis in roster:
        try:
            player = Player.load_from_json(server_id, dis)
            players.append(player)
        except (ObjectNotFoundError, json.JSONDecodeError):
            print(f"Error loading player data for {dis}.")

    Team_1, Team_2, Discarded = best_team_partition(players, match_size)
    # Return the members for this match and clear them from the queue
    members = [dis for dis in roster if dis in Team_1 or dis in Team_2]

    return members, Team_1, Team_2, Discarded


async def create_match_channels(ctx, Team_1, Team_2,
                                match_id, delete_after, embed, view):
    global text_channel_id, channel_id_flag
    guild = ctx.guild
    category = await guild.create_category(f"Match {match_id}")

    # Create text channel
    text_channel = await guild.create_text_channel(f"match-{match_id}-chat", category=category)
    mentions = ' '.join(mem.mention for mem in Team_1 + Team_2)
    await text_channel.send(mentions)
    await text_channel.send(embed=embed, view=view)
    await sleep(10)
    # Create voice channels
    voice_channel1 = await guild.create_voice_channel(f"Blue - {match_id}", category=category)
    voice_channel2 = await guild.create_voice_channel(f"Orange - {match_id}", category=category)

    # Set permissions for text channel
    await text_channel.set_permissions(guild.default_role, view_channel=False)
    for member in Team_1 + Team_2:
        if isinstance(member, discord.Member) or isinstance(member, discord.Role):
            await text_channel.set_permissions(member, view_channel=True, send_messages=True)
        else:
            print(f"Unexpected member type: {type(member)}")

    # Set permissions for voice channels
    # await voice_channel1.set_permissions(guild.default_role, view_channel=False)
    # for member in team1_members:
    #    await voice_channel1.set_permissions(member, view_channel=True, connect=True)
    #
    #    await voice_channel2.set_permissions(guild.default_role, view_channel=False)
    #    for member in team2_members:
    #        await voice_channel2.set_permissions(member, view_channel=True, connect=True)

    # Wait for the specified time before deleting the channels
    await sleep(delete_after)

    # Delete channels
    await text_channel.delete()
    await voice_channel1.delete()
    await voice_channel2.delete()
    await category.delete()


# Bot Commands


@bot.command(name='setup_profile',
             aliases=['setup profile', 'setup'],
             help='Make a user profile')
async def setup_profiles(ctx):
    guild = ctx.guild
    new_user = ctx.author
    if guild is None:
        await ctx.send("This command can only be used in a server.")
        return

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
@bot.group(name="Queue", aliases=["q"], help='join, leave, list')
async def Queue(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send("Please use a valid subcommand: Join, Leave, or List")


# Subcommand for joining the queue
@Queue.command(name='Join', aliases=['join', 'j', 'J', 'JOIN'])
async def Join(ctx,
               region: Optional[str] = None,
               role: Optional[str] = "Flex"):
    server_id = ctx.guild.id
    user = ctx.author
    role_dict[user] = role
    # Fetch player's system and region
    player = check_profile(server_id, user)
    if player == "NUP":
        await ctx.send("No user profile, make one with !setup_profile")
        return
    system = player.system.lower()
    if region:
        if region in list_of_major_regions:
            major_region = region
        else:
            await ctx.sent(
                f"invalid region, use a region form this list: \n {list_of_major_regions}"
            )
    else:
        major_region = player.region[:2].lower()
        if major_region not in list_of_major_regions:
            await ctx.send(
                "Invalid region in profile. Please update your profile with a valid region."
            )
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

        await discord.utils.get(
            ctx.guild.text_channels, name="bot-commands"
        ).send(
            f"{user.mention} has joined the queue for {system} players in {major_region.upper()} region!"
        )
    else:
        await discord.utils.get(
            ctx.guild.text_channels, name="bot-commands"
        ).send(
            f"{user.mention}, you're already in the queue for {player.region} region."
        )
    # Try to make a match
    if len(queue[server_id]) >= match_size:
        await discord.utils.get(ctx.guild.text_channels,
                                name="bot-commands").send('making a match')
        members, Team_1, Team_2, Discarded = make_a_match(
            ctx, queue[server_id], server_id)
        if members:
            await create_lobby(ctx, "Blue Team DEF", "Orange Team ATK",
                               members)
            queue[server_id] = [
                user for user in queue.get(server_id, [])
                if user not in members
            ]


@Queue.command(name="Leave", aliases=['leave', 'l', 'L', 'LEAVE'])
async def Leave(ctx):
    server_id = ctx.guild.id
    user = ctx.author
    left_queue = False

    # Iterate over all regions and systems
    for region in list_of_major_regions:
        for system in ['pc', 'console']:
            queue = queue_regions[region][system]
            if server_id in queue and user in queue[server_id]:
                queue[server_id].remove(user)
                await ctx.send(
                    f"{user.mention} has left the {system.upper()} queue for the {region} region."
                )
                left_queue = True

    if not left_queue:
        await ctx.send(f"{user.mention}, you are not in any queues.")


# Subcommand for listing the queue
@Queue.command(name="List", aliases=['list', 'LIST'])
async def ListQ(ctx):
    server_id = ctx.guild.id
    response = ""

    queues_with_players = []
    for region, systems in queue_regions.items():
        for system, queue in systems.items():
            if server_id in queue and queue[server_id]:
                queue_list = "\n".join(
                    [str(item) for item in queue[server_id]])
                response += f"{system.upper()} Queue for {region}:\n{queue_list}\n{len(queue[server_id])}/{match_size}\n\n"
                queues_with_players.append(f"{region} - {system.upper()}")

    if not queues_with_players:
        response = "All queues are empty."

    await ctx.send(response)


# Match Reporting
@bot.command()
async def create_lobby(ctx, team_a: str, team_b: str, members: list):
    # Create the lobby with unique match ID
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
                                  f"🟠{members[9].mention}\n\n"
                                  f"Indicate the winner!\n🔵 {team_a} vs. 🟠 {team_b}\n\n"
                                  "React with 🔵 or 🟠")

    # Add reactions for voting
    await poll_message.add_reaction("🔵")
    await poll_message.add_reaction("🟠")

    def check(reaction, user):
        return (user != bot.user and str(reaction.emoji) in ["🔵", "🟠"]
                and reaction.message.id == poll_message.id)

    try:
        # Wait for a certain amount of time (e.g., 60 seconds) or until one team has 6 votes
        while True:
            reaction, user = await bot.wait_for("reaction_add",
                                                timeout=14400,
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


@bot.command(name='assign_system_roles', help='defunct')
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
                    roles = system.split(
                    )  # In case multiple systems are provided (e.g., "PC PS")
                    for role_name in roles:
                        role = get(guild.roles, name=role_name)
                        if role:
                            await member.add_roles(role)
                            await ctx.send(
                                f"Assigned role {role_name} to {member.name}")
                        else:
                            await ctx.send(
                                f"Role {role_name} not found on the server.")
            else:
                await ctx.send(f"No profile found for {member.name}")


@bot.command(name='clear', help='Clear a queue')
@commands.has_permissions(administrator=True)
async def clear_input(ctx, *, arg: str):
    user = ctx.author
    try:
        regions = list_of_major_regions
        systems = ['pc', 'console']

        if arg == "all":
            # Clear all queues
            for region in regions:
                for system in systems:
                    queue_regions[region][system] = {}
            await ctx.send(f"All queues have been cleared.")

        else:
            input_text_lower = arg.lower()
            if input_text_lower in regions:
                # Clear queues for a specific region
                for system in systems:
                    queue_regions[input_text_lower][system] = {}
                await ctx.send(
                    f"All queues for the {arg} region have been cleared.")

            else:
                await ctx.send(
                    f"{user.mention}, your input '{arg}' is not recognized. Please try again with a valid region or 'all'."
                )

    except Exception as e:
        print(f"An error occurred: {e}")
        await ctx.send(f"An error occurred: {e}. Please try again.")

    @clear_input.error
    async def clear_input_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                f"{ctx.author.mention}, you do not have permission to use this command."
            )
        else:
            await ctx.send(f"An error occurred: {str(error)}")


@bot.command(name='feature-request',
             aliases=['fr', 'request', 'suggest'],
             help='Submit a feature request')
async def feature_request(ctx, *, arg):
    user = ctx.author
    await ctx.send("Feature request submitted! Thank you for your feedback.")
    await discord.utils.get(
        ctx.guild.text_channels,
        name="dev").send(f"{user.name} suggessted: \n {arg}")


# Run the bot
bot.run(os.environ['DISCORD_KEY'])
