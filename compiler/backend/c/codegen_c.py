"""Gerador IR -> C99 portável, v0.2 (ints/bools; goto direto dos labels)."""
from __future__ import annotations

RT_H = r"""#pragma once
/* Runtime embutido do Lumen (C99 portável: só <stdio.h>/<stdlib.h>). */
#include <stdio.h>
#include <stdlib.h>
typedef long long lumen_int;
static inline void lumen_print_int(lumen_int x){ printf("%lld\n", x); }
static inline lumen_int lumen_checked_div(lumen_int a, lumen_int b){
    if (b == 0){ fprintf(stderr, "erro: divisão por zero\n"); exit(1); }
    return a / b;
}
static inline lumen_int lumen_checked_mod(lumen_int a, lumen_int b){
    if (b == 0){ fprintf(stderr, "erro: divisão por zero\n"); exit(1); }
    return a % b;
}
"""

_CMP = {"eq": "==", "neq": "!=", "lt": "<", "gt": ">", "le": "<=", "ge": ">="}
_ARI = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%"}


def _v(n: str) -> str:
    return "v_" + n.replace("%", "").replace(".", "_")


def _cval(v) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(int(v))
    return "0"


def gerar_c(mod_ir) -> tuple[str, str]:
    decls: list[str] = []
    for f in mod_ir.funcoes:
        params = ", ".join(f"lumen_int {_v(p)}" for p in f.params) or "void"
        temps: list[str] = []

        def tmp(n):
            v = _v(n)
            if v not in temps and v not in [_v(p) for p in f.params]:
                temps.append(v)
            return v

        lines: list[str] = []
        for bl in f.blocos:
            for i in bl.instrs:
                op = i.op
                if op == "label":
                    lines.append(f"  {i.args[0]}: ;")
                elif op == "const":
                    lines.append(f"  {tmp(i.dst)} = {_cval(i.val)};")
                elif op == "copy":
                    lines.append(f"  {tmp(i.dst)} = {tmp(i.args[0])};")
                elif op in _ARI:
                    if op == "div":
                        lines.append(f"  {tmp(i.dst)} = lumen_checked_div({tmp(i.args[0])}, {tmp(i.args[1])});")
                    elif op == "mod":
                        lines.append(f"  {tmp(i.dst)} = lumen_checked_mod({tmp(i.args[0])}, {tmp(i.args[1])});")
                    else:
                        lines.append(f"  {tmp(i.dst)} = {tmp(i.args[0])} {_ARI[op]} {tmp(i.args[1])};")
                elif op in _CMP:
                    lines.append(f"  {tmp(i.dst)} = {tmp(i.args[0])} {_CMP[op]} {tmp(i.args[1])};")
                elif op == "not":
                    lines.append(f"  {tmp(i.dst)} = !{tmp(i.args[0])};")
                elif op == "call":
                    fn, ags = i.args[0], i.args[1:]
                    if fn in ("println", "print"):
                        for a in ags:
                            lines.append(f"  lumen_print_int({tmp(a)});")
                        lines.append(f"  {tmp(i.dst)} = 0;")
                    elif fn.endswith("!") or fn in ("vec", "map", "metodo") \
                            or "::" in fn or "." in fn:
                        lines.append(f"  {tmp(i.dst)} = 0;")
                    else:
                        lines.append(f"  {tmp(i.dst)} = lumen_{fn}({', '.join(tmp(a) for a in ags)});")
                elif op == "print":
                    lines.append(f"  lumen_print_int({tmp(i.args[0])});")
                elif op == "ret":
                    lines.append(f"  return {tmp(i.args[0])};")
                elif op == "jmp":
                    lines.append(f"  goto {i.args[0]};")
                elif op == "br":
                    c, t, fl = i.args
                    lines.append(f"  if ({tmp(c)}) goto {t}; else goto {fl};")
        tdecl = ("  lumen_int " + ", ".join(temps) + ";\n" if temps else "")
        decls.append(f"lumen_int lumen_{f.nome}({params}) {{\n{tdecl}" + "\n".join(lines) + "\n}")
    has_main = any(f.nome == "main" for f in mod_ir.funcoes)
    main = ("int main(void){ lumen_print_int(lumen_main()); return 0; }\n"
            if has_main else "int main(void){ return 0; }\n")
    return RT_H, '#include "lumen_rt.h"\n' + "\n".join(decls) + "\n" + main

MAKE_TMPL = """CC=cc
CFLAGS=-std=c99 -O2 -Wall -Wextra
SRC=main.c
OUT=app

all: $(OUT)

$(OUT): $(SRC) lumen_rt.h
\t$(CC) $(CFLAGS) -o $(OUT) $(SRC)

run: $(OUT)
\t./$(OUT)

clean:
\trm -f $(OUT)

.PHONY: all run clean
"""


def gerar_makefile() -> str:
    """Makefile portável p/ o C gerado (targets: all, run, clean)."""
    return MAKE_TMPL
