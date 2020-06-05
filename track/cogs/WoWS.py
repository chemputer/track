from discord.ext import commands, menus
import discord
from unidecode import unidecode
import wargaming
import polib
from PIL import Image
import matplotlib.pyplot as plt
import imageio
import numpy

import random
import io
import pickle
import json
from datetime import datetime
import sqlite3
import difflib
from typing import Dict, Tuple, NamedTuple, List
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import math
from lxml import etree
import os
import collections

import config
import utils
# from replay_unpack import replay_reader
# from replay_unpack.clients.wows import ReplayPlayer


# gets rid of annoying logs for expected missing tables by maplesyrup queries
logging.getLogger('aiosqlite').setLevel(logging.CRITICAL)

# Turns off interactive plotting?
plt.ioff()

Tier = int


class TierBound(NamedTuple):
    lower: int
    upper: int


class ArmorThreshold(NamedTuple):
    value: int
    name: str
    tiers: TierBound


# T1 can meet T1-T1, T2 can meet T2-T3, T3 can meet T2-4, etc.
_matchmaking = {1: (1, 1), 2: (2, 3), 3: (2, 4), 4: (3, 5), 5: (4, 7),
                6: (5, 8), 7: (5, 9), 8: (6, 10), 9: (7, 10), 10: (8, 10)}
# Handpicked "significant" armor thresholds and descriptions of what has them
# Used to assist in deciding whether or not to take IFHE
_thresholds = {16: {'Tier 3 Battleship/Stern': (3, 3),
                    'Tier 6-7 Battleship Superstructure': (6, 7),
                    'Most Tier 6-7 Cruiser Bow/Stern': (6, 7)},
               19: {'Tier 4-5 Battleship Bow/Stern': (4, 5),
                    'Tier 8-10 Battleship Superstructure': (8, 10),
                    'Tier 8-10 Destroyer Plating': (8, 10)},
               25: {'Some Tier 8-10 Cruiser Bow/Stern': (8, 10),
                    'Tier 8 CA Plating': (8, 8)},
               26: {'Tier 6-7 Battleship Bow/Stern/Upper Belt/Deck': (6, 7)},
               27: {'Some Tier 8-10 Cruiser Bow/Stern': (8, 10),
                    'Tier 9 CA Plating': (9, 9)},
               30: {'Tier 10 CA Plating': (10, 10)},
               32: {'Tier 8-10 Battleship Bow/Stern': (8, 10),
                    'Tier 8-10 MNF & RN Battleship Plating/Deck': (8, 10)},
               38: {'Tier 8-10 USN Battleship Casemate': (8, 10)},
               50: {'Khabarovsk Belt': (10, 10),
                    'Moskva/Stalingrad Plating': (10, 10),
                    'Großer Kurfürst Deck': (10, 10)},
               57: {'Izumo/Yamato Deck': (9, 10)},
               60: {'Sovetsky Soyuz/Kremlin Deck': (9, 10)}}
# Base fire protection coefficients for BBs
# Used in E(t) calculations for setting fires
_base_fp = {3: 0.9667, 4: 0.9001, 5: 0.8335, 6: 0.7669, 7: 0.7003, 8: 0.6337, 9: 0.5671, 10: 0.5005}


REGIONS = ['na', 'eu', 'ru', 'asia']
VERSION = '0.9.4.1'
SIMILAR_SHIPS: List[Tuple] = [('Montana', 'Ohio'),
                              ('Thunderer', 'Conqueror'),
                              ('Fletcher', 'Black'),
                              ('Prinz Eugen', 'Admiral Hipper', 'Mainz'),
                              ('Des Moines', 'Salem'),
                              ('Musashi', 'Yamato'),
                              ('Massachusetts', 'Alabama'),
                              ('King George V', 'Duke of York'),
                              ('Irian', 'Mikhail Kutuzov'),
                              ('Admiral Makarov', 'Nürnberg'),
                              ('Kamikaze', 'Kamikaze R', 'Fūjin'),
                              ('Iowa', 'Missouri'),
                              ('Le Fantasque', 'Le Terrible'),
                              ('Nueve de Julio', 'Boise'),
                              ('Fushun', 'Anshan'),
                              ('Kléber', 'Marceau'),
                              ('Halland', 'Småland')]
MATCHMAKING: Dict[Tier, TierBound] = {k: TierBound(*v)
                                      for k, v in _matchmaking.items()}
THRESHOLDS: List[ArmorThreshold] = [ArmorThreshold(k, name, TierBound(*bound))
                                    for k, v in _thresholds.items()
                                    for name, bound in v.items()]
BASE_FP: Dict[Tier, float] = {k: v for k, v in _base_fp.items()}

PENETRATION = 0.5561613
GRAVITY = 9.80665  # N / kg
TEMPERATURE = 288.15  # K (sea level)
LAPSE_RATE = 0.0065  # K / m
PRESSURE = 101325.0  # Pa (sea level)
UNIV_GAS_CONSTANT = 8.31447  # J / (mol * K)
AIR_MOLAR_MASS = 0.0289644  # kg / mo

del _matchmaking
del _thresholds


@dataclass
class Ship:
    name: str
    short_name: str
    params: dict

    @classmethod
    async def convert(cls, ctx, argument):
        error = None

        # XXX: Potential @lru_cache function
        matches = {}
        for name, index in ctx.bot.mapping.items():
            if unidecode(argument.lower()) == name.lower():  # edge cases: Erie is in Algerie etc.
                matches = {name: index}
                break
            elif unidecode(argument.lower()) in name.lower():
                # there are old versions of some ships left in the game code
                # will only include them in the results if user requests it
                if 'old' in name.lower() and 'old' not in argument.lower():
                    continue
                matches[name] = index
        # End

        if len(matches) == 0:
            error = f'No ships found containing `{argument}` :('
        elif len(matches) > 1:
            error = f'Multiple ships found containing `{argument}`!'

        if error:
            # XXX: Potential @lru_cache function
            similar = difflib.get_close_matches(argument, list(ctx.bot.mapping.keys()), n=3, cutoff=0.6)
            # End

            if len(similar) != 0:
                error += f'\nDid you mean...\n' + '\n'.join(f'- {result}' for result in similar)
            raise commands.UserInputError(error)

        name, index = matches.popitem()

        # XXX: Potential @lru_cache function
        c = await ctx.bot.gameparams.execute(f'SELECT value FROM Ship WHERE id = \'{index}\'')
        params = await c.fetchone()
        return Ship(name=ctx.bot.globalmo[f'IDS_{params["index"]}_FULL'],
                    short_name=ctx.bot.globalmo[f'IDS_{params["index"]}'],
                    params=params)
        # End


