from discord.ext import commands, menus
import discord

import difflib
import random
import re

import utils

BUKI_EMOJI_SERVERS = (552570749953507338, 611977431959732234,
                      641016852864040991, 677591786138632192)
# Shouldn't need 13 secondary car colors, but just in case
ESCAPE_MAPPING = {'EXIT': '<:exit:721338399276924998>',
                  'o': '<:e:721338399176523856>',
                  'x': '<:b:721338399142707291>',
                  'A': '<:primary:691810735126478889>',
                  0: '<:esc0:691810735399108608>',
                  1: '<:esc1:691810735348646018>',
                  2: '<:esc2:691810735264890891>',
                  3: '<:esc3:691810735344451654>',
                  4: '<:esc4:691810735441051699>',
                  5: '<:esc5:691810735344320533>',
                  6: '<:esc6:691810735218491393>',
                  7: '<:esc7:691810735415754842>',
                  8: '<:esc8:691810735138930689>',
                  9: '<:esc9:691810735394914375>',
                  10: '<:esc10:691810735482732617>',
                  11: '<:esc11:691810735201714177>',
                  12: '<:esc12:691810735260565635>',
                  13: '<:esc13:691810735394652170>'}
BUKIPASTAS = ['You’re in a desert walking along in the sand when all of the sudden you look down, '
              'and you see a buki, crawling toward you. You reach down, you flip the buki over on its back. '
              'The buki lays on its back, its belly baking in the hot sun, beating its legs trying to turn '
              'itself over, but it can’t, not without your help. But you’re not helping. Why is that?',
              'I don\'t think it\'s nice, you laughin\'. You see, my buki don\'t like people '
              'laughing. She gets the crazy idea you\'re laughin\' at her. Now if you apologize, '
              'like I know you\'re going to, I might convince her that you really didn\'t mean it.',
              'Did you ever hear the tragedy of Buki The Wise? I thought not. It\'s not a story the Imperial '
              'Japanese Navy would tell you. It\'s an Asian legend. Buki was a Special Type Destroyer, so powerful '
              'and so wise she could use the Combined Fleet to influence the shipyards to create additional Bukis. '
              'She had such a knowledge of Kantai Kessen that she could even keep the ones she cared about from sinking. '
              'The dark side of the Decisive Battle Strategy is a pathway to many abilities some consider to be unnatural. '
              'She became so powerful, that the only thing she was afraid of was losing her power, which eventually, of '
              'course, she did. Unfortunately, she taught her successor everything she knew, then under her successor she '
              'sunk in her sleep. Ironic. She could save others from sinking, but not herself.',
              'Then out spake brave Fubuki,\nThe Captain of the Destroyer:\n\"To every buki upon this earth\n'
              'Death cometh soon or late.\nAnd how can any buki die better\nThan facing fearful odds,\n'
              'For the ashes of her builders,\nAnd the temples of her Emperors.\"']


