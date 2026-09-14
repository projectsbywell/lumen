"""lumen run: .lum -> dict -> VM. Uso: python3 compiler/run.py prog.lum"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from compiler.frontend.lexer import tokenize
from compiler.frontend.parser import Parser
from compiler.frontend.semantica import analisar
from compiler.frontend.borrowck import verificar as ver_borrow
from compiler.middle.ir import Baixador
from compiler.middle.passes import otimizar
from compiler.backend.vm.codegen_vm import gerar_dict
from runtime.vm import VM


def run_src(src: str, entry: str = "main"):
    from compiler.lumenc import explicar
    toks = tokenize(src)
    ps = Parser(toks)
    prog = ps.parse()
    if ps.errs:
        raise SyntaxError(explicar(src, ps.errs))
    errs, _ = analisar(prog)
    if errs:
        raise SyntaxError(explicar(src, errs))
    berrs = ver_borrow(prog)
    if berrs:
        raise SyntaxError(explicar(src, berrs))
    mir = Baixador().baixar(prog)
    otimizar(mir)
    mod = gerar_dict(mir, entry)
    vm = VM()
    result = vm.executar(mod)
    return result, vm.output


def main(a):
    if len(a) < 2:
        print("uso: run.py <arq.lum> [entry]")
        return 2
    src = open(a[1], encoding="utf8").read()
    entry = a[2] if len(a) > 2 else "main"
    try:
        result, out = run_src(src, entry)
    except Exception as e:
        print(f"erro: {e}")
        return 1
    for line in out:
        print(line)
    if result is not None:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
