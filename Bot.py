import asyncio
from asyncio import sleep
import datetime
import json
import os
import random
import re
import time
from typing import Union
from itertools import combinations
import numpy as np
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
role_dict = {}
match_size = 8
members = []
list_of_regions = [
    "Asia East", "Asia South East", "Japan East", "South Africa North",
    "UAE North", "EU West", "EU North", "US East", "US Central", "US West",
    "US South Central", "Brazil South", "Australia East"
]
list_of_ranks = ["C1", "B1", "S1", "G1", "P1", "E1", "D1", "CP"]

# list_of_ranks = [
#    "C5", "C4", "C3", "C2", "C1", "B5", "B4", "B3", "B2", "B1", "S5", "S4",
#    "S3", "S2", "S1", "G5", "G4", "G3", "G2", "G1", "P5", "P4", "P3", "P2",
#    "P1", "E5", "E4", "E3", "E2", "E1", "D5", "D4", "D3", "D2", "D1", "CP"]

list_of_systems = ["PC", "PS", "Xbox"]

list_of_major_regions = ["ja", "so", "ua", "eu", "us", "br", "au", "af"]
queue_regions = {
    region: {
        'pc': {},
        'console': {}
    }
    for region in list_of_major_regions
}

maps = ["Bank", "Border", "Chalet", "Clubhouse", "Consulate", "Kafe Dostoyevsky", "Lair", "Night Haven", "Skyscraper"]

intents = discord.Intents.default()
intents.members = True
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
            # self.player_list.append(user)
            if len(self.player_list) >= match_size:
                print(self.player_list)
                roster = [
                    Player.load_from_json(self.server_id, p.name)
                    for p in self.player_list
                ]
                self.player_list = []
                self.update_players_field(embed)
                await self.embed_message.edit(embed=embed)
                print(roster)
                members, Team_1, Team_2, Discarded = make_a_match(self.ctx, roster, self.server_id)
                for mem in range(len(Team_1)):
                    Team_1[mem] = discord.utils.get(
                        self.ctx.guild.members,
                        name=Team_1[mem].dis_name)
                for mem in range(len(Team_2)):
                    Team_2[mem] = discord.utils.get(
                        self.ctx.guild.members,
                        name=Team_2[mem].dis_name)
                await asyncio.create_task(match_info(self.ctx, self.GID, Team_1, Team_2))
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


class LView(View):
    def __init__(self, ctx, Team_1, Team_2, server_id):
        super().__init__(timeout=7200)
        self.randMapUsed = False
        self.matchOutcomeReported = False
        self.ctx = ctx
        self.Team_1 = Team_1
        self.Team_2 = Team_2
        self.server_id = server_id
        self.blue_votes = 0
        self.orange_votes = 0
        self.voted_users = set()  # Track users who have voted

    @discord.ui.button(label="Get Random Map", style=discord.ButtonStyle.primary)
    async def random_map_button(self, interaction: discord.Interaction, button: Button):
        if not self.randMapUsed:
            random_map = random.choice(maps)
            await interaction.response.send_message(f"The random map is: {random_map}")
            self.randMapUsed = True

    @discord.ui.button(label="Vote for Blue Team", style=discord.ButtonStyle.green, custom_id="vote_blue")
    async def blue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if not self.matchOutcomeReported:
            if user_id in self.voted_users:
                await interaction.response.send_message("You have already voted.", ephemeral=True)
                return

            self.blue_votes += 1
            self.voted_users.add(user_id)
            await interaction.response.send_message(f"Blue Team now has {self.blue_votes} votes.", ephemeral=True)

            if self.blue_votes > match_size / 2:
                await interaction.channel.send("Blue Team wins!")
                self.matchOutcomeReported = True
                await self.adjust_elo(self.Team_1, self.Team_2)
        else:
            await interaction.response.send_message("Match outcome already reported.", ephemeral=True)

    @discord.ui.button(label="Vote for Orange Team", style=discord.ButtonStyle.green, custom_id="vote_orange")
    async def orange_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if not self.matchOutcomeReported:
            if user_id in self.voted_users:
                await interaction.response.send_message("You have already voted.", ephemeral=True)
                return

            self.orange_votes += 1
            self.voted_users.add(user_id)
            await interaction.response.send_message(f"Orange Team now has {self.orange_votes} votes.", ephemeral=True)

            if self.orange_votes > match_size / 2:
                await interaction.channel.send("Orange Team wins!")
                self.matchOutcomeReported = True
                await self.adjust_elo(self.Team_2, self.Team_1)
        else:
            await interaction.response.send_message("Match outcome already reported.", ephemeral=True)

    async def on_timeout(self):
        # Handle timeout if needed
        pass

    async def adjust_elo(self, winning_team, losing_team):
        for mem in winning_team:
            player = Player.load_from_json(self.server_id, mem.name)
            player.elo = player.elo + 100
            player.save_to_json(self.server_id, mem.name)
            await sleep(1)

        for mem in losing_team:
            player = Player.load_from_json(self.server_id, mem.name)
            player.elo = player.elo - 100
            player.save_to_json(self.server_id, mem.name)
            await sleep(1)

        make_leaderboard(self.ctx)


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

    def save_to_json(self, filename, username):
        file_safe_name = self.sanitize_filename(username)
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
# Creates the blurb containing all match info in a new lobby
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
    view = LView(ctx, Team_1, Team_2, ctx.guild.id)
    await create_match_channels(ctx, Team_1, Team_2, match_id[-4:], 7200, embed, view)
    # Send the embed to the channel


