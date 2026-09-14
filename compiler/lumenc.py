"""Driver lumenc: .lum -> .lbc (dict JSON) / .wat / .c / ir"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from compiler.frontend.lexer import tokenize
from compiler.frontend.parser import Parser
from compiler.frontend.semantica import analisar
from compiler.frontend.borrowck import verificar as ver_borrow
from compiler.middle.ir import Baixador, ir_to_str, verificar as ver_ir
from compiler.middle.passes import otimizar
from compiler.backend.vm.codegen_vm import gerar as gen_vm
from compiler.backend.wasm.codegen_wasm import gerar_wat
from compiler.backend.c.codegen_c import gerar_c

def explicar(src: str, errs: list[str]) -> str:
    """Diagnóstico de alta qualidade: cada erro com snippet da linha.

    Os erros do front-end já trazem `linha:col`; aqui anexamos a linha
    fonte e um cursor `^` para localização imediata.
    """
    lines = src.splitlines()
    out = []
    for e in errs:
        out.append(f"erro: {e}")
        import re
        m = re.search(r"(\d+):(\d+)", e)
        if m:
            ln, col = int(m.group(1)), int(m.group(2))
            if 1 <= ln <= len(lines):
                out.append(f"  {lines[ln - 1]}")
                out.append(f"  {' ' * max(col - 1, 0)}^")
    return "\n".join(out)


def compilar(src: str, target="vm", opt=True):
    toks = tokenize(src)
    ps = Parser(toks)
    prog = ps.parse()
    if ps.errs: raise SyntaxError("; ".join(ps.errs))
    errs, _ = analisar(prog)
    if errs: raise SyntaxError("; ".join(errs))
    berrs = ver_borrow(prog)
    if berrs: raise SyntaxError("; ".join(berrs))
    mir = Baixador().baixar(prog)
    if opt: otimizar(mir)
    if target == "vm": return gen_vm(mir)
    if target == "lbc": return gen_vm(mir)  # mesmo dict; arquivo grava JSON
    if target == "wat": return gerar_wat(mir)
    if target == "c": return gerar_c(mir)
    if target == "ir": return ir_to_str(mir)
    raise ValueError(target)

def main(a):
    if len(a) < 3:
        print("uso: lumenc.py <arq.lum> <vm|lbc|wat|c|ir> [saida]"); return 2
    src = open(a[1], encoding="utf8").read()
    tgt = a[2]
    out = compilar(src, tgt)
    dest = a[3] if len(a) > 3 else None
    if tgt in ("vm", "lbc"):
        txt = json.dumps(out, ensure_ascii=False)
        if dest: open(dest, "w", encoding="utf8").write(txt)
        else: print(txt)
    else:
        txt = out[1] if tgt == "c" else out
        (open(dest, "w").write(txt) if dest else print(txt))
    return 0

if __name__ == "__main__": raise SystemExit(main(sys.argv))
