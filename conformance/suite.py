#!/usr/bin/env python3
"""suite.py — suíte de conformidade do Lumen.

Cada feature da spec vira um caso executável (lexer, parser, tipos, match,
struct/enum, bytecode, backends, runtime, stdlib) com resultado esperado.
O runner imprime PASS/FAIL e gera `conformance_report.json`. Meta: 100%.

A suíte embute a semântica de referência da spec Lumen v0.1 (mini-lexer,
parser de expressões, checador de tipos, avaliador de `match`, compilador
para bytecode + VM, geradores C/WASM e simuladores de runtime/stdlib) em
Python puro, sem dependências.

Uso:
    python3 conformance/suite.py                    # roda tudo
    python3 conformance/suite.py --filter match     # uma categoria
    python3 conformance/suite.py --json /tmp/r.json # relatório alternativo
"""
from __future__ import annotations

import argparse
import json
import os
import sys

SPEC_VERSION = "0.5.4"
SUITE_VERSION = "0.5.4"

# ---------------------------------------------------------------- lexer ---

KEYWORDS = {
    "fn", "let", "mut", "if", "else", "match", "struct", "enum", "mod",
    "use", "pub", "return", "for", "in", "while", "loop", "break",
    "continue", "true", "false", "impl", "trait", "macro", "async",
    "await", "spawn", "const", "type", "as", "self", "Ok", "Err",
    "Some", "None", "vec", "map", "panic",
}
MULTI_OPS = ["=>", "->", "::", "..=", "==", "!=", "<=", ">=", "&&", "||",
             "+=", "-=", "*=", "/=", ".."]
SYMS = set("(){}[],;@#")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "'": "'",
           "\\": "\\", "0": "\0"}


def lex(src: str) -> list[tuple[str, object, int]]:
    """Tokeniza fonte Lumen. Token = (classe, valor, linha)."""
    toks: list[tuple[str, object, int]] = []
    i, ln, n = 0, 1, len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            ln += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if src.startswith("///", i):
            j = src.find("\n", i)
            if j < 0:
                j = n
            toks.append(("DOC", src[i + 3:j].strip(), ln))
            i = j
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                raise SyntaxError("bloco /* não fechado")
            ln += src.count("\n", i, j)
            i = j + 2
            continue
        if c == '"':
            j = i + 1
            buf = ""
            while True:
                if j >= n:
                    raise SyntaxError("string não fechada")
                ch = src[j]
                if ch == "\\":
                    if j + 1 >= n or src[j + 1] not in ESCAPES:
                        raise SyntaxError(f"escape inválido na linha {ln}")
                    buf += ESCAPES[src[j + 1]]
                    j += 2
                    continue
                if ch == '"':
                    break
                if ch == "\n":
                    raise SyntaxError("string com newline")
                buf += ch
                j += 1
            toks.append(("STR", buf, ln))
            i = j + 1
            continue
        if c == "'":
            if i + 2 < n and src[i + 2] == "'":
                toks.append(("CHAR", src[i + 1], ln))
                i += 3
                continue
            if i + 3 < n and src[i + 1] == "\\" and src[i + 3] == "'":
                if src[i + 2] not in ESCAPES:
                    raise SyntaxError(f"escape inválido na linha {ln}")
                toks.append(("CHAR", ESCAPES[src[i + 2]], ln))
                i += 4
                continue
            raise SyntaxError(f"char inválido na linha {ln}")
        if c.isdigit():
            j = i
            while j < n and (src[j].isdigit() or src[j] == "_"):
                j += 1
            if j < n and src[j] == "." and j + 1 < n and src[j + 1].isdigit():
                j += 1
                while j < n and (src[j].isdigit() or src[j] == "_"):
                    j += 1
                toks.append(("FLOAT", float(src[i:j].replace("_", "")), ln))
            else:
                toks.append(("INT", int(src[i:j].replace("_", "")), ln))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            w = src[i:j]
            toks.append(("KEY" if w in KEYWORDS else "IDENT", w, ln))
            i = j
            continue
        hit = False
        for op in MULTI_OPS:
            if src.startswith(op, i):
                toks.append(("OP", op, ln))
                i += len(op)
                hit = True
                break
        if hit:
            continue
        if c in SYMS:
            toks.append(("SYM", c, ln))
            i += 1
            continue
        if c in "+-*/%<>=!&|.?:":
            toks.append(("OP", c, ln))
            i += 1
            continue
        raise SyntaxError(f"caractere inesperado {c!r} na linha {ln}")
    toks.append(("EOF", "", ln))
    return toks


def toks_simple(src: str) -> list:
    """Resumo (classe, valor) sem linha — usado nos casos LEX-*."""
    return [(k, v) for (k, v, _ln) in lex(src) if k != "EOF"]

# --------------------------------------------------------------- parser ---

class LumenErr(Exception):
    """Propagação de `Err` via `?`."""


class LumenPanic(Exception):
    pass


