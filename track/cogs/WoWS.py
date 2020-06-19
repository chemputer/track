from discord.ext import commands, menus
import discord
import wargaming
from PIL import Image
from hashids import Hashids
from unidecode import unidecode
import polib
import aiohttp
from bs4 import BeautifulSoup
import pandas
import seaborn as sns
import matplotlib

import collections
import json
import io
from concurrent.futures import ThreadPoolExecutor
import re
import pickle
from typing import Dict, Tuple, NamedTuple, List
from datetime import datetime
import asyncio
import sqlite3
import logging
import random

import config
import utils


Tier = int


class TierBound(NamedTuple):
    lower: int
    upper: int


class ArmorThreshold(NamedTuple):
    value: int
    name: str
    tiers: TierBound


class Ship(NamedTuple):
    pretty_name: str
    short_name: str
    params: dict


class MSShip(NamedTuple):
    name: str
    regions: dict


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


REGION_CODES = ['na', 'eu', 'ru', 'asia']
VERSION = '0.9.4.1'
MAPLESYRUP_URL = 'http://maplesyrup.sweet.coocan.jp/wows/shipstatswk/'
SKILL_NICKNAMES = {'1': ['bft'], '2': ['bos'], '3': ['em'], '4': ['tae'],
                   '5': ['ha'], '7': ['vig', 'vigi'], '8': ['de'], '9': ['aft'],
                   '10': ['aa', 'plane armor', 'pa'], '11': ['ieb'], '12': ['ce'], '13': ['joat'],
                   '14': ['fp'], '15': ['ss', 'sight stabs'], '16': ['ie'], '17': ['si'],
                   '18': ['pm'], '19': ['ifa'], '20': ['ls'], '21': ['el'],
                   '23': ['ar'], '24': ['ta'], '25': ['se'], '26': ['mfcfsa', 'mfcsa', 'mansec', 'mansecs', 'mansex'],
                   '27': ['maaf', 'maa', 'massive aa'], '28': ['pt'], '29': ['as'], '30': ['sse'],
                   '31': ['dcff', 'dcf', 'direction center'], '32': ['lg'], '33': ['iffhs', 'ifhe'], '34': ['rl', 'rpf', 'rdf']}
SIMILAR_SHIPS: List[Tuple] = [('PASB017', 'PASB510'),  # Montana, Ohio
                              ('PBSB510', 'PBSB110'),  # Thunderer, Conqueror
                              ('PASD021', 'PASD709'),  # Fletcher, Black
                              ('PGSC508', 'PGSC108', 'PGSC518'),  # Prinz Eugen, Hipper, Mainz
                              ('PASC020', 'PASC710'),  # Salem
                              ('PJSB509', 'PJSB018', 'PJSB510'),  # Musashi, Yamato, Shikishima
                              ('PASB518', 'PASB508'),  # Massachusetts, Alabama
                              ('PBSB107', 'PBSB527'),  # King George V, Duke Of York
                              ('PZSC508', 'PRSC508'),  # Irian, Kutuzov
                              ('PRSC606', 'PGSC106'),  # Makarov, Nurnberg
                              ('PJSD025', 'PJSD026', 'PJSD017'),  # Kamikaze, Kamikaze R, Fujin
                              ('PASB018', 'PASB509'),  # Iowa, Missouri
                              ('PFSD108', 'PFSD508'),  # Le Fantasque, Le Terrible
                              ('PVSC507', 'PASC597'),  # Nueve De Julio, Boise
                              ('PZSD106', 'PZSD506'),  # Fushun, Anshan
                              ('PFSD110', 'PFSD210'),  # Kleber, Marceau
                              ('PWSD110', 'PWSD610'),  # Halland, Smaland
                              ('PFSB510', )]  # Bourgogne,
WG_LOGO = 'https://cdn.discordapp.com/attachments/651324664496521225/651332148963442688/logo.png'
DEFAULT_GROUPS = ('start', 'peculiar', 'demoWithoutStats', 'earlyAccess', 'special', 'ultimate',
                  'specialUnsellable', 'upgradeableExclusive', 'upgradeable')
GUESS_GROUPS = ('start', 'peculiar', 'special', 'ultimate',
                'specialUnsellable', 'upgradeableExclusive', 'upgradeable')
GUESS_BLOCKED = ('Alabama ST', 'Arkansas Beta', 'Siliwangi', 'Wukong', 'Bajie')
MAPLESYRUP_COLORS = {'na': [0.4901, 0.7647, 0.9607, 1], 'eu': [0.4901, 0.9607, 0.6235, 1],
                     'ru': [0.9607, 0.4039, 0.4039, 1], 'asia': [0.9490, 0.5019, 0.6901, 1]}
MAPLESYRUP_LABELS = {'battles': 'Battles', 'winrate': 'Winrate (%)', 'damage': 'Damage'}
MATCHMAKING: Dict[Tier, TierBound] = {k: TierBound(*v)
                                      for k, v in _matchmaking.items()}
THRESHOLDS: List[ArmorThreshold] = [ArmorThreshold(k, name, TierBound(*bound))
                                    for k, v in _thresholds.items()
                                    for name, bound in v.items()]
BASE_FP: Dict[Tier, float] = {k: v for k, v in _base_fp.items()}

# excluded i, I, 1, O, 0 from Base62 to prevent confusion
hashids = Hashids(min_length=3, alphabet='abcdefghjklmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789')
logging.getLogger('aiosqlite').setLevel(logging.CRITICAL)
sns.set(style='dark', font='Trebuchet MS', font_scale=0.9, rc={'axes.facecolor': (0, 0, 0, 0),
                                                               'axes.labelcolor': 'white',
                                                               'text.color': 'white',
                                                               'xtick.color': 'white',
                                                               'ytick.color': 'white',
                                                               'xtick.direction': 'in',
                                                               'ytick.direction': 'in',
                                                               'xtick.bottom': True,
                                                               'ytick.left': True,
                                                               'axes.spines.top': False,
                                                               'axes.spines.right': False,
                                                               'figure.figsize': (10.0, 4.5)})
