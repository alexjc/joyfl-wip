## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#
import lark

class JoyError(Exception):
    pass

class JoyParseError(JoyError):
    def __init__(self, message, *, filename=None, line=None, column=None, token=None):
        super().__init__(message)
        self.filename = filename
        self.line = line
        self.column = column
        self.token = token

class JoyIncompleteParse(JoyParseError, lark.exceptions.ParseError):
    def __init__(self, message, *, filename=None, line=None, column=None, token=None):
        super().__init__(message, filename=filename, line=line, column=column, token=token)

class JoyNameError(JoyError, NameError):
    def __init__(self, message, token=None):
        super().__init__(message)
        self.token = token

class JoyRuntimeError(JoyError, RuntimeError):
    pass