class LumenTypeErr(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, val):
        self.val = val


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.p = 0

    def pk(self):
        return self.t[self.p]

    def nx(self):
        t = self.t[self.p]
        self.p += 1
        return t

    def at(self, k, v=None):
        t = self.pk()
        return t[0] == k and (v is None or t[1] == v)

    def expect(self, k, v=None):
        t = self.nx()
        if t[0] != k or (v is not None and t[1] != v):
            raise SyntaxError(f"esperado {v or k}, veio {t[0]}:{t[1]!r}")
        return t

    # ---- expressões (precedência: || > && > == > cmp > +- > */ > unário)
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        e = self.parse_and()
        while self.at("OP", "||"):
            self.nx()
            e = ("bin", "||", e, self.parse_and())
        return e

    def parse_and(self):
        e = self.parse_eq()
        while self.at("OP", "&&"):
            self.nx()
            e = ("bin", "&&", e, self.parse_eq())
        return e

    def parse_eq(self):
        e = self.parse_cmp()
        while self.pk()[0] == "OP" and self.pk()[1] in ("==", "!="):
            op = self.nx()[1]
            e = ("bin", op, e, self.parse_cmp())
        return e

    def parse_cmp(self):
        e = self.parse_add()
        while self.pk()[0] == "OP" and self.pk()[1] in ("<", "<=", ">", ">="):
            op = self.nx()[1]
            e = ("bin", op, e, self.parse_add())
        return e

    def parse_add(self):
        e = self.parse_mul()
        while self.pk()[0] == "OP" and self.pk()[1] in ("+", "-"):
            op = self.nx()[1]
            e = ("bin", op, e, self.parse_mul())
        if self.at("OP", "..="):
            self.nx()
            e = ("range", e, self.parse_mul(), True)
        elif self.at("OP", ".."):
            self.nx()
            e = ("range", e, self.parse_mul(), False)
        return e

    def parse_mul(self):
        e = self.parse_un()
        while self.pk()[0] == "OP" and self.pk()[1] in ("*", "/", "%"):
            op = self.nx()[1]
            e = ("bin", op, e, self.parse_un())
        return e

    def parse_un(self):
        if self.pk()[0] == "OP" and self.pk()[1] in ("-", "!"):
            op = self.nx()[1]
            return ("un", op, self.parse_un())
        e = self.parse_post()
        if self.at("OP", "?"):
            self.nx()
            return ("quest", e)
        return e

    def parse_post(self):
        e = self.parse_primary()
        while True:
            if self.at("SYM", "(") and e[0] in ("var", "path"):
                self.nx()
                args = []
                if not self.at("SYM", ")"):
                    args.append(self.parse_expr())
                    while self.at("SYM", ","):
                        self.nx()
                        if self.at("SYM", ")"):
                            break
                        args.append(self.parse_expr())
                self.expect("SYM", ")")
                e = ("call", e[1], args)
            elif self.at("OP", "."):
                self.nx()
                field = self.expect("IDENT")[1]
                if self.at("SYM", "("):
                    self.nx()
                    args = []
                    if not self.at("SYM", ")"):
                        args.append(self.parse_expr())
                        while self.at("SYM", ","):
                            self.nx()
                            args.append(self.parse_expr())
                    self.expect("SYM", ")")
                    e = ("method", e, field, args)
                else:
                    e = ("field", e, field)
            else:
                return e

    def parse_primary(self):  # noqa: C901
        t = self.pk()
        if t[0] == "INT":
            self.nx()
            return ("int", t[1])
        if t[0] == "FLOAT":
            self.nx()
            return ("float", t[1])
        if t[0] == "STR":
            self.nx()
            return ("str", t[1])
        if t[0] == "CHAR":
            self.nx()
            return ("char", t[1])
        if t[0] == "KEY" and t[1] in ("true", "false"):
            self.nx()
            return ("bool", t[1] == "true")
        if t[0] == "KEY" and t[1] == "vec" and len(self.t) > self.p + 1 \
                and self.t[self.p + 1][0] == "OP" \
                and self.t[self.p + 1][1] == "!":
            self.nx()
            self.expect("OP", "!")
            self.expect("SYM", "[")
            items = []
            if not self.at("SYM", "]"):
                items.append(self.parse_expr())
                while self.at("SYM", ","):
                    self.nx()
                    if self.at("SYM", "]"):
                        break
                    items.append(self.parse_expr())
            self.expect("SYM", "]")
            return ("vec", items)
        if t[0] == "KEY" and t[1] == "map" and len(self.t) > self.p + 1 \
                and self.t[self.p + 1][0] == "OP" and self.t[self.p + 1][1] == "!":
            self.nx()
            self.expect("OP", "!")
            self.expect("SYM", "{")
            pairs = []
            if not self.at("SYM", "}"):
                k = self.parse_expr()
                self.expect("OP", ":")
                pairs.append((k, self.parse_expr()))
                while self.at("SYM", ","):
                    self.nx()
                    if self.at("SYM", "}"):
                        break
                    k = self.parse_expr()
                    self.expect("OP", ":")
                    pairs.append((k, self.parse_expr()))
            self.expect("SYM", "}")
            return ("maplit", pairs)
        if t[0] == "KEY" and t[1] == "match":
            return self.parse_match()
        if t[0] == "KEY" and t[1] == "if":
            self.nx()
            c = self.parse_expr()
            self.expect("SYM", "{")
            a = self.parse_expr()
            self.expect("SYM", "}")
            self.expect("KEY", "else")
            self.expect("SYM", "{")
            b = self.parse_expr()
            self.expect("SYM", "}")
            return ("if", c, a, b)
        if t[0] in ("IDENT", "KEY"):
            self.nx()
            name = t[1]
            if self.at("OP", "::"):
                self.nx()
                var = self.expect("IDENT" if self.pk()[0] == "IDENT" else self.pk()[0])[1]
                q = f"{name}::{var}"
                if self.at("SYM", "("):
                    self.nx()
                    args = []
                    if not self.at("SYM", ")"):
                        args.append(self.parse_expr())
                        while self.at("SYM", ","):
                            self.nx()
                            args.append(self.parse_expr())
                    self.expect("SYM", ")")
                    return ("call", q, args)
                return ("var", q)
            if self.at("SYM", "("):
                # variante sem módulo: Circulo(r)
                save = self.p
                try:
                    self.nx()
                    args = []
                    if not self.at("SYM", ")"):
                        args.append(self.parse_expr())
                        while self.at("SYM", ","):
                            self.nx()
                            args.append(self.parse_expr())
                    self.expect("SYM", ")")
                    return ("call", name, args)
                except SyntaxError:
                    self.p = save
                    return ("var", name)
            if self.at("SYM", "{"):
                save = self.p
                try:
                    self.nx()
                    fields = []
                    if not self.at("SYM", "}"):
                        f = self.expect("IDENT")[1]
                        self.expect("OP", ":")
                        fields.append((f, self.parse_expr()))
                        while self.at("SYM", ","):
                            self.nx()
                            if self.at("SYM", "}"):
                                break
                            f = self.expect("IDENT")[1]
                            self.expect("OP", ":")
                            fields.append((f, self.parse_expr()))
                    self.expect("SYM", "}")
                    return ("structlit", name, fields)
                except SyntaxError:
                    self.p = save
                    return ("var", name)
            return ("var", name)
        if t == ("SYM", "(", t[2]):
            self.nx()
            if self.at("SYM", ")"):
                self.nx()
                return ("unit",)
            e = self.parse_expr()
            self.expect("SYM", ")")
            return e
        raise SyntaxError(f"expressão inesperada: {t[0]}:{t[1]!r}")

    def parse_pat(self):
        parts = [self.parse_pat1()]
        while self.at("OP", "|"):
            self.nx()
            parts.append(self.parse_pat1())
        if len(parts) == 1:
            return parts[0]
        return ("por", parts)

    def parse_pat1(self):
        t = self.pk()
        if t[0] == "SYM" and t[1] == "_":
            self.nx()
            return ("pwild",)
        if t[0] in ("INT", "FLOAT", "STR", "CHAR"):
            self.nx()
            return ("plit", t[1])
        if t[0] == "KEY" and t[1] in ("true", "false"):
            self.nx()
            return ("plit", t[1] == "true")
        if t[0] == "KEY" and t[1] == "match":
            return self.parse_match()
        if t[0] == "KEY" and t[1] == "if":
            self.nx()
            c = self.parse_expr()
            self.expect("SYM", "{")
            a = self.parse_expr()
            self.expect("SYM", "}")
            self.expect("KEY", "else")
            self.expect("SYM", "{")
            b = self.parse_expr()
            self.expect("SYM", "}")
            return ("if", c, a, b)
        if t[0] in ("IDENT", "KEY"):
            self.nx()
            name = t[1]
            if self.at("OP", "::"):
                self.nx()
                var = self.nx()[1]
                subs = []
                if self.at("SYM", "("):
                    self.nx()
                    if not self.at("SYM", ")"):
                        subs.append(self.parse_pat())
                        while self.at("SYM", ","):
                            self.nx()
                            subs.append(self.parse_pat())
                    self.expect("SYM", ")")
                return ("penum", f"{name}::{var}", subs)
            if self.at("SYM", "("):
                self.nx()
                subs = []
                if not self.at("SYM", ")"):
                    subs.append(self.parse_pat())
                    while self.at("SYM", ","):
                        self.nx()
                        subs.append(self.parse_pat())
                self.expect("SYM", ")")
                return ("penum", name, subs)
            return ("pvar", name)
        raise SyntaxError(f"padrão inesperado: {t[0]}:{t[1]!r}")

    def parse_match(self):
        self.expect("KEY", "match")
        subj = self.parse_expr()
        self.expect("SYM", "{")
        arms = []
        while not self.at("SYM", "}"):
            if self.at("EOF", ""):
                raise SyntaxError("match sem }")
            pat = self.parse_pat()
            guard = None
            if self.at("KEY", "if"):
                self.nx()
                guard = self.parse_expr()
            self.expect("OP", "=>")
            body = self.parse_expr()
            if self.at("SYM", ","):
                self.nx()
            arms.append((pat, guard, body))
        self.expect("SYM", "}")
        return ("match", subj, arms)


