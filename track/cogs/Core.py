from collections import Counter
from datetime import datetime
import time
import traceback
import sys
import pickle

from discord.ext import commands
import aiosqlite

import config
import utils

DEFAULT_GUILD_SETTINGS = (pickle.dumps(config.default_prefixes), None)


def dict_factory(cursor, row):
    return {col[0]: pickle.loads(row[index]) if type(row[index]) == bytes
            else row[index] for index, col in enumerate(cursor.description)}


class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.db = await aiosqlite.connect('assets/private/bot.db')
        self.bot.gameparams = await aiosqlite.connect('assets/private/gameparams.db')
        self.bot.maplesyrup = await aiosqlite.connect('assets/private/maplesyrup.db')

        self.bot.db.row_factory = dict_factory
        self.bot.gameparams.row_factory = dict_factory
        self.bot.maplesyrup.row_factory = dict_factory

        async with utils.Transaction(self.bot.db) as conn:
            # Get guild options
            c = await conn.execute(f'SELECT * FROM guilds')
            guilds = await c.fetchall()
            self.bot.guild_options = {guild['id']: guild for guild in guilds}

            # Check if bot was invited to new guilds while offline
            for guild in self.bot.guilds:
                if guild.id not in self.bot.guild_options:
                    self.bot.guild_options[guild.id] = DEFAULT_GUILD_SETTINGS
                    await conn.execute('INSERT INTO guilds VALUES (?, ?, ?)', (guild.id,) + DEFAULT_GUILD_SETTINGS)

            # Get latest row of stats
            c = await conn.execute('SELECT stats FROM stats ORDER BY stats DESC LIMIT 1')
            stats = await c.fetchone()
            self.bot.stats = stats['stats'] if stats is not None else Counter()

        print(f'Ready!          [{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}]\n'
              f'Name: {self.bot.user} | ID: {self.bot.user.id}')

    @commands.Cog.listener()
    async def on_disconnect(self):
        print(f'Disconnected... [{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}]')

    @commands.Cog.listener()
    async def on_resumed(self):
        print(f'Reconnected...  [{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}]')

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        self.bot.guild_options[guild.id] = DEFAULT_GUILD_SETTINGS
        async with utils.Transaction(self.bot.db) as conn:
            await conn.execute('INSERT INTO guilds VALUES (?, ?, ?)', (guild.id,) + DEFAULT_GUILD_SETTINGS)

    async def logout(self):
        async with utils.Transaction(self.bot.db) as conn:
            await conn.execute('INSERT INTO stats VALUES (?, ?)',
                               (int(time.time()), pickle.dumps(self.bot.stats)))

        await self.bot.logout()

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        error = getattr(error, 'original', error)

        if isinstance(error, (commands.CommandNotFound, utils.SilentError)):
            return

        elif isinstance(error, utils.CustomError):
            return await ctx.send(error.message)

        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(f'`{ctx.command}` has been disabled.')

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(f'`{ctx.command}` cannot be used in Private Messages.')
            except:
                pass

        elif isinstance(error, commands.NotOwner):
            return await ctx.send('This command is reserved for bot owner.')

        elif isinstance(error, (commands.MissingRequiredArgument, commands.TooManyArguments)):
            return await ctx.send(f'Invalid number of arguments passed. Correct usage:\n`{utils.get_signature(ctx.command)}`')

        elif isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(f'Command on cooldown for `{error.retry_after:.1f} seconds`.')

        elif isinstance(error, (commands.UserInputError, commands.ConversionError)):
            return await ctx.send(error)

        print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    async def bot_check_once(self, ctx):
        options = self.bot.guild_options[ctx.guild.id]
        if (ctx.command.name not in options['disabled_commands'] and
              ctx.command.cog.qualified_name not in options['disabled_cogs']):
            return True
        raise utils.CustomError('This command or its category has been disabled in this server.')

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        self.bot.stats['commands_run'] += 1


def setup(bot):
    bot.add_cog(Core(bot))
