from discord.ext import commands

import asyncio
from contextlib import asynccontextmanager
import inspect
from datetime import datetime

import utils


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


async def confirm(ctx, message, timeout=30):
    message = await ctx.send(f'{message}\nAre you sure?')
    await message.add_reaction('<:yes:651325958514802689>')
    await message.add_reaction('<:no:653131696169811979>')

    def check(reaction, user):
        return reaction.emoji.id in [651325958514802689, 653131696169811979] and user.id == ctx.author.id

    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', check=check, timeout=timeout)
    except asyncio.TimeoutError:
        raise commands.UserInputError('Did not receive a response in time, aborting command.')
    else:
        if reaction.emoji.id == 653131696169811979:
            await message.edit(content='Aborted.')
            raise commands.CommandNotFound()  # raise error EH will ignore


async def fetch_user(conn, user):
    c = await conn.execute(f'SELECT * FROM users WHERE id = {user.id}')
    details = await c.fetchone()
    if details is None:
        await conn.execute(f'INSERT INTO users VALUES (?, ?, ?)', (user.id, 0, 60.0))
        await conn.commit()
    c = await conn.execute(f'SELECT * FROM users WHERE id = {user.id}')
    return await c.fetchone()


class Transaction:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        await self.conn.commit()