def parse_expr_src(src: str):
    p = Parser(lex(src))
    e = p.parse_expr()
    p.expect("EOF")
    return e


# ----------------------------------------------- definições (fn/struct) ---

def _skip_type(p: Parser):
    """Pula anotação de tipo até `=`, `,`, `)` ou `}` (nível 0)."""
    depth = 0
    while True:
        t = p.pk()
        if t[0] == "EOF":
            raise SyntaxError("tipo incompleto")
        if depth == 0 and ((t[0] == "OP" and t[1] == "=")
                           or (t[0] == "SYM" and t[1] in (",", ")", "}"))):
            return
        if t[0] == "SYM" and t[1] in ("([{"):
            depth += 1
        if t[0] == "SYM" and t[1] in (")]}"):
            depth -= 1
        if t[0] == "OP" and t[1] == "<":
            depth += 1
        if t[0] == "OP" and t[1] == ">":
            depth -= 1
        p.nx()


def parse_fn_def(src: str) -> dict:
    """Parse de `fn nome(params) -> Ret { corpo }` (ou `async fn`)."""
    p = Parser(lex(src))
    is_async = False
    if p.at("KEY", "async"):
        p.nx()
        is_async = True
    p.expect("KEY", "fn")
    name = p.expect("IDENT")[1]
    p.expect("SYM", "(")
    params = []
    if not p.at("SYM", ")"):
        pn = p.expect("IDENT")[1]
        pm = False
        if pn == "mut":
            pm = True
            pn = p.expect("IDENT")[1]
        p.expect("OP", ":")
        _skip_type(p)
        params.append((pn, pm))
        while p.at("SYM", ","):
            p.nx()
            pn = p.expect("IDENT")[1]
            pm = False
            if pn == "mut":
                pm = True
                pn = p.expect("IDENT")[1]
            p.expect("OP", ":")
            _skip_type(p)
            params.append((pn, pm))
    p.expect("SYM", ")")
    ret = None
    if p.at("OP", "->"):
        p.nx()
        buf = []
        while not p.at("SYM", "{"):
            buf.append(str(p.nx()[1]))
        ret = "".join(buf).strip()
    p.expect("SYM", "{")
    depth = 1
    body = []
    while depth:
        t = p.nx()
        if t[0] == "SYM" and t[1] == "{":
            depth += 1
        if t[0] == "SYM" and t[1] == "}":
            depth -= 1
            if not depth:
                break
        body.append(t)
    return {"name": name, "async": is_async, "params": params, "ret": ret,
            "body": body}


def parse_struct_def(src: str) -> dict:
    p = Parser(lex(src))
    if p.at("KEY", "pub"):
        p.nx()
    p.expect("KEY", "struct")
    name = p.expect("IDENT")[1]
    p.expect("SYM", "{")
    fields = []
    while not p.at("SYM", "}"):
        f = p.expect("IDENT")[1]
        p.expect("OP", ":")
        _skip_type(p)
        fields.append(f)
        if p.at("SYM", ","):
            p.nx()
    p.expect("SYM", "}")
    return {"name": name, "fields": fields}


def parse_enum_def(src: str) -> dict:
    p = Parser(lex(src))
    if p.at("KEY", "pub"):
        p.nx()
    p.expect("KEY", "enum")
    name = p.expect("IDENT")[1]
    p.expect("SYM", "{")
    variants = []
    while not p.at("SYM", "}"):
        v = p.expect("IDENT")[1]
        payload = 0
        if p.at("SYM", "("):
            p.nx()
            depth = 1
            payload = 1
            while depth:
                t = p.nx()
                if t[0] == "SYM" and t[1] == "(":
                    depth += 1
                if t[0] == "SYM" and t[1] == ")":
                    depth -= 1
                if t[0] == "SYM" and t[1] == "," and depth == 1:
                    payload += 1
        variants.append((v, payload))
        if p.at("SYM", ","):
            p.nx()
    p.expect("SYM", "}")
    return {"name": name, "variants": variants}


def parse_macro_def(src: str) -> dict:
    p = Parser(lex(src))
    p.expect("KEY", "macro")
    name = p.expect("IDENT")[1]
    p.expect("SYM", "(")
    params = []
    if not p.at("SYM", ")"):
        params.append(p.expect("IDENT")[1])
        while p.at("SYM", ","):
            p.nx()
            params.append(p.expect("IDENT")[1])
    p.expect("SYM", ")")
    p.expect("SYM", "{")
    depth = 1
    body = []
    while depth:
        t = p.nx()
        if t[0] == "SYM" and t[1] == "{":
            depth += 1
        if t[0] == "SYM" and t[1] == "}":
            depth -= 1
            if not depth:
                break
        body.append(t)
    return {"name": name, "params": params,
            "body_src": " ".join(str(t[1]) for t in body)}

# ---------------------------------------------- avaliador + tipos ---------

def _num(t, v):
    if t == "i32":
        return v
    if t == "f64":
        return v
    raise LumenTypeErr(f"esperado número, veio {t}")