matplotlib.use('agg')

Regions = collections.namedtuple('Regions', REGION_CODES)


class Builds(commands.Converter):
    def __init__(self, one=False, queued=False, not_queued=True):
        self.one = one
        self.queued = queued
        self.not_queued = not_queued

    async def convert(self, ctx, argument):
        c = await ctx.bot.db.execute('SELECT rowid, * FROM builds WHERE guild_id = ?', (ctx.guild.id,))

        builds = []
        async for build in c:
            if argument == hashids.encode(build['rowid']):
                if (self.queued and build['in_queue'] or
                        self.not_queued and not build['in_queue']):
                    return build if self.one else [build]
            elif (argument == f'<@{build["author"]}>' or
                    argument == f'<@!{build["author"]}>' or
                    argument == str(build['author']) or
                    argument.lower() in build['title'].lower()):
                if (self.queued and build['in_queue'] or
                        self.not_queued and not build['in_queue']):
                    builds.append(build)

        if not builds:
            raise utils.CustomError('No builds found.')
        if self.one and len(builds) > 1:
            embed = discord.Embed(title='Multiple builds found...',
                                  description='Please try your command again with a more specific query.',
                                  color=ctx.bot.color)
            pages = menus.MenuPages(source=BuildsPages(embed, builds), clear_reactions_after=True)
            await pages.start(ctx)
        else:
            return builds[0] if self.one else builds


class Ships(commands.Converter):
    def __init__(self, one=False, groups=DEFAULT_GROUPS, ignored_chars=(' ', '-', '.')):
        """
        Groups:

        event - Event ships.
        start - The tier 1 ships.
        peculiar - The ARP and Chinese Dragon ships.
        earlyAccess - Early access ships. Sometimes actually a test ship with stats tracked.
        demoWithoutStats - Test ships, stats not tracked.
        special - Premium ships.
        disabled - Misc. disabled ships, such as Kitakami and Tone...
        ultimate - The tier 10 reward ships.
        clan - Rental ships for CB.
        specialUnsellable - Ships you can't sell, like Flint, Missouri, and Alabama ST.
        preserved - Leftover ships such as the RTS carriers and pre-split RU DDs.
        unavailable - Inaccessible ships such as Operation enemies.
        upgradeableExclusive - Free EXP ships such as Nelson and Alaska.
        upgradeable - Normal tech-tree ships.
        """
        self.one = one
        self.groups = groups
        self.ignored_chars = ignored_chars

    def clean(self, string):
        for char in self.ignored_chars:
            string = string.replace(char, '')
        return string.lower()

    async def fetch(self, ctx, name):
        c = await ctx.bot.gameparams.execute('SELECT value FROM Ship WHERE id = ?', (name,))
        return await c.fetchone()

    async def convert(self, ctx, argument):
        ships = []
        for ship in ctx.bot.ships:
            try:
                pretty_name = ctx.bot.globalmo[f'IDS_{ship["index"]}_FULL']
                short_name = ctx.bot.globalmo[f'IDS_{ship["index"]}']
            except KeyError:
                continue

            cleaned = self.clean(unidecode(argument))
            cleaned_pretty = self.clean(unidecode(pretty_name))
            cleaned_short = self.clean(unidecode(short_name))

            if cleaned == cleaned_pretty or cleaned == cleaned_short:
                if ship['group'] in self.groups:
                    return (Ship(pretty_name, short_name, await self.fetch(ctx, ship['name'])) if self.one
                            else [Ship(pretty_name, short_name, await self.fetch(ctx, ship['name']))])
            elif cleaned in cleaned_pretty or cleaned in cleaned_short:
                # there are old versions of some ships left in the game code
                # will only include them in the results if user requests it
                if ('old' in cleaned_pretty or 'old' in cleaned_short) and 'old' not in cleaned:
                    continue

                if len(ships) == 5:
                    raise utils.CustomError('>5 ships returned by query. Be more specific.')
                if ship['group'] in self.groups:
                    ships.append(Ship(pretty_name, short_name, await self.fetch(ctx, ship['name'])))

        if not ships:
            raise utils.CustomError('No ships found.')
        elif self.one and len(ships) > 1:
            raise utils.CustomError('Multiple ships found. Retry with one of the following:\n' +
                                    '\n'.join([ship.pretty_name for ship in ships]))
        else:
            return ships[0] if self.one else ships


class MSConverter(commands.Converter):
    def __init__(self,  ignored_chars=(' ', '-', '.')):
        self.ignored_chars = ignored_chars

    def clean(self, string):
        for char in self.ignored_chars:
            string = string.replace(char, '')
        return string.lower()

    async def get_data(self, ctx, name, regions):
        data = {}
        for region in regions:
            c = await ctx.bot.maplesyrup.execute(f'SELECT * FROM "{region}_{name}"')
            data[region] = [sample async for sample in c]

        return MSShip(name, data)

    async def convert(self, ctx, argument):
        ships = []
        for name, regions in ctx.bot.ms_ships.items():
            cleaned_arg = self.clean(argument)
            cleaned_name = self.clean(name)
            if cleaned_arg == cleaned_name:
                return await self.get_data(ctx, name, regions)
            elif cleaned_arg in cleaned_name:
                if 'old' in cleaned_name and 'old' not in cleaned_arg:
                    continue

                if len(ships) == 5:
                    raise utils.CustomError('>5 ships returned by query. Be more specific.')
                if '[' not in name:
                    ships.append((name, regions))

        if not ships:
            raise utils.CustomError('No ships found.')
        elif len(ships) > 1:
            raise utils.CustomError('Multiple ships found. Retry with one of the following:\n' +
                                    '\n'.join([ship[0] for ship in ships]))
        else:
            ship = ships.pop()
            return await self.get_data(ctx, ship[0], ship[1])


class BuildsPages(menus.ListPageSource):
    def __init__(self, embed, builds):
        super().__init__(builds, per_page=7)
        self.embed = embed

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        embed = self.embed.copy()
        embed.add_field(name=f'Results ({menu.current_page + 1}/{self.get_max_pages()})',
                        value='\n'.join([f'`{count + 1}.`   **{build["title"]}**\n'
                                         f'`by`   <@{build["author"]}> (ID: {hashids.encode(build["rowid"])})'
                                         for count, build in enumerate(entries, start=offset)]))
        return embed


