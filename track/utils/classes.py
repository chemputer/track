from discord.ext import commands
from Crypto.Cipher import Blowfish

import struct
import json
import zlib
from typing import NamedTuple
import io

REPLAY_SIGNATURE = b'\x12\x32\x34\x11'
BLOWFISH_KEY = b''.join([b'\x29', b'\xB7', b'\xC9', b'\x09', b'\x38', b'\x3F', b'\x84', b'\x88',
                         b'\xFA', b'\x98', b'\xEC', b'\x4E', b'\x13', b'\x19', b'\x79', b'\xFB'])


class SilentError(commands.CommandError):
    pass


class CustomError(commands.CommandError):
    def __init__(self, message):
        self.message = message


ReplayInfo = NamedTuple('ReplayInfo', [('engine_data', dict),
                                       ('extra_data', list),
                                       ('decrypted_data', bytes)])


class ReplayReader:
    """
    Adapted to use BytesIO buffer.
    """

    def __init__(self, file):
        self.file = file

    def get_data(self):
        if self.file.read(4) != REPLAY_SIGNATURE:
            raise CustomError('File is not a valid replay.')

        blocks_count = struct.unpack("i", self.file.read(4))[0]

        block_size = struct.unpack("i", self.file.read(4))[0]
        engine_data = json.loads(self.file.read(block_size))

        extra_data = []
        for i in range(blocks_count - 1):
            block_size = struct.unpack("i", self.file.read(4))[0]
            data = json.loads(self.file.read(block_size))
            extra_data.append(data)

        decrypted_data = zlib.decompress(self.__decrypt_data(self.file.read()))

        return ReplayInfo(engine_data=engine_data,
                          extra_data=extra_data,
                          decrypted_data=decrypted_data)

    @staticmethod
    def __chunkify_string(string, length=8):
        for i in range(0, len(string), length):
            yield i, string[0 + i:length + i]

    def __decrypt_data(self, dirty_data):
        previous_block = None  # type: str
        blowfish = Blowfish.new(BLOWFISH_KEY, Blowfish.MODE_ECB)
        decrypted_data = io.BytesIO()

        for index, chunk in self.__chunkify_string(dirty_data):
            if index == 0:
                continue

            decrypted_block, = struct.unpack('q', blowfish.decrypt(chunk))
            if previous_block:
                decrypted_block ^= previous_block
            previous_block = decrypted_block

            decrypted_data.write(struct.pack('q', decrypted_block))

        return decrypted_data.getvalue()

