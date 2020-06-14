from discord.ext import commands
import discord

import pickle

import config
import utils


class Options(commands.Cog):
    """
    Commands for customizing the bot. Administrator permissions required.
    """

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '⚙️'
        self.display_name = 'Options'

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        elif (not await self.bot.is_owner(ctx.author) and
              not ctx.channel.permissions_for(ctx.message.author).administrator):
            raise utils.CustomError('You must be an administrator to use this command.')
        return True

    @commands.group(aliases=['prefix'], invoke_without_command=True, brief='Server prefixes.')
    async def prefixes(self, ctx):
        """
        Customize up to 10 prefixes the bot will accept for this server.
        You may delete the default prefix, but mentions are always a prefix.

        Not using a subcommand shows you this servers' prefixes.
        """
        description = '\n'.join([f'{count}. `{prefix}`' for count, prefix in
                                 enumerate(self.bot.guild_options[ctx.guild.id]['prefixes'], start=1)])
        embed = discord.Embed(title=f'{ctx.guild.name}\'s server prefixes',
                              description=description,
                              color=self.bot.color)
        await ctx.send(embed=embed)

    @prefixes.command(aliases=['create'], brief='Add a prefix.')
    async def add(self, ctx, prefix):
        """
        Add a prefix.
        Prefixes with spaces should use " to wrap the whole prefix, "like this".
        """
        prefixes = self.bot.guild_options[ctx.guild.id]['prefixes']

        async with utils.Transaction(self.bot.db) as conn:
            if len(prefixes) >= 10:
                return await ctx.send('Maximum number of prefixes (10) reached. Please remove some before adding another.')
            elif prefix in prefixes:
                return await ctx.send('Prefix already exists.')

            prefixes.add(prefix)
            await conn.execute('UPDATE guilds SET prefixes = ? WHERE id = ?', (pickle.dumps(prefixes), ctx.guild.id))
            await ctx.send('Prefix added.')

    @prefixes.command(aliases=['remove'], brief='Delete a prefix.')
    async def delete(self, ctx, prefix):
        """
        Delete a prefix.
        """
        prefixes = self.bot.guild_options[ctx.guild.id]['prefixes']

        async with utils.Transaction(self.bot.db) as conn:
            try:
                prefixes.remove(prefix)
                await conn.execute('UPDATE guilds SET prefixes = ? WHERE id = ?', (pickle.dumps(prefixes), ctx.guild.id))
                await ctx.send('Prefix removed.')
            except KeyError:
                await ctx.send('Prefix not found.')

    @prefixes.command(brief='Reset prefixes to default.')
    async def reset(self, ctx):
        """
        Reset prefixes to default.
        """
        async with utils.Transaction(self.bot.db) as conn:
            self.bot.guild_options[ctx.guild.id]['prefixes'] = config.default_prefixes.copy()
            await conn.execute('UPDATE guilds SET prefixes = ? WHERE id = ?', (pickle.dumps(config.default_prefixes.copy()), ctx.guild.id))
            await ctx.send('Prefixes reset.')

    @commands.group(invoke_without_command=True, brief='Approve-only mode for builds.')
    async def approve_only(self, ctx):
        """
        Enable or disable approve-only mode for this server.

        By default, this option is disabled, but recommended for large servers.
        Anybody with the ability to write to the specified channel will be able to approve builds.
        Builds created in the specified channel are also automatically approved.

        Not using a subcommand lists approve-only mode's status.
        """
        channel_id = self.bot.guild_options[ctx.guild.id]['builds_channel']
        if channel_id is None:
            return await ctx.send(f'Approve-only mode is currently disabled.')

        channel = self.bot.get_channel(channel_id)
        await ctx.send(f'Approve-only mode is currently enabled to {channel.mention}.')

    @approve_only.command(brief='Enables approve-only mode.')
    async def enable(self, ctx, channel: discord.TextChannel):
        """
        Enables approve-only mode for build submission on this server.
        """
        async with utils.Transaction(self.bot.db) as conn:
            self.bot.guild_options[ctx.guild.id]['builds_channel'] = channel.id
            await conn.execute('UPDATE guilds SET builds_channel = ? WHERE id = ?', (channel.id, ctx.guild.id))
            await ctx.send(f'Approve-only mode enabled with {channel.mention}.')

    @approve_only.command(brief='Disables approve-only mode.')
    async def disable(self, ctx):
        """
        Disables approve-only mode for build submission on this server.

        **All builds that were in queue will be approved!**
        """
        await utils.confirm(ctx, 'This action will approve all builds currently in the queue. Are you sure?')
        async with utils.Transaction(self.bot.db) as conn:
            self.bot.guild_options['builds_channel'] = None
            await conn.execute('UPDATE guilds SET builds_channel = ? WHERE id = ?', (None, ctx.guild.id))
            await conn.execute('UPDATE builds SET in_queue = 0 WHERE guild_id = ?', (ctx.guild.id,))
            await ctx.send('Approve-only mode disabled.')

    @commands.group(name='command', aliases=['cmd'], invoke_without_command=True, brief='Enable and disable commands.')
    async def cmd(self, ctx):
        """
        Enable and disable commands.

        Not using a subcommand shows you what commands are disabled.
        """
        disabled_commands = self.bot.guild_options[ctx.guild.id]['disabled_commands']
        if not disabled_commands:
            return await ctx.send('All commands are enabled.')

        embed = discord.Embed(title=f'{ctx.guild.name}\'s commands',
                              color=self.bot.color)
        embed.add_field(name='Disabled:',
                        value='∙'.join([f'`{command}`' for command in disabled_commands]))
        await ctx.send(embed=embed)

    @cmd.command(name='enable', brief='Enable a command.')
    async def enable_cmd(self, ctx, command):
        """
        Enable a command.
        """
        command = self.bot.get_command(command)
        disabled_commands = self.bot.guild_options[ctx.guild.id]['disabled_commands']

        async with utils.Transaction(self.bot.db) as conn:
            if command is None:
                return await ctx.send('Command not found.')

            try:
                disabled_commands.remove(command.qualified_name)
                await conn.execute('UPDATE guilds SET disabled_commands = ? WHERE id = ?',
                                   (pickle.dumps(disabled_commands), ctx.guild.id))
                await ctx.send(f'`{command.qualified_name}` enabled.')
            except KeyError:
                await ctx.send(f'`{command.qualified_name}` is already enabled.')

    @cmd.command(name='disable', brief='Disables a command.')
    async def disable_cmd(self, ctx, command):
        """
        Disable a command.
        """
        command = self.bot.get_command(command)
        disabled_commands = self.bot.guild_options[ctx.guild.id]['disabled_commands']

        async with utils.Transaction(self.bot.db) as conn:
            if command is None:
                return await ctx.send('Command not found.')
            elif (command.parent is not None and command.parent.name in ['command'] or
                  command.name in ['command']):
                return await ctx.send('You cannot disable this command.')
            elif command.parent is not None and command.parent.name in disabled_commands:
                return await ctx.send(f'`{command.name}`\'s parent, `{command.parent.name}`, is already disabled.')
            elif command.qualified_name in disabled_commands:
                return await ctx.send(f'`{command.qualified_name}` is already disabled.')

            disabled_commands.add(command.qualified_name)
            await conn.execute('UPDATE guilds SET disabled_commands = ? WHERE id = ?',
                               (pickle.dumps(disabled_commands), ctx.guild.id))
            await ctx.send(f'`{command.qualified_name}` disabled.')

    @commands.group(name='category', aliases=['cat'], invoke_without_command=True, brief='Enable and disable categories.')
    async def cat(self, ctx):
        """
        Enable and disable categories.
        """
        disabled_cogs = self.bot.guild_options[ctx.guild.id]['disabled_cogs']
        if not disabled_cogs:
            return await ctx.send('All categories are enabled.')

        embed = discord.Embed(title=f'{ctx.guild.name}\'s categories',
                              color=self.bot.color)
        embed.add_field(name='Disabled:',
                        value='\n'.join([f'`{cog}`' for cog in disabled_cogs]))
        await ctx.send(embed=embed)

    @cat.command(name='enable', brief='Enable a category.')
    async def enable_cat(self, ctx, category):
        """
        Enable a category.
        """
        cog = self.bot.get_cog(category.title())
        disabled_cogs = self.bot.guild_options[ctx.guild.id]['disabled_cogs']

        async with utils.Transaction(self.bot.db) as conn:
            if cog is None:
                return await ctx.send('Category not found.')

            try:
                disabled_cogs.remove(cog.qualified_name)
                await conn.execute('UPDATE guilds SET disabled_cogs = ? WHERE id = ?',
                                   (pickle.dumps(disabled_cogs), ctx.guild.id))
                await ctx.send(f'`{cog.qualified_name}` enabled.')
            except KeyError:
                await ctx.send(f'`{cog.qualified_name}` is already enabled.')

    @cat.command(name='disable', brief='Disable a category.')
    async def disable_cat(self, ctx, category):
        """
        Disable a category.
        """
        cog = self.bot.get_cog(category.title())
        disabled_cogs = self.bot.guild_options[ctx.guild.id]['disabled_cogs']

        async with utils.Transaction(self.bot.db) as conn:
            if cog is None:
                return await ctx.send('Category not found.')
            elif cog.qualified_name in ['Options']:
                return await ctx.send('You cannot disable this category.')
            elif cog.qualified_name in disabled_cogs:
                return await ctx.send(f'`{cog.qualified_name}` is already disabled.')

            disabled_cogs.add(cog.qualified_name)
            await conn.execute('UPDATE guilds SET disabled_cogs = ? WHERE id = ?',
                               (pickle.dumps(disabled_cogs), ctx.guild.id))
            await ctx.send(f'`{cog.qualified_name}` disabled.')


def setup(bot):
    bot.add_cog(Options(bot))
