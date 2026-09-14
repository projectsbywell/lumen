"""JSON utilities for the Lumen standard library."""

import json
from typing import Any, Union


def ldumps(obj: Any, indent: int = 2, sort_keys: bool = False) -> str:
    """Serialize object to JSON string."""
    return json.dumps(obj, indent=indent, sort_keys=sort_keys, ensure_ascii=False)


def lloads(s: str) -> Any:
    """Deserialize JSON string to object."""
    return json.loads(s)


def lto_json(obj: Any) -> str:
    """Convert object to JSON string (compact)."""
    return json.dumps(obj, ensure_ascii=False)


def lfrom_json(s: str) -> Any:
    """Convert JSON string to object."""
    return json.loads(s)


def lto_json_file(obj: Any, filepath: str) -> int:
    """Write object as JSON to file."""
    with open(filepath, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        return f.tell()


def lfrom_json_file(filepath: str) -> Any:
    """Read JSON from file."""
    with open(filepath, "r") as f:
        return json.load(f)


def lpretty(obj: Any, indent: int = 4) -> str:
    """Pretty-print object as JSON."""
    return json.dumps(obj, indent=indent, ensure_ascii=False)


def lis_json(s: str) -> bool:
    """Check if string is valid JSON."""
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, ValueError, TypeError):
        return False


def lmerge(*dicts: dict) -> dict:
    """Merge multiple dicts, later values override earlier."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def ldeep_merge(*dicts: dict) -> dict:
    """Deep merge multiple dicts."""
    result = {}
    for d in dicts:
        for k, v in d.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = ldeep_merge(result[k], v)
            else:
                result[k] = v
    return result
