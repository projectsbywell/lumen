"""IR Lumen em SSA."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Instr:
    op: str; dst: str = ""; args: list = field(default_factory=list); val: object = None
    def __str__(self):
        if self.op == "const": return f"{self.dst} = const {self.val!r}"
        if self.op == "label": return f"{self.args[0]}:"
        if self.op == "phi": return f"{self.dst} = phi({', '.join(self.args)})"
        if self.op in ("jmp",): return f"jmp {self.args[0]}"
        if self.op in ("br",): return f"br {self.args[0]} {self.args[1]} {self.args[2]}"
        if self.op in ("ret",): return f"ret {self.args[0] if self.args else ''}"
        if self.op in ("call",): return f"{self.dst} = call {self.args[0]}({', '.join(self.args[1:])})"
        return f"{self.dst} = {self.op} {', '.join(self.args)}"

@dataclass
class Bloco:
    nome: str; instrs: list = field(default_factory=list)

@dataclass
class FuncaoIR:
    nome: str; params: list = field(default_factory=list); blocos: list = field(default_factory=list)

@dataclass
class ModuloIR:
    nome: str = "main"; funcoes: list = field(default_factory=list)

_tmp = [0]
_lab = [0]

def tmp(p="t"):
    _tmp[0] += 1; return f"%{p}{_tmp[0]}"

def lab(p="L"):
    _lab[0] += 1; return f"{p}{_lab[0]}"

BINOP = {"+":"add","-":"sub","*":"mul","/":"div","%":"mod","==":"eq","!=":"neq",
         "<":"lt",">":"gt","<=":"le",">=":"ge"}

class Baixador:
    def __init__(self): self.mod = ModuloIR(); self.consts = {}; self._in_const = set()

    def baixar(self, prog) -> ModuloIR:
        items = []
        for it in getattr(prog, "itens", []):
            if type(it).__name__ == "Fn":
                items.append(it)
            elif type(it).__name__ == "Let" and it.expr is not None:
                self.consts[it.name] = it.expr  # const de módulo
            items.extend(getattr(it, "methods", []))
        for it in items:
            self.fn(it)
        if not self.mod.funcoes:
            f = FuncaoIR("main"); b = Bloco("entry")
            d = tmp(); b.instrs.append(Instr("const", d, [], 0)); b.instrs.append(Instr("ret", "", [d]))
            f.blocos.append(b); self.mod.funcoes.append(f)
        return self.mod

    def fn(self, fn) -> None:
        from compiler.frontend import ast_nodes as A
        f = FuncaoIR(fn.name, [p[0] if isinstance(p, tuple) else str(p) for p in fn.params])
        b = Bloco("entry")
        body = list(fn.body)
        # v0.2: a expressão final vira o valor de retorno (if/match/bloco
        # e expressões puras); let, atribuição e loops valem unit (0),
        # como em Rust. Antes, toda cauda sem `return` virava `ret 0`.
        tail_value = None
        if body and not any(i.op == "ret" for i in b.instrs):
            last = body[-1]
            if isinstance(last, (A.If, A.Match)):
                for st in body[:-1]:
                    self.stmt(st, b, f)
                tail_value = self.expr(last, b)
                body = []
            elif isinstance(last, A.Block):
                for st in body[:-1]:
                    self.stmt(st, b, f)
                for s in last.stmts:
                    self.stmt(s, b, f)
                tail_value = self._last_value(b)
                body = []
            elif not isinstance(last, (A.Let, A.Return, A.While, A.For)) \
                    and not (isinstance(last, A.BinOp) and last.op in
                             ("=", "+=", "-=", "*=", "/=", "%=")) \
                    and type(last).__name__ != "ErrorNode":
                for st in body[:-1]:
                    self.stmt(st, b, f)
                tail_value = self.expr(last, b)
                body = []
        for st in body:
            self.stmt(st, b, f)
        if not b.instrs or b.instrs[-1].op != "ret":
            if tail_value is None:
                tail_value = tmp()
                b.instrs.append(Instr("const", tail_value, [], 0))
            b.instrs.append(Instr("ret", "", [tail_value]))
        f.blocos.append(b); self.mod.funcoes.append(f)

    # -- expressões: devolve nome SSA com o valor -------------------------
    def expr(self, e, b: Bloco) -> str:
        from compiler.frontend import ast_nodes as A
        if isinstance(e, A.Lit):
            if e.kind == "id":
                if str(e.val) in self.consts and str(e.val) not in self._in_const:
                    self._in_const.add(str(e.val))
                    v = self.expr(self.consts[str(e.val)], b)
                    self._in_const.discard(str(e.val))
                    return v
                return str(e.val)
            if e.kind == "unit":
                d = tmp(); b.instrs.append(Instr("const", d, [], 0)); return d
            d = tmp(); b.instrs.append(Instr("const", d, [], e.val)); return d
        if isinstance(e, A.BinOp):
            if e.op in ("=", "+=", "-=", "*=", "/=", "%="):
                r = self.expr(e.r, b)
                base = e.l.val if type(e.l).__name__ == "Lit" else tmp()
                if e.op != "=":
                    l = self.expr(e.l, b); d0 = tmp()
                    b.instrs.append(Instr(BINOP[e.op[0]], d0, [l, r])); r = d0
                b.instrs.append(Instr("copy", base, [r])); return base
            if e.op in ("&&", "||"):
                return self._logic(e, b)
            if e.op == "..":
                return self.expr(e.l, b)  # limite inferior (coleções: v0.3)
            l = self.expr(e.l, b); r = self.expr(e.r, b); d = tmp()
            b.instrs.append(Instr(BINOP.get(e.op, "add"), d, [l, r])); return d
        if isinstance(e, A.UnOp):
            if e.op == "?":
                return self._question(e.e, b)
            v = self.expr(e.e, b); d = tmp()
            if e.op == "-":
                z = tmp(); b.instrs.append(Instr("const", z, [], 0))
                b.instrs.append(Instr("sub", d, [z, v]))
            elif e.op in ("!", "not"):
                b.instrs.append(Instr("not", d, [v]))
            else:  # await, spawn-valor, as, &, &mut, *
                b.instrs.append(Instr("copy", d, [v]))
            return d
        if isinstance(e, A.Call):
            if e.fn.endswith("!") or e.fn in ("vec", "map", "metodo"):
                d = tmp(); b.instrs.append(Instr("const", d, [], 0)); return d
            if e.fn in ("println", "print"):
                for a in e.args:
                    v = self.expr(a, b)
                    b.instrs.append(Instr("print", "", [v]))
                d = tmp(); b.instrs.append(Instr("const", d, [], 0)); return d
            argvs = [self.expr(a, b) for a in e.args]
            d = tmp(); b.instrs.append(Instr("call", d, [e.fn] + argvs)); return d
        if isinstance(e, A.Field):
            return self.expr(e.base, b)  # campos: v0.3 (usa a raiz)
        if isinstance(e, A.If):
            return self._if_value(e, b)
        if isinstance(e, A.Match):
            return self._match_value(e, b)
        if isinstance(e, A.Block):
            for st in e.stmts: self.stmt(st, b, None)
            d = tmp(); b.instrs.append(Instr("const", d, [], 0)); return d
        d = tmp(); b.instrs.append(Instr("const", d, [], 0)); return d

    def _logic(self, e, b: Bloco) -> str:
        res = tmp(); l_end, l_rhs, l_short = lab(), lab(), lab()
        l = self.expr(e.l, b)
        if e.op == "&&":
            b.instrs.append(Instr("br", "", [l, l_rhs, l_short]))
        else:
            b.instrs.append(Instr("br", "", [l, l_short, l_rhs]))
        b.instrs.append(Instr("label", "", [l_rhs]))
        r = self.expr(e.r, b)
        b.instrs.append(Instr("copy", res, [r]))
        b.instrs.append(Instr("jmp", "", [l_end]))
        b.instrs.append(Instr("label", "", [l_short]))
        z = tmp(); b.instrs.append(Instr("const", z, [], 0 if e.op == "&&" else 1))
        b.instrs.append(Instr("copy", res, [z]))
        b.instrs.append(Instr("label", "", [l_end]))
        return res

    def _if_value(self, e, b: Bloco):
        res = tmp(); l_then, l_else, l_end = lab(), lab(), lab()
        c = self.expr(e.cond, b)
        if e.els:
            b.instrs.append(Instr("br", "", [c, l_then, l_else]))
        else:
            b.instrs.append(Instr("br", "", [c, l_then, l_end]))
        b.instrs.append(Instr("label", "", [l_then]))
        for st in e.then: self.stmt(st, b, None)
        b.instrs.append(Instr("copy", res, [self._last_value(b)]))
        b.instrs.append(Instr("jmp", "", [l_end]))
        if e.els:
            b.instrs.append(Instr("label", "", [l_else]))
            for st in e.els: self.stmt(st, b, None)
            b.instrs.append(Instr("copy", res, [self._last_value(b)]))
        b.instrs.append(Instr("label", "", [l_end]))
        return res

    def _last_value(self, b: Bloco) -> str:
        for i in reversed(b.instrs):
            if i.op in ("label", "jmp", "br", "ret", "print"):
                continue
            if i.dst:
                return i.dst
        d = tmp(); b.instrs.append(Instr("const", d, [], 0)); return d

    def _question(self, inner, b: Bloco) -> str:
        """`expr?`: desembrulha Ok ou retorna Err precoce."""
        v = self.expr(inner, b)
        t_ok = tmp(); d = tmp()
        b.instrs.append(Instr("is_ok", t_ok, [v]))
        l_ok, l_err = lab(), lab()
        b.instrs.append(Instr("br", "", [t_ok, l_ok, l_err]))
        b.instrs.append(Instr("label", "", [l_err]))
        b.instrs.append(Instr("ret", "", [v]))
        b.instrs.append(Instr("label", "", [l_ok]))
        b.instrs.append(Instr("unwrap", d, [v]))
        return d

    @staticmethod
    def _is_var_pat(pat: str) -> bool:
        return (isinstance(pat, str) and pat.isidentifier()
                and (pat[0].islower() or pat[0] == "_")
                and pat not in ("true", "false")
                and "(" not in pat and "|" not in pat and ":" not in pat)

    @staticmethod
    def _split_ok_err(pat: str):
        s = str(pat).strip()
        for tag in ("Ok", "Err"):
            if s.startswith(tag + "(") and s.endswith(")"):
                inner = s[len(tag) + 1:-1].strip()
                return tag, inner
        return None, None

    def _match_value(self, e, b: Bloco):
        from compiler.frontend import ast_nodes as A
        res = tmp(); l_end = lab()
        subj = self.expr(e.alvo, b)
        for bra in e.bracos:
            l_next, l_body = lab(), lab()
            pat = bra.pat if isinstance(bra.pat, str) else str(bra.pat)
            gd = getattr(bra, "guard", None)
            # wildcard `_` (ou `_nome`): sempre casa
            if pat == "_" or (isinstance(pat, str) and pat.startswith("_") and "(" not in pat and "|" not in pat):
                if pat != "_" and self._is_var_pat(pat):
                    b.instrs.append(Instr("copy", pat, [subj]))
                if gd is not None:
                    g = self.expr(gd, b)
                    b.instrs.append(Instr("br", "", [g, l_body, l_next]))
                    b.instrs.append(Instr("label", "", [l_body]))
                    self._arm_body(bra, b, res, l_end)
                    b.instrs.append(Instr("label", "", [l_next]))
                    continue
                self._arm_body(bra, b, res, l_end)
                break
            # variável simples `v` (catch-all nomeado), com ou sem guard
            if self._is_var_pat(pat):
                b.instrs.append(Instr("copy", pat, [subj]))
                if gd is not None:
                    b.instrs.append(Instr("label", "", [l_body + "_chk"]))
                    g = self.expr(gd, b)
                    b.instrs.append(Instr("br", "", [g, l_body, l_next]))
                    b.instrs.append(Instr("label", "", [l_body]))
                    self._arm_body(bra, b, res, l_end)
                    b.instrs.append(Instr("label", "", [l_next]))
                    continue
                self._arm_body(bra, b, res, l_end)
                break
            # Ok(v) / Err(e) sobre Result
            tag, inner = self._split_ok_err(pat)
            if tag is not None:
                t_ok = tmp()
                b.instrs.append(Instr("is_ok", t_ok, [subj]))
                l_chk = lab()
                if tag == "Ok":
                    b.instrs.append(Instr("br", "", [t_ok, l_chk, l_next]))
                else:
                    b.instrs.append(Instr("br", "", [t_ok, l_next, l_chk]))
                b.instrs.append(Instr("label", "", [l_chk]))
                if inner and inner != "_" and inner.isidentifier():
                    b.instrs.append(Instr("unwrap", inner, [subj]))
                if gd is not None:
                    g = self.expr(gd, b)
                    b.instrs.append(Instr("br", "", [g, l_body, l_next]))
                else:
                    b.instrs.append(Instr("jmp", "", [l_body]))
                b.instrs.append(Instr("label", "", [l_body]))
                self._arm_body(bra, b, res, l_end)
                b.instrs.append(Instr("label", "", [l_next]))
                continue
            # or-pattern `a | b | c` (com guard opcional no braço todo)
            if "|" in pat:
                alts = [a.strip() for a in pat.split("|")]
                l_chk_guard = lab()
                for idx, alt in enumerate(alts):
                    t = tmp(); pv = self._pat_const(alt, b)
                    b.instrs.append(Instr("eq", t, [subj, pv]))
                    if idx < len(alts) - 1:
                        l_alt_next = lab()
                        b.instrs.append(Instr("br", "", [t, l_chk_guard if gd is not None else l_body, l_alt_next]))
                        b.instrs.append(Instr("label", "", [l_alt_next]))
                    else:
                        b.instrs.append(Instr("br", "", [t, l_chk_guard if gd is not None else l_body, l_next]))
                if gd is not None:
                    b.instrs.append(Instr("label", "", [l_chk_guard]))
                    g = self.expr(gd, b)
                    b.instrs.append(Instr("br", "", [g, l_body, l_next]))
                b.instrs.append(Instr("label", "", [l_body]))
                self._arm_body(bra, b, res, l_end)
                b.instrs.append(Instr("label", "", [l_next]))
                continue
            pv = self._pat_const(str(pat), b)
            t = tmp(); b.instrs.append(Instr("eq", t, [subj, pv]))
            if gd is not None:
                l_chk = lab()
                b.instrs.append(Instr("br", "", [t, l_chk, l_next]))
                b.instrs.append(Instr("label", "", [l_chk]))
                g = self.expr(gd, b)
                b.instrs.append(Instr("br", "", [g, l_body, l_next]))
            else:
                b.instrs.append(Instr("br", "", [t, l_body, l_next]))
            b.instrs.append(Instr("label", "", [l_body]))
            self._arm_body(bra, b, res, l_end)
            b.instrs.append(Instr("label", "", [l_next]))
        b.instrs.append(Instr("label", "", [l_end]))
        return res

    def _pat_const(self, pat: str, b: Bloco) -> str:
        d = tmp()
        try: v = int(pat)
        except ValueError:
            try: v = float(pat)
            except ValueError:
                v = pat.strip('"')
        b.instrs.append(Instr("const", d, [], v)); return d

    def _arm_body(self, bra, b: Bloco, res: str, l_end: str) -> None:
        from compiler.frontend import ast_nodes as A
        body = bra.expr
        if type(body).__name__ == "Return":
            v = self.expr(body.expr, b) if body.expr is not None else tmp()
            b.instrs.append(Instr("ret", "", [v])); return
        if type(body).__name__ == "Block":
            for st in body.stmts: self.stmt(st, b, None)
            b.instrs.append(Instr("copy", res, [self._last_value(b)]))
        else:
            v = self.expr(body, b)
            b.instrs.append(Instr("copy", res, [v]))
        b.instrs.append(Instr("jmp", "", [l_end]))

    # -- statements ------------------------------------------------------
    def stmt(self, st, b: Bloco, f) -> None:
        from compiler.frontend import ast_nodes as A
        if isinstance(st, A.Let):
            v = self.expr(st.expr, b) if st.expr is not None else tmp()
            b.instrs.append(Instr("copy", st.name, [v])); return
        if isinstance(st, A.Return):
            v = self.expr(st.expr, b) if st.expr is not None else tmp()
            b.instrs.append(Instr("ret", "", [v])); return
        if isinstance(st, A.If):
            self._if_value(st, b); return
        if isinstance(st, A.While):
            l_c, l_b, l_e = lab(), lab(), lab()
            b.instrs.append(Instr("label", "", [l_c]))
            c = self.expr(st.cond, b)
            b.instrs.append(Instr("br", "", [c, l_b, l_e]))
            b.instrs.append(Instr("label", "", [l_b]))
            for s2 in st.body: self.stmt(s2, b, f)
            b.instrs.append(Instr("jmp", "", [l_c]))
            b.instrs.append(Instr("label", "", [l_e])); return
        if isinstance(st, A.For):
            self._for(st, b, f); return
        if isinstance(st, A.Match):
            self._match_value(st, b); return
        self.expr(st, b)

    def _for(self, st, b: Bloco, f) -> None:
        from compiler.frontend import ast_nodes as A
        it = st.iter
        if type(it).__name__ == "BinOp" and it.op == "..":
            lo = self.expr(it.l, b); hi = self.expr(it.r, b)
            b.instrs.append(Instr("copy", st.var, [lo]))
            l_c, l_b, l_e = lab(), lab(), lab()
            b.instrs.append(Instr("label", "", [l_c]))
            t = tmp(); b.instrs.append(Instr("lt", t, [st.var, hi]))
            b.instrs.append(Instr("br", "", [t, l_b, l_e]))
            b.instrs.append(Instr("label", "", [l_b]))
            for s2 in st.body: self.stmt(s2, b, f)
            one = tmp(); b.instrs.append(Instr("const", one, [], 1))
            nx = tmp(); b.instrs.append(Instr("add", nx, [st.var, one]))
            b.instrs.append(Instr("copy", st.var, [nx]))
            b.instrs.append(Instr("jmp", "", [l_c]))
            b.instrs.append(Instr("label", "", [l_e])); return
        self.expr(it, b)  # iterador não-faixa: avalia e ignora (v0.3)

def baixar(prog) -> ModuloIR:
    return Baixador().baixar(prog)

def ir_to_str(m: ModuloIR) -> str:
    out = [f"module {m.nome}"]
    for f in m.funcoes:
        out.append(f"fn {f.nome}({', '.join(f.params)}):")
        for bl in f.blocos:
            out.append(f"  {bl.nome}:")
            for i in bl.instrs: out.append(f"    {i}")
    return "\n".join(out)

def verificar(m: ModuloIR) -> list[str]:
    """Verificador do IR: labels, defs SSA, `ret` final e alvos de salto."""
    errs = []
    for f in m.funcoes:
        labels: set[str] = set()
        for bl in f.blocos:
            for i in bl.instrs:
                if i.op == "label":
                    if i.args[0] in labels:
                        errs.append(f"{f.nome}: label duplicado `{i.args[0]}`")
                    labels.add(i.args[0])
        defs: set[str] = set(f.params)
        for bl in f.blocos:
            for i in bl.instrs:
                if i.dst: defs.add(i.dst)
        for bl in f.blocos:
            for i in bl.instrs:
                if i.op in ("jmp",):
                    if i.args[0] not in labels:
                        errs.append(f"{f.nome}: salto p/ label indefinido `{i.args[0]}`")
                elif i.op == "br":
                    for L in i.args[1:]:
                        if L not in labels:
                            errs.append(f"{f.nome}: desvio p/ label indefinido `{L}`")
                elif i.op == "phi":
                    if len(i.args) < 2:
                        errs.append(f"{f.nome}: phi exige >= 2 entradas em `{i.dst}`")
                for a in i.args:
                    if isinstance(a, str) and a.startswith("%") and a not in defs:
                        errs.append(f"{f.nome}: uso sem definição `{a}` ({i.op})")
        tail = [i for bl in f.blocos for i in bl.instrs if i.op != "label"]
        if not tail or tail[-1].op != "ret":
            errs.append(f"{f.nome}: função sem `ret` final")
    return errs


# -- fluxo de dados + escape (v0.2) --------------------------------------

def _usos_defs(ins: Instr) -> tuple[set[str], set[str]]:
    usos = {a for a in ins.args if isinstance(a, str)
            and (a.startswith("%") or a.isidentifier()) and not a[0].isupper()}
    defs = {ins.dst} if ins.dst else set()
    if ins.op in ("jmp", "br", "label", "ret", "print"):
        defs = set()
    if ins.op == "ret":
        usos = {a for a in ins.args if isinstance(a, str)}
    return usos, defs


def liveness(f: FuncaoIR) -> list[dict]:
    """Liveness linear (backward) por instrução: [{live_in, live_out}]."""
    flat = [i for bl in f.blocos for i in bl.instrs]
    live: set[str] = set()
    out = []
    for i in reversed(flat):
        usos, defs = _usos_defs(i)
        out.append({"live_in": (live - defs) | usos, "live_out": set(live)})
        live = (live - defs) | usos
    out.reverse()
    return out


def reaching_defs(f: FuncaoIR) -> list[set[str]]:
    """Reaching definitions (forward, linear): defs vivas antes de cada instr."""
    flat = [i for bl in f.blocos for i in bl.instrs]
    reached: dict[str, int] = {}
    out = []
    for idx, i in enumerate(flat):
        out.append(set(f"{v}@{n}" for v, n in reached.items()))
        if i.dst:
            reached[i.dst] = idx
    return out


def escape_analysis(m: ModuloIR) -> dict[str, bool]:
    """`True` = a variável escapa (passada a call/print/ret ou global)."""
    esc: dict[str, bool] = {}
    for f in m.funcoes:
        for bl in f.blocos:
            for i in bl.instrs:
                if i.op == "call":
                    for a in i.args[1:]:
                        if isinstance(a, str): esc[a] = True
                elif i.op in ("ret", "print"):
                    for a in i.args:
                        if isinstance(a, str): esc[a] = True
                elif i.dst and i.dst not in esc:
                    esc[i.dst] = False
    return esc
