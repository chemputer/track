from datetime import datetime
import os
import sys
import traceback
import time
import pickle
import sqlite3

from discord.ext import commands

import config
import utils

DEFAULT_GUILD_SETTINGS = {'prefixes': config.default_prefixes, 'builds_channel': None,
                          'disabled_commands': set(), 'disabled_cogs': set()}
DEFAULT_GUILD_ROW = (pickle.dumps(config.default_prefixes), None, pickle.dumps(set()), pickle.dumps(set()))


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
                    except commands.ExtensionError as error:
                        print(f'Failed to load extension {error.name}.')
                        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        self.load_extension('jishaku')

        self.started = False
        self.uptime = datetime.utcnow()
        self.created_on = datetime.fromtimestamp(config.created_on)
        self.color = config.color  # color used to theme embeds

    async def get_prefix(self, message):
        prefixes = {f'<@!{self.user.id}> ', f'<@{self.user.id}> '}  # Nicknamed mention and normal mention, respectively
        if message.guild is None:
            return prefixes | config.default_prefixes
        else:
            try:
                return prefixes | self.guild_options[message.guild.id]['prefixes']
            except KeyError:
                print('Attempting to fix missing guild...')
                try:
                    self.guild_options[message.guild.id] = DEFAULT_GUILD_SETTINGS.copy()
                    async with utils.Transaction(self.db) as conn:
                        await conn.execute('INSERT INTO guilds VALUES (?, ?, ?, ?, ?)', (message.guild.id,) + DEFAULT_GUILD_ROW)
                    return prefixes | self.guild_options[message.guild.id]['prefixes']
                except sqlite3.IntegrityError:
                    pass  # rejoining a guild

    async def on_message(self, message):
        if not self.started:
            return

        await self.process_commands(message)

    async def logout(self):
        async with utils.Transaction(self.db) as conn:
            await conn.execute('INSERT INTO stats VALUES (?, ?)',
                               (int(time.time()), pickle.dumps(self.stats)))

        await super().logout()


if __name__ == '__main__':
    Track().run(config.discord_token)
