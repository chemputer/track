import sqlite3

with sqlite3.connect('../../assets/private/rush.db') as conn:
    conn.execute('DROP TABLE IF EXISTS puzzles')
    conn.execute('CREATE TABLE puzzles (moves INTEGER, setup TEXT, states INTEGER)')
    with open('rush.txt') as fp:
        for line in fp:
            moves, setup, states = line.split(' ')
            conn.execute('INSERT INTO puzzles VALUES (?, ?, ?)', (int(moves), setup, int(states)))