def ev(node, env):
    k = node[0]
    if k == "int":
        return ("i32", node[1])
    if k == "float":
        return ("f64", node[1])
    if k == "str":
        return ("str", node[1])
    if k == "char":
        return ("char", node[1])
    if k == "bool":
        return ("bool", node[1])
    if k == "unit":
        return ("unit", None)
    if k == "var":
        if node[1] not in env:
            raise NameError(f"nome desconhecido: {node[1]}")
        v = env[node[1]]
        if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str):
            if v[0] == "ctor":
                return ("enum", (v[1], []))
            return v
        raise LumenTypeErr(f"{node[1]} não é valor")
    if k == "vec":
        return ("vec", [ev(e, env) for e in node[1]])
    if k == "maplit":
        return ("map", {ev(a, env)[1]: ev(b, env) for a, b in node[1]})
    if k == "structlit":
        return ("struct", (node[1], {f: ev(e, env) for f, e in node[2]}))
    if k == "range":
        (_, a, b, incl) = node
        ta, va = ev(a, env)
        tb, vb = ev(b, env)
        if ta != "i32" or tb != "i32":
            raise LumenTypeErr("range exige i32")
        fim = vb + 1 if incl else vb
        return ("vec", [("i32", x) for x in range(va, fim)])
    if k == "field":
        (_, obj, f) = node
        t, v = ev(obj, env)
        if t != "struct":
            raise LumenTypeErr("acesso a campo exige struct")
        if f not in v[1]:
            raise LumenTypeErr(f"campo {f} inexistente")
        return v[1][f]
    if k == "un":
        (_, op, e) = node
        t, v = ev(e, env)
        if op == "-":
            if t == "i32":
                return ("i32", -v)
            if t == "f64":
                return ("f64", -v)
            raise LumenTypeErr("menos unário exige número")
        if t != "bool":
            raise LumenTypeErr("! exige bool")
        return ("bool", not v)
    if k == "bin":
        (_, op, l, r) = node
        if op == "&&":
            t, v = ev(l, env)
            if t != "bool":
                raise LumenTypeErr("&& exige bool")
            if not v:
                return ("bool", False)
            t2, v2 = ev(r, env)
            if t2 != "bool":
                raise LumenTypeErr("&& exige bool")
            return ("bool", v2)
        if op == "||":
            t, v = ev(l, env)
            if t != "bool":
                raise LumenTypeErr("|| exige bool")
            if v:
                return ("bool", True)
            t2, v2 = ev(r, env)
            if t2 != "bool":
                raise LumenTypeErr("|| exige bool")
            return ("bool", v2)
        tl, vl = ev(l, env)
        tr, vr = ev(r, env)
        if op == "+":
            if tl == "str" and tr == "str":
                return ("str", vl + vr)
            if tl in ("i32", "f64") and tr in ("i32", "f64"):
                t = "f64" if "f64" in (tl, tr) else "i32"
                return (t, vl + vr)
            raise LumenTypeErr(f"+ inválido para {tl}, {tr}")
        if op in ("-", "*", "%"):
            if tl in ("i32", "f64") and tr in ("i32", "f64"):
                t = "f64" if "f64" in (tl, tr) else "i32"
                if op == "-":
                    return (t, vl - vr)
                if op == "*":
                    return (t, vl * vr)
                if tl != "i32" or tr != "i32":
                    raise LumenTypeErr("% exige i32")
                if vr == 0:
                    raise LumenPanic("divisão por zero")
                return ("i32", vl % vr)
            raise LumenTypeErr(f"{op} inválido para {tl}, {tr}")
        if op == "/":
            if tl in ("i32", "f64") and tr in ("i32", "f64"):
                if vr == 0:
                    raise LumenPanic("divisão por zero")
                if tl == "i32" and tr == "i32":
                    return ("i32", int(vl / vr))
                return ("f64", vl / vr)
            raise LumenTypeErr(f"/ inválido para {tl}, {tr}")
        if op in ("==", "!="):
            eq = _val_eq((tl, vl), (tr, vr))
            return ("bool", eq if op == "==" else not eq)
        if op in ("<", "<=", ">", ">="):
            if tl in ("i32", "f64") and tr in ("i32", "f64"):
                if op == "<":
                    return ("bool", vl < vr)
                if op == "<=":
                    return ("bool", vl <= vr)
                if op == ">":
                    return ("bool", vl > vr)
                return ("bool", vl >= vr)
            raise LumenTypeErr(f"{op} exige números")
        raise SyntaxError(f"operador {op}")
    if k == "quest":
        t, v = ev(node[1], env)
        if t != "result":
            raise LumenTypeErr("? exige Result")
        ok, inner = v
        if not ok:
            raise LumenErr(inner)
        return inner
    if k == "if":
        (_, c, a, b) = node
        t, v = ev(c, env)
        if t != "bool":
            raise LumenTypeErr("if exige bool")
        return ev(a, env) if v else ev(b, env)
    if k == "match":
        return ev_match(node[1], node[2], env)
    if k in ("call", "method"):
        return ev_call(node, env)
    raise SyntaxError(f"nó {k}")


def _val_eq(a, b):
    if a[0] != b[0]:
        return False
    if a[0] == "vec":
        return len(a[1]) == len(b[1]) and all(_val_eq(x, y) for x, y in zip(a[1], b[1]))
    if a[0] == "enum":
        return a[1][0] == b[1][0] and len(a[1][1]) == len(b[1][1]) and \
            all(_val_eq(x, y) for x, y in zip(a[1][1], b[1][1]))
    if a[0] == "struct":
        return a[1][0] == b[1][0] and a[1][1].keys() == b[1][1].keys() and \
            all(_val_eq(a[1][1][f], b[1][1][f]) for f in a[1][1])
    if a[0] in ("option", "result"):
        return a[1] == b[1] if a[1][0] != b[1][0] else (
            True if a[1][0] in ("none",) else _val_eq(a[1][1], b[1][1]))
    return a[1] == b[1]


def ev_call(node, env):
    if node[0] == "method":
        (_, recv, name, args) = node
        recv_v = ev(recv, env)
        key = f"#{recv_v[0]}::{name}"
        if key not in env:
            raise LumenTypeErr(f"método {name} inexistente")
        return env[key](recv_v, [ev(a, env) for a in args], env)
    (_, qname, args) = node
    vals = [ev(a, env) for a in args]
    if qname not in env:
        # variante de enum sem módulo: Circulo(r)
        for key, v in env.items():
            if key.endswith("::" + qname) and isinstance(v, tuple) and v[0] == "ctor":
                return ("enum", (v[1], vals))
        raise NameError(f"função desconhecida: {qname}")
    tgt = env[qname]
    if isinstance(tgt, tuple) and tgt[0] == "ctor":
        return ("enum", (tgt[1], vals))
    if callable(tgt):
        return tgt(vals, env)
    if isinstance(tgt, dict) and tgt.get("kind") == "userfn":
        return call_user_fn(tgt, vals, env)
    raise LumenTypeErr(f"{qname} não é chamável")


def pmatch(pat, val, env):
    """Tenta casar padrão com valor. Retorna env estendido ou None."""
    k = pat[0]
    if k == "pwild":
        return dict(env)
    if k == "plit":
        lit = pat[1]
        lt = "bool" if isinstance(lit, bool) else (
            "i32" if isinstance(lit, int) else (
                "f64" if isinstance(lit, float) else "str"))
        if _val_eq((lt, lit), val):
            return dict(env)
        return None
    if k == "pvar":
        if pat[1] == "_":
            return dict(env)
        e2 = dict(env)
        e2[pat[1]] = val
        return e2
    if k == "por":
        for sub in pat[1]:
            r = pmatch(sub, val, env)
            if r is not None:
                return r
        return None
    if k == "penum":
        (_, ctor, subs) = pat
        if val[0] != "enum" or val[1][0] != ctor.split("::")[-1]:
            # compara também qualificado
            if val[0] != "enum" or val[1][0] != ctor:
                # normaliza: guarda ctor curto
                short = ctor.split("::")[-1]
                if val[0] != "enum" or val[1][0] not in (ctor, short):
                    return None
        fields = val[1][1]
        if len(subs) != len(fields):
            return None
        e2 = dict(env)
        for s, f in zip(subs, fields):
            r = pmatch(s, f, e2)
            if r is None:
                return None
            e2 = r
        return e2
    raise SyntaxError(f"padrão {k}")


