from discord.ext import commands
import discord

import polib
from unidecode import unidecode
import wargaming
from PIL import Image
import matplotlib.pyplot as plt

import random
import io
import pickle
import json
from datetime import datetime
import urllib.parse
import sqlite3
import difflib
from typing import Dict, Tuple, NamedTuple, List
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

import config
import utils


# gets rid of annoying logs for expected missing tables
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
# Used in E(x) calculations for setting fires
_base_fp = {3: 0.033, 4: 0.1, 5: 0.166, 6: 0.233, 7: 0.3, 8: 0.366, 9: 0.433, 10: 0.5}


REGIONS = ['na', 'eu', 'ru', 'asia']
VERSION = '0.9.2'
SIMILAR_SHIPS: List[Tuple] = [('Montana', 'Ohio'),
                              ('Thunderer', 'Conqueror'),
                              ('Fletcher', 'Black'),
                              ('Prinz Eugen', 'Admiral Hipper'),
                              ('Des Moines', 'Salem'),
                              ('Musashi', 'Yamato'),
                              ('Massachusetts', 'Alabama'),
                              ('King George V', 'Duke of York'),
                              ('Irian', 'Mikhail Kutuzov'),
                              ('Admiral Makarov', 'Nurnberg'),
                              ('Kamikaze', 'Kamikaze R', 'Fujin'),
                              ('Iowa', 'Missouri'),
                              ('Le Fantasque', 'Le Terrible'),
                              ('Nueve de Julio', 'Boise'),
                              ('Fushun', 'Anshan')]
MATCHMAKING: Dict[Tier, TierBound] = {k: TierBound(*v)
                                      for k, v in _matchmaking.items()}
THRESHOLDS: List[ArmorThreshold] = [ArmorThreshold(k, name, TierBound(*bound))
                                    for k, v in _thresholds.items()
                                    for name, bound in v.items()]
BASE_FP: Dict[Tier, float] = {k: v for k, v in _base_fp.items()}

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
            if argument.lower() == name.lower():  # edge cases: Erie is in Algerie etc.
                matches = {name: index}
                break
            elif argument.lower() in name.lower():
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
        params_blob = await c.fetchone()
        params = json.loads(params_blob['value'])
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
            if argument.lower() == ship.lower():  # edge cases: Erie is in Algerie etc.
                matches = [ship]
                break
            elif argument.lower() in ship.lower():
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
    id: int
    author: int
    title: str
    description: str
    skills: list
    total: int
    guild_id: int

    @classmethod
    async def convert(cls, ctx, argument):
        c = await ctx.bot.db.execute(f'SELECT * FROM builds WHERE guild_id = \'{ctx.guild.id}\'')
        builds = await c.fetchall()

        results = []
        for build in builds:
            if argument == str(build['id']):
                return [build]
            elif (argument.startswith('<@!') and argument.endswith('>') and argument[3:-1] == str(build['author']) or
                  argument.startswith('<@') and argument.endswith('>') and argument[2:-1] == str(build['author']) or
                  argument == str(build['author']) or
                  argument.lower() in build['title'].lower()):
                results.append(build)

        if len(results) == 0:
            raise commands.UserInputError('No builds found.')
        elif len(results) > 1:
            embed = discord.Embed(title='Builds',
                                  description=f'Query: `{argument}`\n' +
                                              '\n'.join([f'**{build["title"]}**\n'
                                                         f'by <@{build["author"]}> (ID: {build["id"]})' for build in results]),
                                  color=ctx.bot.color)
            await ctx.send(embed=embed)
            raise commands.CommandNotFound()  # raise error EH will ignore

        build = results.pop()
        return Build(id=build['id'], author=build['author'], title=build['title'],
                     description=build['description'], skills=pickle.loads(build['skills']),
                     total=build['total'], guild_id=build['guild_id'])


