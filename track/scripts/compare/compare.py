import json
import struct
import zlib
import pickle

import deepdiff

VER_1 = '0_9_4_ST1.data'
VER_2 = '0_9_4_ST2.data'


class GPEncode(json.JSONEncoder):
    def default(self, o):  # pylint: disable=E0202
        def has_dict(o):
            try:
                o.__dict__
                return True
            except AttributeError:
                return False

        if has_dict(o):
            t = o.__dict__
            for key in t:
                if isinstance(t[key], str):
                    try:
                        t[key].decode('utf8')
                    except:
                        try:
                            t[key] = t[key].decode('MacCyrillic')
                        except:
                            try:
                                t[key] = t[key].encode('hex')
                            except:
                                pass
            return o.__dict__


def process_file(file):
    print(f'Starting processing of {file}.')
    data = []
    with open(file, 'rb') as f:
        byte = f.read(1)
        while byte:
            data.append(byte[0])
            byte = f.read(1)
    print('Deflating data.')
    deflate = struct.pack('B' * len(data), *data[::-1])
    print('Decompressing data.')
    decompressed = zlib.decompress(deflate)
    pickle_data = pickle.loads(decompressed, encoding='MacCyrillic')
    print('Converting to dict.')
    raw = json.loads(json.dumps(pickle_data, cls=GPEncode, sort_keys=True, indent=4, separators=(',', ': ')))
    print('Getting entity types.')
    entity_types = []
    for key, entity in raw.items():
        entity_type = entity['typeinfo']['type']
        if entity_type not in entity_types:
            entity_types.append(entity_type)
    print('Restructuring by entity type.')
    grouped = {}
    for entity_type in entity_types:
        grouped[entity_type] = {}
        for key, entity in raw.items():
            if entity_type == entity['typeinfo']['type']:
                grouped[entity_type][key] = entity
    return grouped


data_1, data_2 = process_file(VER_1), process_file(VER_2)
print('Comparing files.')
ddiff = deepdiff.DeepDiff(data_1, data_2, ignore_order=True, report_repetition=True)
print('Writing to file.')
with open('differences.txt', 'w') as file:
    file.write(ddiff.to_json())