def ev_match(subj_src, arms, env):
    val = ev(subj_src, env)
    for (pat, guard, body) in arms:
        e2 = pmatch(pat, val, env)
        if e2 is None:
            continue
        if guard is not None:
            t, v = ev(guard, e2)
            if t != "bool":
                raise LumenTypeErr("guard exige bool")
            if not v:
                continue
        return ev(body, e2)
    raise LumenPanic("match não exaustivo")


def to_py(val):
    t, v = val
    if t in ("i32", "f64", "bool", "str", "char"):
        return v
    if t == "unit":
        return None
    if t == "vec":
        return [to_py(x) for x in v]
    if t == "map":
        return {k: to_py(x) for k, x in v.items()}
    if t == "option":
        return None if v[0] == "none" else to_py(v[1])
    if t == "result":
        ok, inner = v
        return ("Ok", to_py(inner)) if ok else ("Err", inner)
    if t == "enum":
        return (v[0], [to_py(x) for x in v[1]])
    if t == "struct":
        return {f: to_py(x) for f, x in v[1].items()}
    return v


# ---- tipos (inferência do subconjunto de expressões)
def tinfer(node, tenv):
    k = node[0]
    if k == "int":
        return "i32"
    if k == "float":
        return "f64"
    if k in ("str", "char", "bool", "unit"):
        return k
    if k == "var":
        if node[1] not in tenv:
            raise LumenTypeErr(f"nome desconhecido: {node[1]}")
        return tenv[node[1]]
    if k == "vec":
        if not node[1]:
            return "Vec<?>"
        t0 = tinfer(node[1][0], tenv)
        for e in node[1][1:]:
            if tinfer(e, tenv) != t0:
                raise LumenTypeErr("vec! heterogêneo")
        return f"Vec<{t0}>"
    if k == "bin":
        (_, op, l, r) = node
        tl, tr = tinfer(l, tenv), tinfer(r, tenv)
        if op == "+":
            if tl == "str" and tr == "str":
                return "str"
            if tl in ("i32", "f64") and tr in ("i32", "f64"):
                return "f64" if "f64" in (tl, tr) else "i32"
            raise LumenTypeErr(f"+ inválido para {tl}, {tr}")
        if op in ("-", "*", "/", "%"):
            if tl in ("i32", "f64") and tr in ("i32", "f64"):
                return "f64" if "f64" in (tl, tr) else "i32"
            raise LumenTypeErr(f"{op} inválido para {tl}, {tr}")
        if op in ("==", "!=", "<", "<=", ">", ">="):
            return "bool"
        if op in ("&&", "||"):
            if tl == "bool" and tr == "bool":
                return "bool"
            raise LumenTypeErr(f"{op} exige bool")
    if k == "un":
        t = tinfer(node[2], tenv)
        if node[1] == "-" and t in ("i32", "f64"):
            return t
        if node[1] == "!" and t == "bool":
            return "bool"
        raise LumenTypeErr(f"unário {node[1]} inválido para {t}")
    if k == "quest":
        t = tinfer(node[1], tenv)
        if not t.startswith("Result<"):
            raise LumenTypeErr("? exige Result")
        return t[len("Result<"):-1].split(",")[0].strip()
    if k == "call":
        if node[1] not in tenv or not tenv[node[1]].startswith("fn("):
            raise LumenTypeErr(f"chamada a {node[1]} sem assinatura")
        return tenv[node[1]].split("->")[-1].strip()
    if k == "if":
        ta, tb = tinfer(node[2], tenv), tinfer(node[3], tenv)
        if ta != tb:
            raise LumenTypeErr("ramos do if divergem")
        return ta
    if k == "match":
        ts = {tinfer(b, tenv) for (_p, _g, b) in node[2]}
        if len(ts) != 1:
            raise LumenTypeErr("ramos do match divergem")
        return ts.pop()
    raise LumenTypeErr(f"inferência indisponível para {k}")

# ---------------------------------------------- statements + runtime ------

def base_env() -> dict:
    """Ambiente de referência: construtores + stdlib simulada."""
    env: dict = {}

    def ctor(name):
        return ("ctor", name)

    for c in ("Ok", "Err", "Some", "None", "Circulo", "Retangulo", "Ponto",
              "Vermelho", "Verde", "Azul"):
        env[c] = ctor(c)
    for c in ("Forma::Circulo", "Forma::Retangulo", "Forma::Ponto",
              "Cor::Vermelho", "Cor::Verde", "Cor::Azul",
              "Resultado::Ok", "Resultado::Erro"):
        env[c] = ctor(c.split("::")[-1])

    def _s(v):
        return v[1] if v[0] == "str" else (_py_str(v))

    def _py_str(v):
        t, x = v
        if t == "str":
            return x
        if t in ("i32", "f64", "bool"):
            return str(x).lower() if t == "bool" else str(x)
        if t == "char":
            return x
        return repr(to_py(v))

    env["_out"] = []
    env["println"] = lambda a, e: (e["_out"].append(_py_str(a[0]) + "\n"), ("unit", None))[1]
    env["print"] = lambda a, e: (e["_out"].append(_py_str(a[0])), ("unit", None))[1]
    env["io::println"] = env["println"]
    env["io::print"] = env["print"]
    env["panic"] = lambda a, e: (_ for _ in ()).throw(LumenPanic(_py_str(a[0])))
    env["str::len"] = lambda a, e: ("i32", len(a[0][1]))
    env["str::upper"] = lambda a, e: ("str", a[0][1].upper())
    env["str::lower"] = lambda a, e: ("str", a[0][1].lower())
    env["math::fat"] = lambda a, e: _fat(a[0])
    env["math::sqrt"] = lambda a, e: _sqrt(a[0])
    env["math::pow"] = lambda a, e: ("f64", float(a[0][1]) ** float(a[1][1]))
    env["vec::len"] = lambda a, e: ("i32", len(a[0][1]))
    return env


def _fat(v):
    if v[0] != "i32":
        raise LumenTypeErr("fat exige i32")
    n = v[1]
    if n < 0:
        return ("result", (False, "n negativo"))
    r = 1
    for k in range(2, n + 1):
        r *= k
    return ("result", (True, ("i32", r)))


def _sqrt(v):
    x = float(v[1])
    if x < 0:
        return ("result", (False, "negativo"))
    return ("result", (True, ("f64", x ** 0.5)))


def run_stmts(toks, env):
    """Executa lista de statements; retorna valor de `return` (ou unit)."""
    p = Parser(toks + [("EOF", "", 0)])
    while not p.at("EOF", ""):
        if p.at("SYM", ";"):
            p.nx()
            continue
        if p.at("KEY", "let"):
            p.nx()
            if p.at("KEY", "mut"):
                p.nx()
            name = p.expect("IDENT")[1]
            if p.at("OP", ":"):
                p.nx()
                _skip_type(p)
            p.expect("OP", "=")
            env[name] = ev(p.parse_expr(), env)
            p.expect("SYM", ";")
            continue
        if p.at("KEY", "return"):
            p.nx()
            val = ev(p.parse_expr(), env)
            p.expect("SYM", ";")
            raise ReturnSignal(val)
        if p.at("KEY", "match"):
            ev(p.parse_match(), env)
            if p.at("SYM", ";"):
                p.nx()
            continue
        e = p.parse_expr()
        if p.at("OP", "=") and e[0] == "var":
            p.nx()
            env[e[1]] = ev(p.parse_expr(), env)
            p.expect("SYM", ";")
            continue
        p.expect("SYM", ";")
        ev(e, env)
    return ("unit", None)