class HEMenu(menus.Menu):
    def __init__(self, ship, main_batteries, secondaries, initial_page, signals, de, bft):
        super().__init__(clear_reactions_after=True)
        self.ship = ship
        self.main_batteries = main_batteries
        self.secondaries = secondaries
        self.current = initial_page - 1
        self.pages = len(main_batteries) + len(secondaries)
        self.signals = signals
        self.de = de
        self.bft = bft
        self.last_page = None

    @staticmethod
    def toggle(var):
        if var:
            return '<:toggleon1:719882432056393799><:toggleon2:719882432911900803>'
        else:
            return '<:toggleoff1:719882434036105236><:toggleoff2:719882431901204542>'

    async def send_initial_message(self, ctx, channel):
        embed = self.generate_embed()
        self.last_page = embed
        return await ctx.send(embed=embed)

    def generate_embed(self):
        if self.current < len(self.main_batteries):
            upgrade = list(self.main_batteries.keys())[self.current]
            details = self.main_batteries[upgrade]
        else:
            upgrade = list(self.secondaries.keys())[self.current - len(self.main_batteries)]
            details = self.secondaries[upgrade]
        embed = discord.Embed(title=self.bot.globalmo[f'IDS_{upgrade.upper()}'],
                              description=f'Data extracted from WoWS {VERSION}.\n'
                                          'Use the reactions to cycle through pages and toggle the fire chance signals, '
                                          'Demolition Expert, and Basic Firing Training.',
                              color=self.bot.color)
        embed.set_author(icon_url=WG_LOGO, name=f'{self.ship.pretty_name}\'s HE ({self.current + 1}/{self.pages})')
        # embed.set_thumbnail(url='https://media.discordapp.net/attachments/651324664496521225/651331492596809739/ammo_he_2x.png')
        # thumbnail creates prettier embed but causes jarring updates
        embed.set_footer(text='Fire chance calculation uses same-tier BB with DCM1 & FP, and E(t) calculation uses a 30% hitrate. '
                              'If you can\'t see the reactions (bot is missing permissions), use the optional parameters of this command.')

        embed.add_field(name='Configuration',
                        value=f'{self.toggle(self.signals)} Fire signals (🎏)\n'
                              f'{self.toggle(self.de)} Demolition Expert (🔥)\n'
                              f'{self.toggle(self.bft)} Basic Fire Training (📈)')

        for identifier, data in details.items():
            ammo_params = data['ammo_params']
            turrets = data['turrets']

            tier = self.ship.params['level']
            pen = ammo_params['alphaPiercingHE']
            fire_chance = ammo_params['burnProb']
            diameter = ammo_params['bulletDiametr']
            barrels = 0
            for turret in turrets:
                barrels += turret['numBarrels']
            reload = turrets[0]['shotDelay']
            species = turrets[0]['typeinfo']['species']

            bypassed = []
            for threshold in THRESHOLDS:
                if int(pen) < threshold.value <= int(pen * 1.25):
                    matchmaking = MATCHMAKING[tier]
                    if (matchmaking.lower <= threshold.tiers.lower <= matchmaking.upper or
                            matchmaking.lower <= threshold.tiers.upper <= matchmaking.upper):
                        bypassed.append(threshold)

            if bypassed:
                thresholds = ('IFHE bypasses:\n- ' +
                              '\n- '.join([f'{threshold.name} `[{threshold.value}mm]`' for threshold in bypassed]) +
                              '\n')
            else:
                thresholds = f'IFHE bypasses no notable armor thresholds at Tier {tier}.\n'

            if tier == 1 or tier == 2:
                fires = 'Fire insight unavailable for T1 & T2.'
            else:
                if self.signals:
                    signals_bonus = 0.02 if diameter > 0.160 else 0.01
                else:
                    signals_bonus = 0

                if self.de:
                    de_bonus = 0.02
                else:
                    de_bonus = 0

                if self.bft:
                    if species == 'Main':
                        bft_bonus = 0.9 if diameter <= 0.139 else 1
                    else:
                        bft_bonus = 0.9
                else:
                    bft_bonus = 1

                reduction = BASE_FP[tier] * 0.95 * 0.9
                base = reduction * (fire_chance + signals_bonus + de_bonus)
                ifhe = reduction * (0.5 * fire_chance + signals_bonus + de_bonus)
                fires = ('Configured Fire Chance (no IFHE & IFHE):\n'
                         f'`{base * 100:.2f}%` -> `{ifhe * 100:.2f}%`\n'
                         'Configured E(t) of fire (no IFHE & IFHE):\n'
                         f'`{(reload * bft_bonus) / base / barrels / 0.3:.2f}s` -> `{(reload * bft_bonus) / ifhe / barrels / 0.3:.2f}s`')

            embed.add_field(name='Details' if species == 'Main' else self.bot.globalmo[f'IDS_{ammo_params["name"].upper()}'],
                            value=f'Alpha Damage: `{ammo_params["alphaDamage"]}`\n'
                                  f'Base Pen: `{int(pen)} mm`\n'
                                  f'IFHE Pen: `{int(pen * 1.25)} mm`\n'
                                  f'Base Fire Chance: `{fire_chance * 100:.1f}%`\n' +
                                  thresholds + fires,
                            inline=False)

        return embed

    @menus.button('⏹️', position=menus.Last(1))
    async def end(self, payload):
        """
        Stops the interactive session.
        """
        self.stop()

    @menus.button('❓', position=menus.Last(0))
    async def info(self, payload):
        """
        Toggle the help page.
        """
        if self.last_page is not None:
            await self.message.edit(embed=self.last_page)
            self.last_page = None
        else:
            self.last_page = self.message.embeds[0]

            embed = discord.Embed(title='HE - Help',
                                  description='This command shows you information about the given ship\'s HE. '
                                              'E(t) is the expected time to get a fire.\n\n'
                                              'Use the reactions below to change the configuration.',
                                  color=self.bot.color)
            for emoji, button in self.buttons.items():
                embed.add_field(name=emoji,
                                value=button.action.__doc__,
                                inline=False)
            await self.message.edit(embed=embed)

    @menus.button('◀️')
    async def left(self, payload):
        """
        Move page to the left, cycling through gun options (Main Battery HE) and Hulls (Secondaries with HE) that the ship has.
        """
        self.last_page = None
        if not self.current:
            return

        self.current = self.current - 1
        await self.message.edit(embed=self.generate_embed())

    @menus.button('▶️')
    async def right(self, payload):
        """
        Move page to the right, cycling through gun options (Main Battery HE) and Hulls (Secondaries with HE) that the ship has.
        """
        self.last_page = None
        if self.current == self.pages - 1:
            return

        self.current = self.current + 1
        await self.message.edit(embed=self.generate_embed())

    @menus.button('🎏')
    async def signals(self, payload):
        """
        Toggle fire signals.
        """
        self.last_page = None

        self.signals = not self.signals
        await self.message.edit(embed=self.generate_embed())

    @menus.button('🔥')
    async def de(self, payload):
        """
        Toggle Demolition Expert.
        """
        self.last_page = None

        self.de = not self.de
        await self.message.edit(embed=self.generate_embed())

    @menus.button('📈')
    async def bft(self, payload):
        """
        Toggle Basic Fire Training.
        """
        self.last_page = None

        self.bft = not self.bft
        await self.message.edit(embed=self.generate_embed())


