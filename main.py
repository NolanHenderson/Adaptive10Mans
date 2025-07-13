import asyncio
import datetime
import json
import os
import random
import re
import time
import math
from asyncio import sleep
from itertools import combinations
from typing import Optional, Union, List

import discord
import numpy as np
import requests
from discord import file, team
from discord.ext import commands, tasks
from discord.ui import Button, View
from discord.utils import get
from replit.object_storage import Client
from replit.object_storage.errors import ObjectNotFoundError

from JSON_helper import *

from Dis_Lookup import search_player

client = Client()  # Create a client instance
role_dict = {}
match_size = 10
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

maps = [
    "Bank", "Border", "Chalet", "Clubhouse", "Consulate", "Kafe Dostoyevsky",
    "Lair", "Night Haven", "Skyscraper"
]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", case_insensitive=True, intents=intents)

# Get Discord token from environment variable
leaderboard_update_time = datetime.datetime.now()


def has_permission_ctx(ctx, **options):
    """
    Permission checker for prefix commands (uses ctx instead of interaction)
    """
    member = ctx.author
    user = ctx.author

    # Check if user is bot owner (highest priority)
    if options.get('bot_owner_ids') and user.id in options['bot_owner_ids']:
        return True

    # For guild-specific checks
    if ctx.guild and isinstance(member, discord.Member):
        # Check if user is server admin
        if options.get('require_admin') and member.guild_permissions.administrator:
            return True

        # Check if user has manage server permission
        if options.get('require_manage_server') and member.guild_permissions.manage_guild:
            return True

        # Check specific roles
        if options.get('required_roles'):
            if any(role.name in options['required_roles'] or role.id in options['required_roles']
                   for role in member.roles):
                return True

        # Check if user has any of the specified permissions
        if options.get('required_permissions'):
            for perm_name in options['required_permissions']:
                if hasattr(member.guild_permissions, perm_name):
                    if getattr(member.guild_permissions, perm_name):
                        return True

    # Check specific user IDs
    if options.get('allowed_user_ids') and user.id in options['allowed_user_ids']:
        return True

    return False


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
        self.last_join_time = datetime.datetime.now()  # Track whaen the last player joined
        self.timeout_task = asyncio.create_task(self.check_queue_timeout())  # Start timeout checker
        self.queue_timeout = 3600 * 3  # 1 hour timeout * n
        # self.queue_timeout = 60 # 1 Minute
        self.timeout_warning_sent = False  # Flag to track if a warning was sent

    def get_player_list(self):
        # Return the list of players in a formatted string
        displayed_players = self.player_list[:15]  # Only display first 15 players
        more_players_count = len(self.player_list) - 15

        players_text = "\n".join(
            [player.mention for player in displayed_players])
        if more_players_count > 0:
            players_text += f"\n+ {more_players_count} more"

        return players_text

    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.green, custom_id="join_game")
    async def join_game(self, interaction: discord.Interaction, button: Button):
        try:
            embed = self.embed_message.embeds[0]
            user = interaction.user
            guild_id = interaction.guild.id

            player = await load_or_create_player(guild_id, user)

            if user not in self.player_list:
                self.player_list.append(user)
                self.last_join_time = datetime.datetime.now()  # Update the timestamp when someone joins
                self.timeout_warning_sent = False  # Reset warning flag if a new player joins

            self.update_players_field(embed)
            await self.embed_message.edit(embed=embed)
            await interaction.response.send_message("You have joined the queue!", ephemeral=True)

            # For testing
            print(f"length of player list: {len(self.player_list)}")

            if len(self.player_list) >= match_size:
                print(self.player_list)
                roster = []
                for p in self.player_list:
                    loaded = await load_or_create_player(guild_id, p)
                    if loaded is None:
                        await interaction.response.send_message(f"Could not load profile for {p}", ephemeral=True)
                        return
                    roster.append(loaded)

                self.player_list = []
                self.update_players_field(embed)
                await self.embed_message.edit(embed=embed)
                print(roster)
                members, Team_1, Team_2, Discarded, elo_scale = make_a_match(self.ctx, roster, self.server_id)
                Team_1 = [discord.utils.get(self.ctx.guild.members, name=p.dis_name) for p in Team_1]
                Team_2 = [discord.utils.get(self.ctx.guild.members, name=p.dis_name) for p in Team_2]

                await asyncio.create_task(match_info(self.ctx, self.GID, Team_1, Team_2, elo_scale))
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

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

    async def check_queue_timeout(self):
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute

                # Calculate time since last join
                time_diff = (datetime.datetime.now() - self.last_join_time).total_seconds()

                # If 5 minutes before timeout and queue has players, send warning
                if time_diff > (self.queue_timeout - 300) and not self.timeout_warning_sent and len(
                        self.player_list) > 0:
                    channel = self.ctx.channel
                    await channel.send(f"⚠️ Warning: This queue will timeout in 5 minutes if no new players join.")
                    self.timeout_warning_sent = True

                # If timeout reached and queue has players, empty it
                if time_diff > self.queue_timeout and len(self.player_list) > 0:
                    embed = self.embed_message.embeds[0]

                    # Notify players that the queue timed out
                    channel = self.ctx.channel
                    player_mentions = " ".join([player.mention for player in self.player_list])
                    await channel.send(
                        f"Queue timed out after {self.queue_timeout // 60} minutes of inactivity. {player_mentions}")

                    # Empty the queue
                    self.player_list = []
                    self.update_players_field(embed)
                    await self.embed_message.edit(embed=embed)
                    self.timeout_warning_sent = False  # Reset warning flag

                # Reset the timer if queue is empty
                if len(self.player_list) == 0:
                    self.last_join_time = datetime.datetime.now()
                    self.timeout_warning_sent = False

        except Exception as e:
            print(f"Error in timeout checker: {e}")
            # Restart the task if it crashes
            self.timeout_task = asyncio.create_task(self.check_queue_timeout())


