import os
import aiofiles
import json

PLAYER_ROOT = "player_data"

async def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

async def get_player_path(guild_id: int, user_id: int) -> str:
    guild_path = os.path.join(PLAYER_ROOT, str(guild_id))
    await ensure_dir(guild_path)
    return os.path.join(guild_path, f"{user_id}.json")

async def load_or_create_player(guild_id: int, user) -> Player:
    path = await get_player_path(guild_id, user.id)

    # Try to load existing player file
    try:
        async with aiofiles.open(path, "r") as f:
            content = await f.read()
            data = json.loads(content)
            return Player(**data)
    except FileNotFoundError:
        # Create default player if file does not exist
        player = Player.default(user.display_name)
        await save_player(guild_id, user.id, player)
        return player

async def save_player(guild_id: int, user_id: int, player: Player):
    path = await get_player_path(guild_id, user_id)
    async with aiofiles.open(path, "w") as f:
        await f.write(json.dumps(player.to_dict(), indent=4))
