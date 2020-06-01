from discord.ext import commands


class SilentError(commands.CommandError):
    pass


class CustomError(commands.CommandError):
    def __init__(self, message):
        self.message = message
