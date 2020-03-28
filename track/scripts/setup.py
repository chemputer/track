import sqlite3

with sqlite3.connect('../assets/private/track.db') as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS guilds (id INTEGER PRIMARY KEY, prefixes BLOB)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, contours_played INTEGER, contours_record REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS builds (id INTEGER PRIMARY KEY,
                                                       author INTEGER,
                                                       title TEXT,
                                                       description TEXT,
                                                       skills BLOB,
                                                       total INTEGER,
                                                       guild_id INTEGER,
                                                       FOREIGN KEY(guild_id) REFERENCES guilds(id))''')
