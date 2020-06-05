from discord.ext import commands, menus
import discord
from datetime import datetime
import timeago
import sys
import psutil

import config
import utils

VISIBLE_COGS = ['General', 'Wows', 'Misc', 'Options']


class Help(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={'brief': 'Take a wild guess...',
                                        'help': 'Seriously?'})

    class HelpMenu(menus.Menu):
        def __init__(self, cogs, main_embed, instance):
            super().__init__(clear_reactions_after=True)
            self.cogs = cogs
            self.main_embed = main_embed
            self.instance = instance
            for cog in cogs:
                self.add_button(menus.Button(cog.emoji, self.cog_embed))

        async def send_initial_message(self, ctx, channel):
            return await ctx.send(embed=self.main_embed)

        @menus.button('↩️')
        async def main(self, payload):
            await self.message.edit(embed=self.main_embed)

        @menus.button('⏹️', position=menus.Last())
        async def end(self, payload):
            self.stop()

        async def cog_embed(self, payload):
            for cog in self.cogs:
                if payload.emoji.name == cog.emoji:
                    await self.message.edit(embed=await self.instance.cog_embed(cog))

    async def send_bot_help(self, mapping):
        cogs = [self.context.bot.get_cog(cog) for cog in VISIBLE_COGS]
        perms = discord.Permissions.text()
        perms.update(read_messages=True, manage_messages=True,
                     mention_everyone=False, send_tts_messages=False)

        embed = discord.Embed(title='Help',
                              description='A bot with WoWS related utilities and more.\n'
                                          'Contact Trackpad#1234 for issues.\n'
                                          'This bot is currently WIP.',
                              color=self.context.bot.color)
        embed.add_field(name='Command Categories',
                        value='\n'.join([f'{cog.emoji} {cog.display_name}' for cog in cogs]))
        embed.add_field(name='Links',
                        value=f'[Invite me here!]({discord.utils.oauth_url(self.context.bot.user.id, perms)})\n'
                              f'[Support server](https://discord.gg/dU39sjq)\n'
                              f'[Need WoWS help?](https://discord.gg/c4vK9rM)\n')
        embed.set_thumbnail(url='https://cdn.discordapp.com/attachments/651324664496521225/651326808423137300/thumbnail.png')
        embed.set_footer(text='Use the below reactions or help <category> / help <command> to view details')

        await self.HelpMenu(cogs, embed, self).start(self.context)

    async def send_cog_help(self, cog):
        await self.context.send(embed=await self.cog_embed(cog))

    async def cog_embed(self, cog):
        if cog.qualified_name not in VISIBLE_COGS:
            return

        def descriptor(command):
            string = f'`{command.name}` - {command.short_doc}'
            if isinstance(command, commands.Group):
                string += f'\n┗ {", ".join(f"`{sub.name}`" for sub in command.commands)}'
            return string

        embed = discord.Embed(title=f'Help - {cog.qualified_name}',
                              description=cog.description,
                              color=self.context.bot.color)
        embed.add_field(name='Available Commands',
                        value='\n'.join([descriptor(command) for command in cog.get_commands() if not command.hidden]))
        embed.set_footer(text='Use help <command> to view the usage of that command.')

        return embed

    async def send_group_help(self, group):
        embed = discord.Embed(title=f'Help - {group.name}',
                              description=group.help,
                              color=self.context.bot.color)
        if group.aliases:
            embed.add_field(name='Aliases',
                            value=', '.join(f'`{alias}`' for alias in group.aliases),
                            inline=False)
        for command in group.commands:
            embed.add_field(name=command.name,
                            value=f'{command.help} ```{utils.get_signature(command)}```',
                            inline=False)
        embed.set_footer(text='<REQUIRED argument> | [OPTIONAL argument] | (Do not type these symbols!)')

        await self.context.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=f'Help - {command.name}',
                              description=command.help,
                              color=self.context.bot.color)
        if command.aliases:
            embed.add_field(name='Aliases',
                            value=', '.join(f'`{alias}`' for alias in command.aliases),
                            inline=False)
        embed.add_field(name='Usage',
                        value=f'```{utils.get_signature(command)}```')
        embed.set_footer(text='<REQUIRED argument> | [OPTIONAL argument] | (Do not type these symbols!)')
        await self.context.send(embed=embed)

    # Override to make cogs not case-sensitive
    async def command_callback(self, ctx, *, command=None):
        await self.prepare_help_command(ctx, command)
        bot = ctx.bot

        if command is None:
            mapping = self.get_bot_mapping()
            return await self.send_bot_help(mapping)

        cog = bot.get_cog(command.title())
        if cog is not None:
            return await self.send_cog_help(cog)

        maybe_coro = discord.utils.maybe_coroutine

        keys = command.split(' ')
        cmd = bot.all_commands.get(keys[0])
        if cmd is None:
            string = await maybe_coro(self.command_not_found, self.remove_mentions(keys[0]))
            return await self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)
            except AttributeError:
                string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                return await self.send_error_message(string)
            else:
                if found is None:
                    string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                    return await self.send_error_message(string)
                cmd = found

        if isinstance(cmd, commands.Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)


