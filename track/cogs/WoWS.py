from discord.ext import commands, menus
import discord
import wargaming
from PIL import Image, ImageDraw, ImageFont
from hashids import Hashids
from unidecode import unidecode
import polib
import requests
import aiohttp
from bs4 import BeautifulSoup
import pandas
import seaborn as sns
import matplotlib
from lxml import etree
import imageio
import numpy

import collections
import json
import io
from concurrent.futures import ThreadPoolExecutor
import re
import pickle
from typing import Dict, Tuple, NamedTuple, List, Optional
from datetime import datetime
import asyncio
import sqlite3
import logging
import random
import math
import os

import config
import utils
from replay_unpack.clients.wows import ReplayPlayer


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
VERSION = '0.9.11'
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
                              ('PASC020', 'PASC710'),  # Des Moines, Salem
                              ('PJSB509', 'PJSB018', 'PJSB510'),  # Musashi, Yamato, Shikishima
                              ('PASB012', 'PASB508', 'PASB518', 'PASB517'),  # North Carolina, Alabama, Massachusetts, Florida
                              ('PBSB107', 'PBSB527'),  # King George V, Duke Of York
                              ('PZSC508', 'PRSC508'),  # Irian, Kutuzov
                              ('PRSC606', 'PGSC106'),  # Makarov, Nurnberg
                              ('PJSD025', 'PJSD026', 'PJSD017'),  # Kamikaze, Kamikaze R, Fujin
                              ('PASB018', 'PASB509'),  # Iowa, Missouri
                              ('PFSD108', 'PFSD508'),  # Le Fantasque, Le Terrible
                              ('PVSC507', 'PASC597'),  # Nueve De Julio, Boise
                              ('PZSD106', 'PZSD506', 'PRSD206'),  # Fushun, Anshan, Gnevny
                              ('PFSD110', 'PFSD210'),  # Kleber, Marceau
                              ('PWSD110', 'PWSD610'),  # Halland, Smaland
                              ('PASD008', 'PZSD108'),  # Benson, Hsienyang
                              ('PBSC508', 'PBSC208'),  # Cheshire, Albemarle
                              ('PFSB109', 'PFSB510'),  # Alsace, Bourgogne
                              ('PRSD207', 'PRSD507'),  # Minsk, Leningrad
                              ('PGSD519', 'PGSD110', 'PGSD107'),  # Z-35, Z-44, Leberecht Maass
                              ('PASA110', 'PASA510'),  # Midway, Franklin D. Roosevelt
                              ('PASB006', 'PASB705'),  # New York, Texas
                              ('PRSC108', 'PRSC518'),  # Chapayev, Lazo
                              ('PBSC108', 'PBSC510'),  # Edinburgh, Plymouth
                              ('PGSA518', 'PGSA108')]  # Graf Zeppelin, August von Parseval
WG_LOGO = 'https://cdn.discordapp.com/attachments/651324664496521225/651332148963442688/logo.png'
DEFAULT_GROUPS = ('start', 'peculiar', 'demoWithoutStats', 'earlyAccess', 'special', 'ultimate',
                  'specialUnsellable', 'upgradeableExclusive', 'upgradeable', 'upgradeableUltimate')
GUESS_GROUPS = ('start', 'peculiar', 'special', 'ultimate', 'specialUnsellable',
                'upgradeableExclusive', 'upgradeable', 'upgradeableUltimate')
GUESS_BLOCKED = ('Alabama ST', 'Arkansas Beta', 'Siliwangi', 'Wukong', 'Bajie')
MAPLESYRUP_COLORS = {'na': [0.4901, 0.7647, 0.9607, 1], 'eu': [0.4901, 0.9607, 0.6235, 1],
                     'ru': [0.9607, 0.4039, 0.4039, 1], 'asia': [0.9490, 0.5019, 0.6901, 1]}
MS_GRAPH_TYPES = ('battles', 'winrate', 'damage')
MAPLESYRUP_LABELS = {'battles': 'Battles', 'winrate': 'Winrate (%)', 'damage': 'Damage'}
MAPLESYRUP_MAPPING = {'battles': ('total battles', 'total battles'),
                      'winrate': ('average of rates', 'win'),
                      'damage': ('average of rates', 'damagecaused')}
HISTDATA_CHANNEL = 797620471452663818
TL_GRIDS = 10
TL_SAMPLE_RATE = 0.5
TL_COLORS = {'ally': (70, 224, 163), 'enemy': (248, 64, 0),
             'teamkiller': (252, 130, 180), 'division': (252, 202, 101)}
TL_CAP_COLORS = {'neutral': ((255, 255, 255, 170), (255, 255, 255, 30)),
                 'ally': ((70, 224, 163, 170), (70, 224, 163, 30)),
                 'enemy': ((248, 64, 0, 170), (248, 64, 0, 30))}
