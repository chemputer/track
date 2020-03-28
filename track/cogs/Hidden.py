from discord.ext import commands
import discord


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
        await ctx.send(' '.join(list(message.upper())).replace('O', '<:omegalul:653131858791628840>'))

    @commands.command(brief='Made by ItsLateHere')
    async def bukipasta(self, ctx):
        """
        <a:bukiwiggle:606204351320424609> Made by ItsLateHere <a:bukiwiggle:606204351320424609>
        """
        await ctx.send('You’re in a desert walking along in the sand when all of the sudden you look down, '
                       'and you see a buki, crawling toward you. You reach down, you flip the buki over on its back. '
                       'The buki lays on its back, its belly baking in the hot sun, beating its legs trying to turn '
                       'itself over, but it can’t, not without your help. But you’re not helping. Why is that?')

    @commands.command(brief='Ono another one')
    async def bukipasta2(self, ctx):
        """
        Ono another one
        """
        await ctx.send('I don\'t think it\'s nice, you laughin\'. You see, my buki don\'t like people '
                       'laughing. She gets the crazy idea you\'re laughin\' at her. Now if you apologize, '
                       'like I know you\'re going to, I might convince her that you really didn\'t mean it.')

    @commands.command(brief='Why Hello There')
    async def bukipasta3(self, ctx):
        """
        General Buki
        """
        await ctx.send('Did you ever hear the tragedy of Buki The Wise? I thought not. It\'s not a story the Imperial '
                       'Japanese Navy would tell you. It\'s an Asian legend. Buki was a Special Type Destroyer, so powerful '
                       'and so wise she could use the Combined Fleet to influence the shipyards to create additional Bukis. '
                       'She had such a knowledge of Kantai Kessen that she could even keep the ones she cared about from sinking. '
                       'The dark side of the Decisive Battle Strategy is a pathway to many abilities some consider to be unnatural. '
                       'She became so powerful, that the only thing she was afraid of was losing her power, which eventually, of '
                       'course, she did. Unfortunately, she taught her successor everything she knew, then under her successor she '
                       'sunk in her sleep. Ironic. She could save others from sinking, but not herself.')

    @commands.command(brief='Ancient buki')
    async def bukipasta4(self, ctx):
        """
        Ancient Buki
        """
        await ctx.send('Then out spake brave Fubuki,\nThe Captain of the Destroyer:\n\"To every buki upon this earth\n'
                       'Death cometh soon or late.\nAnd how can any buki die better\nThan facing fearful odds,\n'
                       'For the ashes of her builders,\nAnd the temples of her Emperors.\"')

    @commands.command(brief='Tomorrow is coming')
    async def aah(self, ctx):
        """
        Tomorrow is coming
        """
        await ctx.send('https://cdn.discordapp.com/attachments/651330014532468736/677358572186632192/Aaaaaaaaaaaaahhhh.mp4')


def setup(bot):
    bot.add_cog(Hidden(bot))
