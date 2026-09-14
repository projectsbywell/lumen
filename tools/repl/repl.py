#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lumen-repl — REPL interativo do Lumen (Python puro).

* usa lexer/parser/VM do compilador Lumen se disponível em sys.path
  (lumen.compiler / lumen.runtime); senão usa o avaliador embutido
  (lexer próprio + parser recursivo descendente + ambiente com closures);
* autocomplete por prefixo de keywords/builtins/comandos (readline);
* histórico em ~/.lumen/history (respeita LUMEN_HOME);
* entrada multilinha: continua enquanto chaves/parênteses estiverem abertos;
* comandos: :doc <nome>, :help, :vars, :clear, :quit; Ctrl-D sai, Ctrl-C
  limpa a linha atual.

Uso:
  python3 repl.py                 # REPL interativo
  python3 repl.py -c "let x = 2*21" -c "print x"
  python3 repl.py -c "print(1+2)*3"
"""

import os
import sys
import traceback
from pathlib import Path

try:
    import readline
except ImportError:  # pragma: no cover
    readline = None

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# engine: tenta o compilador Lumen, cai para o avaliador embutido
# ---------------------------------------------------------------------------

_ENGINE = None
_ENGINE_NAME = "embed"


class EngineAPI:
    """Interface mínima esperada de um engine: run(src, env) -> valor."""

    def run(self, src, env):  # pragma: no cover - abstrato
        raise NotImplementedError


def _load_compiler_engine():
    """Tenta carregar lexer/parser/VM reais do compilador Lumen."""
    try:
        from lumen.compiler.lexer import tokenize, LexError  # noqa: F401
        from lumen.compiler.parser import Parser                # noqa: F401
        from lumen.runtime.vm import VM                         # noqa: F401

        class _CompilerEngine(EngineAPI):
            name = "compiler"

            def run(self, src, env):
                toks = tokenize(src)
                ast = Parser(toks).parse_program()
                return VM(env).run(ast)

        return _CompilerEngine()
    except Exception:
        return None


def get_engine():
    global _ENGINE, _ENGINE_NAME
    if _ENGINE is not None:
        return _ENGINE
    ce = _load_compiler_engine()
    if ce is not None:
        _ENGINE, _ENGINE_NAME = ce, "compiler"
    else:
        _ENGINE, _ENGINE_NAME = _EmbedEngine(), "embed"
    return _ENGINE


# ===========================================================================
# avaliador embutido (lexer + parser + evaluator)
# ===========================================================================

KEYWORDS = {"let", "print", "if", "else", "while", "for", "in", "def",
            "return", "and", "or", "not", "true", "false", "None"}
BUILTIN_DOCS = {
    "print": "print(a, b, ...) — imprime os valores separados por espaço.",
    "len": "len(x) — tamanho de uma lista ou string.",
    "str": "str(x) — converte para string.",
    "int": "int(x) — converte para inteiro.",
    "float": "float(x) — converte para float.",
    "bool": "bool(x) — converte para booleano.",
    "abs": "abs(x) — valor absoluto.",
    "min": "min(a, b, ...) — menor valor.",
    "max": "max(a, b, ...) — maior valor.",
    "sum": "sum(lista) — soma dos elementos.",
    "range": "range(n) — lista [0..n-1]; range(a, b[, passo]) — intervalo.",
    "input": "input([prompt]) — lê uma linha do usuário.",
    "type": "type(x) — nome do tipo de x.",
    "list": "list(x) — converte para lista.",
}
DOCS = {
    "let": "let <nome> = <expr> — declara uma variável no escopo atual.",
    "print": "print <expr>[, <expr>...] — imprime valores (idem builtin print).",
    "if": "if <cond> { ... } [else { ... }] — condicional.",
    "else": "else { ... } — ramo alternativo do if.",
    "while": "while <cond> { ... } — laço enquanto a condição for verdadeira.",
    "for": "for <nome> in <expr> { ... } — itera sobre uma lista.",
    "def": "def <nome>(<params>) { ... } — define uma função.",
    "return": "return [<expr>] — retorna um valor de uma função.",
    "and": "and — E lógico (curto-circuito).",
    "or": "or — OU lógico (curto-circuito).",
    "not": "not — negação lógica.",
    "true": "true — literal booleano verdadeiro.",
    "false": "false — literal booleano falso.",
    "None": "None — valor nulo.",
    "lumen": "REPL do Lumen. Comandos: :help, :doc <nome>, :vars, :clear, :quit.",
}
DOCS.update(BUILTIN_DOCS)

COMMANDS = (":help", ":doc", ":vars", ":clear", ":quit", ":exit")


class LangError(Exception):
    """Erro de linguagem (lex/parse/execução)."""


# ------------------------------------------------------------------ tokens

class Tok:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind, value, line=0):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Tok({self.kind}, {self.value!r})"


class Lexer:
    def __init__(self, src):
        self.src = src
        self.i = 0
        self.line = 1

    def tokenize(self):
        toks = []
        s = self.src
        n = len(s)
        while self.i < n:
            c = s[self.i]
            if c in " \t\r":
                self.i += 1
            elif c == "\n":
                toks.append(Tok("NEWLINE", None, self.line))
                self.i += 1
                self.line += 1
            elif c == "#":
                while self.i < n and s[self.i] != "\n":
                    self.i += 1
            elif c in "\"'":
                toks.append(self._string(c))
            elif c.isdigit() or (c == "." and self.i + 1 < n
                                 and s[self.i + 1].isdigit()):
                toks.append(self._number())
            elif c.isalpha() or c == "_":
                toks.append(self._ident())
            elif c in "()[]{}.,:+-*/%=<>!":
                toks.append(self._op())
            else:
                raise LangError(f"caractere inesperado {c!r} (linha "
                                f"{self.line})")
        toks.append(Tok("EOF", None, self.line))
        return toks

    def _string(self, quote):
        start = self.i
        self.i += 1
        buf = []
        while self.i < len(self.src):
            c = self.src[self.i]
            if c == "\\" and self.i + 1 < len(self.src):
                nxt = self.src[self.i + 1]
                buf.append({"n": "\n", "t": "\t", "\\": "\\", "'": "'",
                            '"': '"'}.get(nxt, nxt))
                self.i += 2
            elif c == quote:
                self.i += 1
                return Tok("STRING", "".join(buf), self.line)
            elif c == "\n":
                raise LangError("string sem fechamento (linha "
                                f"{self.line})")
            else:
                buf.append(c)
                self.i += 1
        raise LangError(f"string sem fechamento (iniciada na linha "
                        f"{self.line})")

    def _number(self):
        start = self.i
        while self.i < len(self.src) and self.src[self.i].isdigit():
            self.i += 1
        is_float = False
        if self.i < len(self.src) and self.src[self.i] == ".":
            j = self.i + 1
            if j < len(self.src) and self.src[j].isdigit():
                is_float = True
                self.i = j
                while self.i < len(self.src) and self.src[self.i].isdigit():
                    self.i += 1
        text = self.src[start:self.i]
        return Tok("FLOAT" if is_float else "INT",
                   float(text) if is_float else int(text), self.line)

    def _ident(self):
        start = self.i
        while self.i < len(self.src) and \
                (self.src[self.i].isalnum() or self.src[self.i] == "_"):
            self.i += 1
        word = self.src[start:self.i]
        return Tok("IDENT", word, self.line)

    def _op(self):
        two = self.src[self.i:self.i + 2]
        if two in ("==", "!=", "<=", ">=", "//", "**"):
            self.i += 2
            return Tok("OP", two, self.line)
        c = self.src[self.i]
        self.i += 1
        return Tok("OP", c, self.line)


# ------------------------------------------------------------------ parser

class Node:
    __slots__ = ("kind", "value")

    def __init__(self, kind, value):
        self.kind = kind
        self.value = value

    def __repr__(self):
        return f"Node({self.kind}, {self.value!r})"


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.pos = 0

    def peek(self):
        return self.toks[self.pos]

    def next(self):
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def expect(self, kind, value=None):
        t = self.next()
        if t.kind != kind or (value is not None and t.value != value):
            raise LangError(f"esperado {value or kind}, recebido "
                            f"{t.value!r} (linha {t.line})")
        return t

    def skip_newlines(self):
        while self.peek().kind == "NEWLINE":
            self.pos += 1

    # ---- statements -------------------------------------------------------
    def parse_program(self):
        stmts = []
        self.skip_newlines()
        while self.peek().kind != "EOF":
            stmts.append(self.parse_stmt())
            self.skip_newlines()
        return Node("PROGRAM", stmts)

    def parse_stmt(self):
        t = self.peek()
        if t.kind == "IDENT":
            if t.value == "let":
                return self._stmt_let()
            if t.value == "print":
                return self._stmt_print()
            if t.value == "if":
                return self._stmt_if()
            if t.value == "while":
                return self._stmt_while()
            if t.value == "for":
                return self._stmt_for()
            if t.value == "def":
                return self._stmt_def()
            if t.value == "return":
                return self._stmt_return()
            # atribuição: IDENT '=' expr
            if t.value not in KEYWORDS:
                save = self.pos
                self.next()
                if self.peek().kind == "OP" and self.peek().value == "=":
                    self.next()
                    rhs = self.parse_expr()
                    return Node("ASSIGN", (t.value, rhs))
                self.pos = save
        if t.kind == "OP" and t.value == "{":
            return self.parse_block()
        self.pos = save_pos = self.pos
        expr = self.parse_expr()
        return Node("EXPR", expr)

    def _stmt_let(self):
        self.next()  # let
        name = self.expect("IDENT").value
        self.expect("OP", "=")
        return Node("LET", (name, self.parse_expr()))

    def _stmt_print(self):
        self.next()  # print
        if self.peek().kind == "OP" and self.peek().value == "(":
            # print(a, b, ...) — forma parentizada
            self.next()
            args = []
            if not (self.peek().kind == "OP" and self.peek().value == ")"):
                while True:
                    args.append(self.parse_expr())
                    if self.peek().kind == "OP" and self.peek().value == ",":
                        self.next()
                        continue
                    break
            self.expect("OP", ")")
        else:
            args = [self.parse_expr()]
            while self.peek().kind == "OP" and self.peek().value == ",":
                self.next()
                args.append(self.parse_expr())
        return Node("PRINT", args)

    def _stmt_if(self):
        self.next()  # if
        cond = self.parse_expr()
        then = self.parse_block()
        node = Node("IF", (cond, then, None))
        t = self.peek()
        if t.kind == "IDENT" and t.value == "else":
            self.next()
            if self.peek().kind == "IDENT" and self.peek().value == "if":
                node.value = (cond, then,
                              Node("IF", self._stmt_if().value))
            else:
                node.value = (cond, then, self.parse_block())
        return node

    def _stmt_while(self):
        self.next()  # while
        cond = self.parse_expr()
        return Node("WHILE", (cond, self.parse_block()))

    def _stmt_for(self):
        self.next()  # for
        name = self.expect("IDENT").value
        self.expect("IDENT", "in")
        seq = self.parse_expr()
        return Node("FOR", (name, seq, self.parse_block()))

    def _stmt_def(self):
        self.next()  # def
        name = self.expect("IDENT").value
        self.expect("OP", "(")
        params = []
        if self.peek().kind != "OP" or self.peek().value != ")":
            while True:
                params.append(self.expect("IDENT").value)
                if self.peek().kind == "OP" and self.peek().value == ",":
                    self.next()
                    continue
                break
        self.expect("OP", ")")
        body = self.parse_block()
        return Node("DEF", (name, params, body))

    def _stmt_return(self):
        self.next()  # return
        if self.peek().kind in ("NEWLINE", "EOF", "RBRACE") or \
                (self.peek().kind == "OP" and self.peek().value == "}"):
            return Node("RETURN", None)
        return Node("RETURN", self.parse_expr())

    def parse_block(self):
        self.expect("OP", "{")
        stmts = []
        self.skip_newlines()
        while not (self.peek().kind == "OP" and self.peek().value == "}"):
            if self.peek().kind == "EOF":
                raise LangError("bloco sem fechamento (falta '}')")
            stmts.append(self.parse_stmt())
            self.skip_newlines()
        self.next()  # }
        return Node("BLOCK", stmts)

    def _ifexpr(self):
        """if-expressão: if <cond> { a } [else { b }] — devolve valor.
        O token 'if' já foi consumido por _atom."""
        cond = self.parse_expr()
        then = self.parse_block()
        node = Node("IFEXPR", (cond, then, None))
        nxt = self.peek()
        if nxt.kind == "IDENT" and nxt.value == "else":
            self.next()
            if self.peek().kind == "IDENT" and self.peek().value == "if":
                node.value = (cond, then,
                              Node("IFEXPR", self._ifexpr().value))
            else:
                node.value = (cond, then, self.parse_block())
        return node

    # ---- expressões (Pratt com precedência) ------------------------------
    def parse_expr(self):
        return self._or()

    def _or(self):
        left = self._and()
        while self.peek().kind == "IDENT" and self.peek().value == "or":
            self.next()
            left = Node("BINOP", ("or", left, self._and()))
        return left

    def _and(self):
        left = self._not()
        while self.peek().kind == "IDENT" and self.peek().value == "and":
            self.next()
            left = Node("BINOP", ("and", left, self._not()))
        return left

    def _not(self):
        if self.peek().kind == "IDENT" and self.peek().value == "not":
            self.next()
            return Node("NOT", self._not())
        return self._compare()

    def _compare(self):
        left = self._add()
        ops = {"==", "!=", "<", "<=", ">", ">="}
        while self.peek().kind == "OP" and self.peek().value in ops:
            op = self.next().value
            right = self._add()
            left = Node("CMP", (op, left, right))
        return left

    def _add(self):
        left = self._mul()
        while self.peek().kind == "OP" and self.peek().value in ("+", "-"):
            op = self.next().value
            left = Node("BINOP", (op, left, self._mul()))
        return left

    def _mul(self):
        left = self._unary()
        while self.peek().kind == "OP" and \
                self.peek().value in ("*", "/", "//", "%"):
            op = self.next().value
            left = Node("BINOP", (op, left, self._unary()))
        return left

    def _unary(self):
        if self.peek().kind == "OP" and self.peek().value in ("-", "+"):
            op = self.next().value
            return Node("UNARY", (op, self._unary()))
        return self._power()

    def _power(self):
        left = self._atom()
        while self.peek().kind == "OP" and self.peek().value == "**":
            self.next()
            left = Node("BINOP", ("**", left, self._unary()))
        return left

    def _atom(self):
        t = self.next()
        if t.kind in ("INT", "FLOAT"):
            return Node("NUM", t.value)
        if t.kind == "STRING":
            return Node("STR", t.value)
        if t.kind == "IDENT" and t.value == "if":
            return self._ifexpr()
        if t.kind == "IDENT":
            if t.value == "true":
                return Node("NUM", True)
            if t.value == "false":
                return Node("NUM", False)
            if t.value == "None":
                return Node("NUM", None)
            node = Node("NAME", t.value)
        elif t.kind == "OP" and t.value == "(":
            node = self.parse_expr()
            self.expect("OP", ")")
        elif t.kind == "OP" and t.value == "[":
            items = []
            if not (self.peek().kind == "OP" and self.peek().value == "]"):
                while True:
                    items.append(self.parse_expr())
                    if self.peek().kind == "OP" and self.peek().value == ",":
                        self.next()
                        continue
                    break
            self.expect("OP", "]")
            node = Node("LIST", items)
        else:
            raise LangError(f"expressão inesperada: {t.value!r} "
                            f"(linha {t.line})")
        # chamada de função
        while self.peek().kind == "OP" and self.peek().value == "(":
            self.next()
            args = []
            if not (self.peek().kind == "OP" and self.peek().value == ")"):
                while True:
                    args.append(self.parse_expr())
                    if self.peek().kind == "OP" and self.peek().value == ",":
                        self.next()
                        continue
                    break
            self.expect("OP", ")")
            node = Node("CALL", (node, args))
        # indexação
        while self.peek().kind == "OP" and self.peek().value == "[":
            self.next()
            idx = self.parse_expr()
            self.expect("OP", "]")
            node = Node("INDEX", (node, idx))
        return node


# ------------------------------------------------------------------ evaluator

class Env:
    """Ambiente com encadeamento para closures."""

    def __init__(self, parent=None):
        self.parent = parent
        self.vars = {}

    def has(self, name):
        e = self
        while e is not None:
            if name in e.vars:
                return True
            e = e.parent
        return False

    def get(self, name):
        e = self
        while e is not None:
            if name in e.vars:
                return e.vars[name]
            e = e.parent
        raise LangError(f"nome indefinido: {name}")

    def set_local(self, name, value):
        self.vars[name] = value

    def assign(self, name, value):
        e = self
        while e is not None:
            if name in e.vars:
                e.vars[name] = value
                return
            e = e.parent
        raise LangError(f"nome indefinido (use let): {name}")

    def locals_sorted(self):
        return sorted(self.vars.items())


class _ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class _UserFun:
    def __init__(self, name, params, body, env):
        self.name = name
        self.params = params
        self.body = body
        self.env = env

    def __repr__(self):
        return f"<função {self.name}({', '.join(self.params)})>"


class Builtin:
    def __init__(self, name, fn, doc):
        self.name = name
        self.fn = fn
        self.doc = doc

    def __repr__(self):
        return f"<builtin {self.name}>"

    def __call__(self, *args):
        return self.fn(*args)


def _truthy(v):
    if v is None or v is False:
        return False
    if v == 0:
        return False
    if isinstance(v, str) and v == "":
        return False
    if isinstance(v, list) and not v:
        return False
    return True


class Evaluator:
    def __init__(self, env, out=None):
        self.env = env
        self.out = out or sys.stdout

    def eval(self, node):
        n = node.kind
        v = node.value
        if n == "PROGRAM":
            last = None
            for st in v:
                last = self.eval(st)
            return last
        if n == "EXPR":
            return self.eval(v)
        if n == "NUM":
            return v
        if n == "STR":
            return v
        if n == "LIST":
            return [self.eval(x) for x in v]
        if n == "NAME":
            return self.env.get(v)
        if n == "UNARY":
            op, e = v
            x = self.eval(e)
            if op == "-":
                return -x
            if op == "+":
                return +x
            raise LangError(f"operador unário inválido: {op}")
        if n == "NOT":
            return not _truthy(self.eval(v))
        if n == "BINOP":
            op, a, b = v
            if op == "and":
                x = self.eval(a)
                return x if not _truthy(x) else self.eval(b)
            if op == "or":
                x = self.eval(a)
                return x if _truthy(x) else self.eval(b)
            x, y = self.eval(a), self.eval(b)
            return self._arith(op, x, y)
        if n == "CMP":
            op, a, b = v
            x, y = self.eval(a), self.eval(b)
            if op == "==":
                return x == y
            if op == "!=":
                return x != y
            if type(x) is not type(y) and not isinstance(x, (int, float)) \
                    or (isinstance(x, (int, float)) and
                        not isinstance(y, (int, float))):
                raise LangError(f"comparação entre tipos incompatíveis: "
                                f"{type(x).__name__} vs {type(y).__name__}")
            if op == "<":
                return x < y
            if op == "<=":
                return x <= y
            if op == ">":
                return x > y
            if op == ">=":
                return x >= y
            raise LangError(f"comparador inválido: {op}")
        if n == "LET":
            name, expr = v
            self.env.set_local(name, self.eval(expr))
            return None
        if n == "ASSIGN":
            name, expr = v
            self.env.assign(name, self.eval(expr))
            return None
        if n == "PRINT":
            vals = [self.eval(a) for a in v]
            print(*[self._fmt(x) for x in vals], file=self.out)
            return None
        if n == "BLOCK":
            last = None
            for st in v:
                last = self.eval(st)
            return last
        if n == "IF":
            cond, then, otherwise = v
            if _truthy(self.eval(cond)):
                return self.eval(then)
            if otherwise is not None:
                return self.eval(otherwise)
            return None
        if n == "IFEXPR":
            cond, then, otherwise = v
            if _truthy(self.eval(cond)):
                return self.eval(then)
            if otherwise is not None:
                return self.eval(otherwise)
            return None
        if n == "WHILE":
            cond, body = v
            while _truthy(self.eval(cond)):
                self.eval(body)
            return None
        if n == "FOR":
            name, seq_expr, body = v
            seq = self.eval(seq_expr)
            if not isinstance(seq, (list, str)):
                raise LangError("for só itera sobre lista ou string")
            for item in seq:
                self.env.set_local(name, item)
                self.eval(body)
            return None
        if n == "DEF":
            name, params, body = v
            self.env.set_local(name, _UserFun(name, params, body, self.env))
            return None
        if n == "RETURN":
            raise _ReturnSignal(None if v is None else self.eval(v))
        if n == "CALL":
            callee, args = v
            fn = self.eval(callee)
            argv = [self.eval(a) for a in args]
            return self._call(fn, argv)
        if n == "INDEX":
            target, idx = v
            t = self.eval(target)
            i = self.eval(idx)
            try:
                return t[i]
            except (IndexError, TypeError, KeyError) as e:
                raise LangError(f"indexação falhou: {e}")
        raise LangError(f"nó desconhecido: {n}")

    def _arith(self, op, x, y):
        if op == "+":
            if isinstance(x, str) and isinstance(y, str):
                return x + y
            if isinstance(x, list) and isinstance(y, list):
                return x + y
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                return x + y
            raise LangError(f"'+' entre tipos incompatíveis: "
                            f"{type(x).__name__}, {type(y).__name__}")
        if op == "*":
            if isinstance(x, str) and isinstance(y, int):
                return x * y
            if isinstance(x, int) and isinstance(y, str):
                return y * x
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise LangError(f"'{op}' exige números, recebidos "
                            f"{type(x).__name__}, {type(y).__name__}")
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            if y == 0:
                raise LangError("divisão por zero")
            return x / y
        if op == "//":
            if y == 0:
                raise LangError("divisão por zero")
            return x // y
        if op == "%":
            if y == 0:
                raise LangError("divisão por zero")
            return x % y
        if op == "**":
            return x ** y
        raise LangError(f"operador inválido: {op}")

    def _call(self, fn, args):
        if isinstance(fn, Builtin):
            try:
                return fn(*args)
            except LangError:
                raise
            except Exception as e:
                raise LangError(f"builtin {fn.name} falhou: {e}")
        if isinstance(fn, _UserFun):
            env = Env(fn.env)
            if len(args) != len(fn.params):
                raise LangError(
                    f"{fn.name} espera {len(fn.params)} argumento(s), "
                    f"recebeu {len(args)}")
            for p, a in zip(fn.params, args):
                env.set_local(p, a)
            try:
                return self.eval_block_for_fun(fn.body, env)
            except _ReturnSignal as r:
                return r.value
        raise LangError(f"{fn!r} não é chamável")

    def eval_block_for_fun(self, body, env):
        old = self.env
        self.env = env
        try:
            last = None
            for st in body.value if body.kind == "BLOCK" else body:
                last = self.eval(st)
            return last
        finally:
            self.env = old

    @staticmethod
    def _fmt(x):
        if x is None:
            return "None"
        if x is True:
            return "true"
        if x is False:
            return "false"
        if isinstance(x, str):
            return x
        if isinstance(x, list):
            return "[" + ", ".join(Evaluator._fmt(i) for i in x) + "]"
        return str(x)


def _mk_builtins():
    def _range(*a):
        if len(a) == 1:
            return list(range(a[0]))
        if len(a) == 2:
            return list(range(a[0], a[1]))
        if len(a) == 3:
            return list(range(a[0], a[1], a[2]))
        raise LangError("range espera 1..3 argumentos")

    bins = [
        Builtin("print", lambda *a: print(*a), BUILTIN_DOCS["print"]),
        Builtin("len", len, BUILTIN_DOCS["len"]),
        Builtin("str", str, BUILTIN_DOCS["str"]),
        Builtin("int", int, BUILTIN_DOCS["int"]),
        Builtin("float", float, BUILTIN_DOCS["float"]),
        Builtin("bool", bool, BUILTIN_DOCS["bool"]),
        Builtin("abs", abs, BUILTIN_DOCS["abs"]),
        Builtin("min", min, BUILTIN_DOCS["min"]),
        Builtin("max", max, BUILTIN_DOCS["max"]),
        Builtin("sum", sum, BUILTIN_DOCS["sum"]),
        Builtin("range", _range, BUILTIN_DOCS["range"]),
        Builtin("input", input, BUILTIN_DOCS["input"]),
        Builtin("type", lambda x: type(x).__name__, BUILTIN_DOCS["type"]),
        Builtin("list", list, BUILTIN_DOCS["list"]),
    ]
    return {b.name: b for b in bins}


class _EmbedEngine(EngineAPI):
    name = "embed"

    def __init__(self):
        self.builtins = _mk_builtins()

    def new_env(self):
        env = Env()
        for k, v in self.builtins.items():
            env.set_local(k, v)
        return env

    def run(self, src, env=None, out=None):
        """Executa um source; retorna o valor da última expressão."""
        if env is None:
            env = self.new_env()
        try:
            toks = Lexer(src).tokenize()
        except LangError:
            raise
        ast = Parser(toks).parse_program()
        ev = Evaluator(env, out=out)
        return ev.eval(ast), env


def run_source(src, env=None, out=None, engine=None):
    """Interface pública: retorna (valor, env) após executar `src`."""
    eng = engine or get_engine()
    if isinstance(eng, _EmbedEngine):
        return eng.run(src, env=env, out=out)
    value = eng.run(src, env if env is not None else {})
    return value, env


# ===========================================================================
# autocomplete / histórico / multilinha
# ===========================================================================

def _completion_words(env):
    words = set(KEYWORDS) | set(BUILTIN_DOCS) | {"lumen", "def", "let"}
    if hasattr(env, "vars"):
        words |= set(env.vars.keys())
    elif isinstance(env, dict):
        words |= set(env.keys())
    return sorted(words)


def _setup_readline(env, history_path):
    if readline is None:  # pragma: no cover
        return False
    try:
        readline.set_completer(_make_completer(env))
        readline.set_completer_delims(" \t\n()[]{}.,:+-*/%=<>!\"'`")
        readline.parse_and_bind("tab: complete")
        if history_path.is_file():
            readline.read_history_file(str(history_path))
    except Exception:
        return False
    return True


def _make_completer(env):
    def completer(text, state):
        words = _completion_words(env)
        if text.startswith(":"):
            candidates = [c for c in COMMANDS if c.startswith(text)]
        else:
            candidates = [w for w in words
                          if w.startswith(text) and not w.startswith(":")]
        if state < len(candidates):
            return candidates[state]
        return None
    return completer


def _balanced(src):
    """True se chaves/parênteses/colchetes e strings estão balanceados."""
    stack = []
    i, n = 0, len(src)
    quote = None
    while i < n:
        c = src[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
        elif c == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue
        elif c in "([{":
            stack.append(c)
        elif c in ")]}":
            if not stack or \
                    {"(": ")", "[": "]", "{": "}"}[stack.pop()] != c:
                return True  # imbalance → deixa o avaliador reportar
        i += 1
    return not stack and quote is None


def _print_value(v):
    if v is None:
        return
    if v is True:
        print("true")
    elif v is False:
        print("false")
    elif isinstance(v, list):
        print("[" + ", ".join(_fmt_val(x) for x in v) + "]")
    elif isinstance(v, str):
        print(v)
    else:
        print(v)


def _fmt_val(x):
    if x is True:
        return "true"
    if x is False:
        return "false"
    if x is None:
        return "None"
    if isinstance(x, str):
        return repr(x)
    return str(x)


# ===========================================================================
# REPL
# ===========================================================================

def _history_path():
    return Path(os.environ.get("LUMEN_HOME", str(Path.home() / ".lumen"))) \
        / "history"


def handle_command(line, env, engine, out=None):
    parts = line.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    out = out or sys.stdout

    def p(*a):
        print(*a, file=out)

    if cmd in (":quit", ":exit"):
        raise SystemExit(0)
    if cmd == ":help":
        p("REPL do Lumen. Comandos:")
        for c in COMMANDS:
            p(f"  {c}")
        p("  palavras-chave: " + ", ".join(KEYWORDS))
        p("  builtins: " + ", ".join(sorted(BUILTIN_DOCS)))
        p("  Ctrl-D sai; Ctrl-C limpa a linha; multilinha com { }")
        return True
    if cmd == ":doc":
        if not arg:
            p("uso: :doc <nome>  (ex.: :doc def, :doc print, :doc let)")
            return True
        name = arg.strip()
        doc = DOCS.get(name)
        if doc is None:
            # função definida pelo usuário?
            try:
                v = env.get(name)
                p(f"  {name} = {v!r}")
                return True
            except LangError:
                p(f"sem documentação para {name!r}")
                return True
        p(f"  {name}: {doc}")
        return True
    if cmd == ":vars":
        if hasattr(env, "locals_sorted"):
            items = env.locals_sorted()
        elif isinstance(env, dict):
            items = sorted(env.items())
        else:
            items = []
        for k, v in items:
            p(f"  {k} = {_fmt_val(v)}")
        return True
    if cmd == ":clear":
        return True  # limpa o buffer multilinha (lida pelo loop)
    p(f"comando desconhecido: {cmd}  (:help para a lista)")
    return True


def repl_loop(engine, env, history_path, stdin=None, stdout=None,
              quiet=False):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    def p(*a, **kw):
        print(*a, file=stdout, **kw)

    if not quiet:
        p(f"lumen-repl {__version__} (engine: {getattr(engine, 'name', '?')}) "
          f"— :help para ajuda, :quit para sair")

    history_on = _setup_readline(env, history_path)
    buffer = []
    try:
        while True:
            prompt = "... " if buffer else "lumen> "
            try:
                line = stdin.readline() if _is_pipe(stdin) else input(prompt)
            except EOFError:
                p()
                break
            except KeyboardInterrupt:
                p("^C")
                buffer = []
                continue
            if line is None or line == "":
                if _is_pipe(stdin):
                    # stdin não interativo: processa o que sobrou e sai
                    break
                p()
                break
            line = line.rstrip("\n")
            if not line.strip():
                continue
            stripped = line.lstrip()
            if stripped.startswith(":") and not buffer:
                try:
                    if handle_command(line, env, engine, out=stdout):
                        if stripped == ":clear":
                            buffer = []
                        continue
                except SystemExit:
                    raise
                continue
            buffer.append(line)
            src = "\n".join(buffer)
            if not _balanced(src):
                continue
            buffer = []
            if not src.strip() or src.strip().startswith("#"):
                continue
            if history_on and readline:
                readline.add_history(src)
            try:
                value, env = engine.run(src, env)
                _print_value(value)
            except KeyboardInterrupt:
                p("^C (execução cancelada)")
            except LangError as e:
                p(f"erro: {e}")
            except _ReturnSignal as r:
                _print_value(r.value)
            except Exception as e:  # pragma: no cover - segurança
                p(f"erro interno: {type(e).__name__}: {e}")
                if os.environ.get("LUMEN_REPL_DEBUG"):
                    traceback.print_exc(file=stdout)
    except SystemExit:
        pass
    finally:
        if history_on and readline and history_path:
            try:
                history_path.parent.mkdir(parents=True, exist_ok=True)
                readline.write_history_file(str(history_path))
            except OSError:
                pass


def _is_pipe(stream):
    try:
        return not stream.isatty()
    except Exception:
        return False


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="repl.py",
                                 description="REPL interativo do Lumen")
    ap.add_argument("-c", "--command", action="append", default=[],
                    help="executa um comando e sai (pode repetir)")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="não imprime banner")
    ap.add_argument("--engine", choices=("auto", "embed", "compiler"),
                    default="auto")
    args = ap.parse_args(argv)

    if args.engine == "embed":
        global _ENGINE, _ENGINE_NAME
        _ENGINE = _EmbedEngine()
        _ENGINE_NAME = "embed"
    engine = get_engine()

    if args.command:
        env = engine.new_env() if hasattr(engine, "new_env") else {}
        for src in args.command:
            try:
                value, env = engine.run(src, env)
                _print_value(value)
            except LangError as e:
                print(f"erro: {e}", file=sys.stderr)
                return 1
            except _ReturnSignal as r:
                _print_value(r.value)
        return 0

    env = engine.new_env() if hasattr(engine, "new_env") else {}
    repl_loop(engine, env, _history_path(), quiet=args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())