class General(commands.Cog):
    """
    General commands for the bot.
    """

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '📔'
        self.display_name = 'General'

        self._original_help_command = bot.help_command
        bot.help_command = Help()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.command(aliases=['join'], brief='Gets bot\'s invite link.')
    async def invite(self, ctx):
        """
        Gets an invite link for the bot.
        """
        perms = discord.Permissions.text()
        perms.update(read_messages=True, manage_messages=True,
                     mention_everyone=False, send_tts_messages=False)
        await ctx.send(f'Invite me here:\n<{discord.utils.oauth_url(self.bot.user.id, perms)}>')

    @commands.command(aliases=['server'], brief='Gets support server\'s invite link.')
    async def support(self, ctx):
        """
        Gets an invite link to the support server.
        """
        await ctx.send('Support server:\nhttps://discord.gg/dU39sjq')

    @commands.command(aliases=['latency'], brief='Pong?')
    async def ping(self, ctx):
        """
        Pong?
        """
        start = datetime.now()
        await ctx.trigger_typing()
        end = datetime.now()
        await ctx.send(f'Ping: `{(end - start).total_seconds() * 1000:.2f}ms`.')

    @commands.command(brief='Displays bot\'s uptime.')
    async def uptime(self, ctx):
        """
        Shows you the last time the bot was launched.
        """
        await ctx.send(f'Online since {self.bot.uptime.strftime("%m/%d/%Y %H:%M UTC")} '
                       f'(~{timeago.format(self.bot.uptime, datetime.utcnow())})')

    @commands.command(aliases=['suggest'], brief='Send feedback (suggestions & feature requests).')
    @commands.cooldown(rate=1, per=60, type=commands.cooldowns.BucketType.user)
    async def feedback(self, ctx, *, message):
        """
        Send in feedback here! Attachments accepted, but remember to attach them all.
        """
        channel = self.bot.get_channel(config.feedback_channel)  # feedback chanel in support server

        embed = discord.Embed(title='New Feedback!',
                              description=message,
                              color=self.bot.color)
        embed.add_field(name='Author',
                        value=ctx.author.mention)
        embed.add_field(name='Server',
                        value=ctx.guild.name)
        if ctx.message.attachments:
            embed.add_field(name='Attachments',
                            value='\n'.join(f'[{file.filename}]({file.url})' for file in ctx.message.attachments),
                            inline=False)
        embed.set_footer(text='Vote on this submissions using the reactions so I can determine what to focus on!')

        message = await channel.send(embed=embed)
        await message.add_reaction('<:upvote:651325140663140362>')
        await message.add_reaction('<:downvote:651325233105600544>')
        await ctx.send('Thank you for your submission! '
                       'If you haven\'t already, consider joining the support server with `support`.')

    @commands.command(aliases=['about', 'details'], brief='Displays extra information about the bot.')
    async def info(self, ctx):
        """
        Displays specifics of the bot.
        """
        python = sys.version_info
        process = psutil.Process()

        embed = discord.Embed(title='Info',
                              color=self.bot.color)
        embed.add_field(name='Latest Changelog',
                        value='Restructured the project.',
                        inline=False)
        embed.add_field(name='Creators',
                        value='\n'.join(self.bot.get_user(owner).mention for owner in self.bot.owner_ids))
        embed.add_field(name='Created on',
                        value=f'{self.bot.created_on.strftime("%m/%d/%Y")}\n'
                              f'(~{timeago.format(self.bot.created_on, datetime.utcnow())})')
        embed.add_field(name='Made With',
                        value=f'[Python {python.major}.{python.minor}.{python.micro}](https://www.python.org/)\n'
                              f'[discord.py {discord.__version__}](https://discordpy.readthedocs.io/en/latest/)')
        embed.add_field(name='Status',
                        value=f'Latency: {self.bot.latency * 1000:.2f}ms\n'
                              f'CPU: {process.cpu_percent()}%\n'
                              f'RAM: {process.memory_info().rss / 1048576:.2f}MB')  # bits to bytes
        embed.add_field(name='Uptime',
                        value='Online since:\n'
                              f'{self.bot.uptime.strftime("%m/%d/%Y %H:%M UTC")}\n'
                              f'(~{timeago.format(self.bot.uptime, datetime.utcnow())})')
        embed.add_field(name='Statistics',
                        value=f'Commands Run: {self.bot.stats["commands_run"]}\n'
                              f'Guilds: {len(list(self.bot.guilds))}\n'
                              f'Users: {len(list(self.bot.get_all_members()))} '
                              f'(Unique: {len(set(self.bot.get_all_members()))})')
        # embed.add_field(name='Acknowledgements',
        #                 value='',
        #                 inline=False)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(General(bot))