WG_FONT_BOLD = ImageFont.truetype('assets/public/Warhelios Bold.ttf')
WG_FONT_BOLD_LARGE = ImageFont.truetype('assets/public/Warhelios Bold.ttf', size=14)
MATCHMAKING: Dict[Tier, TierBound] = {k: TierBound(*v)
                                      for k, v in _matchmaking.items()}
THRESHOLDS: List[ArmorThreshold] = [ArmorThreshold(k, name, TierBound(*bound))
                                    for k, v in _thresholds.items()
                                    for name, bound in v.items()]
BASE_FP: Dict[Tier, float] = {k: v for k, v in _base_fp.items()}
GAMEMODES_ACCEPTED = ['randoms', 'pvp', 'coop', 'co-op', 'pve', 'rank', 'ranked']
GAMEMODES_ALIASES = {'randoms': 'pvp', 'coop': 'pve', 'co-op': 'pve', 'ranked': 'rank'}

# excluded i, I, 1, O, 0 from Base62 to prevent confusion
hashids = Hashids(min_length=3, alphabet='abcdefghjklmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789')
logging.getLogger('aiosqlite').setLevel(logging.CRITICAL)
sns.set(style='dark', font='Trebuchet MS', font_scale=0.9, rc={'axes.facecolor': (0, 0, 0, 0),
                                                               'axes.labelcolor': 'white',
                                                               'figure.figsize': (10.0, 4.5),
                                                               'text.color': 'white',
                                                               'xtick.color': 'white',
                                                               'ytick.color': 'white',
                                                               'xtick.direction': 'in',
                                                               'ytick.direction': 'in',
                                                               'xtick.bottom': True,
                                                               'ytick.left': True,
                                                               'axes.spines.top': False,
                                                               'axes.spines.right': False})
