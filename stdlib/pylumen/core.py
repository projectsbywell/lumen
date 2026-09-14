"""Core types and conversions for the Lumen standard library."""

from enum import Enum
from typing import Any, Union, Optional
import functools


class LumenType(Enum):
    NIL = "nil"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    LIST = "list"
    MAP = "map"
    SET = "set"
    TUPLE = "tuple"
    FUNCTION = "function"
    CUSTOM = "custom"


class LumenNil:
    """Singleton nil type, analogous to None/null."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "nil"

    def __eq__(self, other):
        return isinstance(other, LumenNil) or other is None


NIL = LumenNil()


class LumenString(str):
    """String subclass with Lumen-aware methods."""
    def __new__(cls, value=""):
        return super().__new__(cls, value)

    def to_upper(self):
        return self.upper()

    def to_lower(self):
        return self.lower()

    def strip(self, chars=None):
        return str.strip(self, chars)

    def split(self, sep=None, maxsplit=-1):
        return str.split(self, sep, maxsplit)

    def replace(self, old, new, count=-1):
        return str.replace(self, old, new, count)

    def find(self, sub, start=0, end=None):
        return str.find(self, sub, start, end if end is not None else len(self))

    def matches(self, pattern):
        import re
        return re.search(pattern, self) is not None


class LumenInt(int):
    """Int subclass with Lumen-aware methods."""
    def __new__(cls, value=0):
        return super().__new__(cls, value)

    def to_float(self):
        return float(self)

    def to_str(self):
        return str(self)

    def abs(self):
        return abs(self)

    def mod(self, other):
        return self % other

    def pow(self, exp):
        return self ** exp


class LumenFloat(float):
    """Float subclass with Lumen-aware methods."""
    def __new__(cls, value=0.0):
        return super().__new__(cls, value)

    def to_int(self):
        return int(self)

    def to_str(self):
        return str(self)

    def round(self, ndigits=0):
        return round(self, ndigits)

    def sqrt(self):
        import math
        return math.sqrt(self)


class LumenBool:
    """Bool wrapper with Lumen-aware methods (bool cannot be subclassed)."""
    def __init__(self, value=False):
        self._value = bool(value)

    def __bool__(self):
        return self._value

    def __eq__(self, other):
        if isinstance(other, LumenBool):
            return self._value == other._value
        return self._value == other

    def __repr__(self):
        return "LumenBool(true)" if self._value else "LumenBool(false)"

    def __hash__(self):
        return hash(self._value)

    def to_int(self):
        return 1 if self._value else 0

    def to_str(self):
        return "true" if self._value else "false"


def ltype_of(value: Any) -> LumenType:
    """Return the LumenType of a value."""
    if value is None or isinstance(value, LumenNil):
        return LumenType.NIL
    if isinstance(value, bool) or isinstance(value, LumenBool):
        return LumenType.BOOL
    if isinstance(value, int) and not isinstance(value, bool):
        return LumenType.INT
    if isinstance(value, float):
        return LumenType.FLOAT
    if isinstance(value, str):
        return LumenType.STRING
    if isinstance(value, list):
        return LumenType.LIST
    if isinstance(value, dict):
        return LumenType.MAP
    if isinstance(value, set):
        return LumenType.SET
    if isinstance(value, tuple):
        return LumenType.TUPLE
    if callable(value):
        return LumenType.FUNCTION
    return LumenType.CUSTOM


def ltype_name(value: Any) -> str:
    """Return the name of the LumenType of a value."""
    return ltype_of(value).value


def lconvert(value: Any, target_type: LumenType) -> Any:
    """Convert a value to a target LumenType."""
    if target_type == LumenType.INT:
        if isinstance(value, str):
            return int(value)
        return int(value)
    elif target_type == LumenType.FLOAT:
        if isinstance(value, str):
            return float(value)
        return float(value)
    elif target_type == LumenType.STRING:
        return str(value)
    elif target_type == LumenType.BOOL:
        return bool(value)
    elif target_type == LumenType.LIST:
        if isinstance(value, (str, dict, set, tuple)):
            return list(value)
        return list(value)
    elif target_type == LumenType.MAP:
        if isinstance(value, list):
            return dict(value)
        return dict(value)
    elif target_type == LumenType.SET:
        return set(value)
    return value


def lto_int(value: Any) -> int:
    """Convert value to int."""
    return lconvert(value, LumenType.INT)


def lto_float(value: Any) -> float:
    """Convert value to float."""
    return lconvert(value, LumenType.FLOAT)


def lto_str(value: Any) -> str:
    """Convert value to string."""
    return lconvert(value, LumenType.STRING)


def lto_bool(value: Any) -> bool:
    """Convert value to bool."""
    return lconvert(value, LumenType.BOOL)


def lis_nil(value: Any) -> bool:
    """Check if value is nil."""
    return value is None or isinstance(value, LumenNil)


def lis_type(value: Any, ttype: LumenType) -> bool:
    """Check if value is of a given LumenType."""
    return ltype_of(value) == ttype


def lassert_type(value: Any, ttype: LumenType) -> bool:
    """Assert that value is of the given type, raise TypeError if not."""
    if not lis_type(value, ttype):
        raise TypeError(f"Expected {ttype.value}, got {ltype_name(value)}")
    return True
