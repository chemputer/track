import json
import struct
import zlib
import pickle
import sqlite3


class GPEncode(json.JSONEncoder):
    def default(self, o):
        try:
            for e in ['Cameras', 'DockCamera', 'damageDistribution']:
                o.__dict__.pop(e, o.__dict__)
            return o.__dict__
        except:
            return {}


print('Opening "Gameparams.data".')
data = []
with open('GameParams.data', 'rb') as f:
    byte = f.read(1)
    while byte:
        data.append(byte[0])
        byte = f.read(1)
print('Deflating data.')
deflate = struct.pack('B' * len(data), *data[::-1])
print('Decompressing data.')
decompressed = zlib.decompress(deflate)
# pickle_data = pickle.loads(decompressed, encoding='MacCyrillic')
pickle_data = pickle.loads(decompressed, encoding='latin1')
print('Converting to dict.')
raw = json.loads(json.dumps(pickle_data, cls=GPEncode, sort_keys=True, indent=4, separators=(',', ': ')))
print('Getting entity types.')
entity_types = []
for key, entity in raw.items():
    entity_type = entity['typeinfo']['type']
    if entity_type not in entity_types:
        entity_types.append(entity_type)
print('Filtering entities into db.')
with sqlite3.connect('../../assets/private/gameparams.db') as conn:
    for entity_type in entity_types:
        conn.execute(f'DROP TABLE IF EXISTS {entity_type}')
        conn.execute(f'CREATE TABLE {entity_type}(id TEXT PRIMARY KEY, value TEXT)')
        for key, entity in raw.items():
            if entity_type == entity['typeinfo']['type']:
                conn.execute(f'INSERT INTO {entity_type} VALUES (?, ?)', [key, pickle.dumps(entity)])
