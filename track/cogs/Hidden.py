from discord.ext import commands
import discord

from datetime import datetime

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


class Hidden(commands.Cog):
    """
    Hidden commands. Mostly inside jokes.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='<:omegalul:651328721327882240>')
    async def wow(self, ctx, *, message):
        """
        W <:omegalul:653131858791628840> W
        """
        message = discord.utils.escape_mentions(message)
        await ctx.send(' '.join(list(message.upper())).replace('O', '<:omegalul:653131858791628840>'))

    @commands.command(brief='Not mom\'s lasagna')
    async def bukipasta(self, ctx, num: int):
        if not 1 <= num <= len(BUKIPASTAS):
            return await ctx.send(f'`num` must be an integer between 1 and {len(BUKIPASTAS)}.')
        await ctx.send(BUKIPASTAS[num - 1])

    @commands.command(brief='Tomorrow is coming')
    async def aah(self, ctx):
        """
        Tomorrow is coming
        """
        await ctx.send('https://cdn.discordapp.com/attachments/651330014532468736/677358572186632192/Aaaaaaaaaaaaahhhh.mp4')

    # @commands.command(brief='Embed test.')
    # async def embeddemo(self, ctx):
    #     """
    #     Embed test.
    #     """
    #     embed = discord.Embed(title="Division up with Staff - NA",
    #                           color=0xffffff,
    #                           description="If you would like to be pinged when this event starts, please react with 🙌🏻 below!",
    #                           timestamp=datetime.utcfromtimestamp(1586552400))
    #
    #     embed.set_author(name="Warships Team", icon_url="https://cdn.discordapp.com/icons/669128285527080961/a_7e645d67fc7f212af0660df4bcbdc594.png")
    #     embed.set_footer(text="Starts at")
    #
    #     embed.add_field(name="What", value="Join us here on discord and division with staff in random battles & training rooms!", inline=False)
    #     embed.add_field(name="When", value="```14:00-16:00 PST (21:00 - 23:00 UTC/GMT)```The timezone below is adjusted for your system locale.",
    #                     inline=False)
    #
    #     await ctx.send(embed=embed)
    #
    #     embed = discord.Embed(title="Division up with Staff - EU",
    #                           color=0xffffff,
    #                           description="If you would like to be pinged when this event starts, please react with 🙌🏻 below!",
    #                           timestamp=datetime.utcfromtimestamp(1586534400))
    #
    #     embed.set_author(name="Warships Team", icon_url="https://cdn.discordapp.com/icons/669128285527080961/a_7e645d67fc7f212af0660df4bcbdc594.png")
    #     embed.set_footer(text="Starts at")
    #
    #     embed.add_field(name="What", value="Join us here on discord and division with staff in random battles & training rooms!", inline=False)
    #     embed.add_field(name="When", value="```18:00-20:00 CEST (16:00 - 18:00 UTC/GMT)```The timezone below is adjusted for your system locale.",
    #                     inline=False)
    #
    #     await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Hidden(bot))