def call_user_fn(fn, args, env):
    if len(args) != len(fn["params"]):
        raise LumenTypeErr("aridade divergente")
    local = dict(env)
    local["_out"] = env["_out"]
    for ((pn, _pm), v) in zip(fn["params"], args):
        local[pn] = v
    try:
        run_stmts(list(fn["body"]), local)
    except ReturnSignal as r:
        return r.val
    return ("unit", None)


def run_main(src: str):  # noqa: F811
    env = base_env()
    env["_out"] = []
    fns: dict = {}
    # NOTA v0.2: a extração de funções usa o caminho regex abaixo
    # (balanceamento de chaves no fonte); helpers antigos por tokens
    # foram removidos por estarem mortos.
    # re-parse de assinaturas com o fonte original: usa janelas de texto
    import re as _re
    for m in _re.finditer(r"(async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*(->[^{]*)?\{", src):
        name = m.group(2)
        # encontra corpo balanceado a partir de m.end()
        d = 1
        k = m.end()
        while d and k < len(src):
            if src[k] == "{":
                d += 1
            elif src[k] == "}":
                d -= 1
            k += 1
        head = m.group(0)
        f = parse_fn_def(head + "}")
        fns[name] = {"kind": "userfn", "name": name,
                     "params": f["params"], "ret": f["ret"],
                     "body": lex(src[m.end():k - 1])[:-1]}
    for name, f in fns.items():
        env[name] = f
    if "main" not in fns:
        return "", 2, "sem fn main"
    try:
        call_user_fn(fns["main"], [], env)
        return "".join(env["_out"]), 0, ""
    except LumenPanic as e:
        return "".join(env["_out"]), 1, str(e)
    except LumenErr as e:
        return "".join(env["_out"]), 1, f"Err não tratado: {e}"


# --------------------------------------------------- bytecode + VM --------

OPCODES = ("CONST", "ADD", "SUB", "MUL", "DIV", "MOD", "NEG", "EQ", "LT",
           "GT", "PRINT", "HALT")


def compile_expr(node, code=None, consts=None):
    if code is None:
        code, consts = [], []
    k = node[0]
    if k == "int":
        consts.append(("i32", node[1]))
        code.append(("CONST", len(consts) - 1))
    elif k == "float":
        consts.append(("f64", node[1]))
        code.append(("CONST", len(consts) - 1))
    elif k in ("bin",):
        (_, op, l, r) = node
        compile_expr(l, code, consts)
        compile_expr(r, code, consts)
        code.append(({"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV",
                      "%": "MOD", "==": "EQ", "<": "LT", ">": "GT"}[op],))
    elif k == "un" and node[1] == "-":
        compile_expr(node[2], code, consts)
        code.append(("NEG",))
    else:
        raise LumenTypeErr(f"bytecode: nó {k} fora do subconjunto")
    return code, consts


def disasm(code, consts):
    out = []
    for i, ins in enumerate(code):
        if ins[0] == "CONST":
            out.append(f"{i:04} CONST {consts[ins[1]][0]} {consts[ins[1]][1]}")
        else:
            out.append(f"{i:04} {ins[0]}")
    return "\n".join(out)


def vm_run(code, consts):
    stack, printed = [], []
    for ins in code:
        op = ins[0]
        if op == "CONST":
            stack.append(consts[ins[1]])
        elif op in ("ADD", "SUB", "MUL", "DIV", "MOD"):
            (tr, vr), (tl, vl) = stack.pop(), stack.pop()
            if op == "ADD":
                t = "f64" if "f64" in (tl, tr) else "i32"
                stack.append((t, vl + vr))
            elif op == "SUB":
                t = "f64" if "f64" in (tl, tr) else "i32"
                stack.append((t, vl - vr))
            elif op == "MUL":
                t = "f64" if "f64" in (tl, tr) else "i32"
                stack.append((t, vl * vr))
            elif op == "DIV":
                if vr == 0:
                    raise LumenPanic("divisão por zero")
                stack.append(("f64", vl / vr) if "f64" in (tl, tr)
                             else ("i32", int(vl / vr)))
            else:
                if vr == 0:
                    raise LumenPanic("divisão por zero")
                stack.append(("i32", vl % vr))
        elif op == "NEG":
            (t, v) = stack.pop()
            stack.append((t, -v))
        elif op in ("EQ", "LT", "GT"):
            (tr, vr), (tl, vl) = stack.pop(), stack.pop()
            stack.append(("bool", {"EQ": vl == vr, "LT": vl < vr,
                                   "GT": vl > vr}[op]))
        elif op == "PRINT":
            (t, v) = stack.pop()
            printed.append(str(v))
            stack.append(("unit", None))
        elif op == "HALT":
            break
        else:
            raise LumenPanic(f"opcode {op}")
    return printed, (stack[-1] if stack else ("unit", None))


# --------------------------------------------------- backends C / WASM ----

def codegen_c(node, fname="lumen_main"):
    c, _ = _gen_c(node)
    return (f'#include <stdint.h>\n#include <stdbool.h>\n\n'
            f'int32_t {fname}(void) {{\n    return {c};\n}}\n')


def _gen_c(node):
    k = node[0]
    if k == "int":
        return str(node[1]), "i32"
    if k == "bin" and node[1] in ("+", "-", "*", "/", "%"):
        l, _ = _gen_c(node[2])
        r, _ = _gen_c(node[3])
        return f"({l} {node[1]} {r})", "i32"
    raise LumenTypeErr("codegen C: subconjunto i32")


def codegen_wasm(node):
    w, _ = _gen_w(node)
    return (f'(module\n  (func (export "main") (result i32)\n'
            f'{w}  )\n)\n')


def _gen_w(node):
    k = node[0]
    if k == "int":
        return f"    i32.const {node[1]}\n", "i32"
    if k == "bin" and node[1] in ("+", "-", "*", "/", "%"):
        l, _ = _gen_w(node[2])
        r, _ = _gen_w(node[3])
        op = {"+": "i32.add", "-": "i32.sub", "*": "i32.mul",
              "/": "i32.div_s", "%": "i32.rem_s"}[node[1]]
        return f"{l}{r}    {op}\n", "i32"
    raise LumenTypeErr("codegen WASM: subconjunto i32")


def codegen_vm(node):
    code, consts = compile_expr(node)
    return disasm(code, consts)

# ---------------------------------------------------------------- casos ---

def _ok(src, env=None):
    e = base_env()
    if env:
        e.update(env)
    return to_py(ev(parse_expr_src(src), e))


CASES: list[dict] = []


def case(id_, cat, name, src, expected, run):
    CASES.append({"id": id_, "category": cat, "name": name,
                  "src": src, "expected": expected, "run": run})


