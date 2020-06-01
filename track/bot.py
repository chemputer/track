from datetime import datetime
import os

from discord.ext import commands

import config


class Track(commands.AutoShardedBot):
    """
    Base bot class. Listeners are stored in the Core cog for easy reloading.
    """

    def __init__(self):
        super().__init__(command_prefix=self.get_prefix, case_insensitive=True,
                         owner_ids=config.owner_ids, activity=config.activity)

        for root, dirs, files in os.walk('cogs'):
            for file in files:
                if file.endswith('.py'):
                    try:
                        self.load_extension(f'{root}.{file[:-3]}'.replace("/", "."))
                    except commands.ExtensionError as e:
                        print(f'Failed to load extension {e.name}.')
        self.load_extension('jishaku')

        self.uptime = datetime.utcnow()
        self.created_on = datetime.fromtimestamp(config.created_on)
        self.color = config.color  # color used to theme embeds

    async def get_prefix(self, message):
        prefixes = {f'<@!{self.user.id}> ', f'<@{self.user.id}> '}  # Nicknamed mention and normal mention, respectively.
        if message.guild is None:
            return prefixes | config.default_prefixes
        else:
            return prefixes | self.guild_options[message.guild.id]['prefixes']


if __name__ == '__main__':
    Track().run(config.discord_token)
