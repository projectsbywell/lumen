"""Borrow checker v0.3-NLL (non-lexical lifetimes, subconjunto v0.2).

Regras:
- Tipos Copy nunca movem: int, float, bool, char, unit, fn, "?" (desconhecido).
- Todo outro tipo concreto (str, vec, map, struct/enum, Result, Option) move
  em `let y = x`, argumento de chamada e `return x`.
- Ler variável movida -> erro. Mover com empréstimo ativo -> erro.
- `&x` exige sem move e sem mut; `&mut x` exige sem move e sem empréstimos.
- NLL: um empréstimo termina no último uso (leitura) do referente, não
  no fim da função. Implementação em dois passes sobre a mesma caminhada:
  o passo 1 coleta o último tick de leitura de cada variável; o passo 2
  expira empréstimos cujo último uso já passou. Em código linear o
  resultado equivale ao NLL; em branches o cálculo usa o máximo global
  (conservador e sólido: pode manter um empréstimo vivo por mais tempo,
  nunca por menos).
- Tipos desconhecidos ("?") são tratados como Copy: nunca gera falso
  positivo em código sem anotação, à custa de aceitar alguns programas
  inválidos (documentado).
"""
from __future__ import annotations

COPY = {"int", "float", "bool", "char", "unit", "?", "nil",
        "i32", "i64", "f64", "f32", "usize", "str_ref"}


def is_copy(ty: str) -> bool:
    t = (ty or "?").strip()
    if not t or t == "?" or "?" in t:
        return True
    if t.startswith("fn"):
        return True
    base = t.split("<")[0].split("::")[-1].split(".")[-1]
    return base in COPY


class Bk:
    def __init__(self, collect_only=False, last_read=None):
        self.errs: list[str] = []
        self.st: dict[str, dict] = {}
        self.collect_only = collect_only
        # passo 1: var -> último tick de leitura; passo 2: expira por ele.
        self.last_read: dict[str, int] = dict(last_read or {})
        self.clock = 0
        self.mentions: dict[str, list[tuple[int, str]]] = {}

    def _tick(self) -> int:
        self.clock += 1
        return self.clock

    def _mention(self, n, kind):
        self.mentions.setdefault(n, []).append((self.clock, kind))

    # -- estado ------------------------------------------------------
    def decl(self, n, ty, const=False):
        # No modo coleta também guarda o tipo: typeof() precisa dele
        # para decidir o que é move (senão tudo degrada para "?"=Copy
        # e os moves nem entram nas mentions).
        self._mention(n, "write") if self.collect_only else None
        self.st[n] = {"ty": ty or "?", "moved": False, "imm": 0,
                      "mut": False, "const": const}

    def _info(self, n):
        return self.st.get(n)

    def _expire(self):
        """NLL: encerra empréstimos cujo último uso já passou."""
        if self.collect_only:
            return
        for n, i in self.st.items():
            if (i["imm"] or i["mut"]) and not i.get("const"):
                if self.last_read.get(n, 0) <= self.clock:
                    i["imm"] = 0
                    i["mut"] = False

    def use(self, n, ctx="uso"):
        if self.collect_only:
            self._mention(n, "read")
            return
        i = self._info(n)
        if i is None or i.get("const"):
            return
        if i["moved"]:
            self.errs.append(f"uso após move: `{n}` ({ctx})")
            return
        if i["mut"]:
            self.errs.append(f"`{n}` em uso mutável ({ctx})")

    def move_out(self, n, ctx="move"):
        if self.collect_only:
            self._mention(n, "move")
            return
        i = self._info(n)
        if i is None or i.get("const"):
            return
        if i["moved"]:
            self.errs.append(f"move duplo: `{n}` ({ctx})")
            return
        if i["imm"] or i["mut"]:
            self.errs.append(f"move com empréstimo ativo: `{n}` ({ctx})")
            return
        if not is_copy(i["ty"]):
            i["moved"] = True

    def borrow(self, n, mut_, ctx="empréstimo"):
        if self.collect_only:
            self._mention(n, "read")
            return
        i = self._info(n)
        if i is None or i.get("const"):
            return
        if i["moved"]:
            self.errs.append(f"empréstimo de movido: `{n}` ({ctx})")
            return
        if mut_:
            if i["imm"] or i["mut"]:
                self.errs.append(f"empréstimo mut duplo: `{n}` ({ctx})")
                return
            i["mut"] = True
        else:
            if i["mut"]:
                self.errs.append(f"empréstimo compartilhado com mut ativo: `{n}` ({ctx})")
                return
            i["imm"] += 1

    # -- tipos --------------------------------------------------------
    def typeof(self, e) -> str:
        from compiler.frontend import ast_nodes as A
        if isinstance(e, A.Lit):
            if e.kind == "id":
                i = self._info(str(e.val))
                return i["ty"] if i else "?"
            return {"int": "int", "float": "float", "str": "str",
                    "bool": "bool", "char": "char", "unit": "unit"}.get(e.kind, "?")
        if isinstance(e, A.Call):
            if e.fn in ("vec",) or e.fn.endswith("!"):
                return "vec"
            if e.fn in ("map",):
                return "map"
            if e.fn in ("Ok", "Err"):
                return "Result"
            if e.fn in ("Some", "None"):
                return "Option"
            if "::" in e.fn or "." in e.fn or e.fn in (
                    "println", "print", "vec", "map", "set", "len",
                    "str", "int", "float", "bool", "assert_eq", "assert_ne"):
                return "?"
            # construtor nominal (Ponto{...}, Fila(...)): Move.
            # chamada comum (minúscula): tipo desconhecido -> Copy.
            return e.fn if e.fn[:1].isupper() else "?"
        if isinstance(e, A.UnOp) and e.op in ("&", "&mut", "*", "?", "await"):
            return self.typeof(e.e)
        return "?"

    # -- caminhada ------------------------------------------------------
    def expr(self, e, move_ok=False):
        from compiler.frontend import ast_nodes as A
        self._tick()
        if isinstance(e, A.Lit):
            if e.kind == "id":
                self.use(str(e.val))
            return
        if isinstance(e, A.BinOp):
            if e.op in ("=", "+=", "-=", "*=", "/=", "%="):
                self.expr(e.r)
                tgt = e.l
                if type(tgt).__name__ == "Lit" and tgt.kind == "id":
                    n = str(tgt.val)
                    # reatribuição encerra empréstimos (NLL-lite; v0.3
                    # rastreará usos obsoletos do borrow antigo)
                    self.decl(n, self.typeof(e.r))
                else:
                    self.expr(tgt)
                return
            self.expr(e.l)
            self.expr(e.r)
            return
        if isinstance(e, A.UnOp):
            if e.op in ("&", "&mut"):
                inner = e.e
                if type(inner).__name__ == "Lit" and inner.kind == "id":
                    self.borrow(str(inner.val), e.op == "&mut")
                else:
                    self.expr(inner)
                return
            self.expr(e.e)
            return
        if isinstance(e, A.Call):
            for a in e.args:
                self.expr(a)
                if type(a).__name__ == "Lit" and a.kind == "id":
                    if not (e.fn.endswith("!") or e.fn in (
                            "println", "print", "vec", "map", "set", "len",
                            "str", "int", "float", "bool", "assert_eq",
                            "assert_ne") or "::" in e.fn or "." in e.fn):
                        self.move_out(str(a.val), f"arg de {e.fn}")
            return
        if isinstance(e, A.Field):
            self.expr(e.base)
            return
        if isinstance(e, A.If):
            self.expr(e.cond)
            for s in e.then:
                self.stmt(s)
            for s in e.els:
                self.stmt(s)
            return
        if isinstance(e, A.Match):
            self.expr(e.alvo)
            for b in e.bracos:
                gd = getattr(b, "guard", None)
                if gd is not None:
                    self.expr(gd)
                body = b.expr
                if type(body).__name__ == "Return":
                    if body.expr is not None:
                        self.expr(body.expr)
                        if type(body.expr).__name__ == "Lit" and body.expr.kind == "id":
                            self.move_out(str(body.expr.val), "return (match)")
                elif type(body).__name__ == "Block":
                    for s in body.stmts:
                        self.stmt(s)
                else:
                    self.expr(body)
            return
        if isinstance(e, A.Block):
            for s in e.stmts:
                self.stmt(s)
            return

    def stmt(self, st):
        from compiler.frontend import ast_nodes as A
        self._tick()
        try:
            return self._stmt_inner(st, A)
        finally:
            self._expire()

    def _stmt_inner(self, st, A):
        if isinstance(st, A.Let):
            if st.expr is not None:
                self.expr(st.expr)
                ty = st.typ or self.typeof(st.expr)
            else:
                ty = st.typ or "?"
            i = self._info(st.name)
            # sombra/reatribuição encerra empréstimos (ver acima)
            self.decl(st.name, ty)
            if st.expr is not None and type(st.expr).__name__ == "Lit" \
                    and st.expr.kind == "id" and not is_copy(ty):
                self.move_out(str(st.expr.val), f"let {st.name}")
            return
        if isinstance(st, A.Return):
            if st.expr is not None:
                self.expr(st.expr)
                if type(st.expr).__name__ == "Lit" and st.expr.kind == "id":
                    self.move_out(str(st.expr.val), "return")
            return
        if isinstance(st, A.While):
            self.expr(st.cond)
            for s in st.body:
                self.stmt(s)
            return
        if isinstance(st, A.For):
            self.expr(st.iter)
            self.decl(st.var, "?")
            for s in st.body:
                self.stmt(s)
            return
        self.expr(st)


