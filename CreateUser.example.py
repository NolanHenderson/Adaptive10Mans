from peewee import *
from Database import *

User.insert(
    ubisoft_username = "My_Ubisoft_Username",
    discord_username = "My_Discord_Username",
    elo = 1500,
    wins = 0,
    losses = 0,
    rank = Rank.get(Rank.code == "G2"),
    region = Region.get(name = "US East"),
    system = System.get(code = "PC")
).on_conflict_ignore().execute()

user = (
    User
    .select(User, Rank)
    .join(Rank, on=(Rank.rank_id == User.rank_id))
    .join(Region, on=(Region.region_id == User.region_id))
    .join(System, on=(System.system_id == User.system_id))
    .where(User.discord_username == "My_Discord_Username")
    or [None]
)[0]

if user:
    print(f"Player {user.discord_username} is {user.rank.name} and plays on {user.system.name} in region {user.region.name}")
