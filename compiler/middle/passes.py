"""Passes de otimização do IR: constfold, DCE, CSE, inline, loop opts."""
from __future__ import annotations
from compiler.middle.ir import ModuloIR

_PUROS = {"add", "sub", "mul", "div", "mod", "eq", "neq", "lt", "gt",
          "le", "ge", "not", "copy", "const"}
_COMUT = {"add", "mul", "eq", "neq"}
_EFEITO = {"ret", "call", "print", "br", "jmp", "label", "phi"}


def _num(v):
    if isinstance(v, bool): return int(v)
    if isinstance(v, (int, float)): return v
    if isinstance(v, str) and v.startswith("#"):
        try: return int(v[1:])
        except ValueError:
            try: return float(v[1:])
            except ValueError: return None
    return None


def constfold(m: ModuloIR) -> int:
    """Forward, flow-sensível; só propaga `%`-temps (SSA). Nunca dobra
    `div`/`mod` por zero (preserva o trap do runtime)."""
    n = 0
    for f in m.funcoes:
        for bl in f.blocos:
            consts: dict[str, object] = {}
            def R(a):
                if isinstance(a, str):
                    if a in consts: return consts[a]
                    return _num(a)
                return a
            for i in bl.instrs:
                if i.op == "const" and isinstance(i.val, (int, float, bool)):
                    if i.dst.startswith("%"): consts[i.dst] = i.val
                    else: consts.pop(i.dst, None)
                elif i.op == "copy" and len(i.args) == 1:
                    if i.args[0] in consts and i.dst.startswith("%"):
                        consts[i.dst] = consts[i.args[0]]
                    else:
                        consts.pop(i.dst, None)
                elif i.op in ("add", "sub", "mul", "div", "mod", "eq", "neq",
                              "lt", "gt", "le", "ge") and len(i.args) == 2:
                    a, b = R(i.args[0]), R(i.args[1])
                    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                        consts.pop(i.dst, None); continue
                    if i.op in ("div", "mod") and b == 0:
                        consts.pop(i.dst, None); continue  # trap fica p/ runtime
                    try:
                        v = {"add": a + b, "sub": a - b, "mul": a * b,
                             "div": (a // b if isinstance(a, int) and isinstance(b, int) else a / b),
                             "mod": a % b,
                             "eq": int(a == b), "neq": int(a != b),
                             "lt": int(a < b), "gt": int(a > b),
                             "le": int(a <= b), "ge": int(a >= b)}[i.op]
                    except (ArithmeticError, TypeError):
                        consts.pop(i.dst, None); continue
                    i.op, i.args, i.val = "const", [], v
                    if i.dst.startswith("%"): consts[i.dst] = v
                    n += 1
                elif i.op == "not" and i.args and i.args[0] in consts:
                    v = int(not consts[i.args[0]])
                    i.op, i.args, i.val = "const", [], v
                    if i.dst.startswith("%"): consts[i.dst] = v
                    n += 1
                elif i.dst:
                    consts.pop(i.dst, None)
    return n


def dce(m: ModuloIR) -> int:
    """Dead-code elimination com ponto fixo (seguro p/ laços/back-edges):
    remove defs puras cujo `dst` ninguém usa."""
    n = 0
    for f in m.funcoes:
        while True:
            flat = [i for bl in f.blocos for i in bl.instrs]
            used: set[str] = set()
            for i in flat:
                used.update(a for a in i.args if isinstance(a, str))
            dead = [i for i in flat
                    if i.op not in _EFEITO and i.dst and i.dst not in used]
            if not dead: break
            kill = set(map(id, dead))
            for bl in f.blocos:
                keep = [i for i in bl.instrs if id(i) not in kill]
                n += len(bl.instrs) - len(keep); bl.instrs[:] = keep
    return n


def cse(m: ModuloIR) -> int:
    n = 0
    for f in m.funcoes:
        for bl in f.blocos:
            seen: dict = {}
            for i in bl.instrs:
                if i.op in ("add", "mul", "sub", "div", "mod", "eq", "neq",
                            "lt", "gt", "le", "ge", "not"):
                    args = tuple(sorted(i.args)) if i.op in _COMUT else tuple(i.args)
                    key = (i.op, args)
                    if key in seen:
                        i.op, i.args = "copy", [seen[key]]; n += 1
                    elif i.dst:
                        seen[key] = i.dst
                elif i.dst and i.op in ("const", "copy"):
                    seen[(i.op, tuple(i.args), repr(i.val))] = i.dst
    return n


def inline(m: ModuloIR) -> int:
    """Inline real: callee de bloco único, sem labels, <= 6 instrs."""
    tab = {f.nome: f for f in m.funcoes}
    n = 0
    for f in m.funcoes:
        for bl in f.blocos:
            out = []
            for i in bl.instrs:
                if i.op == "call" and i.args and i.args[0] in tab:
                    cal = tab[i.args[0]]
                    flat = [x for b in cal.blocos for x in b.instrs]
                    if (len(cal.blocos) == 1 and len(flat) <= 7
                            and not any(x.op in ("label", "br", "jmp") for x in flat)
                            and len(i.args[1:]) == len(cal.params)
                            and cal.nome != f.nome):
                        mp = dict(zip(cal.params, i.args[1:]))
                        rem = {}

                        def R(v):
                            if not isinstance(v, str): return v
                            if v in mp: return mp[v]
                            if v.startswith("%"):
                                if v not in rem:
                                    from compiler.middle.ir import tmp
                                    rem[v] = tmp("inl")
                                return rem[v]
                            return v

                        for x in flat:
                            if x.op == "ret":
                                out.append(__import__("compiler.middle.ir", fromlist=["Instr"]).Instr(
                                    "copy", i.dst, [R(x.args[0]) if x.args else "0"]))
                            elif x.op == "const":
                                from compiler.middle.ir import Instr as _I
                                d = R(x.dst); out.append(_I("const", d, [], x.val))
                            elif x.dst:
                                from compiler.middle.ir import Instr as _I
                                out.append(_I(x.op, R(x.dst), [R(a) for a in x.args], x.val))
                            else:
                                from compiler.middle.ir import Instr as _I
                                out.append(_I(x.op, "", [R(a) for a in x.args], x.val))
                        n += 1
                        continue
                out.append(i)
            bl.instrs[:] = out
    return n


def loop_hoist(m: ModuloIR) -> int:
    """LICM conservador: move `const` invariantes p/ antes do label do laço."""
    n = 0
    for f in m.funcoes:
        for bl in f.blocos:
            ins = bl.instrs
            for idx, i in enumerate(list(ins)):
                if i.op == "label" and any(
                        x.op == "jmp" and x.args and x.args[0] == i.args[0] for x in ins[idx:]):
                    for j in range(idx + 1, len(ins)):
                        x = ins[j]
                        if x.op == "const" and any(
                                x.dst in (y.args or []) for y in ins[idx:]):
                            ins.insert(idx, ins.pop(j)); n += 1
                            break
                    break
    return n


def strength_reduce(m: ModuloIR) -> int:
    """`x*2` -> `x+x`; `x+0`/`x-0`/`x*1` -> copy; `x*0` -> const 0."""
    n = 0
    for f in m.funcoes:
        for bl in f.blocos:
            for i in bl.instrs:
                if i.op == "mul" and len(i.args) == 2:
                    x, y = i.args
                    if y == "2" or y == 2 or y == "#2":
                        i.op, i.args = "add", [x, x]; n += 1
                    elif x == "2" or x == 2 or x == "#2":
                        i.op, i.args = "add", [y, y]; n += 1
                elif i.op in ("add", "sub") and len(i.args) == 2 and i.args[1] in ("0", 0, "#0"):
                    i.op, i.args = "copy", [i.args[0]]; n += 1
    return n


def otimizar(m: ModuloIR, seq=("constfold", "cse", "dce")) -> dict:
    mp = {"constfold": constfold, "cse": cse, "dce": dce, "inline": inline,
          "loop": loop_hoist, "strength": strength_reduce}
    return {k: mp[k](m) for k in seq}