class APMenu(menus.Menu):
    def __init__(self, ship, main_batteries, initial_page):
        super().__init__(clear_reactions_after=True)
        self.ship = ship
        self.main_batteries = main_batteries
        self.current = initial_page - 1
        self.pages = len(main_batteries)
        self.last_page = None

    async def send_initial_message(self, ctx, channel):
        embed = self.generate_embed()
        self.last_page = embed
        return await ctx.send(embed=embed)

    def generate_embed(self):
        upgrade = list(self.main_batteries.keys())[self.current]
        ammo_params = self.main_batteries[upgrade]

        embed = discord.Embed(title=self.bot.globalmo[f'IDS_{upgrade.upper()}'],
                              description=f'Data extracted from WoWS {VERSION}.\n'
                                          'Use the reactions to cycle through pages.',
                              color=self.bot.color)
        embed.set_author(icon_url=WG_LOGO, name=f'{self.ship.pretty_name}\'s AP ({self.current + 1}/{self.pages})')

        embed.add_field(name='Details',
                        value=f'Alpha Damage: `{int(ammo_params["alphaDamage"])}`\n'
                              f'Diameter: `{int(ammo_params["bulletDiametr"] * 1000)}mm`\n'
                              f'Overmatch: `{int(ammo_params["bulletDiametr"] * 1000 / 14.3)}mm`\n'
                              f'Ricochet Angles: `{ammo_params["bulletRicochetAt"]}°`-`{ammo_params["bulletAlwaysRicochetAt"]}°`\n'
                              f'Initial Shell Velocity: `{ammo_params["bulletSpeed"]}m/s`\n'
                              f'Detonator Threshold: `{ammo_params["bulletDetonatorThreshold"]}mm`\n'
                              f'Detonator Fuse Time: `{ammo_params["bulletDetonator"]}s`\n')

        embed.add_field(name='More Characteristics',
                        value=f'Mass: `{ammo_params["bulletMass"]}kg`\n'
                              f'Air Drag: `{ammo_params["bulletAirDrag"]}`\n'
                              f'Krupp: `{ammo_params["bulletKrupp"]}`')

        return embed

    @menus.button('⏹️', position=menus.Last(1))
    async def end(self, payload):
        """
        Stops the interactive session.
        """
        self.stop()

    @menus.button('❓', position=menus.Last(0))
    async def info(self, payload):
        """
        Toggle the help page.
        """
        if self.last_page is not None:
            await self.message.edit(embed=self.last_page)
            self.last_page = None
        else:
            self.last_page = self.message.embeds[0]

            embed = discord.Embed(title='AP - Help',
                                  description='This command shows you information about the given ship\'s AP.\n\n'
                                              'Use the reactions below to change the configuration.',
                                  color=self.bot.color)
            for emoji, button in self.buttons.items():
                embed.add_field(name=emoji,
                                value=button.action.__doc__,
                                inline=False)
            await self.message.edit(embed=embed)

    @menus.button('◀️')
    async def left(self, payload):
        """
        Move page to the left, cycling through gun options that the ship has.
        """
        self.last_page = None
        if not self.current:
            return

        self.current = self.current - 1
        await self.message.edit(embed=self.generate_embed())

    @menus.button('▶️')
    async def right(self, payload):
        """
        Move page to the right, cycling through gun options that the ship has.
        """
        self.last_page = None
        if self.current == self.pages - 1:
            return

        self.current = self.current + 1
        await self.message.edit(embed=self.generate_embed())


class GuessMenu(menus.Menu):
    def __init__(self, file, tiers, accepted):
        super().__init__(timeout=30.0, clear_reactions_after=True)
        self.file = file
        self.tiers = tiers
        self.accepted = accepted
        self.running = True

    async def send_initial_message(self, ctx, channel):
        embed = discord.Embed(title='Guess the Ship!',
                              description=f'Tiers: `{str(self.tiers)[1:-1]}`\n',
                              color=self.bot.color)
        embed.set_image(url=f'attachment://guess.png')
        embed.set_footer(text='Stuck? React with ⏹️ to give up.')
        return await ctx.send(file=self.file, embed=embed)

    @menus.button('⏹️')
    async def end(self, payload):
        """
        Stops the interactive session.
        """
        if self.running:
            await self.ctx.send(f'Accepted Answers:\n- ' + '\n- '.join(self.accepted))
        self.running = False
        self.stop()


