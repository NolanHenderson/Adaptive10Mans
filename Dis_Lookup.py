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

    if isinstance(search_term, discord.Member):
        for member__ in guild.members:
            if member__ == search_term:
                out = [member__, member__.id, member__.global_name, member__.guild_name]
                return out
    elif isinstance(search_term, int):
        for member__ in guild.members:
            if member__.id == search_term:
                out = [member__, member__.id, member__.global_name, member__.guild_name]
                return out
    elif isinstance(search_term, str):
        for member__ in guild.members:
            if member__.global_name == search_term:
                out = [member__, member__.id, member__.global_name, member__.guild_name]
                return out
        for member__ in guild.members:
            if member__.guild_name == search_term:
                out = [member__, member__.id, member__.global_name, member__.guild_name]
                return out
