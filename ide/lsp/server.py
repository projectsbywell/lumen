#!/usr/bin/env python3
"""Lumen Language Server (LSP) over stdio JSON-RPC.

Runnable:  python3 server.py
Protocol:  LSP 3.17 subset over stdio with Content-Length framing.

Features:
  initialize, initialized, shutdown, exit,
  textDocument/didOpen, didChange, didClose,
  textDocument/completion, hover, definition, references,
  formatting, rename, codeAction,
  textDocument/publishDiagnostics (server -> client)

Reuse strategy: tries to import a real lexer/parser from the Lumen
tree (compiler/frontend/*) if present; otherwise falls back to a
self-contained regex scanner. All analysis helpers are importable so
`test_lsp.py` can exercise them without spawning the server.
"""

from __future__ import annotations

import io
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional reuse of a real lexer/parser when the Lumen frontend exists.
# ---------------------------------------------------------------------------

_REAL_LEXER = None
_REAL_PARSER = None

try:  # pragma: no cover - exercised only when frontend lands
    sys.path.insert(0, "/root/scripts/lumen")
    try:
        from compiler.frontend import lexer as _lx  # type: ignore
        _REAL_LEXER = _lx
    except Exception:
        pass
    try:
        from compiler.frontend import parser as _ps  # type: ignore
        _REAL_PARSER = _ps
    except Exception:
        pass
except Exception:
    pass

SERVER_NAME = "lumen-lsp"
SERVER_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Language model
# ---------------------------------------------------------------------------

KEYWORDS: Dict[str, str] = {
    "fn": "Declara uma função. Ex: `fn soma(a: int, b: int) -> int { return a + b; }`",
    "let": "Declara uma variável imutável. Ex: `let x = 42;`",
    "mut": "Modificador de mutabilidade. Ex: `let mut n = 0;`",
    "const": "Declara uma constante. Ex: `const PI = 3.14;`",
    "struct": "Declara um struct. Ex: `struct Ponto { x: int, y: int }`",
    "enum": "Declara uma enumeração. Ex: `enum Cor { Vermelho, Verde }`",
    "match": "Expressão de pattern matching. Ex: `match x { 0 => \"zero\", _ => \"outro\" }`",
    "if": "Condicional. Ex: `if x > 0 { print(x); }`",
    "else": "Ramo alternativo do `if` / `match`.",
    "for": "Laço `for`. Ex: `for i in 0..10 { print(i); }`",
    "while": "Laço `while`. Ex: `while n > 0 { n = n - 1; }`",
    "loop": "Laço infinito com `break`.",
    "return": "Retorna valor de função.",
    "break": "Interrompe o laço atual.",
    "continue": "Pula para a próxima iteração.",
    "use": "Importa módulo. Ex: `use std::io;`",
    "mod": "Declara módulo. Ex: `mod math { ... }`",
    "pub": "Torna item público. Ex: `pub fn f() {}`",
    "impl": "Bloco de implementação. Ex: `impl Ponto { fn novo() { ... } }`",
    "trait": "Declara trait. Ex: `trait Eq { fn eq(self, outro: Self) -> bool; }`",
    "type": "Alias de tipo. Ex: `type Id = int;`",
    "where": "Cláusula de restrição de genéricos.",
    "as": "Conversão / alias. Ex: `x as float`, `use a as b;`",
    "in": "Pertinência em `for`. Ex: `for x in lista {}`",
    "self": "Receptor do método.",
    "true": "Literal booleano verdadeiro.",
    "false": "Literal booleano falso.",
    "nil": "Ausência de valor.",
    "test": "Bloco de teste. Ex: `test \"soma\" { assert(1 + 1 == 2); }`",
    "assert": "Afirmação de teste. Ex: `assert(x == 1);`",
    "int": "Tipo inteiro.",
    "float": "Tipo ponto flutuante.",
    "string": "Tipo texto.",
    "bool": "Tipo booleano.",
}

