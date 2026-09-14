"""Análise semântica: nomes, tipos, traits e escopos (v0.2: bounds+subtipagem)."""
from __future__ import annotations


class SymTable:
    def __init__(self):
        self.scopes: list[dict] = [{}]
        self.records: dict[str, dict] = {}  # v0.2: Nominal -> {campo: tipo}
    def push(self): self.scopes.append({})
    def pop(self): self.scopes.pop()
    def decl(self, n, t): self.scopes[-1][n] = t
    def lookup(self, n):
        for s in reversed(self.scopes):
            if n in s: return s[n]
        return None
    def declared_here(self, n): return n in self.scopes[-1]


def _fns(prog):
    for it in prog.itens:
        if type(it).__name__ == "Fn":
            yield it
        for m in getattr(it, "methods", []):
            yield m


def _pos(node) -> str:
    sp = getattr(node, "span", None)
    if sp is not None and getattr(sp, "line", 0):
        return f" em {sp.line}:{sp.col}"
    return ""


def analisar(prog):
    errs: list[str] = []; sym = SymTable()
    structs: set[str] = set()
    traits: dict[str, list] = {}   # v0.2: Trait -> [(método, aridade, ret)]
    impls: dict[str, dict] = {}    # v0.2: Tipo -> {método: (aridade, ret)}
    for it in prog.itens:
        nm = getattr(it, "name", "")
        if type(it).__name__ == "Fn":
            if sym.declared_here(it.name):
                errs.append(f"função duplicada: `{it.name}`{_pos(it)}")
            sym.decl(it.name, f"fn->{it.ret}")
        elif type(it).__name__ == "Let":
            sym.decl(it.name, it.typ or "?")  # const de módulo
        elif type(it).__name__ in ("Struct", "Enum"):
            base = nm.split(":")[-1]
            if nm.startswith("trait:"):
                traits[base] = list(getattr(it, "required", []))
                sym.decl(base, "type")
            elif nm.startswith("impl:"):
                meths = {}
                for m in getattr(it, "methods", []):
                    short = m.name.split("::")[-1]
                    meths[short] = (len(m.params), m.ret)
                    sym.decl(m.name, f"fn->{m.ret}")
                impls[base] = meths
            else:
                structs.add(base); sym.decl(base, "type")
                try:
                    sym.records[base] = {fn2: ft for fn2, ft in
                                         (getattr(it, "fields", []) or [])}
                except (TypeError, ValueError):
                    sym.records[base] = {}
    _check_traits(traits, impls, structs, prog, errs)
    for it in _fns(prog):
        sym.push()
        for pn, pt in it.params:
            if isinstance(pn, str) and pn not in ("self", "Self"):
                sym.decl(pn, pt if isinstance(pt, str) else "?")
        for st in it.body: _stmt(st, sym, errs)
        sym.pop()
    return errs, sym


def _check_traits(traits, impls, structs, prog, errs):
    """v0.2: impl cobre a trait? bounds nomeiam traits declaradas?"""
    from compiler.frontend import ast_nodes as A
    for t, req in traits.items():
        if t in impls:
            for m, ar, _rt in req:
                if m not in impls[t]:
                    errs.append(f"impl `{t}` não implementa "
                                f"`{t}.{m}` exigido pela trait")
                elif impls[t][m][0] != ar:
                    errs.append(f"impl `{t}.{m}` tem aridade "
                                f"{impls[t][m][0]}, trait exige {ar}")
    for base in impls:
        if base not in structs and base not in traits:
            errs.append(f"impl de tipo não declarado: `{base}`")
    for it in _fns(prog):
        for tvar, bounds in getattr(it, "bounds", None) or []:
            for b in bounds:
                if b not in traits:
                    errs.append(f"bound refere trait não declarada: "
                                f"`{b}` em `{it.name}<{tvar}>`{_pos(it)}")