# Verify a profile exists
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


# Create a unique match id for more detailed data collection later
def generate_match_id():
    return f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"


# Finds the most even match mathematically based on elo
def best_team_partition(players, match_size):
    print(players)
    n = len(players)
    k = int(match_size / 2)

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


# Loads all player data and returns the team
# Needs to be renamed to reflect functionality or removed as it is a bit redundant
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


# Create the text and voice channels for a lobby. Assign permissions as needed
async def create_match_channels(ctx, Team_1, Team_2,
                                match_id, delete_after, embed, view):
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
    await text_channel.set_permissions(guild.default_role, view_channel=True, send_messages=False)
    await voice_channel1.set_permissions(guild.default_role, view_channel=True, connect=False)
    await voice_channel2.set_permissions(guild.default_role, view_channel=True, connect=False)

    for member in Team_1 + Team_2:
        if isinstance(member, discord.Member) or isinstance(member, discord.Role):
            await text_channel.set_permissions(member, view_channel=True, send_messages=True)
            await voice_channel1.set_permissions(member, view_channel=True, connect=True)
            await voice_channel2.set_permissions(member, view_channel=True, connect=True)
        else:
            print(f"Unexpected member type: {type(member)}")

    # Wait for the specified time before deleting the channels
    await sleep(delete_after)  # default match time is set to 2 hours = 7200 seconds

    # Delete channels
    await text_channel.delete()
    await voice_channel1.delete()
    await voice_channel2.delete()
    await category.delete()


