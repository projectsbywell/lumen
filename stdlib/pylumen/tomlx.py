"""TOML utilities for the Lumen standard library (no external deps).

Supports a pragmatic TOML subset: top-level key/value pairs, ``[table]``
and dotted ``[a.b]`` tables, ``[[array-table]]``, arrays (multi-line),
inline tables ``{k = v}``, and scalars (strings basic/literal, int, float,
bool, dates kept as strings).
"""

from typing import Any, Dict, List, Tuple


def _strip_comment(line: str) -> str:
    in_s = in_d = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            return line[:i]
    return line


def _split_top(text: str, sep: str = ",") -> List[str]:
    parts, depth, cur, in_s, in_d = [], 0, "", False, False
    for ch in text:
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        if not in_s and not in_d:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            elif ch == sep and depth == 0:
                parts.append(cur)
                cur = ""
                continue
        cur += ch
    parts.append(cur)
    return parts


def _unquote(t: str) -> str:
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
        inner = t[1:-1]
        if t[0] == '"':
            inner = (inner.replace('\\"', '"').replace("\\n", "\n")
                     .replace("\\t", "\t").replace("\\\\", "\\"))
        return inner
    return t


def _bare_key(t: str) -> str:
    t = t.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
        return _unquote(t)
    return t


def _scalar(text: str) -> Any:
    t = text.strip()
    if t in ("true", "True"):
        return True
    if t in ("false", "False"):
        return False
    if t.startswith('"') or t.startswith("'"):
        return _unquote(t)
    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p) for p in _split_top(inner)]
    if t.startswith("{") and t.endswith("}"):
        inner = t[1:-1].strip()
        out: Dict[str, Any] = {}
        if inner:
            for part in _split_top(inner):
                if "=" in part:
                    k, _, v = part.partition("=")
                    out[_bare_key(k)] = _scalar(v.strip())
        return out
    # int (incl. hex/oct/bin)
    try:
        return int(t.replace("_", ""), 0) if t.startswith("0") and len(t) > 1 and t[1] in "xXoObB" else int(t.replace("_", ""))
    except ValueError:
        pass
    try:
        return float(t.replace("_", ""))
    except ValueError:
        pass
    return t  # e.g. dates stay strings


def _ensure_path(root: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    cur = root
    for k in keys:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    return cur


def lloads(s: str) -> Dict[str, Any]:
    """Deserialize a TOML-subset string to a dict."""
    # join multi-line arrays first
    buf, depth, in_s, in_d = "", 0, False, False
    logical: List[str] = []
    for raw in s.splitlines():
        for ch in raw:
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            if not in_s and not in_d:
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
        buf += raw + "\n"
        if depth == 0:
            logical.append(buf)
            buf = ""
    if buf.strip():
        logical.append(buf)

    root: Dict[str, Any] = {}
    cur = root
    for chunk in logical:
        line = _strip_comment(chunk).strip()
        if not line:
            continue
        if line.startswith("[["):
            name = line[2:].split("]")[0].strip()
            keys = [_bare_key(k) for k in _split_top(name, ".")]
            parent = _ensure_path(root, keys[:-1])
            arr = parent.get(keys[-1])
            if not isinstance(arr, list):
                arr = []
                parent[keys[-1]] = arr
            item: Dict[str, Any] = {}
            arr.append(item)
            cur = item
        elif line.startswith("["):
            name = line[1:].split("]")[0].strip()
            keys = [_bare_key(k) for k in _split_top(name, ".")]
            cur = _ensure_path(root, keys)
        elif "=" in line:
            k, _, v = line.partition("=")
            key = _bare_key(k)
            val = _scalar(v.strip())
            if "." in k and k.strip()[0] not in ("'", '"'):
                parts = [_bare_key(p) for p in _split_top(k.strip(), ".")]
                target = _ensure_path(cur, parts[:-1])
                target[parts[-1]] = val
            else:
                cur[key] = val
    return root


def _dump_scalar(v: Any) -> str:
    if v is None:
        return '""'
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(_dump_scalar(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_dump_scalar(x)}" for k, x in v.items()) + " }"
    s = str(v)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _is_table(v: Any) -> bool:
    return isinstance(v, dict)


def _dump_table(obj: Dict[str, Any], prefix: str) -> List[str]:
    lines: List[str] = []
    # scalars first
    for k, v in obj.items():
        if not _is_table(v) and not (isinstance(v, list) and v and all(isinstance(x, dict) for x in v)):
            lines.append(f"{k} = {_dump_scalar(v)}")
    # sub-tables
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        if _is_table(v):
            lines.append(f"[{path}]")
            lines.extend(_dump_table(v, path))
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            for item in v:
                lines.append(f"[[{path}]]")
                lines.extend(_dump_table(item, path))
    return lines


def ldumps(obj: Dict[str, Any]) -> str:
    """Serialize a dict to a TOML-subset string."""
    if not isinstance(obj, dict):
        raise TypeError("TOML top level must be a table (dict)")
    return "\n".join(_dump_table(obj, "")) + "\n"


def lto_toml(obj: Dict[str, Any]) -> str:
    """Convert dict to TOML string."""
    return ldumps(obj)


def lfrom_toml(s: str) -> Dict[str, Any]:
    """Convert TOML string to dict."""
    return lloads(s)


def lto_toml_file(obj: Dict[str, Any], filepath: str) -> int:
    """Write dict as TOML to file. Returns chars written."""
    data = ldumps(obj)
    with open(filepath, "w", encoding="utf-8") as fh:
        return fh.write(data)


def lfrom_toml_file(filepath: str) -> Any:
    """Read TOML-subset from file."""
    with open(filepath, "r", encoding="utf-8") as fh:
        return lloads(fh.read())


def lis_toml(s: str) -> bool:
    """Check if string parses as TOML-subset."""
    try:
        v = lloads(s)
        return isinstance(v, dict)
    except Exception:  # noqa: BLE001
        return False
