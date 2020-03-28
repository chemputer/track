from discord.ext import commands
import aiosqlite
from datetime import datetime
import os
import pickle

import config


class Track(commands.AutoShardedBot):
    """
    Base bot class.
    """

    def __init__(self):
        super().__init__(command_prefix=self.get_prefix, case_insensitive=True,
                         owner_ids=config.owner_ids, activity=config.activity)

        self.db = None  # value assigned in on_ready
        self.gameparams = None  # value assigned in on_ready
        self.maplesyrup = None  # value assigned in on_ready
        self.uptime = datetime.utcnow()
        self.color = config.color  # color used to theme embeds
        self.prefixes = None  # value assigned in on_ready
        self.created_on = datetime.fromtimestamp(config.created_on)

        for file in os.listdir('cogs'):
            if file.endswith('.py'):
                self.load_extension(f'cogs.{file[:-3]}')
        self.load_extension('jishaku')  # Debug cog

    async def get_prefix(self, message):
        prefixes = {f'<@!{self.user.id}> ', f'<@{self.user.id}> '}  # Nicknamed mention and normal mention, respectively.
        if message.guild is None:
            return prefixes | config.default_prefixes
        else:
            return prefixes | self.prefixes[message.guild.id]

    async def on_ready(self):
        self.db = await aiosqlite.connect('assets/private/track.db')
        self.gameparams = await aiosqlite.connect('assets/private/GameParams.db')
        self.maplesyrup = await aiosqlite.connect('assets/private/maplesyrup.db')
        self.db.row_factory = aiosqlite.Row
        self.gameparams.row_factory = aiosqlite.Row
        self.maplesyrup.row_factory = aiosqlite.Row
        c = await self.db.execute(f'SELECT * FROM guilds')
        guilds = await c.fetchall()

        # Check if bot was invited to new guilds while offline
        ids = [guild['id'] for guild in guilds]
        for guild in self.guilds:
            if guild.id not in ids:
                await self.db.execute(f'INSERT INTO guilds VALUES ({guild.id}, ?)', (pickle.dumps(config.default_prefixes),))
        await self.db.commit()

        # Load prefixes into memory for better performance
        c = await self.db.execute(f'SELECT * FROM guilds')  # Fetch again, to get the new table
        guilds = await c.fetchall()
        self.prefixes = {guild['id']: pickle.loads(guild['prefixes']) for guild in guilds}

        print(f'Ready! [{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}]\n'
              f'Name: {self.user} | ID: {self.user.id}')

    async def on_disconnect(self):
        print(f'Disconnected... [{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}]')

    async def on_resumed(self):
        print(f'Reconnected... [{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}]')

    async def on_guild_join(self, guild):
        await self.db.execute(f'INSERT INTO guilds VALUES ({guild.id}, ?)', (pickle.dumps(config.default_prefixes),))
        self.prefixes[guild.id] = config.default_prefixes.copy()


if __name__ == '__main__':
    Track().run(config.discord_token)
