import requests
from bs4 import BeautifulSoup
import pandas
import sqlite3
import time

UNIT_BASED_BASE_URL = 'http://maplesyrup.sweet.coocan.jp/wows/shipstatswk/'
PLAYER_BASED_BASE_URL = 'http://maplesyrup.sweet.coocan.jp/wows/ranking/'
PAST_PLAYER_BASED_BASE_URL = 'http://maplesyrup.sweet.coocan.jp/wows/ranking/pastrecords/'


def scrape_player_based(base_url):
    response = requests.get(base_url + 'index.html')
    soup = BeautifulSoup(response.text, 'html.parser')
    # sample link: ./20200229/asia_week/average_ship.html
    links = [tag["href"][2:]
             for tag in soup.findAll('a', href=lambda s: 'average_ship' in s)
             if 'week' in tag["href"][2:]]

    for link_count, link in enumerate(links, 1):
        print(f'Processing link {link_count} of {len(links)}... ({base_url + link})')

        table = pandas.read_html(base_url + link)[0]
        columns = [full[1] for full in list(table.columns)]

        for row in table.values:
            if '_u.html' in link:
                break  # ignore unit-based, because we have a separate link for that

            data = {columns[count]: value for count, value in enumerate(row)}
            region = link[link.index('/') + 1:link.index('_')]
            name = region + '_' + data['name']
            date = int(link[:link.index('/')])

            conn.execute(f'''CREATE TABLE IF NOT EXISTS "{name}" (date INTEGER PRIMARY KEY, nation TEXT, class TEXT, 
                tier INT, prem TEXT, players INT, total battles INT, battles REAL, win REAL, draw REAL, lose REAL, 
                exp INT, damagecaused INT, warshipdestroyed REAL, aircraftdestoryed REAL, basecapture REAL, basedefense REAL, 
                survived REAL, "kill /death" REAL, agrodamage INT, spotdamage INT, hitratio REAL)''')
            try:
                conn.execute(f'''INSERT INTO "{name}" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (date, data.get('nation'), data.get('class'), data.get('tier'), data.get('prem'),
                              data.get('players'), data.get('total battles'), data.get('battles'), data.get('win'), data.get('draw'),
                              data.get('lose'), data.get('exp'), data.get('damagecaused'), data.get('warshipdestroyed'),
                              data.get('aircraftdestoryed'), data.get('basecapture'), data.get('basedefense'), data.get('survived'),
                              data.get('kill /death'), data.get('agrodamage'), data.get('spotdamage'), data.get('hitratio')))
            except sqlite3.IntegrityError:  # date already exists
                continue


def scrape_unit_based(base_url):
    response = requests.get(base_url + 'index.html')
    soup = BeautifulSoup(response.text, 'html.parser')
    # sample link: ./svr/asia/ship_20200229.html
    links = [tag["href"][2:]
             for tag in soup.findAll('a', href=lambda s: 'ship' in s)]

    for link_count, link in enumerate(links, 1):
        print(f'Processing link {link_count} of {len(links)}... ({base_url + link})')

        table = pandas.read_html(base_url + link)[0]
        columns = [full[1] for full in list(table.columns)]

        for row in table.values:
            data = {columns[count]: value for count, value in enumerate(row)}
            region = link[4:link.index('/', 4)]
            name = region + '_' + data['name'] + '_u'
            date = int(link[link.index('ship_') + 5:link.index('.html')])

            conn.execute(f'''CREATE TABLE IF NOT EXISTS "{name}" (date INTEGER PRIMARY KEY, nation TEXT, class TEXT, 
                tier INT, prem TEXT, players INT, "total battles" INT, battles REAL, win REAL, draw REAL, lose REAL, 
                exp INT, damagecaused INT, warshipdestroyed REAL, aircraftdestoryed REAL, basecapture REAL, basedefense REAL, 
                survived REAL, "kill /death" REAL, agrodamage INT, spotdamage INT, hitratio REAL)''')
            try:
                conn.execute(f'''INSERT INTO "{name}" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (date, data.get('nation'), data.get('class'), data.get('tier'), data.get('prem'),
                              data.get('players'), data.get('total battles'), data.get('battles'), data.get('win'), data.get('draw'),
                              data.get('lose'), data.get('exp'), data.get('damagecaused'), data.get('warshipdestroyed'),
                              data.get('aircraftdestoryed'), data.get('basecapture'), data.get('basedefense'), data.get('survived'),
                              data.get('kill /death'), data.get('agrodamage'), data.get('spotdamage'), data.get('hitratio')))
            except sqlite3.IntegrityError:  # date already exists
                continue


with sqlite3.connect('../../assets/private/maplesyrup.db') as conn:
    scrape_unit_based(UNIT_BASED_BASE_URL)
    time.sleep(20)
    scrape_player_based(PLAYER_BASED_BASE_URL)
    scrape_player_based(PAST_PLAYER_BASED_BASE_URL)
