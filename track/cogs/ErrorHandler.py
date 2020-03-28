from discord.ext import commands
import discord
import traceback
import sys

import utils


class CommandErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(f'{ctx.command} has been disabled.')

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
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


def setup(bot):
    bot.add_cog(CommandErrorHandler(bot))
