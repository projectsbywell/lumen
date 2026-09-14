"""Gerador IR -> WAT (WebAssembly texto), v0.2.

Modelo: cada função vira dispatch loop sobre segmentos:
  (func $f (params i32) (result i32)
    (local $pc i32) (local $t1 i32) ...
    (block $halt
      (loop $step
        (if (i32.eq (local.get $pc) (i32.const K)) (then ...seg...))
        ...
        (br $step))))
Saltos viram `local.set $pc` + `br $step`; `ret` grava `$ret` e sai.
Valores: i32 (floats truncados, bool 1/0, resto 0 — v0.3 tipa).
"""
from __future__ import annotations

_CMP = {"eq": "i32.eq", "neq": "i32.ne", "lt": "i32.lt_s",
        "gt": "i32.gt_s", "le": "i32.le_s", "ge": "i32.ge_s"}
_ARI = {"add": "i32.add", "sub": "i32.sub", "mul": "i32.mul",
        "div": "i32.div_s", "mod": "i32.rem_s"}


def _const(v: str) -> str:
    if isinstance(v, bool):
        return f"i32.const {1 if v else 0}"
    if isinstance(v, int):
        return f"i32.const {v}"
    if isinstance(v, float):
        return f"i32.trunc_f64_s (f64.const {v})"
    return "i32.const 0"


IMPORTS_WAT = '(import "lumen" "print" (func $print (param i32)))'
MEMORY_WAT = '(memory (export "mem") 1)'


def exportados(mod_ir) -> list[str]:
    """Nomes exportados pelo módulo (todas as funções)."""
    return [f.nome for f in mod_ir.funcoes]


def validar_wat(wat: str, esperados: list[str] | None = None) -> list[str]:
    """Validação estrutural do WAT gerado (v0.2).

    Checa: parênteses balanceados, presença de `(module`, import de
    `print` e `memory`, cada função esperada exportada com loop de
    dispatch (`$pc`/`$step`/`$halt`) e epílogo `local.get $ret`.
    Retorna lista de erros (vazia = válido).
    """
    errs: list[str] = []
    if wat.count("(") != wat.count(")"):
        errs.append(f"parênteses desbalanceados "
                    f"({wat.count('(')} vs {wat.count(')')})")
    for marca in ("(module", IMPORTS_WAT, MEMORY_WAT):
        if marca not in wat:
            errs.append(f"marca ausente: {marca[:40]}")
    for fn in esperados or []:
        if f'(export "{fn}")' not in wat:
            errs.append(f"função `{fn}` não exportada")
    if "(local $pc i32)" not in wat:
        errs.append("dispatch por $pc ausente")
    if "local.get $ret" not in wat:
        errs.append("epílogo `local.get $ret` ausente")
    return errs


def gerar_wat(mod_ir) -> str:
    names = {f.nome for f in mod_ir.funcoes}
    out = ["(module",
           f'  {IMPORTS_WAT}',
           f'  {MEMORY_WAT}']
    for f in mod_ir.funcoes:
        # segmenta por labels
        segs: list[list] = [[]]
        labmap: dict[str, int] = {}
        for bl in f.blocos:
            for i in bl.instrs:
                if i.op == "label":
                    labmap[i.args[0]] = len(segs)
                    segs.append([])
                else:
                    segs[-1].append(i)
        if segs and not segs[-1] and len(segs) > 1:
            segs.pop()
        # índice do segmento de cada label (labels vazios apontam p/ próx)
        locals_set: list[str] = []
        params = " ".join(f"(param ${p} i32)" for p in f.params)

        def loc(n):
            n = n.replace("%", "t").replace(".", "_").replace(":", "_")
            if n not in f.params and n not in locals_set:
                locals_set.append(n)
            return "$" + n

        body: list[str] = []
        for k, seg in enumerate(segs):
            lines: list[str] = []
            nxt = k + 1
            for ins in seg:
                op = ins.op
                if op == "const":
                    lines.append(f"{_const(ins.val)}")
                    lines.append(f"local.set {loc(ins.dst)}")
                elif op == "copy":
                    lines.append(f"local.get {loc(ins.args[0])}")
                    lines.append(f"local.set {loc(ins.dst)}")
                elif op in _ARI:
                    lines.append(f"local.get {loc(ins.args[0])}")
                    lines.append(f"local.get {loc(ins.args[1])}")
                    lines.append(_ARI[op])
                    lines.append(f"local.set {loc(ins.dst)}")
                elif op in _CMP:
                    lines.append(f"local.get {loc(ins.args[0])}")
                    lines.append(f"local.get {loc(ins.args[1])}")
                    lines.append(_CMP[op])
                    lines.append(f"local.set {loc(ins.dst)}")
                elif op == "not":
                    lines.append(f"local.get {loc(ins.args[0])}")
                    lines.append("i32.eqz")
                    lines.append(f"local.set {loc(ins.dst)}")
                elif op == "call":
                    fn = ins.args[0]
                    if fn in names:
                        for a in ins.args[1:]:
                            lines.append(f"local.get {loc(a)}")
                        lines.append(f"call ${fn}")
                    else:
                        lines.append("i32.const 0")
                    lines.append(f"local.set {loc(ins.dst)}")
                elif op == "print":
                    lines.append(f"local.get {loc(ins.args[0])}")
                    lines.append("call $print")
                elif op == "ret":
                    lines.append(f"local.get {loc(ins.args[0])}")
                    lines.append("local.set $ret")
                    lines.append("i32.const -1")
                    lines.append("local.set $pc")
                    lines.append("br $halt")
                    nxt = -99  # sem fallthrough
                elif op == "jmp":
                    lines.append(f"i32.const {labmap.get(ins.args[0], nxt)}")
                    lines.append("local.set $pc")
                    lines.append("br $step")
                    nxt = -99
                elif op == "br":
                    c, t, fl = ins.args
                    lines.append(f"i32.const {labmap.get(t, nxt)}")
                    lines.append(f"i32.const {labmap.get(fl, nxt)}")
                    lines.append(f"local.get {loc(c)}")
                    lines.append("select")
                    lines.append("local.set $pc")
                    lines.append("br $step")
                    nxt = -99
            if nxt >= 0:
                lines.append(f"i32.const {nxt}")
                lines.append("local.set $pc")
                lines.append("br $step")
            code = "\n        ".join(lines) if lines else "nop"
            body.append(f"    (if (i32.eq (local.get $pc) (i32.const {k}))\n"
                       f"      (then\n        {code}))")
        locs = " ".join(f"(local ${l} i32)" for l in locals_set)
        out.append(f'  (func ${f.nome} (export "{f.nome}") {params} (result i32)')
        out.append(f"    (local $pc i32) (local $ret i32) {locs}".rstrip())
        out.append("    (block $halt")
        out.append("      (loop $step")
        out.extend(body)
        out.append("        (if (i32.lt_s (local.get $pc) (i32.const 0))")
        out.append("          (then (br $halt)))")
        out.append("        (br $step)))")
        out.append("    local.get $ret)")
    out.append(")")
    return "\n".join(out)
