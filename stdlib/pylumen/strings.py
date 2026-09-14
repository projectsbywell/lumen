"""String utilities for the Lumen standard library."""

import re
import unicodedata
from typing import Any, List, Optional, Pattern


def lstrlen(s: str) -> int:
    """Return the length of a string."""
    return len(s)


def lsub(s: str, start: int, end: Optional[int] = None) -> str:
    """Return substring from start to end."""
    if end is None:
        return s[start:]
    return s[start:end]


def lconcat(*strings: str) -> str:
    """Concatenate multiple strings."""
    return "".join(strings)


def lindex(s: str, pos: int) -> str:
    """Return character at position."""
    return s[pos]


def lcompare(a: str, b: str) -> int:
    """Compare two strings lexicographically. Returns -1, 0, or 1."""
    if a < b:
        return -1
    elif a > b:
        return 1
    return 0


def lto_upper(s: str) -> str:
    """Convert to uppercase."""
    return s.upper()


def lto_lower(s: str) -> str:
    """Convert to lowercase."""
    return s.lower()


def lto_title(s: str) -> str:
    """Convert to title case."""
    return s.title()


def lstrip(s: str, chars: Optional[str] = None) -> str:
    """Strip characters from both ends."""
    return s.strip(chars)


def ltrim(s: str, chars: Optional[str] = None) -> str:
    """Trim whitespace from left."""
    return s.lstrip(chars)


def lreplace(s: str, old: str, new: str, count: int = -1) -> str:
    """Replace occurrences of old with new."""
    if count == -1:
        return s.replace(old, new)
    return s.replace(old, new, count)


def lsplit(s: str, sep: Optional[str] = None, maxsplit: int = -1) -> List[str]:
    """Split string by separator."""
    if maxsplit == -1:
        return s.split(sep)
    return s.split(sep, maxsplit)


def ljoin(parts: List[str], sep: str = "") -> str:
    """Join list of strings with separator."""
    return sep.join(parts)


def lmatches(s: str, pattern: str) -> bool:
    """Check if pattern matches string."""
    return re.search(pattern, s) is not None


def lfind(s: str, sub: str, start: int = 0) -> int:
    """Find substring position, return -1 if not found."""
    pos = s.find(sub, start)
    return pos


def lcount(s: str, sub: str) -> int:
    """Count occurrences of substring."""
    return s.count(sub)


def lformat(template: str, *args, **kwargs) -> str:
    """Format string with args and kwargs."""
    if args and kwargs:
        return template.format(*args, **kwargs)
    elif args:
        return template.format(*args)
    elif kwargs:
        return template.format(**kwargs)
    return template


def unicode_category(c: str) -> str:
    """Return Unicode category of character."""
    return unicodedata.category(c)


def unicode_name(c: str) -> str:
    """Return Unicode name of character."""
    return unicodedata.name(c)


def is_unicode_letter(c: str) -> bool:
    """Check if character is a Unicode letter."""
    cat = unicodedata.category(c)
    return cat.startswith('L')


def regex_compile(pattern: str) -> Pattern:
    """Compile a regex pattern."""
    return re.compile(pattern)


def regex_match(pattern: str, s: str) -> Optional[re.Match]:
    """Match pattern against string."""
    return re.match(pattern, s)


def regex_search(pattern: str, s: str) -> Optional[re.Match]:
    """Search pattern in string."""
    return re.search(pattern, s)


def regex_findall(pattern: str, s: str) -> List[str]:
    """Find all matches of pattern in string."""
    return re.findall(pattern, s)


def regex_sub(pattern: str, repl: str, s: str, count: int = 0) -> str:
    """Substitute pattern matches in string."""
    return re.sub(pattern, repl, s, count=count)