class WoWS(commands.Cog, name='Wows'):
    """
    World of Warships commands.
    """

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '🚢'
        self.display_name = 'WoWS'

        self.api = Regions(na=wargaming.WoWS(config.wg_token, region='na', language='en'),
                           eu=wargaming.WoWS(config.wg_token, region='eu', language='en'),
                           ru=wargaming.WoWS(config.wg_token, region='ru', language='en'),
                           asia=wargaming.WoWS(config.wg_token, region='asia', language='en'))

        self.skills = self.api.na.encyclopedia.crewskills().data
        self.bot.globalmo = {entry.msgid: entry.msgstr for entry in polib.mofile('assets/private/global.mo')}

        self.bot.ships = []
        with sqlite3.connect('assets/private/gameparams.db') as conn:
            c = conn.execute('SELECT * FROM Ship')

            for ship, params_blob in c.fetchall():
                params = pickle.loads(params_blob)
                self.bot.ships.append({'name': params['name'],
                                       'index': params['index'],
                                       'level': params['level'],
                                       'group': params['group'],
                                       'typeinfo': params['typeinfo']})

        self.bot.ms_ships = {}
        with sqlite3.connect('assets/private/maplesyrup.db') as conn:
            c = conn.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')
            tables = [table[0] for table in c.fetchall()]  # flatten

            for table in tables:
                if table != 'record':
                    split = table.index('_')
                    region = table[:split]
                    ship = table[split + 1:]
                    if ship not in self.bot.ms_ships:
                        self.bot.ms_ships[ship] = {'na': False, 'eu': False, 'ru': False, 'asia': False}
                    self.bot.ms_ships[ship][region] = True

    @commands.command(hidden=True, brief='Link your WG account!')
    async def link(self, ctx, region: utils.SetValue(REGION_CODES)):
        """
        Link your WG account!

        Make sure you use the right region.
        """
        await ctx.send('WIP, placeholder')

    @commands.command(hidden=True, brief='Pulls global.mo localization string.')
    async def globalmo(self, ctx, index):
        """
        Pulls global.mo localization string given an index.
        """
        try:
            await ctx.send(self.bot.globalmo[index])
        except KeyError:
            await ctx.send('No localization entry for this index.')

    @commands.command(hidden=True, brief='Loads skill data from WGAPI.')
    @commands.is_owner()
    async def api_skills(self, ctx):
        """
        Loads skill data from WGAPI.
        """
        self.skills = self.api.na.encyclopedia.crewskills().data
        print(json.dumps(self.skills, indent=4))
        await ctx.send('Done.')

    @commands.command(hidden=True, brief='Ship details.')
    async def inspect(self, ctx, *, ship: Ships(one=True)):
        embed = discord.Embed(title=f'{ship.pretty_name} ({ship.short_name})',
                              description=f'Tier: {ship.params["level"]}\n'
                                          f'Nation: {ship.params["typeinfo"]["nation"]}\n'
                                          f'Class: {ship.params["typeinfo"]["species"]}')
        embed.set_author(icon_url=WG_LOGO, name=ship.params['name'])
        embed.set_image(url=f'attachment://ship_bar.png')

        fp = io.BytesIO()
        image = Image.open(f'assets/private/ship_bars/{ship.params["index"]}_h.png')
        image.save(fp, 'PNG')
        fp.seek(0)

        # HULL: health, maxSpeed, rudderTime, turningRadius

        await ctx.send(file=discord.File(fp, filename=f'ship_bar.png'), embed=embed)

    @commands.command(hidden=True, brief='Updates maplesyrup data.')
    @commands.is_owner()
    async def update_ms(self, ctx):
        pattern = re.compile(r'(\w+)/\w+_(\w+)')

        async with utils.Transaction(self.bot.maplesyrup) as conn:
            await conn.execute('CREATE TABLE IF NOT EXISTS record (id TEXT PRIMARY KEY)')

            async with aiohttp.ClientSession() as cs:
                async with cs.get(MAPLESYRUP_URL) as index:
                    soup = BeautifulSoup(await index.text(), 'html.parser')
                    table = soup.find('table')

                    links = []
                    for row in table.findAll("tr")[1:]:
                        for cell in row:
                            link = cell.find('a')
                            if link is not None and link != -1:
                                match = re.search(pattern, link['href'])
                                try:
                                    await conn.execute('INSERT INTO record VALUES (?)', (f'{match[1]}_{match[2]}',))
                                    links.append({'region': match[1], 'date': int(match[2]), 'link': link['href'][2:]})
                                except sqlite3.IntegrityError:
                                    pass

                    if not links:
                        return await ctx.send('No new data to process.')

                    await utils.confirm(ctx, f'`{len(links)}` to process. Continue?')

                    for count, link in enumerate(links, start=1):
                        print(f'Processing link {count} of {len(links)}.')

                        async with cs.get(MAPLESYRUP_URL + link['link']) as html:
                            dataframe = pandas.read_html(await html.text())[0]

                            for index, series in dataframe.iterrows():
                                dict_ver = series.to_dict()
                                name = link['region'] + '_' + dict_ver[('name', 'name')]
                                await conn.execute(f'CREATE TABLE IF NOT EXISTS "{name}" (date INTEGER PRIMARY KEY, data BLOB)')
                                await conn.execute(f'INSERT INTO "{name}" VALUES (?, ?)', (link['date'], pickle.dumps(dict_ver)))
                        await asyncio.sleep(0.25)

        await ctx.send('Done.')

    def convert_skill(self, string):
        for skill, data in self.skills.items():
            if string == data['name'].lower():
                return skill
        for skill, nicks in SKILL_NICKNAMES.items():
            if string in nicks:
                return skill
        raise utils.CustomError(f'Unable to resolve `{string}` as a captain skill.')

    def skills_image(self, skills):
        fp = io.BytesIO()
        image = Image.new('RGBA', (680 + 120, 360), (0, 0, 0, 0))

        def paste(_image, _icon, _x, _y):
            _image.paste(_icon, (_x, _y), _icon)

        for skill, data in self.skills.items():
            pattern = re.compile('(icon_perk).+(?=_)')
            name = re.search(pattern, data['icon'])[0]
            x = 30 + data['type_id'] * 80 + (data['type_id'] // 2) * 40
            y = 30 + (data['tier'] - 1) * 80

            paste(image, Image.open(f'assets/private/big/{name}.png'), x, y)
            if skill not in skills:
                paste(image, Image.open(f'assets/private/big/{name}_inactive.png'), x, y)
            else:
                paste(image, Image.open(f'assets/public/checkmark.png'), x + 65, y + 5)

        image.save(fp, 'PNG')
        fp.seek(0)
        return fp

    def build_embed(self, build):
        embed = discord.Embed(title=build['title'],
                              description=build['description'],
                              color=self.bot.color,
                              timestamp=discord.utils.snowflake_time(build['id']))
        embed.add_field(name='Skills',
                        value=', '.join([self.skills[skill]['name'] for skill in build['skills']]))
        embed.add_field(name='Author',
                        value=f'<@{build["author"]}>')
        embed.set_footer(text=f'ID: {hashids.encode(build["rowid"])}\n{build["total"]}/19 points')
        embed.set_image(url='attachment://build.png')

        return embed

    @commands.group(aliases=['build'], invoke_without_command=True, brief='Create and share builds.')
    @commands.guild_only()
    async def builds(self, ctx, *, build: Builds(one=True)):
        """
        Create and share builds.

        Not using a subcommand searches for builds that match the query.
        Queries search by ID, title, and author.
        """
        image = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), self.skills_image, build['skills'])
        await ctx.send(file=discord.File(image, filename='build.png'), embed=self.build_embed(build))

    @builds.command(aliases=['add'], brief='Create a new build.')
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    @commands.guild_only()
    async def create(self, ctx, title: utils.Max(75), captain_skills: utils.lowercase, description='No description given.'):
        """
        Creates a new build for the current server.

        - Note that you must wrap parameters with spaces with quotation marks, "like this".
        - To use quotation marks inside parameters, escape them with `\\"`.
        - `captain_skills` accepts a captain builder link from the WoWS website or comma-separated skill names/abbreviations.

        Example usages:
        `build create "BB Tank Build" https://worldofwarships.eu/en/content/commanders-skills/?skills=2,3,12,14,17,23,28&ship=Battleship`

        `build create "9 point CV build" "AS, Improved Engines, AIRCRAFT armor, se" "These skills are \\"necessary\\" for every CV build."`
        """
        pattern = re.compile(r'(?<=\?skills=)[\d,]+(?=&)')
        match = re.search(pattern, captain_skills)
        if match is None:
            skills = [self.convert_skill(entry.strip()) for entry in captain_skills.split(',')]
        else:
            skills = match[0].split(',')
            for skill in skills:
                if skill not in self.skills:
                    return await ctx.send('Link malformed? Verify that it is copy-pasted correctly and retry.')

        if len(skills) != len(set(skills)):
            return await ctx.send('Duplicate skills detected.')

        total, tiers = 0, [False, False, False, False]
        for skill in skills:
            tier = self.skills[skill]['tier']
            tiers[tier - 1] = True
            total += tier

        try:
            if total > 19:
                return await ctx.send(f'This build costs `{total}` points! The max is 19.')
            elif tiers.index(False) < tiers.index(True, tiers.index(False)):
                return await ctx.send('You cannot skip skill tiers.')
        except ValueError:
            pass

        async with utils.Transaction(self.bot.db) as conn:
            builds_channel = self.bot.guild_options[ctx.guild.id]['builds_channel']

            in_queue = 0 if builds_channel is None or ctx.channel.id == builds_channel else 1
            build = {'id': ctx.message.id, 'author': ctx.author.id, 'title': title, 'description': description,
                     'skills': pickle.dumps(skills), 'total': total, 'guild_id': ctx.guild.id, 'in_queue': in_queue}

            c = await conn.execute('INSERT INTO builds VALUES (?, ?, ?, ?, ?, ?, ?, ?)', list(build.values()))
            build['rowid'] = c.lastrowid
            hash_id = hashids.encode(c.lastrowid)

            if not in_queue:
                await ctx.send(f'Thank you for submission. ID: `{hash_id}`')
            else:
                await ctx.send(f'Your submission has been sent to this server\'s queue. ID: `{hash_id}`')

                channel = self.bot.get_channel(builds_channel)
                message = (f'New build from {ctx.author.mention} (ID: `{hash_id}`)\n'
                           f'Approve with `build approve {hash_id}`, reject with `build reject {hash_id}`')
                build['skills'] = skills  # bootleg solution tbh
                image = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), self.skills_image, skills)
                await channel.send(message, file=discord.File(image, filename=f'build.png'), embed=self.build_embed(build))

    @builds.command(aliases=['remove'], brief='Delete a build.')
    @commands.guild_only()
    async def delete(self, ctx, *, build: Builds(one=True, queued=True)):
        """
        Deletes a build.

        Administrators can delete any builds.
        """
        if build['author'] != ctx.author.id and not ctx.author.guild_permissions.administrator:
            return await ctx.send('You cannot delete a build that is not yours!')

        async with utils.Transaction(self.bot.db) as conn:
            await utils.confirm(ctx, f'\"{build["title"]}\" will be deleted.')

            await conn.execute(f'DELETE FROM builds WHERE id = ?', (build["id"],))
            await ctx.send('Build deleted.')

    @builds.command(aliases=['approve'], brief='Accepts a build.')
    @commands.guild_only()
    async def accept(self, ctx, *, build: Builds(one=True, queued=True, not_queued=False)):
        """
        Accepts a build in queue.
        """
        builds_channel = self.bot.guild_options[ctx.guild.id]['builds_channel']
        if builds_channel is None:
            return await ctx.send('This command may only be used when approve-only mode is active.')
        elif builds_channel != ctx.channel.id:
            return await ctx.send('This command must be used in the designated channel.')

        async with utils.Transaction(self.bot.db) as conn:
            await conn.execute(f'UPDATE builds SET in_queue = 0 WHERE id = ?', (build['id'],))
            await ctx.send('Build accepted.')

    @builds.command(aliases=['deny'], brief='Rejects a build.')
    @commands.guild_only()
    async def reject(self, ctx, *, build: Builds(one=True, queued=True, not_queued=False)):
        """
        Rejects a build in queue.
        """
        builds_channel = self.bot.guild_options[ctx.guild.id]['builds_channel']
        if builds_channel is None:
            return await ctx.send('This command may only be used when approve-only mode is active.')
        elif builds_channel != ctx.channel.id:
            return await ctx.send('This command must be used in the designated channel.')

        async with utils.Transaction(self.bot.db) as conn:
            await conn.execute(f'DELETE FROM builds WHERE id = ?', (build['id'],))
            await ctx.send('Build rejected.')

    @builds.command(brief='List builds in this server.')
    @commands.guild_only()
    async def list(self, ctx):
        c = await self.bot.db.execute('SELECT rowid, * FROM builds WHERE guild_id = ?', (ctx.guild.id,))
        builds = [build async for build in c if not build['in_queue']]
        if not builds:
            return await ctx.send('This server has no builds.')

        embed = discord.Embed(title=f'{ctx.guild.name}\'s Builds',
                              color=ctx.bot.color)
        pages = menus.MenuPages(source=BuildsPages(embed, builds), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.command(aliases=['skillbuilder'], hidden=True, brief='Gives a link to the Commander Skill Builder.')
    async def csb(self, ctx):
        """
        Gives a link to the Commander Skill Builder.
        """
        await ctx.send('https://worldofwarships.com/en/content/captains-skills/')

    @commands.command(aliases=['ifhe'], brief='Detailed info about a ship\'s HE.')
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    async def he(self, ctx, *, ship: Ships(one=True), signals=False, de=False, bft=False, page=1):
        """
        Calculates a ship's HE characteristics, including fire chance and penetration.

        - E(t) is the expected time to obtain a fire.
        - 🎏, 🔥, and 📈 correspond to Fire Signals, Demolition Expert, and Basic Fire Training respectively.
        """
        async def get_he(master, module):
            for turret, turret_params in ship.params[module].items():
                try:
                    for ammo in turret_params['ammoList']:
                        c = await self.bot.gameparams.execute(f'SELECT value FROM Projectile WHERE id = ?', (ammo,))
                        ammo_params = await c.fetchone()

                        if ammo_params['ammoType'] == 'HE':
                            if turret_params['typeinfo']['species'] == 'Main':
                                identifier = ammo_params['name']
                            else:
                                identifier = turret_params['id']

                            if upgrade not in master:
                                master[upgrade] = {identifier: {'ammo_params': ammo_params, 'turrets': [turret_params]}}
                            elif identifier in master[upgrade]:
                                master[upgrade][identifier]['turrets'].append(turret_params)
                            else:
                                master[upgrade][identifier] = {'ammo_params': ammo_params, 'turrets': [turret_params]}

                except (KeyError, TypeError):
                    pass

        main_batteries, secondaries = {}, {}
        for upgrade, upgrade_params in ship.params['ShipUpgradeInfo'].items():
            try:
                if upgrade_params['ucType'] == '_Artillery':
                    await get_he(main_batteries, upgrade_params['components']['artillery'][0])
                elif upgrade_params['ucType'] == '_Hull':
                    try:
                        await get_he(secondaries, upgrade_params['components']['atba'][0])
                    except IndexError:  # Hulls without secondaries
                        pass
            except TypeError:
                pass

        if not main_batteries and not secondaries:
            return await ctx.send('This ship has no HE.')
        if not 1 <= page <= len(main_batteries) + len(secondaries):
            return await ctx.send('Invalid page number.')

        await HEMenu(ship, main_batteries, secondaries, page, signals, de, bft).start(ctx)

    @commands.command(brief='Detailed info about a ship\'s AP.')
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    async def ap(self, ctx, *, ship: Ships(one=True), page=1):
        """
        Calculates a ship's AP characteristics.
        """
        main_batteries = {}
        for upgrade, upgrade_params in ship.params['ShipUpgradeInfo'].items():
            try:
                if upgrade_params['ucType'] == '_Artillery':
                    module = upgrade_params['components']['artillery'][0]
                    for turret, turret_params in ship.params[module].items():
                        try:
                            for ammo in turret_params['ammoList']:
                                c = await self.bot.gameparams.execute(f'SELECT value FROM Projectile WHERE id = ?', (ammo,))
                                ammo_params = await c.fetchone()

                                if ammo_params['ammoType'] == 'AP':
                                    main_batteries[upgrade] = ammo_params
                        except (KeyError, TypeError):
                            pass
            except TypeError:
                pass

        if not main_batteries:
            return await ctx.send('This ship has no AP.')
        if not 1 <= page <= len(main_batteries):
            return await ctx.send('Invalid page number.')

        await APMenu(ship, main_batteries, page).start(ctx)

    @commands.command(aliases=['armor'], brief='Lists notable armor thresholds.')
    async def thresholds(self, ctx):
        """
        Lists notable armor thresholds.
        """
        embed = discord.Embed(title='Armor Thresholds',
                              description='Not comprehensive, but the most notable thresholds are included.',
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

    @commands.command(aliases=['contours'], brief='Who\'s that ~~pokemon~~ ship?')
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    async def guess(self, ctx, tiers: commands.Greedy[int] = (6, 7, 8, 9, 10)):
        """
        A guessing minigame inspired by "Who's that pokemon?".

        Similar ships are accepted together as answers.
        Furthermore, some ships are removed from the list, including:
        - High School Fleet, Azur Lane, Arpeggio of Blue Steel collaboration ships
        - Eastern/Southern Dragon
        - Black Friday Ships
        - Tachibana/Diana Lima, Alabama ST/Arkansas Beta
        - Siliwangi, Wukong, Bajie
        """
        for tier in tiers:
            if tier < 1 or tier > 10:
                return await ctx.send('You cannot add a tier not within 1-10.')
        if len(tiers) != len(set(tiers)):
            return await ctx.send('You cannot have duplicate tiers.')

        copy = self.bot.ships.copy()
        random.shuffle(copy)
        answer = None
        for ship in copy:
            try:
                name = self.bot.globalmo[f'IDS_{ship["index"]}_FULL']
            except KeyError:
                continue

            if (ship['group'] in GUESS_GROUPS and ship['level'] in tiers and
                    not(name.startswith('HSF') or name.startswith('ARP') or name.startswith('AL')) and
                    not(name.endswith(' B') or name.endswith('Dragon') or name.endswith('Lima')) and
                    name not in GUESS_BLOCKED):
                answer = ship
                break

        accepted = {self.bot.globalmo[f'IDS_{answer["index"]}'],
                    self.bot.globalmo[f'IDS_{answer["index"]}_FULL']}
        for group in SIMILAR_SHIPS:
            if answer['index'] in group:
                for ship in group:
                    accepted.add(self.bot.globalmo[f'IDS_{ship}'])
                    accepted.add(self.bot.globalmo[f'IDS_{ship}_FULL'])
        cleaned = [unidecode(ship.lower().replace('-', '').replace('.', '').replace(' ', ''))
                   for ship in accepted]

        fp = io.BytesIO()
        image = Image.open(f'assets/private/ship_bars/{answer["index"]}_h.png')
        image.save(fp, 'PNG')
        fp.seek(0)

        def check(m):
            return unidecode(m.content.lower().replace('-', '').replace('.', '').replace(' ', '')) in cleaned

        message = None
        menu = GuessMenu(discord.File(fp, filename=f'guess.png'), tiers, accepted)
        await menu.start(ctx)
        start = datetime.now()
        try:
            message = await self.bot.wait_for('message', timeout=20, check=check)
        except asyncio.TimeoutError:
            if menu.running:
                if len(tiers) != 1:
                    await ctx.send(f'Need a hint? It\'s a tier `{answer["level"]}`.')
                else:
                    nation = self.bot.globalmo[f'IDS_{answer["typeinfo"]["nation"].upper()}']
                    await ctx.send(f'Need a hint? It\'s a ship from `{nation}`.')

                try:
                    message = await self.bot.wait_for('message', timeout=10, check=check)
                except asyncio.TimeoutError:
                    if menu.running:
                        menu.running = False
                        return await ctx.send(f'Time\'s up. Accepted Answers:\n- ' + '\n- '.join(accepted))
                    return

        if message is not None:
            menu.stop()
            time = (datetime.now() - start).total_seconds()
            data = await utils.fetch_user(self.bot.db, message.author.id)

            result = f'Well done, {message.author.mention}!\nTime taken: `{time:.3f}s`. '
            if data['contours_record'] is None or time < data['contours_record']:
                result += 'A new record!'
                data['contours_record'] = time
            data['contours_played'] += 1

            await ctx.send(result)
            async with utils.Transaction(self.bot.db) as conn:
                await conn.execute('UPDATE users SET data = ? WHERE id = ?', (pickle.dumps(data), message.author.id))

    @commands.command(aliases=['maplesyrup'], brief='View ships\'s historical data.')
    async def histdata(self, ctx, graph: utils.SetValue(['battles', 'winrate', 'damage']), *, ship: MSConverter):
        """
        View the historical performance for specified ships over time.

        Uses data from [Suihei Koubou](http://maplesyrup.sweet.coocan.jp/wows/).
        Uses unit-based data; i.e. the normal dataset.
        """
        data = {region: {} for region in ship.regions}
        for region, samples in ship.regions.items():
            leading_zero_flag = False
            for sample in samples:
                string = str(sample['date'])
                unix = datetime(year=int(string[0:4]),
                                month=int(string[4:6]),
                                day=int(string[6:8])).timestamp()

                observation = None
                if graph == 'battles':
                    observation = sample['data'][('total battles', 'total battles')]
                elif graph == 'winrate':
                    observation = sample['data'][('average of rates', 'win')]
                elif graph == 'damage':
                    observation = sample['data'][('average of rates', 'damagecaused')] / 1000
                print(observation)

                if observation is not None and (observation != 0 or leading_zero_flag):
                    data[region][unix] = observation
                    leading_zero_flag = True

        def generate_image():
            fp = io.BytesIO()

            times = list(max(data.values(), key=len).keys())

            if len(times) < 4:
                raise utils.CustomError('Not enough data for this ship at this time. Try again in the future.')

            if times[-1] - times[0] > 31536000:
                step = 5256576 * ((times[-1] - times[0]) // 31536000)
            elif times[-1] - times[0] > 5256000:
                step = 3285000
            else:
                step = 604800

            formatted = {'Time': times}
            for region, points in data.items():
                formatted[region] = [None if time not in points else points[time]
                                     for time in times]

            df = pandas.DataFrame(formatted)
            colors = [MAPLESYRUP_COLORS[region] for region in data]
            g = sns.lineplot(x='Time', y=MAPLESYRUP_LABELS[graph], hue='Regions', palette=colors,
                             data=pandas.melt(df, ['Time'], var_name='Regions', value_name=MAPLESYRUP_LABELS[graph]))
            g.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(step))
            dates = [pandas.to_datetime(tm, unit='s').strftime('%Y-%m-%d') for tm in g.get_xticks()]
            g.set_xticklabels(dates)
            if graph.lower() == 'damage':
                g.set_yticklabels([f'{int(num)}{"k" if int(num) != 0 else ""}' for num in g.get_yticks()])
            g.figure.suptitle(f'{ship.name}: {graph.title()} vs. Time', x=0.5625, y=0.95)
            g.figure.subplots_adjust(bottom=0.150, top=0.875, left=0.100, right=0.95)
            g.get_legend().get_frame().set_facecolor((0.1, 0.1, 0.1, 0))
            g.axes.xaxis.labelpad = 11
            g.axes.yaxis.labelpad = 11

            g.figure.savefig(fp, facecolor=(0, 0, 0, 0), edgecolor='none')
            g.figure.clf()
            fp.seek(0)
            return fp

        image = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), generate_image)
        await ctx.send(file=discord.File(image, 'graph.png'))


def setup(bot):
    bot.add_cog(WoWS(bot))
