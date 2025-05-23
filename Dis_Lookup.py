import discord


async def search_player(guild, search_term):
    """
    Search for a player based on user ID, username, discord.member object, etc...

    Parameters:
    - guild: discord.Guild, guild (server) you are searching in.
    - search_term: Union[str, int, discord.Member], the term to search for.

    Returns:
    - A list of the form: [discord.Member, user_ID, user_name, guild_nickname]
        missing data will be type None
    """

    print(f"Looking up player with arg: {search_term}")
    try:
        if search_term.startswith("<@"):
            search_term = search_term.strip("<@").strip(">")
            print(f"search_term stripped to: {search_term}")
            search_term = int(search_term)
    except AttributeError:
        pass

    if isinstance(search_term, discord.Member):
        for member__ in guild.members:
            if member__ == search_term:
                out = [member__]
                return out
    elif isinstance(search_term, int):
        for member__ in guild.members:
            if member__.id == search_term:
                out = [member__]
                return out
    elif isinstance(search_term, str):
        for member__ in guild.members:
            if member__.global_name == search_term:
                out = [member__]
                return out
        for member__ in guild.members:
            if member__.display_name == search_term:
                out = [member__]
                return out
        for member__ in guild.members:
            if member__.name == search_term:
                out = [member__]
                return out

    else:
        return None
