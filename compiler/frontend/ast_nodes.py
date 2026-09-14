"""AST Lumen com spans."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Span:
    line: int; col: int; end_line: int = 0; end_col: int = 0
    def __str__(self): return f"{self.line}:{self.col}"
    def merge(self, other: "Span") -> "Span":
        return Span(self.line, self.col, other.end_line or other.line,
                    other.end_col or other.col)

@dataclass
class Node:
    span: Span = field(default_factory=lambda: Span(0,0))

def span_of(line: int, col: int, end_line: int = 0, end_col: int = 0) -> Span:
    return Span(line, col, end_line or line, end_col or col)

def walk(node):
    """Itera a AST em profundidade (nós + listas aninhadas)."""
    stack = [node]
    while stack:
        cur = stack.pop()
        yield cur
        for v in (vars(cur).values() if hasattr(cur, "__dict__") else []):
            if isinstance(v, Node): stack.append(v)
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, Node): stack.append(x)

def format_error(src: str, span: Span, msg: str, hint: str = "") -> str:
    lines = src.splitlines()
    row = lines[span.line - 1] if 1 <= span.line <= len(lines) else ""
    out = f"{span}: {msg}\n  {row}\n  {' ' * max(span.col - 1, 0)}^"
    if hint: out += f"\ndica: {hint}"
    return out

class Attr(str):
    """Atributo que se comporta como str para `in` mas carrega args."""
    def __new__(cls, name, args=None):
        obj = str.__new__(cls, name)
        obj.name = name
        obj.args = list(args or [])
        return obj
    def __eq__(self, other):
        if isinstance(other, str):
            return str(self) == other
        if isinstance(other, Attr):
            return self.name == other.name and self.args == other.args
        return False
    def __hash__(self):
        return hash(str(self))
    def __repr__(self):
        if self.args:
            return f"Attr({self.name!r}, args={self.args!r})"
        return f"Attr({self.name!r})"

@dataclass
class Programa(Node):
    mod: str = ""; imports: list = field(default_factory=list); itens: list = field(default_factory=list)

@dataclass
class Import(Node):
    path: str = ""

@dataclass
class Fn(Node):
    name: str = ""; params: list = field(default_factory=list)
    ret: str = "int"; body: list = field(default_factory=list)
    pub: bool = False; async_: bool = False
    bounds: list = field(default_factory=list)  # v0.2: [(T, [traits])]
    attrs: list = field(default_factory=list)  # v0.3: lista de Attr com args
    test: bool = False
    test_args: list = field(default_factory=list)

@dataclass
class Let(Node):
    name: str = ""; typ: str = ""; expr: object = None; mut_: bool = False

@dataclass
class If(Node):
    cond: object = None; then: list = field(default_factory=list); els: list = field(default_factory=list)

@dataclass
class MatchBraco(Node):
    pat: str = ""; expr: object = None; guard: object = None

@dataclass
class Match(Node):
    alvo: object = None; bracos: list = field(default_factory=list)

@dataclass
class For(Node):
    var: str = ""; iter: object = None; body: list = field(default_factory=list)

@dataclass
class While(Node):
    cond: object = None; body: list = field(default_factory=list)

@dataclass
class Return(Node):
    expr: object = None

@dataclass
class Struct(Node):
    name: str = ""; fields: list = field(default_factory=list)
    required: list = field(default_factory=list)  # v0.2: trait -> [(método, aridade, ret)]
    attrs: list = field(default_factory=list)

@dataclass
class Enum(Node):
    name: str = ""; variants: list = field(default_factory=list)
    attrs: list = field(default_factory=list)

@dataclass
class BinOp(Node):
    op: str = ""; l: object = None; r: object = None

@dataclass
class UnOp(Node):
    op: str = ""; e: object = None

@dataclass
class Call(Node):
    fn: str = ""; args: list = field(default_factory=list)

@dataclass
class Field(Node):
    base: object = None; name: str = ""

@dataclass
class Lit(Node):
    kind: str = ""; val: object = None; suffix: str = ""; raw: bool = False

@dataclass
class Block(Node):
    stmts: list = field(default_factory=list)

@dataclass
class ErrorNode(Node):
    """Sentinela da recuperação de erro: marca trecho inválido já diagnosticado."""
    msg: str = ""
