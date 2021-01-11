from collections import Counter
from datetime import datetime
import traceback
import sys
import pickle
import sqlite3

from discord.ext import commands, menus
import discord
import aiosqlite

import config
import utils

DEFAULT_GUILD_SETTINGS = {'prefixes': config.default_prefixes, 'builds_channel': None,
                          'disabled_commands': set(), 'disabled_cogs': set()}
DEFAULT_GUILD_ROW = (pickle.dumps(config.default_prefixes), None, pickle.dumps(set()), pickle.dumps(set()))
ERROR_CHANNEL_ID = 721202051090219068


def dict_factory(cursor, row):
    if len(cursor.description) == 1:
        return pickle.loads(row[0]) if type(row[0]) == bytes else row[0]
    else:
        return {col[0]: pickle.loads(row[index]) if type(row[index]) == bytes
                else row[index] for index, col in enumerate(cursor.description)}


class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.err_channel = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.bot.started:
            self.bot.db = await aiosqlite.connect('assets/private/bot.db')
            self.bot.gameparams = await aiosqlite.connect('assets/private/gameparams.db')
            self.bot.maplesyrup = await aiosqlite.connect('assets/private/maplesyrup.db')
            self.bot.rush = await aiosqlite.connect('assets/private/rush.db')

            self.bot.db.row_factory = dict_factory
            self.bot.gameparams.row_factory = dict_factory
            self.bot.maplesyrup.row_factory = dict_factory
            self.bot.rush.row_factory = aiosqlite.Row

            async with utils.Transaction(self.bot.db) as conn:
                # Get guild options
                c = await conn.execute(f'SELECT * FROM guilds')
                guilds = await c.fetchall()
                self.bot.guild_options = {guild['id']: guild for guild in guilds}

                # Check if bot was invited to new guilds while offline
                for guild in self.bot.guilds:
                    if guild.id not in self.bot.guild_options:
                        self.bot.guild_options[guild.id] = DEFAULT_GUILD_SETTINGS.copy()
                        await conn.execute('INSERT INTO guilds VALUES (?, ?, ?, ?, ?)', (guild.id,) + DEFAULT_GUILD_ROW)

                # Get latest row of stats
                c = await conn.execute('SELECT stats FROM stats ORDER BY stats DESC LIMIT 1')
                stats = await c.fetchone()
                self.bot.stats = stats if stats is not None else Counter()

            self.bot.started = True

        self.err_channel = self.bot.get_channel(ERROR_CHANNEL_ID)
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
        try:
            self.bot.guild_options[guild.id] = DEFAULT_GUILD_SETTINGS.copy()
            async with utils.Transaction(self.bot.db) as conn:
                await conn.execute('INSERT INTO guilds VALUES (?, ?, ?, ?, ?)', (guild.id,) + DEFAULT_GUILD_ROW)
        except sqlite3.IntegrityError:
            pass  # rejoining a guild

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

        elif isinstance(error, (discord.Forbidden, menus.MenuError)):
            try:
                return await ctx.send(f'Bot is missing permissions to execute this command :(\n'
                                      f'Error: `{error}`')
            except discord.Forbidden:
                pass

        try:
            embed = discord.Embed(title=f'{type(error).__module__}: {type(error).__qualname__}',
                                  description=str(error),
                                  color=self.bot.color)
            embed.add_field(name='Context',
                            value=f'Guild: {ctx.guild.name} (`{ctx.guild.id}`)\n'
                                  f'Channel: {ctx.channel.name} (`{ctx.channel.id}`)\n'
                                  f'User: {ctx.author.name} (`{ctx.author.id}`)',
                            inline=False)
            embed.add_field(name='Invocation Text',
                            value=f'```{ctx.message.content}```')
            await self.err_channel.send(embed=embed)
        except:
            print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    async def bot_check_once(self, ctx):
        if ctx.guild is None:
            return True

        options = self.bot.guild_options[ctx.guild.id]
        if (ctx.command.parent is not None and ctx.command.parent.name in options['disabled_commands'] or
                ctx.command.qualified_name in options['disabled_commands'] or
                ctx.command.cog.qualified_name in options['disabled_cogs']):
            if (not await self.bot.is_owner(ctx.author) and
                    not ctx.channel.permissions_for(ctx.message.author).administrator):
                raise utils.CustomError('This command or its category has been disabled in this server.')
            else:
                await utils.confirm(ctx, 'This command or its category has been disabled in this server. Override?')
        return True

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        self.bot.stats['commands_run'] += 1


def setup(bot):
    bot.add_cog(Core(bot))
