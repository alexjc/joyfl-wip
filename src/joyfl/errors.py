## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import lark


class JoyError(Exception):
    def __init__(self, message: str = "", *, joy_op=None, joy_meta=None):
        super().__init__(message)
        self.joy_op = joy_op
        self.joy_meta = joy_meta

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
    pass

class JoyValueError(JoyError, ValueError):
    pass

class JoyRuntimeError(JoyError, RuntimeError):
    pass

class JoyAssertionError(JoyError, AssertionError):
    pass


class JoyTypeMissing(JoyError, TypeError):
    pass

class JoyTypeError(JoyError, TypeError):
    pass


class JoyImportError(JoyError, ImportError):
    def __init__(self, message, *, joy_op=None, filename=None, joy_meta=None):
        super().__init__(message, joy_op=joy_op, joy_meta=joy_meta)
        self.filename = filename

class JoyModuleError(JoyImportError):
    pass