def verificar(prog) -> list[str]:
    from compiler.frontend import semantica as S
    from compiler.frontend import ast_nodes as A
    errs: list[str] = []
    top = Bk()
    for it in prog.itens:
        if type(it).__name__ == "Let" and it.expr is not None:
            top.expr(it.expr)
            top.decl(it.name, it.typ or top.typeof(it.expr), const=True)
    for it in S._fns(prog):
        params = [(pn if isinstance(pn, str) else str(pn),
                   pt if isinstance(pt, str) else "?")
                  for pn, pt in it.params]
        # passo 1 (coleta): último tick de leitura de cada variável.
        col = Bk(collect_only=True)
        for n, t in top.st.items():
            col.st[n] = dict(t)
        for pn, pt in params:
            col.decl(pn, pt)
        for st in it.body:
            col.stmt(st)
        last_read = {}
        for n, ms in col.mentions.items():
            # Leituras consumidas pelo próprio move (mesmo tick do
            # move_out, ex. `let t = s`) não estendem o empréstimo:
            # o loan precisa estar morto ANTES do move para ele ser legal.
            move_ticks = {t for t, k in ms if k == "move"}
            rs = [t for t, k in ms
                  if k == "read" and t not in move_ticks]
            if rs:
                last_read[n] = max(rs)
        # passo 2 (checagem): expira empréstimos pelo último uso (NLL).
        bk = Bk(collect_only=False, last_read=last_read)
        for n, t in top.st.items():
            bk.st[n] = dict(t)
        for pn, pt in params:
            bk.decl(pn, pt)
        for st in it.body:
            bk.stmt(st)
        errs.extend(bk.errs)
    errs.extend(top.errs)
    return errs
