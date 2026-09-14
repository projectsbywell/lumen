"""YAML utilities for the Lumen standard library (no external deps).

Supports a pragmatic YAML subset: block maps (nested by indentation),
sequences with ``-``, inline ``[a, b]`` / ``{k: v}`` collections, scalars
(int, float, bool, null, quoted/plain strings) and ``#`` comments.
"""

from typing import Any, Dict, List


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


def _scalar(text: str) -> Any:
    t = text.strip()
    if t in ("", "~", "null", "Null", "NULL"):
        return None
    if t in ("true", "True", "TRUE"):
        return True
    if t in ("false", "False", "FALSE"):
        return False
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
        inner = t[1:-1]
        if t[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
        return inner
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
                if ":" in part:
                    k, _, v = part.partition(":")
                    out[_scalar(k.strip())] = _scalar(v.strip())
        return out
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def _split_top(text: str) -> List[str]:
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
            elif ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
                continue
        cur += ch
    parts.append(cur)
    return parts


def lloads(s: str) -> Any:
    """Deserialize a YAML-subset string to an object."""
    lines = [ln.rstrip() for ln in s.splitlines()]
    # drop blanks/comments/doc markers
    cleaned = []
    for ln in lines:
        if not ln.strip() or ln.strip().startswith("#") or ln.strip() in ("---", "..."):
            continue
        cleaned.append(ln)
    if not cleaned:
        return None
    # top-level sequence?
    if all(ln.lstrip().startswith("- ") or ln.lstrip() == "-" for ln in cleaned):
        return _parse_block(cleaned, 0)[0]
    return _parse_block(cleaned, 0)[0]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_block(lines: List[str], base: int):
    """Parse block at indent >= base. Returns (value, next_index)."""
    if lines:
        stripped = lines[0].lstrip()
        if stripped.startswith("- ") or stripped == "-" or stripped.startswith("-\t"):
            return _parse_seq(lines, base)
    return _parse_map(lines, base)


def _parse_seq(lines: List[str], base: int):
    items: List[Any] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or _indent(ln) < base or _indent(ln) != base:
            break
        stripped = ln.strip()
        if not stripped.startswith("-"):
            break
        after = stripped[1:].lstrip()
        if not after:
            # bare "-" — nested block follows or null
            j = i + 1
            nested = []
            while j < len(lines) and lines[j].strip() and _indent(lines[j]) > base:
                nested.append(lines[j])
                j += 1
            if nested:
                val, _ = _parse_block(nested, _indent(nested[0]))
                items.append(val)
                i = j
            else:
                items.append(None)
                i += 1
        elif ": " in after or after.endswith(":"):
            # inline map entry inside sequence: "- key: val"
            extra = []
            j = i + 1
            while j < len(lines) and lines[j].strip() and _indent(lines[j]) > base:
                extra.append(lines[j])
                j += 1
            fake = [" " * (base + 2) + after] + extra
            val, _ = _parse_map(fake, base + 2)
            items.append(val)
            i = j
        else:
            items.append(_scalar(_strip_comment(after).strip()))
            i += 1
    return items, i


def _parse_map(lines: List[str], base: int):
    out: Dict[str, Any] = {}
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        ind = _indent(ln)
        if ind < base:
            break
        if ind > base:
            i += 1
            continue
        content = _strip_comment(ln.strip())
        if content.startswith("- ") or content == "-":
            break
        if ":" not in content:
            i += 1
            continue
        key, _, val = content.partition(":")
        key = _scalar(key.strip())
        val = val.strip()
        # gather nested block
        j = i + 1
        nested = []
        while j < len(lines) and lines[j].strip() and _indent(lines[j]) > base:
            nested.append(lines[j])
            j += 1
        if val == "":
            if nested:
                val_parsed, _ = _parse_block(nested, _indent(nested[0]))
                out[key] = val_parsed
            else:
                out[key] = None
        else:
            out[key] = _scalar(_strip_comment(val).strip())
        i = j if val == "" and nested else i + 1
    return out, i


def _dump_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or any(c in s for c in ":#{}[],&*?|<>%@`\"' \t\n"):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _dump(obj: Any, indent: int) -> List[str]:
    pad = " " * indent
    if isinstance(obj, dict):
        if not obj:
            return [pad + "{}"]
        lines = []
        for k, v in obj.items():
            ks = _dump_scalar(k)
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{ks}:")
                lines.extend(_dump(v, indent + 2))
            else:
                lines.append(f"{pad}{ks}: {_dump_scalar(v)}")
        return lines
    if isinstance(obj, list):
        if not obj:
            return [pad + "[]"]
        lines = []
        for item in obj:
            if isinstance(item, dict) and item:
                pairs = list(item.items())
                k0, v0 = pairs[0]
                if isinstance(v0, (dict, list)) and v0:
                    lines.append(f"{pad}- {_dump_scalar(k0)}:")
                    lines.extend(_dump(v0, indent + 4))
                else:
                    lines.append(f"{pad}- {_dump_scalar(k0)}: {_dump_scalar(v0)}")
                for k, v in pairs[1:]:
                    if isinstance(v, (dict, list)) and v:
                        lines.append(f"{pad}  {_dump_scalar(k)}:")
                        lines.extend(_dump(v, indent + 4))
                    else:
                        lines.append(f"{pad}  {_dump_scalar(k)}: {_dump_scalar(v)}")
            elif isinstance(item, list) and item:
                lines.append(pad + "-")
                lines.extend(_dump(item, indent + 2))
            else:
                lines.append(f"{pad}- {_dump_scalar(item)}")
        return lines
    return [pad + _dump_scalar(obj)]


def ldumps(obj: Any) -> str:
    """Serialize object to a YAML-subset string."""
    if obj is None:
        return "null\n"
    if isinstance(obj, (dict, list)):
        return "\n".join(_dump(obj, 0)) + "\n"
    return _dump_scalar(obj) + "\n"


def lto_yaml(obj: Any) -> str:
    """Convert object to YAML string."""
    return ldumps(obj)


def lfrom_yaml(s: str) -> Any:
    """Convert YAML string to object."""
    return lloads(s)


def lto_yaml_file(obj: Any, filepath: str) -> int:
    """Write object as YAML to file. Returns chars written."""
    data = ldumps(obj)
    with open(filepath, "w", encoding="utf-8") as fh:
        return fh.write(data)


def lfrom_yaml_file(filepath: str) -> Any:
    """Read YAML-subset from file."""
    with open(filepath, "r", encoding="utf-8") as fh:
        return lloads(fh.read())


def lis_yaml(s: str) -> bool:
    """Check if string parses as YAML-subset."""
    try:
        lloads(s)
        return True
    except Exception:  # noqa: BLE001
        return False