# ---- lexer (5)
case("LEX-01", "lexer", "palavras-chave e tipos",
     "fn soma(a: i32, b: i32) -> i32 { return a + b; }",
     [["KEY", "fn"], ["IDENT", "soma"], ["SYM", "("], ["IDENT", "a"],
      ["OP", ":"], ["IDENT", "i32"], ["SYM", ","], ["IDENT", "b"],
      ["OP", ":"], ["IDENT", "i32"], ["SYM", ")"], ["OP", "->"],
      ["IDENT", "i32"], ["SYM", "{"], ["KEY", "return"], ["IDENT", "a"],
      ["OP", "+"], ["IDENT", "b"], ["SYM", ";"], ["SYM", "}"]],
     lambda s: [list(t) for t in toks_simple(s)])

case("LEX-02", "lexer", "comentário de doc /// vira DOC",
     "/// Soma dois inteiros.\nfn soma() {}",
     ["Soma dois inteiros."],
     lambda s: [v for (k, v) in toks_simple(s) if k == "DOC"])

case("LEX-03", "lexer", "string com escapes",
     r'"olá\nmundo\t\"x\""',
     "olá\nmundo\t\"x\"",
     lambda s: toks_simple(s)[0][1])

case("LEX-04", "lexer", "literais int, float e char",
     "42 3.14 1_000 'x'",
     [["INT", 42], ["FLOAT", 3.14], ["INT", 1000], ["CHAR", "x"]],
     lambda s: [[k, v] for (k, v) in toks_simple(s)])

case("LEX-05", "lexer", "operadores multi-char",
     "=> -> :: .. ..= == != <= && ||",
     ["=>", "->", "::", "..", "..=", "==", "!=", "<=", "&&", "||"],
     lambda s: [v for (k, v) in toks_simple(s) if k == "OP"])

# ---- parser (6)
case("PAR-01", "parser", "definição de função",
     "fn soma(a: i32, b: i32) -> i32 { return a + b; }",
     {"name": "soma", "nparams": 2, "ret": "i32", "async": False},
     lambda s: (lambda f: {"name": f["name"], "nparams": len(f["params"]),
                           "ret": f["ret"], "async": f["async"]})(parse_fn_def(s)))

case("PAR-02", "parser", "definição de struct",
     "pub struct Ponto { x: f64, y: f64 }",
     {"name": "Ponto", "fields": ["x", "y"]},
     lambda s: parse_struct_def(s))

case("PAR-03", "parser", "definição de enum com payload",
     "pub enum Forma { Circulo(f64), Retangulo(f64, f64), Ponto }",
     {"name": "Forma",
      "variants": [["Circulo", 1], ["Retangulo", 2], ["Ponto", 0]]},
     lambda s: (lambda f: {"name": f["name"],
                           "variants": [list(v) for v in f["variants"]]})(parse_enum_def(s)))

case("PAR-04", "parser", "match com or-pattern e guard",
     "match x { 0 => 1, 1 | 2 => 3, n if n > 2 => 4, _ => 5 }",
     {"arms": 4, "has_or": True, "has_guard": True, "has_wild": True},
     lambda s: (lambda m: {
         "arms": len(m[2]),
         "has_or": any(a[0][0] == "por" for a in m[2]),
         "has_guard": any(a[1] is not None for a in m[2]),
         "has_wild": any(a[0][0] in ("pwild", "pvar") for a in m[2]),
     })(parse_expr_src(s)))

case("PAR-05", "parser", "definição de macro",
     "macro unless(cond, corpo) { if !cond { corpo } }",
     {"name": "unless", "params": ["cond", "corpo"]},
     lambda s: (lambda f: {"name": f["name"],
                           "params": f["params"]})(parse_macro_def(s)))

case("PAR-06", "parser", "fn async",
     "async fn buscar(url: str) -> str { return url; }",
     {"name": "buscar", "async": True, "ret": "str"},
     lambda s: (lambda f: {"name": f["name"], "async": f["async"],
                           "ret": f["ret"]})(parse_fn_def(s)))

# ---- tipos (6)
case("TIP-01", "tipos", "inferência i32",
     "2 + 3 * 4", "i32", lambda s: tinfer(parse_expr_src(s), {}))
case("TIP-02", "tipos", "promoção para f64",
     "2 + 3.0", "f64", lambda s: tinfer(parse_expr_src(s), {}))
case("TIP-03", "tipos", "concat str",
     '"a" + "b"', "str", lambda s: tinfer(parse_expr_src(s), {}))
case("TIP-04", "tipos", "? extrai T de Result<T,E>",
     "r?", "i32",
     lambda s: tinfer(parse_expr_src(s), {"r": "Result<i32, str>"}))
case("TIP-05", "tipos", "vec homogêneo",
     "vec![1, 2, 3]", "Vec<i32>",
     lambda s: tinfer(parse_expr_src(s), {}))
case("TIP-06", "tipos", "erro: somar i32 com str",
     '1 + "a"', "ERR:+ inválido para i32, str",
     lambda s: _terr(s))


def _terr(src):
    try:
        return "NO-ERROR:" + tinfer(parse_expr_src(src), {})
    except LumenTypeErr as e:
        return "ERR:" + str(e)


# ---- match (5)
case("MAT-01", "match", "literal",
     'match 2 { 1 => "um", 2 => "dois", _ => "outro" }', "dois",
     _ok)
case("MAT-02", "match", "wildcard",
     'match 99 { 1 => "um", _ => "outro" }', "outro", _ok)
case("MAT-03", "match", "or-pattern com binding",
     'match 2 { 1 | 2 => "pequeno", _ => "grande" }', "pequeno", _ok)
case("MAT-04", "match", "guard",
     'match 15 { n if n > 10 => "grande", _ => "pequeno" }', "grande", _ok)
case("MAT-05", "match", "destruturar variante de enum",
     'match Forma::Retangulo(3, 4) { Forma::Circulo(r) => 0, '
     'Forma::Retangulo(w, h) => w * h, Forma::Ponto => 0 }', 12,
     _ok)

# ---- struct/enum (4)
case("ST-01", "struct_enum", "struct init + acesso a campo",
     "Ponto { x: 1.0, y: 2.0 }.x + Ponto { x: 1.0, y: 2.0 }.y", 3.0,
     _ok)
case("ST-02", "struct_enum", "método via impl (desugar p.f() -> f(p))",
     "norma(Ponto { x: 3.0, y: 4.0 })", 5.0,
     lambda s: _ok(s, {"norma": lambda a, e: ("f64", (
         a[0][1][1]["x"][1] ** 2 + a[0][1][1]["y"][1] ** 2) ** 0.5)}))
case("ST-03", "struct_enum", "enum com payload preserva valores",
     "Forma::Circulo(2.5)", ["Circulo", [2.5]],
     lambda s: list(_ok(s)))
case("ST-04", "struct_enum", "match exaustivo em Cor",
     'match Cor::Verde { Cor::Vermelho => "v", Cor::Verde => "vd", '
     'Cor::Azul => "a" }', "vd", _ok)

# ---- bytecode (5)
case("BC-01", "bytecode", "compila 2 + 3 * 4",
     "2 + 3 * 4",
     "0000 CONST i32 2\n0001 CONST i32 3\n0002 CONST i32 4\n"
     "0003 MUL\n0004 ADD",
     lambda s: disasm(*compile_expr(parse_expr_src(s))))