# matplotlib.font_manager._rebuild()
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
            raise utils.SilentError()
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
        upgradeableUltimate - Free EXP ships such as Smaland and Hayate.
        """
        self.one = one
        self.groups = groups
        self.ignored_chars = ignored_chars

    def clean(self, string):
        string = unidecode(string)
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

            cleaned = self.clean(argument)
            cleaned_pretty = self.clean(pretty_name)
            cleaned_short = self.clean(short_name)

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


class ShipStatsMenu(menus.Menu):
    def __init__(self, gamemode, region, player, ship, message_id):
        super().__init__(clear_reactions_after=True)
        self.gamemode = gamemode
        self.region = region
        self.player = player
        self.ship = ship
        self.message_id = message_id
        self.last_page = None

    async def send_initial_message(self, ctx, channel):
        embed = self.generate_embed(self.gamemode)
        self.last_page = embed
        return await ctx.send(embed=embed)

    def format_int(self, num):
        return format(int(num), ',d').replace(',', ' ')

    def format_float(self, num, percent=False):
        if num is not None:
            if percent:
                return '{:.2f}'.format(num) + '%'
            else:
                return '{:.2f}'.format(num)
        else:
            return '-'

    def special_divide(self, numerator, denominator):
        try:
            return numerator / denominator
        except ZeroDivisionError:
            return None

    def get_pr_color(self, pr):
        if pr > 2450:
            return 0xA00DC5
        elif pr > 2100:
            return 0xD042F3
        elif pr > 1750:
            return 0x02C9B3
        elif pr > 1550:
            return 0x318000
        elif pr > 1350:
            return 0x44B300
        elif pr > 1100:
            return 0xFFC71F
        elif pr > 750:
            return 0xFE7903
        else:
            return 0xFE0E00

    def generate_embed(self, group):
        battles = self.ship[group]["battles"]

        embed = discord.Embed(title=f'{self.player["nickname"]}\'s {self.bot.encyclopedia_ships[str(self.ship["ship_id"])]["name"]}',
                              description=f'Battles: `{battles}` '
                                          f'(Last: `{datetime.utcfromtimestamp(self.ship["last_battle_time"]).strftime("%Y-%m-%d %H:%M:%S GMT")}`)\n'
                                          f'WR: `{self.format_float(self.special_divide(100 * self.ship[group]["wins"], battles), percent=True)}` '
                                          f'(`{self.ship[group]["wins"]}`/`{self.ship[group]["losses"]}`/`{self.ship[group]["draws"]}`)\n'
                                          f'SR: `{self.format_float(self.special_divide(100 * self.ship[group]["survived_battles"], battles), percent=True)}` '
                                          f'(`{self.ship[group]["survived_battles"]}`/`{battles - self.ship[group]["survived_battles"]}`)\n'
                                          f'PR: `{int(self.ship[group]["pr"])}`',
                              color=self.get_pr_color(self.ship[group]['pr']),
                              timestamp=discord.utils.snowflake_time(self.message_id))
        embed.set_author(name=f'Random Battles ({self.region.upper()})',
                         url=f'https://{self.region}.wows-numbers.com/player/{self.player["account_id"]},{self.player["nickname"]}/',
                         icon_url='https://media.discordapp.net/attachments/651324664496521225/766209521651286046/595.png')
        embed.set_footer(text='Requested')
        embed.add_field(name='Averages',
                        value=f'<:damage:766222493370286120> Damage: `{self.format_int(self.special_divide(self.ship[group]["damage_dealt"], battles))}`\n'
                              f'<:kills:766222375284506635> Kills: `{self.format_float(self.special_divide(self.ship[group]["frags"], battles))}`\n'
                              f'<:aircraft:766222537759129610> Aircraft: `{self.format_float(self.special_divide(self.ship[group]["planes_killed"], battles))}`\n'
                              f'<:spotting:766759035088535593> Spotting: `{self.format_int(self.special_divide(self.ship[group]["damage_scouting"], battles))}`\n'
                              f'<:potential:766759088574169128> Potential: `{self.format_int(self.special_divide(self.ship[group]["art_agro"] + self.ship[group]["torpedo_agro"], battles))}`')
        embed.add_field(name='Records',
                        value=f'<:damage:766222493370286120> Damage: `{self.format_int(self.ship[group]["max_damage_dealt"])}`\n'
                              f'<:kills:766222375284506635> Kills: `{self.ship[group]["max_frags_battle"]}`\n'
                              f'<:aircraft:766222537759129610> Aircraft: `{self.ship[group]["max_planes_killed"]}`\n'
                              f'<:spotting:766759035088535593> Spotting: `{self.format_int(self.ship[group]["max_damage_scouting"])}`\n'
                              f'<:potential:766759088574169128> Potential: `{self.format_int(self.ship[group]["max_total_agro"])}`')
        embed.add_field(name='Weapon Statistics (Kills/Max/Hitrate)',
                        value=f'Main Battery: (`{self.ship[group]["main_battery"]["frags"]}`/`{self.ship[group]["main_battery"]["max_frags_battle"]}`/`{self.format_float(self.special_divide(100 * self.ship[group]["main_battery"]["hits"], self.ship[group]["main_battery"]["shots"]), percent = True)}`)\n'
                              f'Secondaries: (`{self.ship[group]["second_battery"]["frags"]}`/`{self.ship[group]["second_battery"]["max_frags_battle"]}`/`{self.format_float(self.special_divide(100 * self.ship[group]["second_battery"]["hits"], self.ship[group]["second_battery"]["shots"]), percent = True)}`)\n'
                              f'Torpedoes: (`{self.ship[group]["torpedoes"]["frags"]}`/`{self.ship[group]["torpedoes"]["max_frags_battle"]}`/`{self.format_float(self.special_divide(100 * self.ship[group]["torpedoes"]["hits"], self.ship[group]["torpedoes"]["shots"]), percent = True)}`)\n'
                              f'Aircraft: (`{self.ship[group]["aircraft"]["frags"]}`/`{self.ship[group]["aircraft"]["max_frags_battle"]}`/`-`)\n'
                              f'Ramming: (`{self.ship[group]["ramming"]["frags"]}`/`{self.ship[group]["ramming"]["max_frags_battle"]}`/`-`)',
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

            embed = discord.Embed(title='stats - Help',
                                  description='This command shows you detailed stats of a player\'s ship. '
                                              'PR ([formula](https://wows-numbers.com/personal/rating)) is an aggregate score borrowed from wows-numbers.com. '
                                              'Expected values are synced up with wows-numbers approximately every hour.\n\n'
                                              'Use the reactions below to change the group (All, Solo, Duo, Trio).',
                                  color=self.bot.color)
            for emoji, button in self.buttons.items():
                embed.add_field(name=emoji,
                                value=button.action.__doc__,
                                inline=False)
            await self.message.edit(embed=embed)

    @menus.button('🇦')
    async def main(self, payload):
        """
        The main page. Aggregates the solo, duo, and trio stats.
        """
        self.last_page = None

        await self.message.edit(embed=self.generate_embed(self.gamemode))

    @menus.button('1️⃣')
    async def solo(self, payload):
        """
        Solo stats only.
        """
        self.last_page = None

        await self.message.edit(embed=self.generate_embed(self.gamemode + '_solo'))

    @menus.button('2️⃣')
    async def div2(self, payload):
        """
        Duo stats only.
        """
        self.last_page = None

        await self.message.edit(embed=self.generate_embed(self.gamemode + '_div2'))

    @menus.button('3️⃣')
    async def div3(self, payload):
        """
        Trio stats only.
        """
        self.last_page = None

        await self.message.edit(embed=self.generate_embed(self.gamemode + '_div3'))


class MSMenu(menus.Menu):
    def __init__(self, ship, data, times):
        super().__init__(clear_reactions_after=True)
        self.ship = ship
        self.data = data
        self.times = times
        self.step = WoWS.get_step(self.times)
        self.completed_graphs = {'battles': None, 'winrate': None, 'damage': None}
        self.last_page = None

    async def send_initial_message(self, ctx, channel):
        embed = await self.generate_embed('battles')
        return await ctx.send(embed=embed)

    async def generate_embed(self, graph):
        embed = discord.Embed(title=f'Historical Data for {self.ship.name}',
                              description='Use the reactions below to navigate this interactive embed.\n\n'
                                          'Available graphs:\n'
                                          '- Battles vs. Time (⚔️)\n'
                                          '- Winrate vs. Time (👑)\n'
                                          '- Damage vs. Time (💥)\n',
                              color=self.bot.color)
        if self.completed_graphs[graph] is None:
            fp = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), WoWS.histdata_image,
                                                     self.ship, self.data, graph, self.times, self.step)
            message = await self.bot.get_channel(HISTDATA_CHANNEL).send(file=discord.File(fp, 'graph.png'))
            img_url = message.attachments[0].url
            self.completed_graphs[graph] = img_url
            embed.set_image(url=img_url)
        else:
            embed.set_image(url=self.completed_graphs[graph])
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

            embed = discord.Embed(title='histdata - Help',
                                  description='The historical performance for ships can be viewed with this command.\n'
                                              'To view different metrics, use the reactions below to switch through the available graphs.\n'
                                              'Alternatively, you may use the `histdata graph` subcommand to request a specific graph'
                                              'and skip the interactive session.\n\n'
                                              'Data is unit-based and from [Suihei Koubou](http://maplesyrup.sweet.coocan.jp/wows/).',
                                  color=self.bot.color)
            for emoji, button in self.buttons.items():
                embed.add_field(name=emoji,
                                value=button.action.__doc__,
                                inline=False)
            await self.message.edit(embed=embed)

    @menus.button('⚔️')
    async def battles(self, payload):
        """
        Battles vs. Time graph.
        """
        self.last_page = None

        await self.message.edit(embed=await self.generate_embed('battles'))

    @menus.button('👑')
    async def winrate(self, payload):
        """
        Winrate vs. Time graph.
        """
        self.last_page = None

        await self.message.edit(embed=await self.generate_embed('winrate'))

    @menus.button('💥')
    async def damage(self, payload):
        """
        Damage vs. Time graph.
        """
        self.last_page = None

        await self.message.edit(embed=await self.generate_embed('damage'))


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

        self.bot.histdata_channel = self.bot.get_channel(HISTDATA_CHANNEL)
        self.bot.globalmo = {entry.msgid: entry.msgstr for entry in polib.mofile('assets/private/global.mo')}
        self.skills = self.api.na.encyclopedia.crewskills().data
        self.bot.encyclopedia_ships = {}
        page = 1
        while True:
            try:
                self.bot.encyclopedia_ships = {**self.bot.encyclopedia_ships, **self.api.na.encyclopedia.ships(page_no=page).data}
                page += 1
            except wargaming.exceptions.RequestError:
                break
        # with open('encyclopedia_ships.json', 'w') as fp:
        #     json.dump(self.encyclopedia_ships, fp, indent=4)

        self.wowsnumbers = requests.get('https://api.wows-numbers.com/personal/rating/expected/json/').json()['data']

        self.bot.ships, self.bot.aircraft = [], []
        with sqlite3.connect('assets/private/gameparams.db') as conn:
            c = conn.execute('SELECT * FROM Ship')

            for ship, params_blob in c.fetchall():
                params = pickle.loads(params_blob)
                self.bot.ships.append({'name': params['name'],
                                       'index': params['index'],
                                       'id': params['id'],
                                       'level': params['level'],
                                       'group': params['group'],
                                       'typeinfo': params['typeinfo']})

            c = conn.execute('SELECT * FROM Aircraft')

            for plane, params_blob in c.fetchall():
                params = pickle.loads(params_blob)
                self.bot.aircraft.append({'name': params['name'],
                                          'index': params['index'],
                                          'id': params['id'],
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

    @commands.command(hidden=True, brief='Ship details.')
    async def inspect(self, ctx, *, ship: Ships(one=True)):
        embed = discord.Embed(title=f'{ship.pretty_name} ({ship.short_name})',
                              description=f'Tier: {ship.params["level"]}\n'
                                          f'Nation: {ship.params["typeinfo"]["nation"]}\n'
                                          f'Class: {ship.params["typeinfo"]["species"]}')
        embed.set_author(icon_url=WG_LOGO, name=f'{ship.params["name"]} ({ship.params["index"]})')
        embed.set_image(url=f'attachment://ship_bar.png')

        fp = io.BytesIO()
        image = Image.open(f'assets/private/ship_bars/{ship.params["index"]}_h.png')
        image.save(fp, 'PNG')
        fp.seek(0)

        # HULL: health, maxSpeed, rudderTime, turningRadius

        await ctx.send(file=discord.File(fp, filename=f'ship_bar.png'), embed=embed)

    @commands.command(hidden=True, brief='Loads skill data from WGAPI.')
    @commands.is_owner()
    async def api_skills(self, ctx):
        """
        Loads skill data from WGAPI.
        """
        self.skills = self.api.na.encyclopedia.crewskills().data
        print(json.dumps(self.skills, indent=4))
        await ctx.send('Done.')

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

                    await ctx.send(f'Processing `{len(links)}` new links.')

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
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.user)
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
    @commands.cooldown(rate=1, per=4, type=commands.BucketType.user)
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
    @commands.cooldown(rate=1, per=4, type=commands.BucketType.user)
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
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
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
            return (unidecode(m.content.lower().replace('-', '').replace('.', '').replace(' ', '')) in cleaned and
                    m.channel.id == menu.message.channel.id)

        message = None
        menu = GuessMenu(discord.File(fp, filename='guess.png'), tiers, accepted)
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

        if message is not None and menu.running:
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

    @staticmethod
    def correct_ms_data(ship):
        # API data seems to contain many false points.
        # Values can be observed before the ship is even available.
        # These are usually zero, but sometimes are not.
        # Old versions of ships have strange data values after they are shelved as well.
        # I attempt to fix this by selecting the longest consecutive streak of non-zero
        # values after removing zero values (protecting new releases)
        data = {region: {} for region in ship.regions}

        for region, samples in ship.regions.items():
            leading_zero_flag = False
            current = {}

            for sample in samples:
                string = str(sample['date'])
                unix = datetime(year=int(string[0:4]),
                                month=int(string[4:6]),
                                day=int(string[6:8])).timestamp()

                if sample['data'][('total battles', 'total battles')] != 0:
                    leading_zero_flag = True
                    current[unix] = sample['data']
                else:
                    if leading_zero_flag and len(current) > len(data[region]):
                        data[region] = current

            if leading_zero_flag and len(current) > len(data[region]):
                data[region] = current

        return data

    @staticmethod
    def get_step(times):
        bounds = times[-1] - times[0]
        if bounds > 31536000:  # year
            return 5256576 * ((bounds + 10512000) // 31536000)  # multiple of 2 mo
        elif bounds > 21024000:  # 8 mo
            return 3942000  # 1.5 mo
        elif bounds > 5256000:  # 2 mo
            return 2628000  # 1 mo
        else:
            return 604800  # 1 week

    @staticmethod
    def histdata_image(ship, data, graph, times, step):
        stat = MAPLESYRUP_MAPPING[graph]
        graph_fp, final_fp = io.BytesIO(), io.BytesIO()

        formatted = {'Time': times}
        for region, samples in data.items():
            formatted[region] = [None if time not in samples else samples[time][stat]
                                 for time in times]

        df = pandas.DataFrame(formatted)
        colors = [MAPLESYRUP_COLORS[region] for region in data]
        g = sns.lineplot(x='Time', y=MAPLESYRUP_LABELS[graph], hue='Regions', palette=colors,
                         data=pandas.melt(df, ['Time'], var_name='Regions', value_name=MAPLESYRUP_LABELS[graph]))
        g.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(step))
        dates = [pandas.to_datetime(tm, unit='s').strftime('%Y-%m-%d') for tm in g.get_xticks()]
        g.set_xticklabels(dates)
        if graph.lower() == 'damage':
            g.set_yticklabels([f'{int(num / 1000)}{"k" if int(num) != 0 else ""}' for num in g.get_yticks()])
        g.figure.suptitle(f'{ship.name}: {graph.title()} vs. Time', x=0.525, y=0.95)
        g.figure.subplots_adjust(bottom=0.150, top=0.875, left=0.100, right=0.95)
        g.get_legend().get_frame().set_facecolor((0.1, 0.1, 0.1, 0))
        g.axes.xaxis.labelpad = 11
        g.axes.yaxis.labelpad = 11

        g.figure.savefig(graph_fp, facecolor=(54/255, 57/255, 62/255, 1), edgecolor='none')
        g.figure.clf()
        graph_fp.seek(0)
        graph = Image.open(graph_fp)

        track_logo = Image.open('assets/public/track.png')
        track_logo = track_logo.resize((90, 20))
        graph.paste(track_logo, (900, 420), track_logo)
        graph.save(final_fp, 'PNG')
        final_fp.seek(0)

        return final_fp

    @commands.group(aliases=['maplesyrup', 'ms'], invoke_without_command=True, brief='View a ships\'s historical data.')
    @commands.cooldown(rate=1, per=4, type=commands.BucketType.user)
    async def histdata(self, ctx, *, ship: MSConverter):
        """
        View the historical performance for specified ships over time.

        Available graphs: Battles vs. Time, Winrate vs. Time, Damage vs. Time
        Uses data from [Suihei Koubou](http://maplesyrup.sweet.coocan.jp/wows/).
        Uses unit-based data; i.e. the normal dataset.
        """
        data = self.correct_ms_data(ship)
        times = list(max(data.values(), key=len).keys())

        if len(times) < 4:
            return await ctx.send('Not enough data available for this ship at this time. Try again in the future.')

        await MSMenu(ship, data, times).start(ctx)

    @histdata.command(brief='Pulls specific graph without interactive embed.')
    async def graph(self, ctx, graph: utils.SetValue(MS_GRAPH_TYPES), *, ship: MSConverter):
        """
        Pulls specific graphs without the interactive embed.
        This is the old behavior of the command.
        """
        data = self.correct_ms_data(ship)
        times = list(max(data.values(), key=len).keys())

        if len(times) < 4:
            return await ctx.send('Not enough data available for this ship at this time. Try again in the future.')

        fp = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), self.histdata_image,
                                                 ship, data, graph, times, self.get_step(times))
        await ctx.send(file=discord.File(fp, 'graph.png'))

    @staticmethod
    def get_map_dimensions(map_name):
        with open(f'assets/private/{map_name}/space.settings', 'rb') as f:
            tree = etree.parse(f)

        space_bounds, = tree.xpath('/space.settings/bounds')
        if space_bounds.attrib:
            min_x = int(space_bounds.get('minX'))
            min_y = int(space_bounds.get('minY'))
            max_x = int(space_bounds.get('maxX'))
            max_y = int(space_bounds.get('maxY'))
        else:
            min_x = int(space_bounds.xpath('minX/text()')[0])
            min_y = int(space_bounds.xpath('minY/text()')[0])
            max_x = int(space_bounds.xpath('maxX/text()')[0])
            max_y = int(space_bounds.xpath('maxY/text()')[0])

        chunk_size_elements = tree.xpath('/space.settings/chunkSize')
        if chunk_size_elements:
            chunk_size = float(chunk_size_elements[0].text)
        else:
            chunk_size = 100.0

        return (len(range(min_x, max_x + 1)) * chunk_size - 4 * chunk_size,
                len(range(min_y, max_y + 1)) * chunk_size - 4 * chunk_size)

    @staticmethod
    def create_minimap(map_index):
        water = Image.open(f'assets/private/{map_index}/minimap_water.png')
        land = Image.open(f'assets/private/{map_index}/minimap.png')
        water.paste(land, (0, 0), land)

        overlay = Image.new('RGBA', (water.width, water.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for num in range(1, TL_GRIDS):
            draw.line(((num * water.width // TL_GRIDS), 0,
                       (num * water.width // TL_GRIDS), water.height),
                      fill=(170, 170, 170, 30))
            draw.line((0, (num * water.height // TL_GRIDS),
                       water.width, (num * water.height // TL_GRIDS)),
                      fill=(170, 170, 170, 30))
        del draw

        return Image.alpha_composite(water, overlay)

    @staticmethod
    def draw_caps(width, height, team, base, caps):
        overlay = Image.new('RGBA', (base.width, base.height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        for count, cap in enumerate(caps, start=65):
            x = cap['position'][0] * base.width / width + base.width / 2
            y = -cap['position'][1] * base.height / height + base.height / 2
            r = cap['radius'] * base.height / height

            colors = (TL_CAP_COLORS['neutral'] if cap['teamId'] == -1 else
                      TL_CAP_COLORS['ally'] if cap['teamId'] == team else
                      TL_CAP_COLORS['enemy'])
            overlay_draw.ellipse((x - r, y - r, x + r, y + r), outline=colors[0], fill=colors[1], width=2)

            if cap['teamId'] == -1 or cap['hasInvaders']:
                rings = (((x - 12, y), (x, y - 12), (x + 12, y), (x, y + 12)),
                         ((x - 11, y), (x, y - 11), (x + 11, y), (x, y + 11)),
                         ((x - 10, y), (x, y - 10), (x + 10, y), (x, y + 10)))
            else:
                rings = (((x - 9, y - 9), (x + 9, y - 9), (x + 9, y + 9), (x - 9, y + 9)),
                         ((x - 8, y - 8), (x + 8, y - 8), (x + 8, y + 8), (x - 8, y + 8)))

            for ring in rings:
                overlay_draw.polygon(ring, outline=colors[0], fill=colors[1])

            overlay_draw.text((x - 3, y - 10), text=chr(count), fill=colors[0],
                              font=WG_FONT_BOLD_LARGE, align='center')

        del overlay_draw
        return Image.alpha_composite(base, overlay)

    @commands.command(aliases=['tl'], brief='Generates timelapse video from replay.')
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.user)
    async def timelapse(self, ctx):
        """
        Generates a timelapse of the minimap from a provided .wowsreplay file.

        This is a volatile command, and its usage is limited.
        """
        if not ctx.message.attachments:
            return await ctx.send('No attachment found to use.')
        elif len(ctx.message.attachments) > 1:
            return await ctx.send('Please attach only one file.')
        elif not ctx.message.attachments[0].filename.endswith('.wowsreplay'):
            return await ctx.send('Are you sure this is a WoWS replay file?')

        async with ctx.typing():
            fp = io.BytesIO()
            await ctx.message.attachments[0].save(fp)
            reader = utils.ReplayReader(fp)
            data = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), reader.get_data)
            version = data.engine_data['clientVersionFromExe']
            await ctx.send('Replay parsed.')

        async with ctx.typing():
            try:
                replay_player = ReplayPlayer(version[:version.rfind(',')].replace(',', '_'))
            except RuntimeError as e:
                return await ctx.send(f'{e}. PM owner if bot is outdated.')
            await self.bot.loop.run_in_executor(ThreadPoolExecutor(), replay_player.play, data.decrypted_data)
            info = replay_player.get_info()
            await ctx.send('Encrypted data processed. Building video...')

        map_name = data.engine_data['mapName']
        minimap = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), self.create_minimap, map_name)
        width, height = self.get_map_dimensions(map_name)

        # plane_types = []
        # for details in info['planes'].values():
        #     plane_types.append(next(plane['name'] for plane in self.bot.aircraft if details['gameparams_id'] == plane['id']))
        # print(plane_types)
        #
        # types = set()
        # for aircraft in self.bot.aircraft:
        #     types.add(aircraft['typeinfo']['species'])
        # print(types)

        def draw_priority(player_state):
            player_info = next(player_info for player_info in info['playerInfo']
                               if player_info.avatarId == player_state.avatarId)
            return (0 if not player_state.isAlive else
                    1 if not player_state.isVisible else
                    4 if player_info.isOwner else
                    2 + player_info.isAlly)

        def create_frame(time, states):
            base = minimap.copy()
            base = self.draw_caps(width, height, info['owner_team_id'], base, info['caps_history'][time])
            base_draw = ImageDraw.Draw(base)
            states.sort(key=draw_priority)

            for state in states:
                if state.isVisible is not None:
                    player_info = next(player_info for player_info in info['playerInfo']
                                       if player_info.avatarId == state.avatarId)
                    ship_details = next(ship for ship in self.bot.ships if ship['id'] == player_info.shipParamsId)
                    ship_class = ship_details['typeinfo']['species'].lower()
                    short_name = ctx.bot.globalmo[f'IDS_{ship_details["index"]}']
                    relation = ('self' if player_info.isOwner else 'ally' if player_info.isAlly else 'enemy')
                    angle = 2 * math.degrees(-state.yaw) + (90 if relation == 'enemy' else -90)

                    if not state.isAlive:
                        icon = f'{relation}_sunk_{ship_class}'
                    elif not state.isVisible:
                        icon = f'unspotted_{ship_class}'
                    else:
                        icon = f'{relation}_{ship_class}'

                    icon = Image.open(f'assets/public/ship_icons/{icon}.png')
                    icon = icon.rotate(angle)
                    scaled_x = int(state.x * base.width / width + base.width / 2)
                    scaled_y = int(-state.y * base.height / height + base.height / 2)
                    base.paste(icon, (scaled_x - icon.width // 2, scaled_y - icon.height // 2), icon)

                    if state.isAlive and relation != 'self':
                        size = base_draw.textsize(short_name.upper(), font=WG_FONT_BOLD, spacing=4)
                        base_draw.text((scaled_x - size[0] // 2, scaled_y + 14), text=short_name.upper(), spacing=4,
                                       fill=TL_COLORS[relation], font=WG_FONT_BOLD, align='center')

            del base_draw
            return numpy.array(base)

        with imageio.get_writer(f'assets/temp/{ctx.message.id}.mp4', output_params=['-crf', '10'],
                                fps=60, **{'macro_block_size': None}) as writer:
            for time, player_states in info['timedPlayerStates'].items():
                # print(info['caps_history'][time])
                writer.append_data(await self.bot.loop.run_in_executor(ThreadPoolExecutor(), create_frame, time, player_states))

        await ctx.send(file=discord.File(f'assets/temp/{ctx.message.id}.mp4', filename=f'timelapse.mp4'))
        os.remove(f'assets/temp/{ctx.message.id}.mp4')

    def fetch_players(self, region, search):
        return getattr(self.api, region).account.list(search=search, limit=4)

    def fetch_ship_stats(self, region, player_id, gamemode, ships):
        extra = (['pvp_solo', 'pvp_div2', 'pvp_div3'] if gamemode == 'pvp' else
                 ['pve', 'pve_solo', 'pve_div2', 'pve_div3'] if gamemode == 'pve' else
                 ['rank_solo', 'rank_div2', 'rank_div3'])
        return getattr(self.api, region).ships.stats(account_id=player_id, ship_id=ships, extra=extra).data[str(player_id)]

    def clean(self, string):
        string = unidecode(string)
        for char in (' ', '-', '.'):
            string = string.replace(char, '')
        return string.lower()

    def get_ships(self, search):
        ships = []
        for ship_id, details in self.bot.encyclopedia_ships.items():
            if not details['has_demo_profile']:
                cleaned_search = self.clean(search)
                cleaned_name = self.clean(details['name'])

                if cleaned_search == cleaned_name:
                    return [ship_id]
                elif cleaned_search in cleaned_name:
                    if len(ships) == 10:
                        raise utils.CustomError('>10 ships returned by query. Be more specific.')
                    ships.append(ship_id)

        if not ships:
            raise utils.CustomError(f'No ships found with `{search}`.')
        else:
            return ships

    @commands.command(hidden=True, aliases=['s'], brief='yet another stats command')
    @commands.is_owner()
    async def stats(self, ctx, gamemode: utils.SetValue(GAMEMODES_ACCEPTED) = 'pvp',
                    region: utils.SetValue(REGION_CODES) = None, player=None, *, ship=None):
        if region is None:
            return await ctx.send('`region` is required.')
        elif player is None:
            return await ctx.send('`player` is required.')

        gamemode = GAMEMODES_ALIASES.get(gamemode, gamemode)

        players = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), self.fetch_players, region, player)
        if not players:
            return await ctx.send(f'No players found with `{player}`. Please try again.')
        elif player.lower() != players[0]['nickname'].lower() and len(players) > 1:
            nicknames = '\n- '.join(player['nickname'] for player in players)
            return await ctx.send(f'Many players found with `{player}`. Did you mean:\n- {nicknames}')
        player = players[0]

        ship_stats = await self.bot.loop.run_in_executor(ThreadPoolExecutor(), self.fetch_ship_stats,
                                                         region, player['account_id'], gamemode, self.get_ships(ship))
        if not ship_stats:
            return await ctx.send(f'Didn\'t find any ships in {player["nickname"]}\'s port with `{ship}`.')

        # Sometimes ships that the player does not have are still returned
        # This may only happen on test ships? Observed with Smaland
        # Regardless, fixed by checking for zero battle count.
        ships = []
        for ship in ship_stats:
            battles = 0
            for key, value in ship.items():
                try:
                    battles += value['battles']
                except (KeyError, TypeError):
                    continue
            if battles > 0:
                ships.append(ship)
        if not ships:
            return await ctx.send(f'Didn\'t find any ships in {player["nickname"]}\'s port with battles in the specified gamemode (Randoms by default).')
        elif len(ships) > 1:
            names = ', '.join([f'`{self.bot.encyclopedia_ships[str(ship["ship_id"])]["name"]}`' for ship in ships])
            return await ctx.send(f'Found many ships ({names}). Please refine your search.')

        ship = ships[0]
        # Ranked doesn't seem to have an all-inclusive block, so I created one here
        if gamemode == 'rank':
            ship['rank'] = {}
            for key in ('main_battery', 'second_battery', 'ramming', 'torpedoes', 'aircraft'):
                ship['rank'][key] = {'max_frags_battle': max(ship['rank_solo'][key]['max_frags_battle'],
                                                             ship['rank_div2'][key]['max_frags_battle'],
                                                             ship['rank_div3'][key]['max_frags_battle']),
                                     'frags': (ship['rank_solo'][key]['frags'] +
                                               ship['rank_div2'][key]['frags'] +
                                               ship['rank_div3'][key]['frags'])}
                if key != 'ramming':
                    ship['rank'][key]['hits'] = (ship['rank_solo'][key]['hits'] +
                                                 ship['rank_div2'][key]['hits'] +
                                                 ship['rank_div3'][key]['hits'])
                    ship['rank'][key]['shots'] = (ship['rank_solo'][key]['shots'] +
                                                 ship['rank_div2'][key]['shots'] +
                                                 ship['rank_div3'][key]['shots'])
            for key in ('max_xp', 'max_damage_scouting', 'max_total_agro', 'max_frags_battle', 'max_damage_dealt', 'max_planes_killed'):
                ship['rank'][key] = max(ship['rank_solo'][key],
                                        ship['rank_div2'][key],
                                        ship['rank_div3'][key])
            for key in ('art_agro', 'ships_spotted', 'xp', 'survived_battles', 'dropped_capture_points', 'torpedo_agro',
                        'draws', 'planes_killed', 'battles', 'team_capture_points', 'frags', 'damage_scouting',
                        'capture_points', 'survived_wins', 'wins', 'losses', 'damage_dealt', 'team_dropped_capture_points'):
                ship['rank'][key] = (ship['rank_solo'][key] +
                                     ship['rank_div2'][key] +
                                     ship['rank_div3'][key])

        for key in (gamemode, gamemode + '_solo', gamemode + '_div2', gamemode + '_div3'):
            expected = self.wowsnumbers[str(ship['ship_id'])]
            battles = ship[key]['battles']

            r_dmg = ship[key]['damage_dealt'] / (battles * expected['average_damage_dealt']) if battles != 0 else 0
            r_wins = 100 * ship[key]['wins'] / (battles * expected['win_rate']) if battles != 0 else 0
            r_frags = ship[key]['frags'] / (battles * expected['average_frags']) if battles != 0 else 0

            n_dmg = max(0, (r_dmg - 0.4) / 0.6)
            n_frags = max(0, (r_frags - 0.1) / 0.9)
            n_wins = max(0, (r_wins - 0.7) / 0.3)

            ship[key]['pr'] = 700 * n_dmg + 300 * n_frags + 150 * n_wins

        # print(json.dumps(ship, indent=4))
        # keys for other info such as ship_id, last_battle_time, distance in first dictionary
        menu = ShipStatsMenu(gamemode, region, player, ship, ctx.message.id)
        await menu.start(ctx)


def setup(bot):
    bot.add_cog(WoWS(bot))
