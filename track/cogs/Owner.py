from discord.ext import commands
import discord

import asyncio
import pickle

import utils


class Owner(commands.Cog):
    """
    Commands for bot owner.
    """

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner()
        return True

    @commands.command(brief='Sends a message to current channel.')
    async def echo(self, ctx, *, message):
        """
        Sends a message to current channel.
        """
        await ctx.send(message)

    @commands.command(brief='Sends a message to a channel.')
    async def send(self, ctx, channel: discord.TextChannel, *, message):
        """
        Sends a message to a channel.
        """
        await channel.send(message)
        await ctx.message.add_reaction('✅')

    @commands.command(brief='Starts typing to a channel.')
    async def type(self, ctx, duration=10, channel: discord.TextChannel = None):
        """
        Starts typing to a channel.
        """
        await ctx.message.add_reaction('🕓')
        if channel is None:
            channel = ctx.message.channel
        async with channel.typing():
            await asyncio.sleep(duration)
        await ctx.message.add_reaction('✅')

    @commands.command()
    async def guilds(self, ctx):
        await ctx.send('\n'.join([f'{guild.name} ({guild.member_count})' for guild in self.bot.guilds]))

    @commands.command()
    async def debug(self, ctx, *, string=''):
        async with utils.Transaction(self.bot.db) as conn:
            # await conn.execute('ALTER TABLE guilds ADD builds_channel INTEGER')
            # await conn.execute('ALTER TABLE builds ADD in_queue INTEGER DEFAULT 0')
            # await conn.execute('CREATE TABLE IF NOT EXISTS stats (id timestamp PRIMARY KEY, stats BLOB)')
            # await conn.execute(f'ALTER TABLE guilds ADD disabled_commands BLOB')
            # await conn.execute(f'ALTER TABLE guilds ADD disabled_categories BLOB')
            # await conn.execute(f'UPDATE guilds SET disabled_commands = ?', (pickle.dumps(set()),))
            # await conn.execute(f'UPDATE guilds SET disabled_categories = ?', (pickle.dumps(set()),))
            # await conn.execute('ALTER TABLE guilds RENAME TO guilds_orig')
            # await conn.execute('CREATE TABLE guilds(id INTEGER PRIMARY KEY, prefixes BLOB, builds_channel INTEGER, disabled_commands BLOB, disabled_cogs BLOB)')
            # await conn.execute('INSERT INTO guilds(id , prefixes, builds_channel, disabled_commands, disabled_cogs) SELECT id , prefixes, builds_channel, disabled_commands, disabled_categories FROM guilds_orig')
            # await conn.execute('DROP TABLE guilds_orig')
            # self.bot.guild_options[ctx.guild.id]['disabled_cogs'] = set()
            pass
        await ctx.send('Done.')


def setup(bot):
    bot.add_cog(Owner(bot))