class LView(View):
    def __init__(self, ctx, Team_1, Team_2, server_id, elo_scale):
        super().__init__(timeout=7200)  # 2 hours
        self.randMapUsed = False
        self.matchOutcomeReported = False
        self.ctx = ctx
        self.Team_1 = Team_1
        self.Team_2 = Team_2
        self.elo_scale = elo_scale
        self.server_id = server_id
        self.blue_votes = 0
        self.orange_votes = 0
        self.voted_users = set()

        # Start timeout warning task
        self.timeout_warning_task = asyncio.create_task(self.check_match_timeout())

    async def check_match_timeout(self):
        """Check for match timeout and send warnings"""
        try:
            # Wait 1 hour 50 minutes (10 minutes before timeout)
            await asyncio.sleep(6600)  # 7200 - 600 = 6600 seconds

            if not self.matchOutcomeReported:
                await self.ctx.channel.send("⚠️ **Match Warning**: This match will end in 10 minutes. Current votes:\n"
                                            f"🔵 Blue Team: {self.blue_votes} votes\n"
                                            f"🟠 Orange Team: {self.orange_votes} votes\n"
                                            "Vote now or the team with more votes will win!")

            # Wait another 10 minutes
            await asyncio.sleep(600)

            # If still no outcome, award win to team with most votes
            if not self.matchOutcomeReported:
                await self.handle_timeout_result()

        except asyncio.CancelledError:
            # Task was cancelled (match ended normally)
            pass
        except Exception as e:
            print(f"Error in match timeout checker: {e}")

    async def handle_timeout_result(self):
        """Handle match result when timeout occurs"""
        if self.blue_votes > self.orange_votes:
            await self.ctx.channel.send("🔵 **Blue Team wins by timeout!** (More votes)")
            self.matchOutcomeReported = True
            self.elo_scale = 1 / self.elo_scale
            await self.adjust_elo(self.Team_1, self.Team_2, self.elo_scale)
        elif self.orange_votes > self.blue_votes:
            await self.ctx.channel.send("🟠 **Orange Team wins by timeout!** (More votes)")
            self.matchOutcomeReported = True
            await self.adjust_elo(self.Team_2, self.Team_1, self.elo_scale)
        else:
            await self.ctx.channel.send("⚖️ **Match ended in a draw!** (Equal votes - no ELO changes)")
            self.matchOutcomeReported = True
            # No ELO changes for draws

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

            if self.blue_votes == (match_size / 2) + 1:
                await interaction.channel.send("🔵 **Blue Team wins!**")
                self.matchOutcomeReported = True
                self.elo_scale = 1 / self.elo_scale
                await self.adjust_elo(self.Team_1, self.Team_2, self.elo_scale)
                # Cancel the timeout task since match is over
                self.timeout_warning_task.cancel()
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

            if self.orange_votes == (match_size / 2) + 1:
                await interaction.channel.send("🟠 **Orange Team wins!**")
                self.matchOutcomeReported = True
                await self.adjust_elo(self.Team_2, self.Team_1, self.elo_scale)
                # Cancel the timeout task since match is over
                self.timeout_warning_task.cancel()
        else:
            await interaction.response.send_message("Match outcome already reported.", ephemeral=True)

    async def on_timeout(self):
        """Handle View timeout (fallback)"""
        if not self.matchOutcomeReported:
            await self.handle_timeout_result()

    async def adjust_elo(self, winning_team, losing_team, elo_scale):
        """Adjust ELO and automatically update leaderboard"""
        for mem in winning_team:
            player = Player.load_from_json(self.server_id, mem.name)
            if player:  # Check if player exists
                player.elo = player.elo + (100 * elo_scale)
                player.wins += 1  # Increment wins
                player.save_to_json(self.server_id, mem.name)
            await sleep(1)

        for mem in losing_team:
            player = Player.load_from_json(self.server_id, mem.name)
            if player:  # Check if player exists
                player.elo = player.elo - (100 * elo_scale)
                player.losses += 1  # Increment losses
                player.save_to_json(self.server_id, mem.name)
            await sleep(1)

        # Automatically update leaderboard after ELO changes
        await self.update_leaderboard()

    async def update_leaderboard(self):
        """Automatically update the leaderboard after match completion"""
        try:
            leaderboard = get_sorted_leaderboard()
            client.upload_from_text('leaderboard', json.dumps(leaderboard))
            leaderboard_update_time = datetime.datetime.now()
            print("Leaderboard automatically updated after match completion")
        except Exception as e:
            print(f"Error updating leaderboard: {e}")


