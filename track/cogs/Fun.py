from discord.ext import commands, menus
import discord

import copy

ESCAPE_LEVELS = {1: [[8, 4, 4, 0, 0, 0],
                     [8, 0, 0, 6, 0, 0],
                     [8, 1, 1, 6, 0, 0],
                     [0, 0, 0, 6, 0, 3],
                     [2, 7, 7, 0, 0, 3],
                     [2, 0, 5, 5, 5, 3]],
                 10: [[0, 2, 4, 4, 5, 5],
                      [0, 2, 0, 0, 0, 6],
                      [0, 2, 0, 1, 1, 6],
                      [0, 3, 0, 7, 8, 8],
                      [0, 3, 0, 7, 9, 10],
                      [0, 11, 11, 11, 9, 10]],
                 20: [[2, 0, 0, 4, 4, 4],
                      [2, 3, 3, 7, 0, 0],
                      [1, 1, 5, 7, 0, 10],
                      [0, 0, 5, 0, 0, 10],
                      [0, 0, 6, 8, 8, 10],
                      [0, 0, 6, 9, 9, 9]],
                 31: [[2, 2, 0, 3, 3, 3],
                      [0, 0, 0, 5, 6, 6],
                      [4, 1, 1, 5, 0, 11],
                      [4, 0, 8, 9, 9, 11],
                      [7, 7, 8, 0, 0, 11],
                      [0, 0, 8, 10, 10, 10]],
                 40: [[2, 3, 3, 0, 6, 0],
                      [2, 4, 5, 0, 6, 7],
                      [2, 4, 5, 1, 1, 7],
                      [8, 8, 8, 9, 0, 7],
                      [0, 0, 10, 9, 11, 11],
                      [12, 12, 10, 13, 13, 0]],
                 60: [[2, 2, 4, 0, 5, 5],
                      [3, 3, 4, 0, 9, 0],
                      [6, 0, 1, 1, 9, 0],
                      [6, 8, 8, 8, 9, 12],
                      [6, 0, 0, 10, 0, 12],
                      [7, 7, 0, 10, 11, 11]]}
ESCAPE_MAPPING = {-1: '⬛',
                  0: '▫️',
                  1: '<:esc1:691810735126478889>',
                  2: '<:esc2:691810735399108608>',
                  3: '<:esc3:691810735348646018>',
                  4: '<:esc4:691810735264890891>',
                  5: '<:esc5:691810735344451654>',
                  6: '<:esc6:691810735441051699>',
                  7: '<:esc7:691810735344320533>',
                  8: '<:esc8:691810735218491393>',
                  9: '<:esc9:691810735415754842>',
                  10: '<:esc10:691810735138930689>',
                  11: '<:esc11:691810735394914375>',
                  12: '<:esc12:691810735482732617>',
                  13: '<:esc13:691810735201714177>',
                  14: '<:esc14:691810735260565635>',
                  15: '<:esc15:691810735394652170>'}