def _stmt(st, sym, errs):
    from compiler.frontend import ast_nodes as A
    if isinstance(st, (A.Let,)):
        t = _expr(st.expr, sym, errs) if st.expr is not None else "?"
        if st.typ and t not in ("?", st.typ) and not _compat(st.typ, t, sym):
            errs.append(f"tipo incompatível em `let {st.name}`: "
                        f"declarado `{st.typ}`, expressão é `{t}`{_pos(st)}")
        sym.decl(st.name, st.typ or t)
    elif isinstance(st, A.Return):
        if st.expr is not None: _expr(st.expr, sym, errs)
    elif isinstance(st, A.If):
        tc = _expr(st.cond, sym, errs)
        if tc in ("str",):
            errs.append(f"condição de `if` deve ser bool/int, achado `{tc}`{_pos(st)}")
        sym.push()
        for s in st.then: _stmt(s, sym, errs)
        sym.pop(); sym.push()
        for s in st.els: _stmt(s, sym, errs)
        sym.pop()
    elif isinstance(st, A.While):
        _expr(st.cond, sym, errs)
        sym.push()
        for s in st.body: _stmt(s, sym, errs)
        sym.pop()
    elif isinstance(st, A.For):
        _expr(st.iter, sym, errs)
        sym.push(); sym.decl(st.var, "?")
        for s in st.body: _stmt(s, sym, errs)
        sym.pop()
    elif isinstance(st, A.Match):
        _expr(st.alvo, sym, errs)
        for b in st.bracos:
            sym.push()
            _bind_pat(getattr(b, "pat", ""), sym)
            if getattr(b, "guard", None) is not None: _expr(b.guard, sym, errs)
            _expr_or_block(b.expr, sym, errs)
            sym.pop()
    elif isinstance(st, A.Block):
        sym.push()
        for s in st.stmts: _stmt(s, sym, errs)
        sym.pop()
    elif isinstance(st, A.BinOp) and st.op in ("=", "+=", "-=", "*=", "/=", "%="):
        _expr(st.r, sym, errs)
        tgt = st.l
        if type(tgt).__name__ == "Lit" and tgt.kind == "id":
            base = str(tgt.val).split(".")[0].split("::")[0]
            if sym.lookup(base) is None and base not in BUILTINS:
                errs.append(f"atribuição a nome indefinido: `{tgt.val}`{_pos(st)}")
        else:
            _expr(tgt, sym, errs)
    elif st is not None and type(st).__name__ == "ErrorNode":
        pass  # já diagnosticado no parser
    else:
        _expr(st, sym, errs)


def _expr_or_block(e, sym, errs):
    from compiler.frontend import ast_nodes as A
    if type(e).__name__ == "Block":
        sym.push()
        for s in e.stmts: _stmt(s, sym, errs)
        sym.pop(); return "?"
    if type(e).__name__ == "Return" and e.expr is not None:
        return _expr(e.expr, sym, errs)
    return _expr(e, sym, errs)


def _bind_pat(pat, sym):
    if not isinstance(pat, str) or pat in ("_", ""): return
    for alt in pat.split("|"):
        a = alt.strip()
        if not a or a in ("true", "false"): continue
        if "(" in a and a.endswith(")"):  # Ok(v), Forma::C(r): liga o interno
            inner = a[a.find("(") + 1:a.rfind(")")]
            for x in inner.split(","):
                x = x.strip()
                if x and x != "_" and x[:1].islower() and x.isidentifier():
                    sym.decl(x, "?")
        elif a != "_" and a.isidentifier() and (a[0].islower() or a[0] == "_"):
            sym.decl(a, "?")


def _record_split(t: str):
    """`{a: int, b: str}` -> {a: int, b: str}; None se não for registro."""
    t = (t or "").strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    out: dict[str, str] = {}
    for part in t[1:-1].split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            return None
        f, _, ft = part.partition(":")
        out[f.strip()] = ft.strip()
    return out