def load_all_players():
    unsorted_leaderboard = {}
    new_player_list = []
    player_list = client.list()
    player_list = player_list[1:]
    for i in range(len(player_list)):
        new_player_list.append(player_list[i].name.split('/'))
        new_player_list[i][2] = new_player_list[i][2].split(".")[0]
        print(f"index {i}: {new_player_list[i]}")
    try:
        for file_name in new_player_list:
            player = Player.load_from_json(filename=file_name[1], username=file_name[2])
            unsorted_leaderboard[player.dis_name] = player.elo
    except ObjectNotFoundError:
        print("No player data found.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return unsorted_leaderboard


def get_sorted_leaderboard():
    unsorted_leaderboard = load_all_players()
    sorted_leaderboard = dict(sorted(unsorted_leaderboard.items(), key=lambda item: int(item[1]), reverse=True))
    return sorted_leaderboard


def distribute_ranks(leaderboard):
    # Assign numerical values to ranks
    rank_to_number = {rank: i + 1 for i, rank in enumerate(list_of_ranks)}
    number_to_rank = {i + 1: rank for i, rank in enumerate(list_of_ranks)}

    # Parameters
    N = len(leaderboard)  # Number of players
    mean_rank = len(list_of_ranks) / 2  # Mean rank (middle of the list)
    std_dev = 1.5  # Standard deviation (adjust based on how spread out you want ranks)

    # Generate normally distributed ranks
    np.random.seed(0)  # For reproducibility
    ranks = np.random.normal(loc=mean_rank, scale=std_dev, size=N)

    # Clip ranks to be within the range of available ranks
    ranks = np.clip(ranks, 1, len(list_of_ranks))

    # Convert numeric ranks to rank strings
    ranks = np.round(ranks).astype(int)
    rank_distribution = [number_to_rank[r] for r in ranks]
    sorted_rank_distribution = sorted(rank_distribution, key=lambda x: rank_to_number[x], reverse=True)
    return sorted_rank_distribution


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
        player.save_to_json(ctx.guild.id, dis_name)
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
@bot.group(name="Queue", aliases=["q"], help='Defunct, please use the queues in the top text channels')
async def Queue(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send(f"This command is now defunct, please use the queues in the top text channels")


@bot.command(name='feature-request',
             aliases=['fr', 'request', 'suggest'],
             help='Submit a feature request')
async def feature_request(ctx, *, arg):
    user = ctx.author
    await ctx.send("Feature request submitted! Thank you for your feedback.")
    await discord.utils.get(
        ctx.guild.text_channels,
        name="dev").send(f"{user.name} suggessted: \n {arg}")


# Command to show the leaderboard
@bot.command(name='leaderboard', help='Display the leaderboard sorted by ELO')
async def leaderboard(ctx, arg: Union[int, str] = 1):
    page = 1
    find_name = None

    print(arg)
    if arg is not None:
        if isinstance(arg, int):
            page = arg
            print("page is int")
        elif arg.startswith("<") and arg.endswith(">"):
            print("arg is discord object")
            dis_id = arg.strip("<@").strip(">")
            find_name = await bot.fetch_user(int(dis_id))
            print(f"looking for {find_name}")
        else:
            find_name = str(arg)
            find_name = find_name.lower()
            print(f"leaderboard looking for name {find_name}")

    leaderboard = client.download_as_text('leaderboard')  # download as str
    leaderboard = json.loads(leaderboard)  # convert back to a dict
    # print(leaderboard)
    rank_dist = distribute_ranks(leaderboard)

    if not leaderboard:
        await ctx.send("No players found.")
        return
    emoji = get(ctx.message.guild.emojis, name="CP")
    embed = discord.Embed(title=f"Leaderboard {emoji}", description=f"Page {page}/{len(leaderboard) // 10}",
                          color=discord.Color.yellow())
    table = "`Rank |  Name      |  ELO`\n"
    table += "`---------------------------`\n"

    for rank, (name, elo) in enumerate(leaderboard.items(), start=1):
        if str(find_name) == name:
            await ctx.send(f"{name} is rank {rank} with an elo of {elo}")
            print(f"{name} is rank {rank} with an elo of {elo}")
            return

        if rank > (page * 10 - 10):
            truncated_name = name[:9]  # Truncate the name if necessary
            emoji = get(ctx.message.guild.emojis, name=rank_dist[rank - 1])
            table += f"{str(emoji)}`{rank:<3}|  {truncated_name:<{10}}|  {elo}`\n"
        if rank > page * 10 and not find_name:
            break
    if not find_name:
        embed.add_field(name="Leaderboard", value=f"{table}", inline=False)
        await ctx.send(embed=embed)


@bot.command(name='make_leaderboard', help='create the leaderboard')
@commands.has_permissions(administrator=True)
async def make_leaderboard(ctx):
    leaderboard = get_sorted_leaderboard()
    client.upload_from_text('leaderboard', json.dumps(leaderboard))


# Run the bot
bot.run(os.environ['DISCORD_KEY'])