class EscapeMenu(menus.Menu):
    def __init__(self, embed, moves, initial_setup):
        super().__init__(clear_reactions_after=True)
        self.embed = embed
        self.moves = moves
        self.active = 'A'

        self.board, index, mapping = [[], [], [], [], [], []], 0, {}
        for count, cell in enumerate(initial_setup):
            if cell in ['o', 'x', 'A']:
                self.board[count // 6].append(cell)
            else:
                if cell not in mapping:
                    mapping[cell] = index
                    index += 1
                self.board[count // 6].append(mapping[cell])

        self.add_button(menus.Button(ESCAPE_MAPPING['A'], self.piece))
        for cell in list(mapping.values()):
            self.add_button(menus.Button(ESCAPE_MAPPING[cell], self.piece))

    def get_board(self):
        board = 8 * ESCAPE_MAPPING['x'] + '\n'
        for y, row in enumerate(self.board):
            board += ESCAPE_MAPPING['x']
            for x, cell in enumerate(row):
                board += ESCAPE_MAPPING[cell]
            board += ESCAPE_MAPPING['EXIT'] + '\n' if y == 2 else ESCAPE_MAPPING['x'] + '\n'
        return board + 8 * ESCAPE_MAPPING['x']

    async def update_embed(self):
        embed = self.embed.copy()
        embed.description += '\n\n' + self.get_board()
        embed.add_field(name='Active Piece', value=ESCAPE_MAPPING[self.active])

        # self.embed.set_field_at(0, name='Active Piece', value=ESCAPE_MAPPING[self.active])
        # self.embed.set_field_at(1, name='Board', value=self.get_board())

        return await self.message.edit(embed=embed)

    async def send_initial_message(self, ctx, channel):
        embed = self.embed.copy()
        embed.description += '\n\n' + self.get_board()
        embed.add_field(name='Active Piece', value=ESCAPE_MAPPING[self.active])
        # self.embed.add_field(name='Board', value=self.get_board())

        return await ctx.send(embed=embed)

    @menus.button('⏹️', position=menus.Last())
    async def end(self, payload):
        self.stop()

    @menus.button('🔼')
    async def up(self, payload):
        positions = []
        direction_flag = False
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell == self.active:
                    if y == 0 or self.board[y - 1][x] != cell and self.board[y - 1][x] != 'o':
                        return
                    elif self.board[y - 1][x] == cell:
                        direction_flag = True

                    positions.append((y, x))
        if not direction_flag:
            return
        for y, x in positions:
            self.board[y][x] = 'o'
        for y, x in positions:
            self.board[y - 1][x] = self.active

        await self.update_embed()

    @menus.button('🔽')
    async def down(self, payload):
        positions = []
        direction_flag = False
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell == self.active:
                    if y == 5 or self.board[y + 1][x] != cell and self.board[y + 1][x] != 'o':
                        return
                    elif self.board[y + 1][x] == cell:
                        direction_flag = True

                    positions.append((y, x))
        if not direction_flag:
            return
        for y, x in positions:
            self.board[y][x] = 'o'
        for y, x in positions:
            self.board[y + 1][x] = self.active

        await self.update_embed()

    @menus.button('◀️')
    async def left(self, payload):
        positions = []
        direction_flag = False
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell == self.active:
                    if x == 0 or self.board[y][x - 1] != cell and self.board[y][x - 1] != 'o':
                        return
                    elif self.board[y][x - 1] == cell:
                        direction_flag = True

                    positions.append((y, x))
        if not direction_flag:
            return
        for y, x in positions:
            self.board[y][x] = 'o'
        for y, x in positions:
            self.board[y][x - 1] = self.active

        await self.update_embed()

    @menus.button('▶️')
    async def right(self, payload):
        positions = []
        direction_flag = False
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell == self.active:
                    if self.active == 'A' and x == 5 and y == 2:
                        await self.ctx.send('Well done!')
                        return self.stop()
                    elif x == 5 or self.board[y][x + 1] != cell and self.board[y][x + 1] != 'o':
                        return
                    elif self.board[y][x - 1] == cell:
                        direction_flag = True

                    positions.append((y, x))
        if not direction_flag:
            return
        for y, x in positions:
            self.board[y][x] = 'o'
        for y, x in positions:
            self.board[y][x + 1] = self.active

        await self.update_embed()

    async def piece(self, payload):
        for index, emoji in ESCAPE_MAPPING.items():
            if index not in ['o', 'x'] and str(payload.emoji) == emoji:
                self.active = index

        await self.update_embed()


class Misc(commands.Cog):
    """
    Random commands that don't quite fit anywhere else.
    """

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '🏷️'
        self.display_name = 'Misc'

    @commands.command(brief='A sliding-block game.')
    @commands.cooldown(rate=1, per=90, type=commands.BucketType.user)
    async def escape(self, ctx, min_moves=16, max_moves=60):
        """
        An implementation of [Michael Fogleman](https://www.michaelfogleman.com/rush/)'s solved Rush Hour puzzles.

        - Get the primary piece (represented in red) to the exit.
        - You may only slide pieces along their length.
        """
        embed = discord.Embed(title='Escape!',
                              description='You find yourself in a strange place...\n\n'
                                          'Escape by getting the primary piece (red) to the exit.\n'
                                          'You may only slide pieces along their length.',
                              color=self.bot.color)

        async with utils.Transaction(self.bot.rush) as conn:
            c = await conn.execute('SELECT * FROM puzzles WHERE moves >= ? AND moves <= ? ORDER BY RANDOM() LIMIT 1', (min_moves, max_moves))
            row = await c.fetchone()

            if row is None:
                return await ctx.send('No level found with specified bounds.')

            await EscapeMenu(embed, row['moves'], row['setup']).start(ctx)

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
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.user)
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

    @buki.command(brief='Not mom\'s lasagna.')
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.user)
    async def pasta(self, ctx, num: int):
        """
        Curated pastas from our chefs at the Buki Emote Servers.
        """
        if not 1 <= num <= len(BUKIPASTAS):
            return await ctx.send(f'`num` must be an integer between 1 and {len(BUKIPASTAS)}.')
        await ctx.send(BUKIPASTAS[num - 1])

    @commands.command(brief='Tomorrow is coming')
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.user)
    async def aah(self, ctx):
        """
        Tomorrow is coming
        """
        await ctx.send('https://cdn.discordapp.com/attachments/651330014532468736/677358572186632192/Aaaaaaaaaaaaahhhh.mp4')

    @commands.command(brief='Now in HD!')
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.user)
    async def hdaah(self, ctx):
        """
        Now in HD!
        Thanks Shiro.
        """
        await ctx.send('https://cdn.discordapp.com/attachments/651330014532468736/717655219780976650/Aaaaaaaaaaaaahhhh_hd.mp4')

    @commands.command(hidden=True, brief='<:omegalul:651328721327882240>')
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.user)
    async def wow(self, ctx, *, message):
        """
        W <:omegalul:653131858791628840> W
        """
        message = discord.utils.escape_mentions(message)
        await ctx.send(' '.join(list(message.upper())).replace('O', '<:omegalul:653131858791628840>'))


def setup(bot):
    bot.add_cog(Misc(bot))