BUILTINS: Dict[str, str] = {
    "print": "Imprime valores. Ex: `print(\"olá\");`",
    "println": "Imprime com nova linha. Ex: `println(x);`",
    "len": "Tamanho de string/vetor. Ex: `len(\"abc\")` → `3`",
    "push": "Adiciona ao vetor. Ex: `push(v, 1);`",
    "fib": "Fibonacci (demo do playground). Ex: `fib(10)` → `55`",
}

COMPLETION_ITEMS: List[Dict[str, Any]] = (
    [{"label": k, "kind": 14, "detail": "keyword",
      "documentation": v, "insertText": k} for k, v in KEYWORDS.items()]
    + [{"label": b, "kind": 3, "detail": "builtin",
        "documentation": v, "insertText": b + "($0)",
        "insertTextFormat": 2} for b, v in BUILTINS.items()]
)

WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DEF_PATTERNS = [
    re.compile(r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"\btrait\s+([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"\btype\s+([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"\b(?:let|const)\s+(?:mut\s+)?([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b"),
]

# Chars that are never valid in Lumen source outside string/comment.
INVALID_CHAR_RE = re.compile(r"[`$?\\]")
LINE_COMMENT = "//"


# ---------------------------------------------------------------------------
# Document helpers (fallback scanner)
# ---------------------------------------------------------------------------

def strip_line_comment(line: str) -> str:
    """Remove // comment, respecting double-quoted strings."""
    in_str = False
    esc = False
    for i, ch in enumerate(line):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                return line[:i]
    return line


def word_at_position(lines: List[str], line: int, character: int) -> str:
    if line < 0 or line >= len(lines):
        return ""
    text = lines[line]
    if not text:
        return ""
    character = max(0, min(character, len(text)))
    start = character
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
        start -= 1
    end = character
    while end < len(text) and (text[end].isalnum() or text[end] == "_"):
        end += 1
    return text[start:end]


def offset_to_position(text: str, offset: int) -> Dict[str, int]:
    offset = max(0, min(offset, len(text)))
    line = text.count("\n", 0, offset)
    last_nl = text.rfind("\n", 0, offset)
    return {"line": line, "character": offset - (last_nl + 1)}


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def analyze_diagnostics(text: str) -> List[Dict[str, Any]]:
    """Return LSP Diagnostic[] for lexical problems in `text`.

    Detects: unterminated string literals, invalid characters
    (` $ ? \\ outside strings/comments) and unbalanced (), {}, [].
    If a real lexer is importable and exposes `diagnose(text)`, its
    findings are merged in front of the fallback ones.
    """
    diags: List[Dict[str, Any]] = []

    if _REAL_LEXER is not None and hasattr(_REAL_LEXER, "diagnose"):
        try:
            for d in _REAL_LEXER.diagnose(text):  # type: ignore
                diags.append(d)
        except Exception:
            pass

    lines = text.splitlines()
    stack: List[Tuple[str, int, int]] = []
    pairs = {")": "(", "}": "{", "]": "["}
    opening = {"(": ")", "{": "}", "[": "]"}

    for li, raw in enumerate(lines):
        code = strip_line_comment(raw)
        # --- unterminated string check (per line; Lumen strings don't span lines)
        in_str = False
        esc = False
        str_start = 0
        for ci, ch in enumerate(code):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                    str_start = ci
        if in_str:
            diags.append({
                "range": {"start": {"line": li, "character": str_start},
                          "end": {"line": li, "character": len(raw)}},
                "severity": 1,
                "source": "lumen",
                "code": "unterminated-string",
                "message": "String não terminada: falta aspas de fechamento.",
            })
            # skip further char checks inside the broken string tail
            code = code[:str_start]

        # --- invalid characters (outside strings)
        masked = []
        in_str = False
        esc = False
        for ch in code:
            if in_str:
                masked.append(" ")
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                    masked.append(" ")
                else:
                    masked.append(ch)
        masked_s = "".join(masked)
        for m in INVALID_CHAR_RE.finditer(masked_s):
            ci = m.start()
            diags.append({
                "range": {"start": {"line": li, "character": ci},
                          "end": {"line": li, "character": ci + 1}},
                "severity": 1,
                "source": "lumen",
                "code": "invalid-char",
                "message": f"Caractere léxico inválido: '{m.group(0)}'.",
            })
        # --- bracket balance (outside strings)
        in_str = False
        esc = False
        for ci, ch in enumerate(code):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in opening:
                stack.append((ch, li, ci))
            elif ch in pairs:
                if stack and stack[-1][0] == pairs[ch]:
                    stack.pop()
                else:
                    diags.append({
                        "range": {"start": {"line": li, "character": ci},
                                  "end": {"line": li, "character": ci + 1}},
                        "severity": 1,
                        "source": "lumen",
                        "code": "unbalanced-delimiter",
                        "message": f"Delimitador '{ch}' sem abertura correspondente.",
                    })
    for ch, li, ci in stack:
        diags.append({
            "range": {"start": {"line": li, "character": ci},
                      "end": {"line": li, "character": ci + 1}},
            "severity": 1,
            "source": "lumen",
            "code": "unbalanced-delimiter",
            "message": f"Delimitador '{ch}' sem fechamento correspondente.",
        })
    return diags


# ---------------------------------------------------------------------------
# Language features
# ---------------------------------------------------------------------------

def get_completions(prefix: str = "") -> List[Dict[str, Any]]:
    if not prefix:
        return list(COMPLETION_ITEMS)
    pl = prefix.lower()
    return [i for i in COMPLETION_ITEMS if i["label"].lower().startswith(pl)]


def get_hover(word: str) -> Optional[Dict[str, Any]]:
    if word in KEYWORDS:
        return {"contents": {"kind": "markdown",
                "value": f"**`{word}`** (keyword)\n\n{KEYWORDS[word]}"}}
    if word in BUILTINS:
        return {"contents": {"kind": "markdown",
                "value": f"**`{word}()`** (builtin)\n\n{BUILTINS[word]}"}}
    return None


def find_definitions(text: str, word: str) -> List[Dict[str, Any]]:
    locs: List[Dict[str, Any]] = []
    if not word or not WORD_RE.fullmatch(word):
        return locs
    for li, line in enumerate(text.splitlines()):
        code = strip_line_comment(line)
        for pat in DEF_PATTERNS:
            for m in pat.finditer(code):
                if m.group(1) == word:
                    s = m.start(1)
                    locs.append({
                        "range": {"start": {"line": li, "character": s},
                                  "end": {"line": li, "character": s + len(word)}},
                    })
    return locs


def find_references(text: str, word: str) -> List[Dict[str, Any]]:
    locs: List[Dict[str, Any]] = []
    if not word or not WORD_RE.fullmatch(word):
        return locs
    pat = re.compile(r"\b" + re.escape(word) + r"\b")
    for li, line in enumerate(text.splitlines()):
        for m in pat.finditer(strip_line_comment(line)):
            locs.append({
                "range": {"start": {"line": li, "character": m.start()},
                          "end": {"line": li, "character": m.end()}},
            })
    return locs


def format_document(text: str) -> str:
    """Deterministic formatter: strip trailing ws, normalize indent by braces."""
    if text == "":
        return ""
    lines = text.replace("\t", "    ").split("\n")
    out: List[str] = []
    indent = 0
    for raw in lines:
        s = raw.rstrip()
        stripped = s.strip()
        if stripped.startswith(("}", ")", "]")):
            indent = max(0, indent - 1)
        out.append(("    " * indent + stripped) if stripped else "")
        opens = sum(stripped.count(c) for c in "({[")
        closes = sum(stripped.count(c) for c in ")}]")
        # a line that both opens and closes (e.g. `} else {`) keeps level
        net = opens - closes
        if stripped.endswith(("{", "(", "[")):
            net = max(net, 1) if opens > closes else net
        indent = max(0, indent + max(0, net) if net > 0 else indent + net)
        indent = max(0, indent)
    # collapse >1 consecutive blank lines, ensure single trailing newline
    cleaned: List[str] = []
    blanks = 0
    for l in out:
        if l == "":
            blanks += 1
            if blanks <= 1:
                cleaned.append(l)
        else:
            blanks = 0
            cleaned.append(l)
    return "\n".join(cleaned).rstrip() + "\n"


def get_code_actions(uri: str, diagnostics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for d in diagnostics:
        if d.get("code") == "unterminated-string":
            r = d["range"]
            actions.append({
                "title": "Fechar string com aspas",
                "kind": "quickfix",
                "diagnostics": [d],
                "edit": {"changes": {uri: [{
                    "range": {"start": r["end"], "end": r["end"]},
                    "newText": '"'}]}},
            })
    actions.append({
        "title": "Formatar documento",
        "kind": "source.format",
    })
    return actions


# ---------------------------------------------------------------------------
# JSON-RPC stdio transport
# ---------------------------------------------------------------------------

def read_message(buf: io.BufferedReader) -> Optional[Dict[str, Any]]:
    headers: Dict[str, str] = {}
    while True:
        line = buf.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        if b":" in line:
            k, v = line.split(b":", 1)
            headers[k.strip().decode("latin-1").lower()] = v.strip().decode("latin-1")
    try:
        length = int(headers.get("content-length", "0"))
    except ValueError:
        return None
    if length <= 0:
        return None
    body = b""
    while len(body) < length:
        chunk = buf.read(length - len(body))
        if not chunk:
            break
        body += chunk
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def send_message(buf: io.BufferedWriter, obj: Dict[str, Any]) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    buf.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    buf.flush()


# ---------------------------------------------------------------------------
# Request handling (pure logic, testable without stdio)
# ---------------------------------------------------------------------------

def apply_edit(text: str, change: Dict[str, Any]) -> str:
    """Aplica contentChange incremental (com range) ou full-text."""
    if "range" not in change:
        return change.get("text", text)
    rng = change["range"]
    lines = text.splitlines(keepends=True)
    sl, sc = rng["start"]["line"], rng["start"]["character"]
    el, ec = rng["end"]["line"], rng["end"]["character"]
    sl = min(sl, len(lines))
    el = min(el, len(lines))
    pre = "".join(lines[:sl]) + (lines[sl][:sc] if sl < len(lines) else "")
    post = (lines[el][ec:] if el < len(lines) else "") + "".join(lines[el + 1:])
    return pre + change.get("text", "") + post


class Session:
    def __init__(self) -> None:
        self.docs: Dict[str, str] = {}
        self.versions: Dict[str, int] = {}
        self.shutdown_requested = False
        self.root: Optional[str] = None

    # -- notifications ------------------------------------------------------
    def did_open(self, uri: str, text: str, version: int = 0) -> List[Dict[str, Any]]:
        self.docs[uri] = text
        self.versions[uri] = version
        return analyze_diagnostics(text)

    def did_change(self, uri: str, changes: list, version: Optional[int] = None) -> List[Dict[str, Any]]:
        text = self.docs.get(uri, "")
        for ch in changes:
            text = apply_edit(text, ch)
        self.docs[uri] = text
        if version is not None:
            self.versions[uri] = version
        return analyze_diagnostics(text)

    def did_close(self, uri: str) -> None:
        self.docs.pop(uri, None)
        self.versions.pop(uri, None)

    # -- requests -----------------------------------------------------------
    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {}) or {}

        def ok(result: Any) -> Dict[str, Any]:
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}

        def err(code: int, message: str) -> Dict[str, Any]:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": code, "message": message}}

        if method == "initialize":
            self.root = (params.get("rootUri")
                         or params.get("rootPath"))
            return ok({
                "capabilities": {
                    "textDocumentSync": 2,
                    "completionProvider": {"triggerCharacters": [".", ":"]},
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "documentFormattingProvider": True,
                    "renameProvider": True,
                    "codeActionProvider": True,
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })
        if method in ("initialized", "$/cancelRequest"):
            return None
        if method == "shutdown":
            self.shutdown_requested = True
            return ok(None)
        if method == "exit":
            sys.exit(0 if self.shutdown_requested else 1)

        if method == "textDocument/didOpen":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            diags = self.did_open(uri, td.get("text", ""), td.get("version", 0))
            return {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                    "params": {"uri": uri, "version": self.versions.get(uri, 0),
                               "diagnostics": diags}}
        if method == "textDocument/didChange":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            changes = params.get("contentChanges", [])
            diags = self.did_change(uri, changes, td.get("version"))
            return {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                    "params": {"uri": uri, "version": self.versions.get(uri, 0),
                               "diagnostics": diags}}
        if method == "textDocument/didClose":
            self.did_close(params.get("textDocument", {}).get("uri", ""))
            return None

        if msg_id is None:  # notification we don't handle
            return None

        if method == "textDocument/completion":
            td = params.get("textDocument", {})
            pos = params.get("position", {"line": 0, "character": 0})
            text = self.docs.get(td.get("uri", ""), "")
            lines = text.splitlines()
            prefix = ""
            if 0 <= pos.get("line", 0) < len(lines):
                l = lines[pos["line"]]
                c = max(0, min(pos.get("character", 0), len(l)))
                m = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", l[:c])
                prefix = m.group(0) if m else ""
            return ok(get_completions(prefix))

        if method == "textDocument/hover":
            td = params.get("textDocument", {})
            pos = params.get("position", {"line": 0, "character": 0})
            text = self.docs.get(td.get("uri", ""), "")
            word = word_at_position(text.splitlines(), pos.get("line", 0),
                                    pos.get("character", 0))
            return ok(get_hover(word))

        if method == "textDocument/definition":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            pos = params.get("position", {"line": 0, "character": 0})
            text = self.docs.get(uri, "")
            word = word_at_position(text.splitlines(), pos.get("line", 0),
                                    pos.get("character", 0))
            return ok([{"uri": uri, **loc} for loc in find_definitions(text, word)])

        if method == "textDocument/references":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            pos = params.get("position", {"line": 0, "character": 0})
            text = self.docs.get(uri, "")
            word = word_at_position(text.splitlines(), pos.get("line", 0),
                                    pos.get("character", 0))
            return ok([{"uri": uri, **loc} for loc in find_references(text, word)])

        if method == "textDocument/formatting":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            text = self.docs.get(uri, "")
            new_text = format_document(text)
            if new_text == text:
                return ok([])
            nlines = max(1, len(text.splitlines()))
            return ok([{"range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": nlines, "character": 0}},
                "newText": new_text}])

        if method == "textDocument/rename":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            pos = params.get("position", {"line": 0, "character": 0})
            new_name = params.get("newName", "")
            if not new_name or not WORD_RE.fullmatch(new_name):
                return err(-32602, "newName inválido.")
            text = self.docs.get(uri, "")
            word = word_at_position(text.splitlines(), pos.get("line", 0),
                                    pos.get("character", 0))
            edits = [{"range": loc["range"], "newText": new_name}
                     for loc in find_references(text, word)]
            return ok({"changes": {uri: edits}})

        if method == "textDocument/codeAction":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            ctx = params.get("context", {})
            diags = ctx.get("diagnostics") or analyze_diagnostics(self.docs.get(uri, ""))
            return ok(get_code_actions(uri, diags))

        return err(-32601, f"Método não suportado: {method}")


def serve(stdin: io.BufferedReader | None = None,
          stdout: io.BufferedWriter | None = None) -> None:
    sess = Session()
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    while True:
        msg = read_message(stdin)
        if msg is None:
            break
        try:
            resp = sess.handle(msg)
        except SystemExit:
            raise
        except Exception as exc:  # never kill the pipe on handler bugs
            if msg.get("id") is not None:
                resp = {"jsonrpc": "2.0", "id": msg.get("id"),
                        "error": {"code": -32603, "message": str(exc)}}
            else:
                resp = None
        if resp is not None:
            send_message(stdout, resp)


if __name__ == "__main__":
    serve()
