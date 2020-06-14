from discord.ext import commands
import discord

import asyncio
import pickle
import time

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
    async def send(self, ctx, channel: int, *, message):
        """
        Sends a message to a channel.
        """
        channel = await self.bot.get_channel(channel)
        if channel is None:
            return await ctx.send('Channel not found.')

        await self.bot.get_channel(channel).send(message)
        await ctx.message.add_reaction('✅')

    @commands.command(brief='Deletes a message from the bot.')
    async def delete(self, ctx, channel: int, message_id: int):
        """
        Deletes a message from the bot.
        """
        channel = self.bot.get_channel(channel)
        if channel is None:
            return await ctx.send('Channel not found.')

        try:
            message = await channel.fetch_message(message_id)
            if message.author != self.bot.user:
                return await ctx.send('Message author is not bot.')
            await message.delete()
            await ctx.message.add_reaction('✅')
        except discord.Forbidden:
            await ctx.send('Missing permissions.')
        except discord.NotFound:
            await ctx.send('Message already deleted.')

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

    @commands.command(brief='Guilds list.')
    async def guilds(self, ctx):
        """
        Lazy way for me to check what guilds the bot is in.
        I'll deal with the 2000 character limit later.
        """
        await ctx.send('\n'.join([f'{guild.name} ({guild.member_count})' for guild in self.bot.guilds]))

    @commands.command(hidden=True, brief='Debug tool.')
    async def sms(self, ctx, user_id, streak: int, last: int, skips: int):
        """
        Debug tool.
        """
        data = await utils.fetch_user(self.bot.db, user_id)
        data['morning_streak'] = streak
        data['morning_last'] = last
        data['morning_skips'] = skips

        async with utils.Transaction(self.bot.db) as conn:
            await conn.execute('UPDATE users SET data = ? WHERE id = ?', (pickle.dumps(data), ctx.author.id))

        await ctx.send('Done.')

    @commands.command(hidden=True, brief='Debug tool.')
    async def day(self, ctx):
        await ctx.send(int(time.time()) // 86400)

    @commands.command(brief='Debug command.')
    async def debug(self, ctx, *, string=''):
        """
        Debug command.
        """
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

            # await conn.execute('ALTER TABLE users RENAME TO users_orig')
            # await conn.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, data BLOB)')
            # c = await conn.execute('SELECT * FROM users_orig')
            # table = await c.fetchall()
            # for user in table:
            #     await conn.execute('INSERT INTO users VALUES (?, ?)', (user['id'], pickle.dumps({'contours_played': user['contours_played'], 'contours_record': user['contours_record']})))
            # c = await conn.execute('SELECT * FROM users')
            # table = await c.fetchall()
            # print(table)
            # await conn.execute('DROP TABLE users_orig')

            print(self.bot.guild_options[ctx.guild.id])

            pass
        await ctx.send('Done.')


def setup(bot):
    bot.add_cog(Owner(bot))
