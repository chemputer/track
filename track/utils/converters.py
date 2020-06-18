from discord.ext import commands

import utils


class SetValue(commands.Converter):
    def __init__(self, accepted, case_sensitive=False):
        if not case_sensitive:
            self.accepted = accepted
        else:
            self.accepted = [keyword.lower() for keyword in accepted]
        self.case_sensitive = case_sensitive

    async def convert(self, ctx, argument):
        if not self.case_sensitive:
            argument = argument.lower()

        if argument not in self.accepted:
            parameter = list(ctx.command.clean_params.keys())[len(ctx.args) - 2]  # -2 removes Cog and Context object
            raise utils.CustomError(f'Parameter `{parameter}` must be one of the following: {", ".join(self.accepted)} '
                                    f'({"not " if not self.case_sensitive else ""}case sensitive)')
        return argument


class Max(commands.Converter):
    def __init__(self, maximum):
        self.maximum = maximum

    async def convert(self, ctx, argument):
        length = len(argument)

        if length > self.maximum:
            parameter = list(ctx.command.clean_params.keys())[len(ctx.args) - 2]  # -2 removes Cog and Context object
            raise commands.UserInputError(f'Parameter `{parameter}` has a max length of `{self.maximum}` (`{length}` currently).')

        return argument


def lowercase(argument):
    return argument.lower()