# Command to create a new LFG queue with the updated QView
@bot.command()
async def lfg(ctx, region, system):  # Removed interaction parameter
    permission_options = {
        'require_admin': False,
        'allowed_user_ids': [21084091485834444],
        'required_roles': ['Helper'],
        'bot_owner_ids': []
    }

    # Use ctx instead of interaction for permission checking
    if not has_permission_ctx(ctx, **permission_options):
        await ctx.send("You need staff permissions to use this command.")
        return

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
        return self.__dict__

    @staticmethod
    def default(dis_name):
        return {
            'ubi_name': "unknown",
            'dis_name': dis_name,
            'elo': 1000,
            'wins': 0,
            'losses': 0,
            'rank': "Null",
            'region': "Null",
            'system': "Null"
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
async def match_info(ctx, match_id, Team_1, Team_2, elo_scale):
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
    embed.add_field(name="Or, click below to recieve a random map",
                    value=" ",
                    inline=False)

    # Optionally, add a footer or other information
    embed.set_footer(text="Good luck to both teams!")

    # for mem in range(5):
    #    Team_1_usrs[mem] = discord.utils.get(ctx.guild.members,name=Team_1[mem].dis_name)
    #    Team_2_usrs[mem] = discord.utils.get(ctx.guild.members,name=Team_2[mem].dis_name)
    view = LView(ctx, Team_1, Team_2, ctx.guild.id, elo_scale)
    await create_match_channels(ctx, Team_1, Team_2, match_id[-4:], 7200,
                                embed, view)
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
    random.shuffle(players)
    print(players)
    n = len(players)
    k = int(match_size / 2)

    all_indices = set(range(n))
    min_diff = float('inf')
    best_team1 = None
    best_team2 = None
    best_discarded = None
    best_elo_scale = 1

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
            elo_scale = abs(score1) / abs(score2)
            if diff < min_diff:
                min_diff = diff
                best_elo_scale = elo_scale
                best_team1 = team1
                best_team2 = team2
                best_discarded = discarded

    return best_team1, best_team2, best_discarded, best_elo_scale


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

    Team_1, Team_2, Discarded, elo_scale = best_team_partition(
        players, match_size)
    # Return the members for this match and clear them from the queue
    members = [dis for dis in roster if dis in Team_1 or dis in Team_2]

    return members, Team_1, Team_2, Discarded, elo_scale


# Create the text and voice channels for a lobby. Assign permissions as needed
async def create_match_channels(ctx, Team_1, Team_2, match_id, delete_after,
                                embed, view):
    guild = ctx.guild
    category = await guild.create_category(f"Match {match_id}")

    # Create text channel
    text_channel = await guild.create_text_channel(f"match-{match_id}-chat",
                                                   category=category)
    mentions = ' '.join(mem.mention for mem in Team_1 + Team_2)
    await text_channel.send(mentions)
    await text_channel.send(embed=embed, view=view)
    await sleep(10)
    # Create voice channels
    voice_channel1 = await guild.create_voice_channel(f"Blue - {match_id}",
                                                      category=category)
    voice_channel2 = await guild.create_voice_channel(f"Orange - {match_id}",
                                                      category=category)

    # Set permissions for text channel
    await text_channel.set_permissions(guild.default_role,
                                       view_channel=True,
                                       send_messages=False)
    await voice_channel1.set_permissions(guild.default_role,
                                         view_channel=True,
                                         connect=False)
    await voice_channel2.set_permissions(guild.default_role,
                                         view_channel=True,
                                         connect=False)

    for member in Team_1 + Team_2:
        if isinstance(member, discord.Member) or isinstance(
                member, discord.Role):
            await text_channel.set_permissions(member,
                                               view_channel=True,
                                               send_messages=True)
            await voice_channel1.set_permissions(member,
                                                 view_channel=True,
                                                 connect=True)
            await voice_channel2.set_permissions(member,
                                                 view_channel=True,
                                                 connect=True)
        else:
            print(f"Unexpected member type: {type(member)}")

    # Wait for the specified time before deleting the channels
    await sleep(delete_after
                )  # default match time is set to 2 hours = 7200 seconds

    # Delete channels
    await text_channel.delete()
    await voice_channel1.delete()
    await voice_channel2.delete()
    await category.delete()


def load_all_players():
    """Load all players across all servers"""
    unsorted_leaderboard = {}

    # Get all files from object storage
    player_list = client.list()
    print(f"Total files found: {len(player_list)}")

    # Filter for player_data files only (remove the problematic [2:] slice)
    player_files = [item for item in player_list if item.name.startswith('player_data/')]
    print(f"Player data files found: {len(player_files)}")

    successful_loads = 0
    failed_loads = 0

    for player_file in player_files:
        try:
            # Parse path: player_data/server_id/username.json
            path_parts = player_file.name.split('/')
            if len(path_parts) >= 3:
                server_id = path_parts[1]
                username = path_parts[2].split('.')[0]  # Remove .json extension

                player = Player.load_from_json(filename=server_id, username=username)
                if player and hasattr(player, 'dis_name') and hasattr(player, 'elo'):
                    unsorted_leaderboard[player.dis_name] = player.elo
                    successful_loads += 1
                else:
                    failed_loads += 1
        except Exception as e:
            print(f"Failed to load player from {player_file.name}: {str(e)}")
            failed_loads += 1

    print(f"Successfully loaded: {successful_loads}, Failed: {failed_loads}")
    return unsorted_leaderboard


def load_players_for_server(server_id):
    """Load players only for a specific server - recommended for server-specific leaderboards"""
    unsorted_leaderboard = {}

    # Get all files from object storage
    player_list = client.list()

    # Filter for current server's player data files
    server_player_files = [
        item for item in player_list
        if item.name.startswith(f'player_data/{server_id}/')
    ]

    print(f"Found {len(server_player_files)} player files for server {server_id}")

    successful_loads = 0
    failed_loads = 0

    for player_file in server_player_files:
        try:
            # Extract username from path: player_data/server_id/username.json
            username = player_file.name.split('/')[-1].split('.')[0]

            player = Player.load_from_json(filename=str(server_id), username=username)
            if player and hasattr(player, 'dis_name') and hasattr(player, 'elo'):
                unsorted_leaderboard[player.dis_name] = player.elo
                successful_loads += 1
            else:
                print(f"Invalid player data for {username}")
                failed_loads += 1
        except Exception as e:
            print(f"Failed to load player from {player_file.name}: {str(e)}")
            failed_loads += 1

    print(f"Server {server_id} - Successfully loaded: {successful_loads}, Failed: {failed_loads}")
    return unsorted_leaderboard


def get_sorted_leaderboard(server_id=None):
    """Get sorted leaderboard, optionally filtered by server"""
    if server_id:
        unsorted_leaderboard = load_players_for_server(server_id)
    else:
        unsorted_leaderboard = load_all_players()

    sorted_leaderboard = dict(
        sorted(unsorted_leaderboard.items(),
               key=lambda item: int(item[1]),
               reverse=True))
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
    sorted_rank_distribution = sorted(rank_distribution,
                                      key=lambda x: rank_to_number[x],
                                      reverse=True)
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

        region = "US East"
        # await ask_user_for_input(
        #    new_user, "Please enter your region from this list:\n"
        #              "(Asia East, Asia South East, Japan East, South Africa North, "
        #               "UAE North, EU West, EU North, US East, US Central, US West, "
        #                 "US South Central, Brazil South, Australia East)")
        # if region.lower() in [r.lower() for r in list_of_regions]:
        #    print(f"Collected region: {region}")
        # else:
        #    await new_user.send(
        #        "Invalid region. Please use !setup profile again.")
        #    return

        system = await ask_user_for_input(
            new_user, "Please enter your system:\n"
                      '(PC, Xbox, PS. if you play on multiple, say: "PC PS")')
        if system.lower() in [stm.lower() for stm in list_of_systems]:
            pass
        else:
            await new_user.send(
                "Invalid system. Please use !setup profile again.")
            return

        rank = "G1"
        #        await ask_user_for_input(
        #    new_user, "Please enter your rank:\n"
        #              "(Use the form G1 for Gold 1, P3 for Plat 3, etc... Use D1 for champ.)"
        # )
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
    # Set the bot's status message
    activity = discord.Game(name="Now with ranks!")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(f'Logged in as {bot.user}')


# Create a group of commands under !Queue
@bot.group(name="Queue",
           aliases=["q"],
           help='Defunct, please use the queues in the top text channels')
async def Queue(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send(
            f"This command is now defunct, please use the queues in the top text channels"
        )


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
# Replace your existing leaderboard command with this fixed version

@bot.command(name='leaderboard', help='Display the leaderboard sorted by ELO')
async def leaderboard(ctx, arg: Union[int, str] = 1):
    page = 1
    find_name = None

    print(f"Leaderboard command called with arg: {arg}")

    if arg is not None:
        if isinstance(arg, int):
            page = arg
            print(f"Page is int: {page}")
        elif isinstance(arg, str) and arg.startswith("<") and arg.endswith(">"):
            print("Arg is discord mention")
            dis_id = arg.strip("<@!").strip("<@").strip(">")
            try:
                find_name = await bot.fetch_user(int(dis_id))
                find_name = find_name.name
                print(f"Looking for user: {find_name}")
            except:
                await ctx.send("❌ Could not find that user.")
                return
        else:
            find_name = str(arg).lower()
            print(f"Looking for name: {find_name}")

    try:
        # Try server-specific leaderboard first
        leaderboard_key = f'leaderboard_{ctx.guild.id}'
        try:
            leaderboard = client.download_as_text(leaderboard_key)
            leaderboard = json.loads(leaderboard)
        except:
            # Fall back to global leaderboard or create new one
            print("Server-specific leaderboard not found, creating new one...")
            leaderboard = get_sorted_leaderboard(server_id=ctx.guild.id)
            client.upload_from_text(leaderboard_key, json.dumps(leaderboard))

    except Exception as e:
        await ctx.send("❌ Error loading leaderboard data.")
        print(f"Error loading leaderboard: {e}")
        return

    if not leaderboard:
        await ctx.send("No players found. Use `$make_leaderboard` to create one.")
        return

    # Calculate total pages correctly using ceiling division
    total_pages = math.ceil(len(leaderboard) / 10)

    # If searching for a specific player
    if find_name:
        found_player = False
        for rank, (name, elo) in enumerate(leaderboard.items(), start=1):
            # Check both exact match and case-insensitive partial match
            if (name.lower() == find_name.lower() or
                    find_name.lower() in name.lower()):

                # Get rank distribution for emoji
                rank_dist = distribute_ranks(leaderboard)
                emoji = get(ctx.guild.emojis, name=rank_dist[rank - 1])
                rank_emoji = emoji if emoji else ""

                embed = discord.Embed(
                    title="Player Found!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Player", value=name, inline=True)
                embed.add_field(name="Rank", value=f"#{rank}", inline=True)
                embed.add_field(name="ELO", value=str(elo), inline=True)

                if rank_emoji:
                    embed.add_field(name="Tier", value=f"{rank_emoji} {rank_dist[rank - 1]}", inline=True)

                # Calculate which page this player would be on
                player_page = math.ceil(rank / 10)
                embed.add_field(name="Page", value=f"{player_page}/{total_pages}", inline=True)

                await ctx.send(embed=embed)
                found_player = True
                break

        if not found_player:
            await ctx.send(f"❌ Player '{find_name}' not found in the leaderboard.")
        return

    # Validate page number
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    # Get rank distribution
    rank_dist = distribute_ranks(leaderboard)

    # Create leaderboard embed
    emoji = get(ctx.message.guild.emojis, name="CP")
    embed = discord.Embed(
        title=f"Leaderboard {emoji if emoji else '🏆'}",
        description=f"Page {page}/{total_pages} \nLast Update: {int((datetime.datetime.now() - leaderboard_update_time).total_seconds() // 60)} minutes ago",
        color=discord.Color.yellow()
    )

    # Build the leaderboard table
    table = "`Rank |  Name      |  ELO`\n"
    table += "`---------------------------`\n"

    # Calculate start and end positions for current page
    start_rank = (page - 1) * 10 + 1
    end_rank = min(page * 10, len(leaderboard))

    current_rank = 0
    for name, elo in leaderboard.items():
        current_rank += 1

        # Only show players for the current page
        if start_rank <= current_rank <= end_rank:
            truncated_name = name[:9]  # Truncate the name if necessary
            elo_str = str(elo)[:4]  # Truncate the ELO if necessary

            # Get rank emoji (make sure we don't go out of bounds)
            if current_rank <= len(rank_dist):
                emoji = get(ctx.message.guild.emojis, name=rank_dist[current_rank - 1])
                emoji_str = str(emoji) if emoji else "🔸"
            else:
                emoji_str = "🔸"

            table += f"{emoji_str}`{current_rank:<3}|  {truncated_name:<{10}}|  {elo_str:<{4}}`\n"

    embed.add_field(name="Rankings", value=f"{table}", inline=False)

    # Add navigation hints
    if total_pages > 1:
        nav_text = f"Use `$leaderboard {page - 1 if page > 1 else page}` or `$leaderboard {page + 1 if page < total_pages else page}` to navigate"
        embed.set_footer(text=nav_text)

    await ctx.send(embed=embed)


@bot.command(name='make_leaderboard', help='create the leaderboard')
@commands.has_permissions(administrator=True)
async def make_leaderboard(ctx):
    await ctx.send("🔄 Creating leaderboard...")

    # Use server-specific leaderboard
    leaderboard = get_sorted_leaderboard(server_id=ctx.guild.id)

    # Store with server-specific key
    leaderboard_key = f'leaderboard_{ctx.guild.id}'
    client.upload_from_text(leaderboard_key, json.dumps(leaderboard))

    global leaderboard_update_time
    leaderboard_update_time = datetime.datetime.now()

    embed = discord.Embed(title="Leaderboard Updated ✅", color=discord.Color.green())
    embed.add_field(name="Players Found", value=str(len(leaderboard)), inline=True)
    embed.add_field(name="Server ID", value=str(ctx.guild.id), inline=True)

    await ctx.send(embed=embed)


@bot.command(name='DataBase', help='Refactor the DB')
@commands.has_permissions(administrator=True)
async def DataBase(ctx):
    guild = ctx.guild
    for member in guild.members:
        file_ = Player.load_from_json(guild, member.name)
        if file_ is not None:
            print(f"Loaded {file_}")
            file_.save_to_json(guild, member.id)
            print(f"saved {file_} as {member.id}")


@bot.command(name='adjust_elo',
             aliases=['elo', 'adjust'],
             help='Manually adjust a player\'s ELO points')
@commands.has_permissions(administrator=True)
async def adjust_elo(ctx, user: discord.Member, amount: int):
    """
    Manually adjust a player's ELO and update the leaderboard
    Usage: $adjust_elo @player +50 or $adjust_elo @player -25
    """
    try:
        # Use sanitized filename to match how the data is stored
        sanitized_username = Player.sanitize_filename(user.name)

        # Load the player's profile using the sanitized name
        player = Player.load_from_json(ctx.guild.id, sanitized_username)

        if player is None:
            await ctx.send(f"❌ No profile found for {user.display_name}. They need to use `$setup_profile` first.")
            return

        # Store old ELO for comparison
        old_elo = player.elo

        # Adjust the ELO
        player.elo += amount

        # Prevent negative ELO (optional - remove if you want to allow negative ELO)
        if player.elo < 0:
            player.elo = 0

        # Save the updated player data using the sanitized name
        player.save_to_json(ctx.guild.id, sanitized_username)

        # Update the leaderboard
        leaderboard = get_sorted_leaderboard(server_id=ctx.guild.id)
        leaderboard_key = f'leaderboard_{ctx.guild.id}'
        client.upload_from_text(leaderboard_key, json.dumps(leaderboard))
        global leaderboard_update_time
        leaderboard_update_time = datetime.datetime.now()

        # Create embed for confirmation
        embed = discord.Embed(
            title="ELO Adjustment Complete",
            color=discord.Color.green() if amount > 0 else discord.Color.red()
        )
        embed.add_field(name="Player", value=user.mention, inline=True)
        embed.add_field(name="Previous ELO", value=str(old_elo), inline=True)
        embed.add_field(name="Adjustment", value=f"{'+' if amount > 0 else ''}{amount}", inline=True)
        embed.add_field(name="New ELO", value=str(player.elo), inline=True)
        embed.add_field(name="Change", value=f"{old_elo} → {player.elo}", inline=False)
        embed.set_footer(text=f"Adjusted by {ctx.author.display_name}")

        await ctx.send(embed=embed)
        print(f"ELO adjusted for {user.name}: {old_elo} → {player.elo} (change: {amount})")

    except Exception as e:
        await ctx.send(f"❌ An error occurred while adjusting ELO: {str(e)}")
        print(f"Error adjusting ELO for {user.name}: {e}")


@bot.command(name='debug_players', help='Debug command to check player data')
@commands.has_permissions(administrator=True)
async def debug_players(ctx):
    """Debug command to check how many players are actually stored"""
    try:
        # Get raw player list from object storage
        player_list = client.list()
        print(f"Raw client.list() result: {player_list}")

        # Filter for player data files
        player_files = [item for item in player_list if item.name.startswith('player_data/')]

        embed = discord.Embed(title="Player Data Debug", color=discord.Color.orange())
        embed.add_field(name="Total Files in Storage", value=str(len(player_list)), inline=True)
        embed.add_field(name="Player Data Files", value=str(len(player_files)), inline=True)

        # Count players per server
        server_counts = {}
        for file_item in player_files:
            parts = file_item.name.split('/')
            if len(parts) >= 3:  # player_data/server_id/player.json
                server_id = parts[1]
                server_counts[server_id] = server_counts.get(server_id, 0) + 1

        embed.add_field(name="Players in Current Server",
                        value=str(server_counts.get(str(ctx.guild.id), 0)), inline=True)

        # Show first few player files for current server
        current_server_files = [f for f in player_files if f.name.startswith(f'player_data/{ctx.guild.id}/')]
        if current_server_files:
            sample_files = current_server_files[:5]  # Show first 5
            file_names = '\n'.join([f.name.split('/')[-1] for f in sample_files])
            embed.add_field(name="Sample Player Files", value=f"```{file_names}```", inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Debug error: {str(e)}")
        print(f"Debug error: {e}")


@bot.command(name='debug_leaderboard', help='Debug the leaderboard generation process')
@commands.has_permissions(administrator=True)
async def debug_leaderboard(ctx):
    """Debug the leaderboard generation step by step"""
    try:
        embed = discord.Embed(title="Leaderboard Debug", color=discord.Color.orange())

        # Step 1: Check stored leaderboard
        try:
            stored_leaderboard = client.download_as_text('leaderboard')
            stored_data = json.loads(stored_leaderboard)
            embed.add_field(name="Stored Leaderboard Players",
                            value=str(len(stored_data)), inline=True)
        except Exception as e:
            embed.add_field(name="Stored Leaderboard Error", value=str(e), inline=True)
            stored_data = {}

        # Step 2: Generate fresh leaderboard
        try:
            fresh_leaderboard = load_all_players()
            embed.add_field(name="Fresh Load Players",
                            value=str(len(fresh_leaderboard)), inline=True)
        except Exception as e:
            embed.add_field(name="Fresh Load Error", value=str(e), inline=True)
            fresh_leaderboard = {}

        # Step 3: Compare
        if stored_data and fresh_leaderboard:
            missing_from_stored = set(fresh_leaderboard.keys()) - set(stored_data.keys())
            missing_from_fresh = set(stored_data.keys()) - set(fresh_leaderboard.keys())

            if missing_from_stored:
                embed.add_field(name="Missing from Stored",
                                value=f"{len(missing_from_stored)} players", inline=True)
            if missing_from_fresh:
                embed.add_field(name="Missing from Fresh",
                                value=f"{len(missing_from_fresh)} players", inline=True)

        # Step 4: Show the load_all_players process details
        await ctx.send(embed=embed)

        # Step 5: Show detailed load process
        await debug_load_process(ctx)

    except Exception as e:
        await ctx.send(f"❌ Leaderboard debug error: {str(e)}")
        print(f"Leaderboard debug error: {e}")


async def debug_load_process(ctx):
    """Debug the load_all_players function step by step"""
    try:
        embed = discord.Embed(title="Load Process Debug", color=discord.Color.blue())

        # Replicate load_all_players step by step
        unsorted_leaderboard = {}
        new_player_list = []

        # Step 1: Get player list
        player_list = client.list()
        embed.add_field(name="1. Total Files", value=str(len(player_list)), inline=True)

        # Step 2: Filter and process
        player_list = player_list[2:]  # This line might be problematic!
        embed.add_field(name="2. After [2:] slice", value=str(len(player_list)), inline=True)

        # Step 3: Process file names
        for i in range(len(player_list)):
            new_player_list.append(player_list[i].name.split('/'))
            if len(new_player_list[i]) >= 3:
                new_player_list[i][2] = new_player_list[i][2].split(".")[0]

        # Filter for current server
        current_server_files = [item for item in new_player_list
                                if len(item) >= 3 and item[0] == 'player_data' and item[1] == str(ctx.guild.id)]

        embed.add_field(name="3. Current Server Files",
                        value=str(len(current_server_files)), inline=True)

        # Step 4: Try to load each player
        successful_loads = 0
        failed_loads = 0

        for file_name in current_server_files[:10]:  # Check first 10
            try:
                player = Player.load_from_json(filename=file_name[1], username=file_name[2])
                if player:
                    successful_loads += 1
                else:
                    failed_loads += 1
            except Exception as e:
                failed_loads += 1
                print(f"Failed to load {file_name}: {e}")

        embed.add_field(name="4. Sample Load Results",
                        value=f"✅ {successful_loads} / ❌ {failed_loads}", inline=True)

        # Show some sample file names
        if current_server_files:
            sample_names = ['/'.join(f) for f in current_server_files[:5]]
            embed.add_field(name="Sample File Paths",
                            value=f"```{chr(10).join(sample_names)}```", inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Load process debug error: {str(e)}")
        print(f"Load process debug error: {e}")


@bot.command(name='rebuild_leaderboard', help='Force rebuild the leaderboard from all player data')
@commands.has_permissions(administrator=True)
async def rebuild_leaderboard(ctx):
    """Rebuild the leaderboard from scratch"""
    try:
        await ctx.send("🔄 Rebuilding leaderboard from all player data...")

        # Get fresh leaderboard
        fresh_leaderboard = load_all_players()

        if not fresh_leaderboard:
            await ctx.send("❌ No player data found to rebuild leaderboard.")
            return

        # Sort it
        sorted_leaderboard = dict(
            sorted(fresh_leaderboard.items(),
                   key=lambda item: int(item[1]),
                   reverse=True)
        )

        # Save it
        client.upload_from_text('leaderboard', json.dumps(sorted_leaderboard))
        global leaderboard_update_time
        leaderboard_update_time = datetime.datetime.now()

        embed = discord.Embed(title="Leaderboard Rebuilt ✅", color=discord.Color.green())
        embed.add_field(name="Players Found", value=str(len(sorted_leaderboard)), inline=True)
        embed.add_field(name="Pages", value=str(math.ceil(len(sorted_leaderboard) / 10)), inline=True)

        await ctx.send(embed=embed)

        # Show top 5 for verification
        top_5 = list(sorted_leaderboard.items())[:5]
        top_5_text = '\n'.join([f"{i + 1}. {name}: {elo}" for i, (name, elo) in enumerate(top_5)])

        verification_embed = discord.Embed(title="Top 5 Verification", color=discord.Color.blue())
        verification_embed.add_field(name="Rankings", value=f"```{top_5_text}```", inline=False)
        await ctx.send(embed=verification_embed)

    except Exception as e:
        await ctx.send(f"❌ Rebuild error: {str(e)}")
        print(f"Rebuild error: {e}")


@bot.command(name='ban', help='Display player information for potential ban')
@commands.has_permissions(administrator=True)
async def ban_player(ctx, player_identifier, *, reason="No reason provided"):
    """
    Ban command to find and display player information
    Usage: $ban @player reason or $ban "player_name" reason
    """
    try:
        target_user = None
        player_data = None

        # Try to parse as Discord mention first
        if player_identifier.startswith("<@") and player_identifier.endswith(">"):
            # Extract user ID from mention
            user_id = player_identifier.strip("<@!").strip("<@").strip(">")
            try:
                target_user = await bot.fetch_user(int(user_id))
            except:
                await ctx.send("❌ Could not find that Discord user.")
                return
        else:
            # Try to find by display name or username
            target_user = discord.utils.get(ctx.guild.members, display_name=player_identifier)
            if not target_user:
                target_user = discord.utils.get(ctx.guild.members, name=player_identifier)

        if not target_user:
            await ctx.send(f"❌ Could not find Discord user: `{player_identifier}`")
            return

        # Load player profile data
        sanitized_username = Player.sanitize_filename(target_user.name)
        player_data = Player.load_from_json(ctx.guild.id, sanitized_username)

        # Create embed with player information
        embed = discord.Embed(
            title="🚫 Player Ban Information",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )

        # Discord Information
        embed.add_field(
            name="Discord Information",
            value=f"**Name:** {target_user.name}\n"
                  f"**Display Name:** {target_user.display_name}\n"
                  f"**User ID:** {target_user.id}\n"
                  f"**Mention:** {target_user.mention}",
            inline=False
        )

        # Player Profile Information
        if player_data:
            # Get rank emoji if available
            rank_emoji = get(ctx.guild.emojis, name=player_data.rank)
            rank_display = f"{rank_emoji} {player_data.rank}" if rank_emoji else player_data.rank

            # Calculate win rate
            total_games = player_data.wins + player_data.losses
            win_rate = (player_data.wins / total_games * 100) if total_games > 0 else 0

            embed.add_field(
                name="Game Profile",
                value=f"**Ubisoft Name:** {player_data.ubi_name}\n"
                      f"**ELO:** {player_data.elo}\n"
                      f"**Rank:** {rank_display}\n"
                      f"**Region:** {player_data.region}\n"
                      f"**System:** {player_data.system}",
                inline=True
            )

            embed.add_field(
                name="Match Statistics",
                value=f"**Wins:** {player_data.wins}\n"
                      f"**Losses:** {player_data.losses}\n"
                      f"**Total Games:** {total_games}\n"
                      f"**Win Rate:** {win_rate:.1f}%",
                inline=True
            )
        else:
            embed.add_field(
                name="Game Profile",
                value="❌ No profile found\n*Player has not used `$setup_profile`*",
                inline=False
            )

        # Ban Information
        embed.add_field(
            name="Ban Details",
            value=f"**Reason:** {reason}\n"
                  f"**Requested by:** {ctx.author.mention}\n"
                  f"**Server:** {ctx.guild.name}",
            inline=False
        )

        # Add thumbnail (user avatar)
        embed.set_thumbnail(url=target_user.display_avatar.url)

        # Add footer
        embed.set_footer(
            text=f"Action pending • Server ID: {ctx.guild.id}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None
        )

        await ctx.send(embed=embed)

        # Log to console for debugging
        print(f"Ban command executed by {ctx.author.name} for {target_user.name}")
        print(f"Reason: {reason}")
        print(f"Player data found: {'Yes' if player_data else 'No'}")

    except Exception as e:
        await ctx.send(f"❌ An error occurred while processing the ban command: {str(e)}")
        print(f"Error in ban command: {e}")


# Run the bot
bot.run(os.environ['DISCORD_KEY'])