def _subtipo(sub: str, sup: str, records: dict | None) -> bool:
    """v0.2: subtipagem — igualdade, `?`, torre numérica e registros
    (largura: campos extras ok; profundidade: campos covariantes).
    Nominais com campos conhecidos (structs) valem como registros."""
    if sub == sup or "?" in (sub, sup):
        return True
    num = {"int", "i32", "i64", "usize", "float", "f32", "f64"}
    if sub in num and sup in num:
        return True
    recs = records or {}
    dsub = _record_split(sub)
    if dsub is None and sub in recs:
        dsub = recs[sub]
    dsup = _record_split(sup)
    if dsup is None and sup in recs:
        dsup = recs[sup]
    if dsub is None or dsup is None:
        return False
    return all(f in dsub and _subtipo(dsub[f], dsup[f], recs)
               for f in dsup)


def _compat(decl: str, got: str, sym=None) -> bool:
    # `got` precisa ser subtipo de `decl` (a ordem importa p/ registros).
    recs = getattr(sym, "records", None) if sym is not None else None
    return _subtipo(got, decl, recs)


BUILTINS = {"vec", "map", "set", "Ok", "Err", "Some", "None", "println", "print",
    "assert", "assert_eq", "assert_ne", "assert_almost_eq", "len", "str", "int",
    "float", "bool", "Some", "Ok", "panic", "todo", "unimplemented", "dbg",
    "spawn", "metodo",
    "self", "Self"}


def _expr(e, sym, errs):
    from compiler.frontend import ast_nodes as A
    if e is None: return "?"
    if isinstance(e, A.Lit):
        if e.kind == "id":
            v = str(e.val)
            if "::" in v or "." in v or v in BUILTINS:
                if "." in v and "::" not in v:
                    base = v.split(".")[0]
                    if sym.lookup(base) is None and base not in BUILTINS:
                        errs.append(f"nome indefinido: `{v}`{_pos(e)} "
                                    f"(base `{base}` não declarada)")
                    return "?"
                return "?"
            t = sym.lookup(v)
            if t is None:
                errs.append(f"nome indefinido: `{v}`{_pos(e)}")
            return t or "?"
        return e.kind
    if isinstance(e, A.BinOp):
        tl = _expr(e.l, sym, errs); tr = _expr(e.r, sym, errs)
        if e.op in ("&&", "||") and ("str" in (tl, tr)):
            errs.append(f"operador `{e.op}` exige bool/int{_pos(e)}")
        return "bool" if e.op in ("==", "!=", "<", ">", "<=", ">=") else tl if tl != "?" else tr
    if isinstance(e, A.UnOp):
        return _expr(e.e, sym, errs)
    if isinstance(e, A.Call):
        for a in e.args: _expr(a, sym, errs)
        if e.fn.endswith("!") or "::" in e.fn or "." in e.fn or e.fn in BUILTINS:
            return "?"
        fn = sym.lookup(e.fn.split("(")[0])
        if fn is None:
            errs.append(f"função indefinida: `{e.fn}`{_pos(e)}")
            return "?"
        return fn.split("->")[-1] if "->" in fn else "?"
    if isinstance(e, A.Field):
        _expr(e.base, sym, errs); return "?"
    if isinstance(e, A.If):
        _expr(e.cond, sym, errs)
        sym.push()
        for s in e.then: _stmt(s, sym, errs)
        sym.pop(); sym.push()
        for s in e.els: _stmt(s, sym, errs)
        sym.pop(); return "?"
    if isinstance(e, A.While):
        _expr(e.cond, sym, errs); return "?"
    if isinstance(e, A.For):
        _expr(e.iter, sym, errs); return "?"
    if isinstance(e, A.Match):
        _expr(e.alvo, sym, errs)
        for b in e.bracos:
            sym.push(); _bind_pat(getattr(b, "pat", ""), sym)
            if getattr(b, "guard", None) is not None: _expr(b.guard, sym, errs)
            _expr_or_block(b.expr, sym, errs); sym.pop()
        return "?"
    if isinstance(e, A.Block):
        sym.push()
        for s in e.stmts: _stmt(s, sym, errs)
        sym.pop(); return "?"
    return "?"
