from enum import IntEnum


class Exit(IntEnum):
    OK = 0
    INTERNAL = 1
    USAGE = 2
    FILE = 3
    TOOLCHAIN = 4
    CONVERT = 5
    LIMIT = 6


class TejtexError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code