class WoWS(commands.Cog):
    """
    For your favorite pixelbote collecting game!
    """

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '🚢'

        self.api = wargaming.WoWS(config.wg_token, region='na', language='en')

        self.bot.globalmo = {entry.msgid: entry.msgstr for entry in polib.mofile('assets/private/global.mo')}
        self.bot.mapping = {}  # maps name to index
        with sqlite3.connect('assets/private/GameParams.db') as conn:
            c = conn.execute('SELECT * FROM Ship')

            for ship, params_blob in c:
                params = json.loads(params_blob)
                if params['group'] not in ['disabled', 'unavailable', 'clan']:
                    # the full name of legacy versions of ships contains the date they were removed
                    # instead of (old) or (OLD), making it hard to remember, so in this case the short name is used
                    # unidecode converts unicode into ASCII equivalent (such as ö to o) for easy of access
                    index = params['index']
                    if 'old' in self.bot.globalmo[f'IDS_{index}'].lower():
                        self.bot.mapping[unidecode(self.bot.globalmo[f'IDS_{index}'])] = ship
                    else:
                        self.bot.mapping[unidecode(self.bot.globalmo[f'IDS_{index}_FULL'])] = ship

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
    async def link(self, ctx):
        """
        Link your WG account!
        Make sure you use the right region.
        """
        await ctx.send('https://api.worldoftanks.com/wot/auth/login/?application_id=1c70cec91640dd9f5a11271e74c5137e'
                       f'&redirect_uri={urllib.parse.quote("trackpad.glitch.me/link?id=", safe="")}{ctx.author.id}')

    @commands.command(brief='Tutorial on how to dodge CV attacks')
    async def counterCV(self, ctx):
        """
        Gives you a link to an advanced tutorial on mitigating damage taken from CV attacks.
        """
        embed = discord.Embed(title='Helpful Links',
                              description='[Throttle Jockeying](https://www.youtube.com/watch?v=dQw4w9WgXcQ)'  # rickroll
                                          '[CV Reticules Overview](https://www.youtube.com/watch?v=d1YBv2mWll0)')  # jebaited
        await ctx.send(embed=embed)

    @commands.command(aliases=['ifhe'], brief='Calculates HE pen & IFHE.')
    async def he(self, ctx, *, ship: Ship):
        """
        Calculates HE penetration of target ship before/after taking IFHE.
        A recommendation is also given based on common armor thresholds.
        """

        # Main Battery
        he_ammo = set()
        for upgrade, upgrade_params in ship.params['ShipUpgradeInfo'].items():
            if isinstance(upgrade_params, dict) and upgrade_params['ucType'] == '_Artillery':
                module = upgrade_params['components']['artillery'][0]
                for turret, turret_params in ship.params[module].items():
                    try:
                        for ammo in turret_params['ammoList']:
                            c = await self.bot.gameparams.execute(f'SELECT value FROM Projectile WHERE id = \'{ammo}\'')
                            ammo_params_blob = await c.fetchone()
                            ammo_params = json.loads(ammo_params_blob[0])

                            if ammo_params['ammoType'] == 'HE':
                                # the upper() is necessary because WG made a typo with Kamikaze & her sisters
                                # (PJUA451_120_45_Type_Ha_TRUE_KAMIKAZE vs. PJUA451_120_45_TYPE_HA_TRUE_KAMIKAZE)
                                he_ammo.add((self.bot.globalmo[f'IDS_{upgrade.upper()}'], ammo_params['alphaPiercingHE']))
                    except (KeyError, TypeError):
                        pass

        if len(he_ammo) == 0:
            return await ctx.send(f'`{ship.name}` doesn\'t have main battery HE!')

        embed = discord.Embed(title=ship.name,
                              description=f'Data extracted from WoWS {VERSION}.',
                              color=self.bot.color)

        for upgrade, pen in he_ammo:
            base_threshold_flag = False
            bypassed = []
            for threshold in THRESHOLDS:
                if threshold.value > int(pen):
                    base_threshold_flag = True

                if base_threshold_flag:
                    if threshold.value > int(pen * 1.25):
                        break
                    else:
                        matchmaking = MATCHMAKING[ship.params['level']]
                        if (matchmaking.lower <= threshold.tiers.lower <= matchmaking.upper or
                                matchmaking.lower <= threshold.tiers.upper <= matchmaking.upper):
                            bypassed.append(threshold)

            result = (f'Penetrates up to `{int(pen)} mm` by default.\n'
                      f'With IFHE, up to `{int(pen * 1.25)} mm`.')
            if bypassed:
                result += 'This bypasses:\n- ' + '\n- '.join([f'{threshold.name} `[{threshold.value}mm]`' for threshold in bypassed])
            else:
                result += f'IFHE bypasses no notable armor thresholds at Tier {ship.params["level"]}.'

            embed.add_field(name=upgrade, value=result, inline=False)

        embed.set_author(icon_url='https://cdn.discordapp.com/attachments/651324664496521225/651332148963442688/logo.png', name=ship.params['name'])
        embed.set_thumbnail(url='https://media.discordapp.net/attachments/651324664496521225/651331492596809739/ammo_he_2x.png')
        await ctx.send(embed=embed)

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
    async def create(self, ctx, title: utils.Max(50), captain_skills: utils.lowercase, description='No description given.'):
        """
        Adds a build.
        - The order of your skills is kept!
        - Make sure you wrap multiple word parameters with quotation marks "like this"
        - Shorthand abbreviations, some slang, and indexes are accepted for captain skills. You can even mix them!
        - Split individual skills with commas!
        - Use `\\"` to represent `"` when using quotes inside a parameter!
        For a more detailed visualization of the build template, see `template`.
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

        await ctx.bot.db.execute(f'INSERT INTO builds VALUES (?, ?, ?, ?, ?, ?, ?)',
                                 (ctx.message.id, ctx.author.id, title, description,
                                  pickle.dumps(captain_skills), total, ctx.guild.id))
        await ctx.bot.db.commit()
        await ctx.send(f'Thank you for your submission! ID: `{ctx.message.id}`')

    @builds.command(aliases=['remove'], brief='Delete a build.')
    async def delete(self, ctx, build: Build):
        """
        Delete a build you own.
        - Users with administrator may also delete any build.
        """
        if build.author != ctx.author.id and not ctx.author.guild_permissions.administrator:
            return await ctx.send('You cannot delete a build that is not yours!')

        await utils.confirm(ctx, f'\"{build.title}\" will be deleted.')

        await self.bot.db.execute(f'DELETE FROM builds WHERE id = ?', (build.id,))
        await self.bot.db.commit()
        await ctx.send('Build deleted.')

    # @builds.command(brief='Edit a build.')
    # async def edit(self, ctx, build, parameter: utils.SetValue(['title', 'captain_skills', 'description']), new_value):
    #     """
    #     Edit a build you own.
    #     """
    #     pass

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
        checked = [unidecode(ship.lower().replace('-', '').replace('.', '')) for ship in accepted]

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
                              '".", "-", caps, special chars ignored')

        original = await ctx.send(embed=embed, file=discord.File(fp, filename=f'guess.png'))
        success, message = False, None
        start = datetime.now()

        def check(m):
            return unidecode(m.content.lower().replace('-', '').replace('.', '')) in checked

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

        if success:
            details = await utils.fetch_user(self.bot.db, message.author)
            result = (f'Well done, {message.author.mention}!\n'
                      f'Time taken: `{time:.3f}s`. ')
            if time < details['contours_record']:
                result += 'A new record!'
                await self.bot.db.execute(f'UPDATE users SET contours_record = {time} WHERE id = {message.author.id}')
            await self.bot.db.execute(f'UPDATE users SET contours_played = contours_played + 1 WHERE id = {message.author.id}')
            await self.bot.db.commit()
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
        image = Image.open(f'assets/public/ship_bars/{ship.params["index"]}_h.png')
        image.save(fp, 'PNG')
        fp.seek(0)

        await ctx.send(file=discord.File(fp, filename=f'contour.png'))

    @commands.command(brief='Inspect tool for Ships.')
    async def inspect(self, ctx, ship: Ship):
        """
        Fetches information about a specific ship.
        """
        embed = discord.Embed(title=f'{ship.name} ({ship.short_name})',
                              description=f'')
        embed.set_author(icon_url='https://cdn.discordapp.com/attachments/651324664496521225/651332148963442688/logo.png', name=ship.params['name'])

        fp = io.BytesIO()
        image = Image.open(f'assets/public/ship_bars/{ship.params["index"]}_h.png')
        image.save(fp, 'PNG')
        fp.seek(0)
        ship_bar = discord.File(fp, filename=f'ship_bar.png')

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

    # @commands.command()
    # async def apiskills(self, ctx):
    #     """Get a copy of the latest skills data from the WG API!"""
    #
    #     self.skills = wows_api.encyclopedia.crewskills().data
    #     with open('crewskills.json', 'w') as file:
    #         json.dump(self.skills, file, indent=2)
    #     await ctx.channel.send(file=discord.File(open('crewskills.json', 'r'), filename='crewskills.json'),
    #                            content='Captain Skills Saved.')


def setup(bot):
    bot.add_cog(WoWS(bot))