class Fun(commands.Cog):
    """
    F is for friends who do stuff together...
    """

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '🎉'

    class EscapeMenu(menus.Menu):
        def __init__(self, ctx, layout, embed):
            super().__init__(clear_reactions_after=True)
            self.ctx = ctx
            self.layout = layout
            self.embed = embed
            self.active = 1

            types = {cell for row in self.layout for cell in row if cell != 0}
            for cell in types:
                self.add_button(menus.Button(ESCAPE_MAPPING[cell], self.car))

        def get_board(self):
            board = 8 * ESCAPE_MAPPING[-1] + '\n'
            for y, row in enumerate(self.layout):
                board += ESCAPE_MAPPING[-1]
                for x, cell in enumerate(row):
                    board += ESCAPE_MAPPING[cell]
                if y == 2:
                    board += ESCAPE_MAPPING[0] + '\n'
                else:
                    board += ESCAPE_MAPPING[-1] + '\n'
            return board + 8 * ESCAPE_MAPPING[-1]

        async def update_embed(self):
            self.embed.set_field_at(0, name='Active Piece', value=ESCAPE_MAPPING[self.active])
            self.embed.set_field_at(1, name='Board', value=self.get_board())

            return await self.message.edit(embed=self.embed)

        async def send_initial_message(self, ctx, channel):
            self.embed.add_field(name='Active Piece', value=ESCAPE_MAPPING[self.active])
            self.embed.add_field(name='Board', value=self.get_board())

            return await ctx.send(embed=self.embed)

        @menus.button('⏹️', position=menus.Last())
        async def end(self, payload):
            self.stop()

        @menus.button('🔼')
        async def up(self, payload):
            positions = []
            direction_flag = False
            for y, row in enumerate(self.layout):
                for x, cell in enumerate(row):
                    if cell == self.active:
                        if y == 0 or self.layout[y - 1][x] != cell and self.layout[y - 1][x] != 0:
                            return
                        elif self.layout[y - 1][x] == cell:
                            direction_flag = True

                        positions.append((y, x))
            if not direction_flag:
                return
            for y, x in positions:
                self.layout[y][x] = 0
            for y, x in positions:
                self.layout[y - 1][x] = self.active

            await self.update_embed()

        @menus.button('🔽')
        async def down(self, payload):
            positions = []
            direction_flag = False
            for y, row in enumerate(self.layout):
                for x, cell in enumerate(row):
                    if cell == self.active:
                        if y == 5 or self.layout[y + 1][x] != cell and self.layout[y + 1][x] != 0:
                            return
                        elif self.layout[y + 1][x] == cell:
                            direction_flag = True

                        positions.append((y, x))
            if not direction_flag:
                return
            for y, x in positions:
                self.layout[y][x] = 0
            for y, x in positions:
                self.layout[y + 1][x] = self.active

            await self.update_embed()

        @menus.button('◀️')
        async def left(self, payload):
            positions = []
            direction_flag = False
            for y, row in enumerate(self.layout):
                for x, cell in enumerate(row):
                    if cell == self.active:
                        if x == 0 or self.layout[y][x - 1] != cell and self.layout[y][x - 1] != 0:
                            return
                        elif self.layout[y][x - 1] == cell:
                            direction_flag = True

                        positions.append((y, x))
            if not direction_flag:
                return
            for y, x in positions:
                self.layout[y][x] = 0
            for y, x in positions:
                self.layout[y][x - 1] = self.active

            await self.update_embed()

        @menus.button('▶️')
        async def right(self, payload):
            positions = []
            direction_flag = False
            for y, row in enumerate(self.layout):
                for x, cell in enumerate(row):
                    if cell == self.active:
                        if self.active == 1 and x == 5 and y == 2:
                            await self.ctx.send('Well done!')
                            return self.stop()
                        elif x == 5 or self.layout[y][x + 1] != cell and self.layout[y][x + 1] != 0:
                            return
                        elif self.layout[y][x - 1] == cell:
                            direction_flag = True

                        positions.append((y, x))
            if not direction_flag:
                return
            for y, x in positions:
                self.layout[y][x] = 0
            for y, x in positions:
                self.layout[y][x + 1] = self.active

            await self.update_embed()

        async def car(self, payload):
            for index, emoji in ESCAPE_MAPPING.items():
                if index != -1 and index != 0 and f'<:{payload.emoji.name}:{payload.emoji.id}>' == emoji:
                    self.active = index

            await self.update_embed()

    @commands.command(brief='Minigame inspired by "Rush Hour".')
    async def escape(self, ctx, level: int = 1):
        """
        A minigame inspired by Thinkfun's "Rush Hour".
        """
        embed = discord.Embed(title='escape',
                              description='`ono`\n'
                                          'u been kidnap by `finks`, and are now in his `basement`\n'
                                          'escape by `rearranging` his interestingly rectangular furnitures',
                              color=self.bot.color)

        try:
            await self.EscapeMenu(ctx, copy.deepcopy(ESCAPE_LEVELS[level]), embed).start(ctx)
        except KeyError:
            await ctx.send('Level not found.')


def setup(bot):
    bot.add_cog(Fun(bot))
