from peewee import *

db = SqliteDatabase("db.sqlite")

class BaseModel(Model):
    class Meta:
        database = db

# The player's system (PC, XBOX, PS)
class System(BaseModel):
    system_id = PrimaryKeyField()
    name = CharField(unique=True)
    code = CharField(unique=True)

# A major region - contains one or more region
class MajorRegion(BaseModel):
    major_region_id = PrimaryKeyField()
    name = CharField(unique=True)
    code = CharField(unique=True)
    class Meta:
        table_name = 'major_region'

# A region
class Region(BaseModel):
    region_id = PrimaryKeyField()
    name = CharField(unique=True)
    major_region = ForeignKeyField(MajorRegion, to_field="major_region_id")

# An R6 rank
class Rank(BaseModel):
    rank_id = PrimaryKeyField()
    name = CharField(unique=True)
    code = CharField(unique=True)

# A user
class User(BaseModel):
    user_id = PrimaryKeyField()
    ubisoft_username = CharField(unique=True)
    discord_username = CharField(unique=True)
    elo = IntegerField()
    wins = IntegerField()
    losses = IntegerField()
    rank = ForeignKeyField(Rank, to_field="rank_id")
    region = ForeignKeyField(Region, to_field="region_id")
    system = ForeignKeyField(System, to_field="system_id")

if not System.table_exists():
    System.create_table()

if not MajorRegion.table_exists():
    MajorRegion.create_table()

if not Region.table_exists():
    Region.create_table()

if not Rank.table_exists():
    Rank.create_table()

if not User.table_exists():
    User.create_table()
    
if db.is_closed():
    db.connect()


# Seed database
MajorRegion.insert_many([
    { MajorRegion.name: "Japan", MajorRegion.code: "ja" },
    { MajorRegion.name: "South Africa", MajorRegion.code: "so" },
    { MajorRegion.name: "United Arab Emirates", MajorRegion.code: "ua" },
    { MajorRegion.name: "Europe", MajorRegion.code: "eu" },
    { MajorRegion.name: "United States", MajorRegion.code: "us" },
    { MajorRegion.name: "Brazil", MajorRegion.code: "br" },
    { MajorRegion.name: "Australia", MajorRegion.code: "au" },
    { MajorRegion.name: "Africa", MajorRegion.code: "af" },
]).on_conflict_ignore().execute()

Region.insert_many([
    { Region.name: "Asia East", Region.major_region: MajorRegion.get(MajorRegion.code == "ja") },
    { Region.name: "Asia South East", Region.major_region: MajorRegion.get(MajorRegion.code == "ja") },
    { Region.name: "Japan East", Region.major_region: MajorRegion.get(MajorRegion.code == "ja") },
    { Region.name: "South Africa North", Region.major_region: MajorRegion.get(MajorRegion.code == "so") },
    { Region.name: "UAE North", Region.major_region: MajorRegion.get(MajorRegion.code == "ua") },
    { Region.name: "EU West", Region.major_region: MajorRegion.get(MajorRegion.code == "eu") },
    { Region.name: "EU North", Region.major_region: MajorRegion.get(MajorRegion.code == "eu") },
    { Region.name: "US East", Region.major_region: MajorRegion.get(MajorRegion.code == "us") },
    { Region.name: "US Central", Region.major_region: MajorRegion.get(MajorRegion.code == "us") },
    { Region.name: "US West", Region.major_region: MajorRegion.get(MajorRegion.code == "us") },
    { Region.name: "US South Central", Region.major_region: MajorRegion.get(MajorRegion.code == "us") },
    { Region.name: "Brazil South", Region.major_region: MajorRegion.get(MajorRegion.code == "br") },
    { Region.name: "Australia East", Region.major_region: MajorRegion.get(MajorRegion.code == "au") }
]).on_conflict_ignore().execute()

Rank.insert_many([
    { Rank.name: "Copper V", Rank.code: "C5" },
    { Rank.name: "Copper IV", Rank.code: "C4" },
    { Rank.name: "Copper III", Rank.code: "C3" },
    { Rank.name: "Copper II", Rank.code: "C2" },
    { Rank.name: "Copper I", Rank.code: "C1" },
    { Rank.name: "Bronze V", Rank.code: "B5" },
    { Rank.name: "Bronze IV", Rank.code: "B4" },
    { Rank.name: "Bronze III", Rank.code: "B3" },
    { Rank.name: "Bronze II", Rank.code: "B2" },
    { Rank.name: "Bronze I", Rank.code: "B1" },
    { Rank.name: "Silver V", Rank.code: "S5" },
    { Rank.name: "Silver IV", Rank.code: "S4" },
    { Rank.name: "Silver III", Rank.code: "S3" },
    { Rank.name: "Silver II", Rank.code: "S2" },
    { Rank.name: "Silver I", Rank.code: "S1" },
    { Rank.name: "Gold V", Rank.code: "G5" },
    { Rank.name: "Gold IV", Rank.code: "G4" },
    { Rank.name: "Gold III", Rank.code: "G3" },
    { Rank.name: "Gold II", Rank.code: "G2" },
    { Rank.name: "Gold I", Rank.code: "G1" },
    { Rank.name: "Platinum V", Rank.code: "P5" },
    { Rank.name: "Platinum IV", Rank.code: "P4" },
    { Rank.name: "Platinum III", Rank.code: "P3" },
    { Rank.name: "Platinum II", Rank.code: "P2" },
    { Rank.name: "Platinum I", Rank.code: "P1" },
    { Rank.name: "Emerald V", Rank.code: "E5" },
    { Rank.name: "Emerald IV", Rank.code: "E4" },
    { Rank.name: "Emerald III", Rank.code: "E3" },
    { Rank.name: "Emerald II", Rank.code: "E2" },
    { Rank.name: "Emerald I", Rank.code: "E1" },
    { Rank.name: "Diamond V", Rank.code: "D5" },
    { Rank.name: "Diamond IV", Rank.code: "D4" },
    { Rank.name: "Diamond III", Rank.code: "D3" },
    { Rank.name: "Diamond II", Rank.code: "D2" },
    { Rank.name: "Diamond I", Rank.code: "D1" },
    { Rank.name: "Champion", Rank.code: "F" }
]).on_conflict_ignore().execute()

System.insert_many([
    { System.name: "PC", MajorRegion.code: "PC" },
    { System.name: "PlayStation", MajorRegion.code: "PS" },
    { System.name: "XBox", MajorRegion.code: "Xbox" },
]).on_conflict_ignore().execute()