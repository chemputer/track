from discord.ext import commands

import asyncio
import inspect
from datetime import datetime
import pickle

import utils

DEFAULT_USER_DATA = {'contours_played': 0, 'contours_record': None, 'morning_streak': 0, 'morning_last': None, 'morning_skips': 0}


# https://discordapp.com/developers/docs/reference#snowflakes
def snowflake2timestamp(snowflake):
    return datetime.fromtimestamp(((snowflake >> 22) + 1420070400000) / 1000.0)


def get_signature(command):
    signature = ''

    if command.full_parent_name:
        signature += command.full_parent_name + ' '

    signature += command.name

    for param, details in command.clean_params.items():
        if param == 'ctx':
            continue

        if isinstance(details.annotation, utils.SetValue):
            if details.default == inspect._empty:  # has no default value, i.e. required
                signature += f' <{"|".join(details.annotation.accepted)}>'
            else:
                signature += f' [{"|".join(details.annotation.accepted)}]'
        else:
            if details.default == inspect._empty:
                signature += f' <{param}>'
            else:
                signature += f' [{param}={details.default}]'

    return signature


async def confirm(ctx, text, timeout=30):
    message = await ctx.send(f'{text}')
    await message.add_reaction('<:yes:651325958514802689>')
    await message.add_reaction('<:no:653131696169811979>')

    def check(reaction, user):
        return reaction.emoji.id in [651325958514802689, 653131696169811979] and user.id == ctx.author.id

    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', check=check, timeout=timeout)
    except asyncio.TimeoutError:
        raise utils.CustomError('Did not receive a response in time, aborting action.')
    else:
        if reaction.emoji.id == 653131696169811979:
            await message.edit(content='Aborted.')
            raise utils.SilentError()


async def fetch_user(connection, user_id):
    async with Transaction(connection) as conn:
        c = await conn.execute('SELECT data FROM users WHERE id = ?', (user_id,))
        data = await c.fetchone()

        if data is None:
            await conn.execute('INSERT INTO users VALUES (?, ?)', (user_id, pickle.dumps(DEFAULT_USER_DATA)))
            return DEFAULT_USER_DATA
        else:
            modified = False
            for key, value in DEFAULT_USER_DATA.items():
                if key not in data:
                    data[key] = value
                    modified = True
            if modified:
                await conn.execute('UPDATE users SET data = ? WHERE id = ?', (pickle.dumps(data), user_id))

            return data


class Transaction:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        await self.conn.commit()
