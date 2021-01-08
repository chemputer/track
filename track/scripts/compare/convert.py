import json

with open('differences.txt') as fp:
    data = json.load(fp)
    with open('differences.json', 'w') as _fp:
        json.dump(data, _fp, indent=4)
