from discord.ext import commands, menus
import discord

import difflib
import random
import re

BUKI_EMOJI_SERVERS = (552570749953507338, 611977431959732234,
                      641016852864040991, 677591786138632192)


class Miscellaneous(commands.Cog):
    """
    Random commands that don't quite fit anywhere else.
    """

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '🏷️'

    @commands.group(invoke_without_command=True, brief='(Fu)buki emojis!')
    async def buki(self, ctx, query=None):
        """
        Emojis of (Fu)buki from Kantai Collection.

        Not using a subcommand returns a random emoji or a queried emoji.
        """
        emojis = [emoji for server in BUKI_EMOJI_SERVERS for emoji in self.bot.get_guild(server).emojis]

        if query is None:
            return await ctx.send(random.choice(emojis))

        for emoji in emojis:
            if (emoji.name.lower() == query.lower() or
                    emoji.name.lower() == 'buki' + query.lower()):
                return await ctx.send(emoji)

        error = f'`{query}`? Could not find that Buki <:bukitears:568142198323806249>'
        similar = difflib.get_close_matches(query, [emoji.name.lower() for emoji in emojis], n=3, cutoff=0.75)
        if similar:
            error += '\nDid you mean...\n- ' + '\n- '.join(similar)
        await ctx.send(error)

    @buki.command(brief='List all emojis.')
    async def list(self, ctx):
        """
        Lists all available emojis.
        """
        emojis = [emoji for server in BUKI_EMOJI_SERVERS for emoji in self.bot.get_guild(server).emojis]

        class SplitEmojis(menus.ListPageSource):
            def __init__(self, data):
                super().__init__(data, per_page=25)

            async def format_page(self, menu, entries):
                offset = menu.current_page * self.per_page
                return ''.join(str(emoji) + '\n' if count % 5 == 4 else str(emoji)
                               for count, emoji in enumerate(entries, start=offset))

        pages = menus.MenuPages(source=SplitEmojis(emojis), clear_reactions_after=True)
        await pages.start(ctx)

    @buki.command(brief='Converts %wrapped bukis%.')
    async def convert(self, ctx, *, string):
        """
        Converts %-wrapped bukis in the input string to their emoji equivalents.

        Mentions are escaped.
        """
        string = discord.utils.escape_mentions(string)
        emojis = [emoji for server in BUKI_EMOJI_SERVERS for emoji in self.bot.get_guild(server).emojis]

        def replace(match):
            for emoji in emojis:
                if (emoji.name.lower() == match.group(0)[1:-1].lower() or
                        emoji.name.lower() == 'buki' + match.group(0)[1:-1].lower()):
                    return str(emoji)
            return match.group(0)

        pattern = re.compile('%[^%]+%')
        await ctx.send(re.sub(pattern, replace, string))


def setup(bot):
    bot.add_cog(Miscellaneous(bot))