class MapleSyrupData(NamedTuple):
    player: sqlite3.Row = None
    unit: sqlite3.Row = None


@dataclass
class MapleSyrupShip:
    name: str
    na: MapleSyrupData = None
    eu: MapleSyrupData = None
    ru: MapleSyrupData = None
    asia: MapleSyrupData = None

    @classmethod
    async def convert(cls, ctx, argument):
        error = None

        matches = []
        for ship in ctx.bot.ms_mapping['ALL']:
            if unidecode(argument.lower()) == ship.lower():  # edge cases: Erie is in Algerie etc.
                matches = [ship]
                break
            elif unidecode(argument.lower()) in ship.lower():
                # there are old versions of some ships left in the game code
                # will only include them in the results if user requests it
                if 'old' in ship.lower() and 'old' not in argument.lower():
                    continue
                matches.append(ship)

        if len(matches) == 0:
            error = f'No ships found containing `{argument}` :('
        elif len(matches) > 1:
            error = f'Multiple ships found containing `{argument}`!'

        if error:
            similar = difflib.get_close_matches(argument, ctx.bot.ms_mapping['ALL'], n=3, cutoff=0.6)

            if len(similar) != 0:
                error += f'\nDid you mean...\n' + '\n'.join(f'- {result}' for result in similar)
            raise commands.UserInputError(error)

        ship = matches.pop()

        async def fetch_data(region):
            # http://maplesyrup.sweet.coocan.jp/wows/ranking/avgbased.png
            try:
                c = await ctx.bot.maplesyrup.execute(f'SELECT * FROM "{region}_{ship}"')
                player = await c.fetchall()
            except sqlite3.OperationalError:
                player = None

            try:
                c = await ctx.bot.maplesyrup.execute(f'SELECT * FROM "{region}_{ship}_u"')
                unit = await c.fetchall()
            except sqlite3.OperationalError:
                unit = None

            return MapleSyrupData(player, unit)

        tasks = [fetch_data(region) for region in REGIONS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return MapleSyrupShip(name=ship, na=results[0], eu=results[1], ru=results[2], asia=results[3])


@dataclass
class Build:
    id: int = None
    author: int = None
    title: str = None
    description: str = None
    skills: list = None
    total: int = None
    guild_id: int = None
    in_queue: int = None  # "boolean"
    include_queued: bool = False

    @classmethod
    async def convert(cls, ctx, argument):
        c = await ctx.bot.db.execute(f'SELECT * FROM builds WHERE guild_id = \'{ctx.guild.id}\'')
        builds = await c.fetchall()

        results = []
        for build in builds:
            if argument == str(build['id']):
                if cls.include_queued or not build['in_queue']:
                    return Build(id=build['id'], author=build['author'], title=build['title'],
                                 description=build['description'], skills=pickle.loads(build['skills']),
                                 total=build['total'], guild_id=build['guild_id'], in_queue=build['in_queue'])
            elif (argument.startswith('<@!') and argument.endswith('>') and argument[3:-1] == str(build['author']) or
                  argument.startswith('<@') and argument.endswith('>') and argument[2:-1] == str(build['author']) or
                  argument == str(build['author']) or
                  argument.lower() in build['title'].lower()):
                if cls.include_queued or not build['in_queue']:
                    results.append(build)

        if len(results) == 0:
            raise commands.UserInputError('No builds found. You can make it!')
        elif len(results) > 1:
            pages = menus.MenuPages(source=SplitBuilds(list(results), f'Query: `{argument}`\n'), clear_reactions_after=True)
            await pages.start(ctx)
            raise commands.CommandNotFound()  # raise error EH will ignore

        build = results.pop()
        return Build(id=build['id'], author=build['author'], title=build['title'],
                     description=build['description'], skills=pickle.loads(build['skills']),
                     total=build['total'], guild_id=build['guild_id'], in_queue=build['in_queue'])


class SplitBuilds(menus.ListPageSource):
    def __init__(self, data, description):
        super().__init__(data, per_page=10)
        self.description = description

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        page = '\n'.join([f'**{build["title"]}**\n'
                          f'by <@{build["author"]}> (ID: {build["id"]})'
                          for count, build in enumerate(entries, start=offset)])
        embed = discord.Embed(title=f'Builds (Page {menu.current_page + 1} of {self.get_max_pages()})',
                              description=self.description + page)
        embed.set_footer(text='View a specific page with builds list [page].')
        return embed


class WoWS(commands.Cog, name='Wows'):
    """
    For your favorite pixelbote collecting game!
    """

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '🚢'
        self.display_name = 'WoWS'

        Regions = collections.namedtuple('Regions', REGIONS)
        self.api = Regions(na=wargaming.WoWS(config.wg_token, region='na', language='en'),
                           eu=wargaming.WoWS(config.wg_token, region='eu', language='en'),
                           ru=wargaming.WoWS(config.wg_token, region='ru', language='en'),
                           asia=wargaming.WoWS(config.wg_token, region='asia', language='en'))

        self.bot.globalmo = {entry.msgid: entry.msgstr for entry in polib.mofile('assets/private/global.mo')}
        self.bot.mapping = {}  # maps name to index
        self.bot.ship_id = {}  # maps ship id to index
        with sqlite3.connect('assets/private/gameparams.db') as conn:
            c = conn.execute('SELECT * FROM Ship')

            for ship, params_blob in c:
                params = pickle.loads(params_blob)
                if params['group'] not in ['disabled', 'unavailable', 'clan']:
                    # the full name of legacy versions of ships contains the date they were removed
                    # instead of (old) or (OLD), making it hard to remember, so in this case the short name is used
                    # unidecode converts unicode into ASCII equivalent (such as ö to o) for easy of access
                    index = params['index']
                    if 'old' in self.bot.globalmo[f'IDS_{index}'].lower():
                        self.bot.mapping[unidecode(self.bot.globalmo[f'IDS_{index}'])] = ship
                    else:
                        self.bot.mapping[unidecode(self.bot.globalmo[f'IDS_{index}_FULL'])] = ship

                self.bot.ship_id[params['id']] = params['name']

        with sqlite3.connect('assets/private/maplesyrup.db') as conn:
            c = conn.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')
            tables = [table[0] for table in c.fetchall()]  # flatten

            self.bot.ms_mapping, self.bot.ms_mapping_u = {'ALL': set()}, {'ALL': set()}
            for region in REGIONS:
                ships, ships_u = [], []
                for ship in tables:
                    if ship.startswith(region):
                        if '_u' in ship:
                            ships_u.append(ship[ship.index('_') + 1:-2])
                        else:
                            ships.append(ship[ship.index('_') + 1:])

                self.bot.ms_mapping[region] = ships
                self.bot.ms_mapping_u[region] = ships_u
                self.bot.ms_mapping['ALL'].update(ships)
                self.bot.ms_mapping_u['ALL'].update(ships_u)

            # for region, ships in self.bot.ms_mapping.items():
            #     print(region + ' ' + str(len(ships)))
            #     print(ships)
            # for region, ships in self.bot.ms_mapping_u.items():
            #     print(region + ' ' + str(len(ships)))
            #     print(ships)

        with open('assets/public/skills/skills.json', 'r', encoding='utf-8') as skills:
            self.skills = json.load(skills)

    @commands.command(brief='Link your WG account!')
    async def link(self, ctx, region):
        """
        Link your WG account!

        Make sure you use the right region.
        """
        await ctx.send('WIP, placeholder')

    @commands.command(brief='Tutorial on how to dodge CV attacks.')
    async def counterCV(self, ctx):
        """
        Gives you a link to an advanced tutorial on mitigating damage taken from CV attacks.
        """
        embed = discord.Embed(title='Helpful Links',
                              description='[Throttle Jockeying](https://www.youtube.com/watch?v=dQw4w9WgXcQ)\n'  # rickroll
                                          '[CV Reticules Overview](https://www.youtube.com/watch?v=d1YBv2mWll0)')  # jebaited
        await ctx.send(embed=embed)

    @commands.command(aliases=['ifhe'], brief='Provides detailed info about a ship\'s HE.')
    async def he(self, ctx, *, ship: Ship):
        """
        Calculates HE penetration of target ship before/after taking IFHE.

        A recommendation is also given based on common armor thresholds.
        """
        # Main Battery
        he_ammo = {}
        for upgrade, upgrade_params in ship.params['ShipUpgradeInfo'].items():
            if isinstance(upgrade_params, dict) and upgrade_params['ucType'] == '_Artillery':
                module = upgrade_params['components']['artillery'][0]
                for turret, turret_params in ship.params[module].items():
                    try:
                        for ammo in turret_params['ammoList']:
                            c = await self.bot.gameparams.execute(f'SELECT value FROM Projectile WHERE id = \'{ammo}\'')
                            ammo_params = await c.fetchone()

                            if ammo_params['ammoType'] == 'HE':
                                # the upper() is necessary because WG made a typo with Kamikaze & her sisters
                                # (PJUA451_120_45_Type_Ha_TRUE_KAMIKAZE vs. PJUA451_120_45_TYPE_HA_TRUE_KAMIKAZE)
                                upgrade_name = self.bot.globalmo[f'IDS_{upgrade.upper()}']
                                if upgrade_name in he_ammo:
                                    he_ammo[upgrade_name][2] += int(turret_params['numBarrels'])
                                else:
                                    he_ammo[upgrade_name] = [ammo_params, turret_params['shotDelay'], int(turret_params['numBarrels'])]
                    except (KeyError, TypeError):
                        pass

        if len(he_ammo) == 0:
            return await ctx.send(f'`{ship.name}` doesn\'t have main battery HE!')

        embed = discord.Embed(title=ship.name,
                              description=f'Data extracted from WoWS {VERSION}.',
                              color=self.bot.color)

        for upgrade_name, details in he_ammo.items():
            tier = ship.params['level']
            pen = details[0]['alphaPiercingHE']
            fire_chance = details[0]['burnProb']
            diameter = details[0]['bulletDiametr']
            reload = details[1]
            barrels = details[2]

            base_threshold_flag = False
            bypassed = []
            for threshold in THRESHOLDS:
                if threshold.value > int(pen):
                    base_threshold_flag = True

                if base_threshold_flag:
                    if threshold.value > int(pen * 1.25):
                        break
                    else:
                        matchmaking = MATCHMAKING[tier]
                        if (matchmaking.lower <= threshold.tiers.lower <= matchmaking.upper or
                                matchmaking.lower <= threshold.tiers.upper <= matchmaking.upper):
                            bypassed.append(threshold)

            details = (f'Penetrates up to `{int(pen)} mm` by default.\n'
                       f'With IFHE, up to `{int(pen * 1.25)} mm`.')
            if bypassed:
                details += ' This bypasses:\n- ' + '\n- '.join([f'{threshold.name} `[{threshold.value}mm]`' for threshold in bypassed])
            else:
                details += f'\nIFHE bypasses no notable armor thresholds at Tier {tier}.'

            if tier == 1 or tier == 2:
                details += '\nFire chance insight unavailable for Tier 1 & 2.'
            else:
                signal_bonus = 0.02 if diameter > 0.160 else 0.01
                normal = BASE_FP[tier] * 0.95 * 0.9 * (fire_chance + 0.02 + signal_bonus)
                ifhe = BASE_FP[tier] * 0.95 * 0.9 * (0.5 * fire_chance + 0.02 + signal_bonus)

                details += (f'\nBase Fire Chance: `{fire_chance * 100:.1f}%`\n'
                            f'IFHE effect on fire chance: `{normal * 100:.2f}%` -> `{ifhe * 100:.2f}%`\n'
                            f'IFHE effect on E(t) of fire: `{reload / normal / barrels / 0.3:.2f}s` -> `{reload / ifhe / barrels / 0.3:.2f}s`')

            embed.add_field(name=upgrade_name, value=details, inline=False)

        embed.set_author(icon_url='https://cdn.discordapp.com/attachments/651324664496521225/651332148963442688/logo.png', name=ship.params['name'])
        embed.set_thumbnail(url='https://media.discordapp.net/attachments/651324664496521225/651331492596809739/ammo_he_2x.png')
        embed.set_footer(text='Fire chance calculated using same-tier BB with DCM1 & FP, and DE+signals bonuses.\n'
                              'E(t) of fire calculated using 30% hit chance, but no AR boost.')
        await ctx.send(embed=embed)

    # @commands.command(brief='Provides detailed info about a ship\'s AP.')
    # async def ap(self, ctx, *, ship: Ship):
    #     """
    #     Provides detailed information about AP shell characteristics, including overmatch.
    #     """
    #     ap_ammo = {}
    #     for upgrade, upgrade_params in ship.params['ShipUpgradeInfo'].items():
    #         if isinstance(upgrade_params, dict) and upgrade_params['ucType'] == '_Artillery':
    #             module = upgrade_params['components']['artillery'][0]
    #             for turret, turret_params in ship.params[module].items():
    #                 try:
    #                     for ammo in turret_params['ammoList']:
    #                         c = await self.bot.gameparams.execute(f'SELECT value FROM Projectile WHERE id = \'{ammo}\'')
    #                         ammo_params_blob = await c.fetchone()
    #                         ammo_params = json.loads(ammo_params_blob[0])
    #
    #                         if ammo_params['ammoType'] == 'AP':
    #                             # the upper() is necessary because WG made a typo with Kamikaze & her sisters
    #                             # (PJUA451_120_45_Type_Ha_TRUE_KAMIKAZE vs. PJUA451_120_45_TYPE_HA_TRUE_KAMIKAZE)
    #                             upgrade_name = self.bot.globalmo[f'IDS_{upgrade.upper()}']
    #                             if upgrade_name in ap_ammo:
    #                                 ap_ammo[upgrade_name][2] += int(turret_params['numBarrels'])
    #                             else:
    #                                 ap_ammo[upgrade_name] = [ammo_params, turret_params['shotDelay'], int(turret_params['numBarrels'])]
    #                 except (KeyError, TypeError):
    #                     pass
    #
    #     if len(ap_ammo) == 0:
    #         return await ctx.send(f'`{ship.name}` doesn\'t have main battery AP!')
    #
    #     embed = discord.Embed(title=ship.name,
    #                           description=f'Data extracted from WoWS {VERSION}.',
    #                           color=self.bot.color)
    #
    #     for upgrade_name, details in ap_ammo.items():
    #         tier = ship.params['level']
    #         diameter = details[0]['bulletDiametr']
    #         reload = details[1]
    #         barrels = details[2]
    #
    #         base_threshold_flag = False
    #         bypassed = []
    #         for threshold in THRESHOLDS:
    #             if threshold.value > int(pen):
    #                 base_threshold_flag = True
    #
    #             if base_threshold_flag:
    #                 if threshold.value > int(pen * 1.25):
    #                     break
    #                 else:
    #                     matchmaking = MATCHMAKING[tier]
    #                     if (matchmaking.lower <= threshold.tiers.lower <= matchmaking.upper or
    #                             matchmaking.lower <= threshold.tiers.upper <= matchmaking.upper):
    #                         bypassed.append(threshold)
    #
    #         details = (f'Penetrates up to `{int(pen)} mm` by default.\n'
    #                    f'With IFHE, up to `{int(pen * 1.25)} mm`.')
    #         if bypassed:
    #             details += ' This bypasses:\n- ' + '\n- '.join([f'{threshold.name} `[{threshold.value}mm]`' for threshold in bypassed])
    #         else:
    #             details += f'\nIFHE bypasses no notable armor thresholds at Tier {tier}.'
    #
    #         if tier == 1 or tier == 2:
    #             details += '\nFire chance insight unavailable for Tier 1 & 2.'
    #         else:
    #             signal_bonus = 0.02 if diameter > 0.160 else 0.01
    #             normal = BASE_FP[tier] * 0.95 * 0.9 * (fire_chance + 0.02 + signal_bonus)
    #             ifhe = BASE_FP[tier] * 0.95 * 0.9 * (0.5 * fire_chance + 0.02 + signal_bonus)
    #
    #             details += (f'\nBase Fire Chance: `{fire_chance * 100:.1f}%`\n'
    #                         f'IFHE effect on fire chance: `{normal * 100:.2f}%` -> `{ifhe * 100:.2f}%`\n'
    #                         f'IFHE effect on E(t) of fire: `{reload / normal / barrels / 0.3:.2f}s` -> `{reload / ifhe / barrels / 0.3:.2f}s`')
    #
    #         embed.add_field(name=upgrade_name, value=details, inline=False)
    #
    #     embed.set_author(icon_url='https://cdn.discordapp.com/attachments/651324664496521225/651332148963442688/logo.png', name=ship.params['name'])
    #     embed.set_thumbnail(url='https://media.discordapp.net/attachments/651324664496521225/651331492596809739/ammo_he_2x.png')
    #     embed.set_footer(text='Fire chance calculated using same-tier BB with DCM1 & FP, and DE+signals bonuses.\n'
    #                           'E(t) of fire calculated using 30% hit chance, but no AR boost.')
    #     await ctx.send(embed=embed)

    @commands.group(aliases=['build'], invoke_without_command=True, brief='Create and share builds!')
    async def builds(self, ctx, *, build: Build):
        """
        Create and share builds with other members!

        Not using a subcommand searches for builds that match the query.
        You may search by either title or author.
        """
        fp = io.BytesIO()

        def build_image(skills):
            image = Image.open('assets/public/skills/template.png')
            for skill in skills:
                overlay = Image.open(f'assets/public/skills/{self.skills[str(skill)]["name"]}.png')
                image.paste(overlay, (0, 0), overlay)
            image.save(fp, 'PNG')
            fp.seek(0)

        await self.bot.loop.run_in_executor(ThreadPoolExecutor(), build_image, build.skills)

        embed = discord.Embed(title=build.title,
                              description=build.description,
                              color=self.bot.color,
                              timestamp=utils.snowflake2timestamp(build.id))
        embed.set_image(url=f'attachment://{build.id}.png')
        embed.add_field(name='Author',
                        value=f'<@{build.author}>')
        embed.add_field(name='Raw',
                        value=', '.join([self.skills[str(skill)]['name'] for skill in build.skills]))
        embed.set_footer(text=f'ID: {build.id}\n{build.total}/19 points')

        await ctx.send(file=discord.File(fp, filename=f'{build.id}.png'), embed=embed)

    @builds.command(brief='Lists all builds.')
    async def list(self, ctx, page: int = None):
        """
        Lists all builds.
        """
        c = await ctx.bot.db.execute(f'SELECT * FROM builds WHERE guild_id = \'{ctx.guild.id}\'')
        builds = await c.fetchall()
        visible = [build for build in builds if not build['in_queue']]

        if page is None:
            pages = menus.MenuPages(source=SplitBuilds(visible, ''), clear_reactions_after=True)
            await pages.start(ctx)
        else:
            max_pages = math.ceil(len(visible) / 10)
            if not 1 <= page <= max_pages:
                return await ctx.send(f'`page` must be an integer between 1 and {max_pages}.')

            split = [visible[i * 10:(i + 1) * 10] for i in range((len(visible) + 9) // 10)]
            _page = '\n'.join([f'**{build["title"]}**\n'
                               f'by <@{build["author"]}> (ID: {build["id"]})'
                               for build in split[page - 1]])
            embed = discord.Embed(title=f'Builds (Page {page} of {max_pages})',
                                  description=_page)
            embed.set_footer(text='View a specific page with builds list [page].')
            await ctx.send(embed=embed)

    @builds.command(brief='Shows you the template for builds.')
    async def template(self, ctx):
        """
        Generates a preview of what a build from `builds` looks like.
        """
        content = ('⚠️ **Submitting Details** ⚠️\n'
                   '- The order of your skills is kept!\n'
                   '- When submitting, wrap multiple words with quotation marks \"like this\"\n'
                   '- Shorthand abbreviations, some slang, and indexes(see above) are accepted. You can even mix them!\n'
                   '- Split individual skills with commas!\n'
                   '\n'
                   'Example:\n'
                   '```py\nbuild create "10 point CV build" "AS, TA, AIRCRAFT Armor, 32" "I took TA because I can\'t lead torps, ..."```'
                   'Template:')

        embed = discord.Embed(title='[Build name] (50 characters max)',
                              description='[Description]',
                              color=0xe3e3e3,
                              timestamp=self.bot.created_on)
        embed.set_image(url='https://cdn.discordapp.com/attachments/651324664496521225/669496734556094464/template.png')
        embed.add_field(name='Author', value=self.bot.user.mention, inline=True)
        embed.add_field(name='Raw', value='[Raw Skill Data]', inline=True)
        embed.set_footer(text='?/19 points')

        await ctx.send(content=content, embed=embed)

    @builds.command(aliases=['submit'], brief='Create a build.')
    async def create(self, ctx, title: utils.Max(75), captain_skills: utils.lowercase, description='No description given.'):
        """
        Adds a build.
        - The order of your skills matters, and is kept!
        - Make sure you wrap multiple word parameters with quotation marks "like this"
        - Shorthand abbreviations, some slang, and indexes are accepted for captain skills. You can even mix them!
        - Split individual skills with commas!
        - Use `\\"` to represent `"` when using quotes inside a parameter!
        For an example, see `template`.
        """

        def convert_skill(argument):
            for skill, skill_params in self.skills.items():
                if argument in skill_params['nicknames'] or argument == skill_params['name'].lower():
                    return skill
            return argument

        captain_skills = [entry.strip() for entry in captain_skills.split(',')]
        converted = [convert_skill(entry) for entry in captain_skills]

        captain_skills = []
        for skill in converted:
            try:
                captain_skills.append(int(skill))
            except ValueError:
                return await ctx.send(f'`{skill}` is not a valid captain skill!')

        if len(captain_skills) != len(set(captain_skills)):
            return await ctx.send('Duplicate skills were detected!')

        total, max_tier = 0, 0
        for skill in captain_skills:
            if skill > 32 or skill < 1:
                return await ctx.send(f'`{skill}` is out of the index range (1 to 32)!')
            tier = (skill - 1) // 8 + 1
            if tier > max_tier + 1:
                return await ctx.send(f'Invalid skill order detected! A tier `{tier}` skill '
                                      f'was chosen when the current max was only `{max_tier}`')
            elif tier == max_tier + 1:
                max_tier = tier
            total += tier
        if total > 19:
            return await ctx.send(f'This build costs `{total}` points! The max is 19.')

        async with utils.Transaction(self.bot.db) as conn:
            c = await conn.execute(f'SELECT * FROM guilds WHERE id = ?', (ctx.guild.id,))
            builds_channel = (await c.fetchone())['builds_channel']

            if builds_channel is None or builds_channel == ctx.channel.id:
                await ctx.bot.db.execute(f'INSERT INTO builds VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                         (ctx.message.id, ctx.author.id, title, description,
                                          pickle.dumps(captain_skills), total, ctx.guild.id, 0))
                await ctx.send(f'Thank you for your submission! ID: `{ctx.message.id}`')
            else:
                await ctx.bot.db.execute(f'INSERT INTO builds VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                         (ctx.message.id, ctx.author.id, title, description,
                                          pickle.dumps(captain_skills), total, ctx.guild.id, 1))
                message = await self.bot.get_channel(builds_channel).send(f'New build from {ctx.author.mention}!\n'
                                                                          f'Approve it with `builds approve {ctx.message.id}`, '
                                                                          f'or reject it with `builds reject {ctx.message.id}`.')
                build = Build(id=ctx.message.id, author=ctx.author.id, title=title, description=description,
                              skills=captain_skills, total=total, guild_id=ctx.guild.id, in_queue=True)
                await (await self.bot.get_context(message)).invoke(self.bot.get_command('builds'), build=build)
                await ctx.send(f'Your build has been submitted to this server\'s queue! ID: `{ctx.message.id}`')

    @builds.command(aliases=['remove'], brief='Delete a build.')
    async def delete(self, ctx, *, build: Build):
        """
        Delete a build you own.

        Users with administrator may also delete any build.
        """
        async with utils.Transaction(self.bot.db) as conn:
            if build.author != ctx.author.id and not ctx.author.guild_permissions.administrator:
                return await ctx.send('You cannot delete a build that is not yours!')

            await utils.confirm(ctx, f'\"{build.title}\" will be deleted.')

            await conn.execute(f'DELETE FROM builds WHERE id = ?', (build.id,))
            await ctx.send('Build deleted.')
            if build.in_queue:
                c = await conn.execute(f'SELECT * FROM guilds WHERE id = ?', (ctx.guild.id,))
                builds_channel = (await c.fetchone())['builds_channel']
                await self.bot.get_channel(builds_channel).send(f'{ctx.author.mention} has deleted their build '
                                                                f'"{build.title}" (ID: {build.id}), which was queued.')

    @builds.command(brief='Approve a build in queue.')
    async def approve(self, ctx, build_id: int):
        """
        Approves a build in queue by its ID, if approve-only mode is enabled on this server.

        Must be used in the designated text channel.
        """
        async with utils.Transaction(self.bot.db) as conn:
            c = await conn.execute(f'SELECT * FROM guilds WHERE id = ?', (ctx.guild.id,))
            builds_channel = (await c.fetchone())['builds_channel']
            c = await conn.execute(f'SELECT * FROM builds WHERE id = ?', (build_id,))
            build = await c.fetchone()

            if builds_channel is None:
                return await ctx.send('This command may only be used when approve-only mode is active.')
            elif builds_channel != ctx.channel.id:
                return await ctx.send('This command must be used in the designated channel.')
            elif not build:
                return await ctx.send('Build not found.')
            elif not build['in_queue']:
                return await ctx.send('Build not in queue.')

            await conn.execute(f'UPDATE builds SET in_queue = 0 WHERE id = ?', (build_id,))
            await ctx.send('Build approved.')

    @builds.command(brief='Rejects a build in queue.')
    async def reject(self, ctx, build_id: int):
        """
        Reject a build in queue by its ID, if approve-only mode is enabled on this server.

        Must be used in the designated text channel.
        """
        async with utils.Transaction(self.bot.db) as conn:
            c = await conn.execute(f'SELECT * FROM guilds WHERE id = ?', (ctx.guild.id,))
            builds_channel = (await c.fetchone())['builds_channel']
            c = await conn.execute(f'SELECT * FROM builds WHERE id = ?', (build_id,))
            build = await c.fetchone()

            if builds_channel is None:
                return await ctx.send('This command may only be used when approve-only mode is active.')
            elif builds_channel != ctx.channel.id:
                return await ctx.send('This command must be used in the designated channel.')
            elif not build:
                return await ctx.send('Build not found.')
            elif not build['in_queue']:
                return await ctx.send('Build not in queue.')

            await conn.execute(f'DELETE FROM builds WHERE id = ?', (build_id,))
            await ctx.send('Build rejected.')

    @commands.command(aliases=['armor'], brief='Lists notable armor thresholds.')
    async def thresholds(self, ctx):
        embed = discord.Embed(title='Armor Thresholds',
                              description='Not comprehensive, but the most notable thresholds are listed.',
                              color=self.bot.color)
        thresholds = {}
        for threshold in THRESHOLDS:
            try:
                thresholds[threshold.value].append(threshold.name)
            except KeyError:
                thresholds[threshold.value] = [threshold.name]

        for value, names in thresholds.items():
            embed.add_field(name=f'{value}mm', value='\n'.join([f'- {name}' for name in names]))
        embed.add_field(name='​', value='​')  # Zero Width Spaces, (11 thresholds -> 3x4)
        await ctx.send(embed=embed)

    @commands.command(brief='For Gambie', hidden=True)
    async def taken(self, ctx, *query):
        """
        For Gambie
        """
        for search in query:
            try:
                result = self.api.account.list(search=search, type='exact')
                await ctx.send(f'{search} is ' + ('not taken.' if len(result) == 0 else f'taken ({result[0]}).'))
            except wargaming.exceptions.RequestError as e:
                await ctx.send(f'Encountered error {e} whilst searching {search}.')

    @commands.command(brief='Spreadsheet pls', hidden=True)
    async def shipinfo(self, ctx):
        """
        Spreadsheet dummy boy
        """
        info = {}
        page = 1
        while True:
            try:
                info = {**info, **self.api.encyclopedia.ships(page_no=page).data}
                page += 1
            except wargaming.exceptions.RequestError:
                break

        with open('shipinfo.json', 'r+') as file:
            json.dump(info, file, indent=2)
        await ctx.send(file=discord.File('shipinfo.json'))

    @commands.command(brief='"Who\'s that ~~pokemon~~ ship?"')
    async def guess(self, ctx, min_tier=4, max_tier=10, allow_test_ships: bool = False):
        """
        A guessing minigame inspired by "Who's that pokemon?".
        Some ships are removed from the list, including:
        - High School Fleet, Azur Lane, Arpeggio of Blue Steel collaboration ships
        - Black Friday Ships
        - Eastern/Southern Dragon
        - Tachibana/Diana Lima
        - Alabama ST and Arkansas Beta
        - Siliwangi, Wukong, Bajie
        """
        if not 1 <= min_tier <= 10 or not 1 <= max_tier <= 10:
            return await ctx.send('Tiers must be within 1 and 10.')
        elif min_tier > max_tier:
            return await ctx.send('min_tier must be less than or equal to max_tier!')

        async def random_ship():
            shuffled = random.sample(self.bot.mapping.keys(), len(self.bot.mapping))
            for name in shuffled:
                ship = await Ship.convert(ctx, name)
                if (min_tier <= ship.params['level'] <= max_tier and
                        'old' not in name.lower() and
                        not name.startswith('HSF') and
                        not name.startswith('ARP') and
                        not name.startswith('AL') and
                        not name.endswith(' B') and
                        not name.endswith('Dragon') and
                        not name.endswith('Lima') and
                        name not in ['Alabama ST', 'Arkansas Beta', 'Siliwangi', 'Wukong', 'Bajie'] and
                        (ship.params['group'] != 'demoWithoutStats' if not allow_test_ships else True)):
                    return ship

        ship = await random_ship()
        accepted = {ship.name, ship.short_name}
        for group in SIMILAR_SHIPS:
            if ship.name in group:
                for similar in group:
                    similar_ship = await Ship.convert(ctx, similar)
                    accepted.add(similar_ship.name)
                    accepted.add(similar_ship.short_name)
        checked = [unidecode(ship.lower().replace('-', '').replace('.', '').replace(' ', '')) for ship in accepted]

        fp = io.BytesIO()
        image = Image.open(f'assets/private/ship_bars/{ship.params["index"]}_h.png')
        image.save(fp, 'PNG')
        fp.seek(0)

        embed = discord.Embed(title='Guess the Ship!',
                              description=f'Tiers: `{min_tier}`-`{max_tier}`\n'
                                          f'Test Ships: {"`Enabled`" if allow_test_ships else "`Disabled`"}',
                              color=self.bot.color)
        embed.set_image(url=f'attachment://guess.png')
        embed.set_footer(text='No HSF/ARP/Dragon/AL/B/Lima ships\n'
                              '".", "-", spaces, caps, special chars ignored')

        original = await ctx.send(embed=embed, file=discord.File(fp, filename=f'guess.png'))
        success, message = False, None
        start = datetime.now()

        def check(m):
            return unidecode(m.content.lower().replace('-', '').replace('.', '').replace(' ', '')) in checked

        try:
            message = await self.bot.wait_for('message', timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send(f'Need a hint? It\'s a tier `{ship.params["level"]}`.')
            try:
                message = await self.bot.wait_for('message', timeout=30, check=check)
            except asyncio.TimeoutError:
                await ctx.send(f'Time\'s up. Accepted Answers:\n- ' + '\n- '.join(accepted))
            else:
                success = True
        else:
            success = True

        end = datetime.now()
        time = (end - start).total_seconds()

        async with utils.Transaction(self.bot.db) as conn:
            if success:
                details = await utils.fetch_user(self.bot.db, message.author)
                result = (f'Well done, {message.author.mention}!\n'
                          f'Time taken: `{time:.3f}s`. ')
                if time < details['contours_record']:
                    result += 'A new record!'
                    await conn.execute(f'UPDATE users SET contours_record = {time} WHERE id = {message.author.id}')
                await conn.execute(f'UPDATE users SET contours_played = contours_played + 1 WHERE id = {message.author.id}')
                await ctx.send(result)

            embed.description = f'Answer: `{ship.name}`'
            await original.edit(embed=embed)

    @commands.command(brief='Get user details.')
    async def profile(self, ctx):
        details = await utils.fetch_user(self.bot.db, ctx.author)
        embed = discord.Embed(title='User Details',
                              description=f'UID: {details["id"]}\n'
                                          f'Contours guessed: `{details["contours_played"]}`\n'
                                          f'Contours record: `{details["contours_record"]:3f}s`')
        await ctx.send(embed=embed)

    @commands.command(brief='Fetches contour for ship.')
    async def fc(self, ctx, ship: Ship):
        """
        Fetches contour for ship.
        """
        fp = io.BytesIO()
        image = Image.open(f'assets/private/ship_bars/{ship.params["index"]}_h.png')
        image.save(fp, 'PNG')
        fp.seek(0)

        await ctx.send(file=discord.File(fp, filename=f'contour.png'))

    @commands.command()
    @commands.is_owner()
    async def dump(self, ctx, ship: Ship):
        with open("dump.json", "w") as file:
            json.dump(ship.params, file, ensure_ascii=False, indent=4)

    @commands.command(brief='Inspect tool for Ships.')
    async def inspect(self, ctx, ship: Ship):
        """
        Fetches information about a specific ship.
        """
        embed = discord.Embed(title=f'{ship.name} ({ship.short_name})',
                              description=f'Tier: {ship.params["level"]}\n'
                                          f'Nation: {ship.params["typeinfo"]["nation"]}\n'
                                          f'Class: {ship.params["typeinfo"]["species"]}')
        embed.set_author(icon_url='https://cdn.discordapp.com/attachments/651324664496521225/651332148963442688/logo.png', name=ship.params['name'])

        fp = io.BytesIO()
        image = Image.open(f'assets/private/ship_bars/{ship.params["index"]}_h.png')
        image.save(fp, 'PNG')
        fp.seek(0)
        ship_bar = discord.File(fp, filename=f'ship_bar.png')

        # HULL:
        # health
        # maxSpeed
        # rudderTime
        # turningRadius
        #

        embed.set_thumbnail(url=f'attachment://ship_bar.png')

        await ctx.send(file=ship_bar, embed=embed)

    @commands.command(brief='Historical Data for ships.')
    async def histdata(self, ctx, ship: MapleSyrupShip, region: utils.SetValue(REGIONS) = 'ALL', variable='ALL', start=None, end=None):
        """
        View the historical performance for specified ships over time.

        Uses data from [Suihei Koubou](http://maplesyrup.sweet.coocan.jp/wows/).
        Note that some weeks may have no data due to vacations, and that player-based data is used.
        """
        if region == 'ALL':
            pass

        dates = []
        for row in ship.na.player:
            date = str(row['date'])
            dates.append(datetime(year=int(date[0:4]),
                                  month=int(date[4:6]),
                                  day=int(date[6:8])))
        battles = [row['total'] for row in ship.na.player]

        plt.plot(dates, battles)
        plt.gcf().autofmt_xdate()

        fp = io.BytesIO()
        plt.savefig(fp)
        fp.seek(0)
        plt.close()

        await ctx.send(file=discord.File(fp, filename=f'plot.png'))

        dates_u = []
        for row in ship.na.unit:
            date = str(row['date'])
            dates_u.append(datetime(year=int(date[0:4]),
                                    month=int(date[4:6]),
                                    day=int(date[6:8])))
        battles_u = [row['total'] for row in ship.na.unit]

        plt.plot(dates_u, battles_u)
        plt.gcf().autofmt_xdate()

        fp = io.BytesIO()
        plt.savefig(fp)
        fp.seek(0)
        plt.close()

        await ctx.send(file=discord.File(fp, filename=f'plot_u.png'))

    @commands.command(brief='Pull ENG localization string.')
    async def globalmo(self, ctx, index):
        """
        Pulls ENG localization string from index.
        """
        try:
            await ctx.send(self.bot.globalmo[index])
        except KeyError:
            await ctx.send('No localization entry for this index.')

    # @commands.command()
    # async def apiskills(self, ctx):
    #     """Get a copy of the latest skills data from the WG API!"""
    #
    #     self.skills = wows_api.encyclopedia.crewskills().data
    #     with open('crewskills.json', 'w') as file:
    #         json.dump(self.skills, file, indent=2)
    #     await ctx.channel.send(file=discord.File(open('crewskills.json', 'r'), filename='crewskills.json'),
    #                            content='Captain Skills Saved.')

    @commands.command(hidden=True, brief='Generates minimap timelapse from .wowsreplay file.')
    async def timelapse(self, ctx):
        """
        Generates minimap timelapse from .wowsreplay file.
        """
        # async with ctx.typing():
        #     reader = replay_reader.ReplayReader('/Users/anan/PycharmProjects/replays/20200428_145105_PASC020-Des-Moines-1948_14_Atlantic.wowsreplay')
        #     data = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), reader.get_replay_data)
        #
        #     player_name = data.engine_data["playerName"]
        #     map_name = self.bot.globalmo[f'IDS_{data.engine_data["mapName"].upper()}']
        #     gamemode_name = self.bot.globalmo[f'IDS_GAMEMODE_{data.engine_data["logic"].upper()}_TITLE']
        #     ship_index = data.engine_data["playerVehicle"][:data.engine_data["playerVehicle"].index("-")]
        #     ship_name = self.bot.globalmo[f'IDS_{ship_index.upper()}_FULL']
        #
        #     embed = discord.Embed(title='Processing Replay...',
        #                           description=f'Player Name: `{player_name}`\n'
        #                                       f'Map: `{map_name} ({gamemode_name})`\n'
        #                                       f'Ship: `{ship_name}`')
        #     embed.set_footer(text='This process may take up to a minute.')
        #     await ctx.send(embed=embed)
        #
        # def base_image(map_index):
        #     water = Image.open(f'assets/private/{map_index}/minimap_water.png')
        #     minimap = Image.open(f'assets/private/{map_index}/minimap.png')
        #     water.paste(minimap, (0, 0), minimap)
        #
        #     return water
        #
        # base = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), base_image, data.engine_data['mapName'])
        #
        # with open(f'assets/private/{data.engine_data["mapName"]}/space.settings', 'rb') as f:
        #     tree = etree.parse(f)
        #
        # space_bounds, = tree.xpath('/space.settings/bounds')
        # if space_bounds.attrib:
        #     min_x = int(space_bounds.get('minX'))
        #     min_y = int(space_bounds.get('minY'))
        #     max_x = int(space_bounds.get('maxX'))
        #     max_y = int(space_bounds.get('maxY'))
        # else:
        #     min_x = int(space_bounds.xpath('minX/text()')[0])
        #     min_y = int(space_bounds.xpath('minY/text()')[0])
        #     max_x = int(space_bounds.xpath('maxX/text()')[0])
        #     max_y = int(space_bounds.xpath('maxY/text()')[0])
        #
        # chunk_size_elements = tree.xpath('/space.settings/chunkSize')
        # if chunk_size_elements:
        #     chunk_size = float(chunk_size_elements[0].text)
        # else:
        #     chunk_size = 100.0
        #
        # size_x = len(range(min_x, max_x + 1)) * chunk_size - 4 * chunk_size
        # size_y = len(range(min_y, max_y + 1)) * chunk_size - 4 * chunk_size
        #
        # player = ReplayPlayer('093', data)
        # await self.bot.loop.run_in_executor(ThreadPoolExecutor(), player.play, data.decrypted_data)
        #
        # def create_frame(frame, team, ship_class):
        #     if team == 'ally':
        #         angle = math.degrees(-location.angle) + 90
        #     else:
        #         angle = math.degrees(-location.angle) - 90
        #
        #     icon = Image.open(f'assets/public/ship_icons/icon_{team}_{ship_class}.png')
        #     icon = icon.rotate(angle)
        #     x = int(location.x * base.width / size_x + base.width / 2 - icon.width / 2)
        #     y = int(-location.y * base.height / size_y + base.height / 2 - icon.height / 2)
        #     frame.paste(icon, (x, y), icon)
        #
        # frames = []
        # locations = {location.owner: location for location in list(player.locations.values())[0]}  # used for missing data
        # next_bar = list(player.locations.keys())[0] - 2
        #
        # info = player.get_info()
        # # print(data.engine_data)
        # # print(info)
        # for time, movements in player.locations.items():
        #     if time > next_bar:
        #         next_bar += 2
        #         frame = base.copy()
        #         for owner, location in locations.items():
        #             index = None
        #
        #             for playerId, player in info['players'].items():
        #                 if player['avatarId'] == location.owner:
        #                     for vehicle in data.engine_data['vehicles']:
        #                         if vehicle['id'] == playerId:
        #                             index = self.bot.ship_id[vehicle['shipId']]
        #                             break
        #
        #             c = await ctx.bot.gameparams.execute(f'SELECT value FROM Ship WHERE id = ?', (index,))
        #             params_blob = await c.fetchone()
        #             params = json.loads(params_blob['value'])
        #             team = 'ally' if location.teamId == 1 else 'enemy'
        #             ship_class = params["typeinfo"]["species"]
        #             # name = ctx.bot.globalmo[f'IDS_{params["index"]}_FULL']
        #
        #             await self.bot.loop.run_in_executor(ThreadPoolExecutor(), create_frame, frame, team, ship_class)
        #         frames.append(frame)
        #
        #     for movement in movements:
        #         locations[movement.owner] = movement
        #
        # # fp = io.BytesIO()
        # # frames[0].save(fp, format='GIF', append_images=frames[1:], save_all=True, duration=1, loop=0)
        # # fp.seek(0)
        # with imageio.get_writer(f'assets/private/{ctx.message.id}.mp4', fps=30) as writer:
        #     for frame in frames:
        #         writer.append_data(numpy.array(frame.resize((768, 768), resample=Image.BILINEAR)))
        #
        # await ctx.send(file=discord.File(f'assets/private/{ctx.message.id}.mp4', filename=f'timelapse.mp4'))
        # os.remove(f'assets/private/{ctx.message.id}.mp4')
        pass


def setup(bot):
    bot.add_cog(WoWS(bot))
