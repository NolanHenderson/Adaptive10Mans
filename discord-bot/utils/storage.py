import json
from replit.object_storage import Client

client = Client()

def save_profile(guild_id, username, data):
    key = f"player_data/{guild_id}/{username}.json"
    client.upload_from_text(key, json.dumps(data))

def load_player(guild_id, username):
    key = f"player_data/{guild_id}/{username}.json"
    try:
        data = client.download_as_text(key)
        return json.loads(data)
    except:
        return None

def get_sorted_leaderboard():
    leaderboard = client.download_as_text('leaderboard')
    return dict(sorted(json.loads(leaderboard).items(), key=lambda x: x[1], reverse=True))