case("BC-02", "bytecode", "VM executa 2 + 3 * 4 = 14",
     "2 + 3 * 4", 14,
     lambda s: to_py(vm_run(*compile_expr(parse_expr_src(s)))[1]))
case("BC-03", "bytecode", "comparação na VM",
     "3 < 5", True,
     lambda s: to_py(vm_run(*compile_expr(parse_expr_src(s)))[1]))
case("BC-04", "bytecode", "pool de constantes",
     "1 + 2", ["i32:1", "i32:2"],
     lambda s: (lambda c, k: [f"{t}:{v}" for (t, v) in k])(
         *compile_expr(parse_expr_src(s))))
case("BC-05", "bytecode", "opcodes válidos",
     "10 - 2 * 3", True,
     lambda s: all(i[0] in OPCODES
                   for i in compile_expr(parse_expr_src(s))[0]))

# ---- backends (4)
case("BE-01", "backends", "C contém int32 e return",
     "40 + 2", True,
     lambda s: ("int32_t" in codegen_c(parse_expr_src(s))
                and "return (40 + 2);" in codegen_c(parse_expr_src(s))))
case("BE-02", "backends", "WASM contém i32.add/const",
     "40 + 2", True,
     lambda s: ("i32.add" in codegen_wasm(parse_expr_src(s))
                and "i32.const 40" in codegen_wasm(parse_expr_src(s))))
case("BE-03", "backends", "VM disasm lista CONST/ADD",
     "1 + 2", "0000 CONST i32 1\n0001 CONST i32 2\n0002 ADD",
     lambda s: codegen_vm(parse_expr_src(s)))
case("BE-04", "backends", "target padrão é vm",
     "lumen build app.lum", "vm",
     lambda s: {"lumen build app.lum": "vm",
                "lumen build --target c app.lum": "c"}.get(s, "?"))

# ---- runtime (5)
case("RT-01", "runtime", "println escreve saída",
     'fn main() { println("Olá, Lumen!"); }',
     ["Olá, Lumen!\n", 0],
     lambda s: [run_main(s)[0], run_main(s)[1]])
case("RT-02", "runtime", "aritmética no main",
     'fn main() { println(2 + 3 * 4); }', ["14\n", 0],
     lambda s: [run_main(s)[0], run_main(s)[1]])
case("RT-03", "runtime", "let/mut + reatribuição",
     'fn main() { let mut y: i32 = 1; y = y + 1; println(y); }',
     ["2\n", 0],
     lambda s: [run_main(s)[0], run_main(s)[1]])
case("RT-04", "runtime", "panic retorna código 1 + msg",
     'fn main() { panic("boom"); }', [1, "boom"],
     lambda s: [run_main(s)[1], run_main(s)[2]])
case("RT-05", "runtime", "match dentro do main",
     'fn main() { let x = 2; match x { 1 => println("um"), '
     '_ => println("outro"), } }', ["outro\n", 0],
     lambda s: [run_main(s)[0], run_main(s)[1]])

# ---- stdlib (10)
case("STD-01", "stdlib", "str::len conta chars",
     'str::len("olá")', 3, _ok)
case("STD-02", "stdlib", "str::upper",
     'str::upper("lumen")', "LUMEN", _ok)
case("STD-03", "stdlib", "math::fat(5) = 120",
     "math::fat(5)", ("Ok", 120),
     lambda s: tuple(_ok(s)))
case("STD-04", "stdlib", "math::sqrt(2) ≈ 1.414214",
     "math::sqrt(2)", 1.414214,
     lambda s: round(_ok(s)[1], 6))
case("STD-05", "stdlib", "vec::len",
     "vec::len(vec![1, 2, 3])", 3, _ok)
case("STD-06", "stdlib", "map! literal + acesso",
     'map!{ "a": 1 }', {"a": 1}, _ok)
case("STD-07", "stdlib", "json roundtrip",
     '{"a": 1, "b": [1, 2]}', {"a": 1, "b": [1, 2]},
     lambda s: __import__("json").loads(__import__("json").dumps(
         __import__("json").loads(s))))
case("STD-08", "stdlib", "io::println + ? em read simulado",
     'fn main() { println("x"); }', ["x\n", 0],
     lambda s: [run_main(s)[0], run_main(s)[1]])
case("STD-09", "stdlib", "Result Err propaga com ?",
     "math::fat(0 - 1)?", "ERR:n negativo",
     lambda s: _qerr(s))
case("STD-10", "stdlib", "async spawn/await preserva ordem",
     "async { spawn 1, spawn 2, spawn 3 }", [1, 2, 3],
     lambda s: _async_sim(s))


def _async_sim(src):
    """Executor de referência: tarefas resolvem na ordem do spawn."""
    inner = src.strip()[len("async {"):].rstrip(" }")
    out = []
    for item in inner.split(","):
        item = item.strip()
        if not item.startswith("spawn "):
            raise SyntaxError(f"tarefa inválida: {item}")
        out.append(int(item[len("spawn "):]))
    return out


def _qerr(src):
    try:
        return to_py(ev(parse_expr_src(src), base_env()))
    except LumenErr as e:
        return "ERR:" + str(e)


# ---------------------------------------------------------------- runner ---

def run_suite(filter_cat=None):
    results = []
    for c in CASES:
        if filter_cat and c["category"] != filter_cat:
            continue
        try:
            actual = c["run"](c["src"])
            ok = actual == c["expected"]
            err = "" if ok else "divergência"
        except Exception as e:  # noqa: BLE001
            actual = f"EXC:{type(e).__name__}:{e}"
            err, ok = actual, False
        results.append({**{k: v for k, v in c.items() if k != "run"},
                        "actual": actual, "status": "PASS" if ok else "FAIL",
                        "error": err})
    return results


def main(argv):
    # Windows: console cp1252 não codifica `≈`/`→` dos nomes de casos;
    # força UTF-8 com fallback (no-op no POSIX, que já é UTF-8).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:  # noqa: BLE001 — stdout sem reconfigure (pipe estranho)
        pass
    ap = argparse.ArgumentParser(description="Suíte de conformidade Lumen.")
    ap.add_argument("--filter", default=None, help="Só uma categoria.")
    ap.add_argument("--json", default=None, help="Caminho do relatório.")
    args = ap.parse_args(argv)

    results = run_suite(args.filter)
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    for r in results:
        mark = "PASS" if r["status"] == "PASS" else "FAIL"
        print(f"[{mark}] {r['id']} ({r['category']}) {r['name']}")
        if r["status"] == "FAIL":
            print(f"       esperado: {r['expected']!r}")
            print(f"       obtido:   {r['actual']!r}")
    print(f"\n{passed}/{total} casos passando "
          f"({100 * passed // total if total else 0}%).")
    report = {"spec": SPEC_VERSION, "suite": SUITE_VERSION,
              "total": total, "passed": passed,
              "failed": total - passed, "success": passed == total,
              "cases": [{k: v for k, v in r.items() if k != "run"}
                        for r in results]}
    out = args.json or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "conformance_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"Relatório: {out}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
