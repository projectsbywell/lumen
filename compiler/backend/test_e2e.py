"""E2E v0.2: .lum -> .lbc (dict JSON) -> VM, C (cc) e WAT.

Cobre aritmética, recursão, branches, loops e match de ponta a ponta,
além do verificador de operandos (verificar_dict) e do validador WAT.
Rode: python3 -m unittest compiler.backend.test_e2e
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from compiler.frontend.lexer import tokenize
from compiler.frontend.parser import Parser
from compiler.frontend.semantica import analisar
from compiler.frontend.borrowck import verificar as ver_borrow
from compiler.middle.ir import Baixador
from compiler.middle.passes import otimizar
from compiler.backend.vm.codegen_vm import gerar_dict, verificar_dict
from compiler.backend.wasm.codegen_wasm import gerar_wat, validar_wat
from compiler.backend.c.codegen_c import gerar_c, gerar_makefile
from runtime.vm import VM

FAT = """
fn fat(n: int) -> int {
    if n <= 1 { return 1; }
    return n * fat(n - 1);
}
fn main() -> int { return fat(5) + 10 * 2 - 3; }
"""

LOOPS = """
fn soma(n: int) -> int {
    let t: int = 0;
    let i: int = 1;
    while i <= n { t = t + i; i = i + 1; }
    return t;
}
fn classifica(x: int) -> int {
    match x { 0 => 100, 1 | 2 => 200, _ => 300 }
}
fn main() -> int { return soma(10) + classifica(2); }
"""


def pipeline(src: str, entry: str = "main") -> dict:
    """Pipeline completo .lum -> dict (igual a lumenc alvo lbc)."""
    ps = Parser(tokenize(src))
    prog = ps.parse()
    if ps.errs:
        raise SyntaxError(ps.errs[0])
    errs, _ = analisar(prog)
    if errs:
        raise SyntaxError(errs[0])
    berrs = ver_borrow(prog)
    if berrs:
        raise SyntaxError(berrs[0])
    mir = Baixador().baixar(prog)
    otimizar(mir)
    return gerar_dict(mir, entry)


def exec_dict(mod: dict):
    vm = VM()
    return vm.executar(mod), vm.output


class TestE2E(unittest.TestCase):
    def test_fatorial_aritmetica_vm(self):
        mod = pipeline(FAT)
        rep = verificar_dict(mod)
        self.assertEqual(rep["erros"], [], rep)
        result, _ = exec_dict(mod)
        self.assertEqual(result, 137)  # 120 + 20 - 3

    def test_lbc_json_roundtrip(self):
        # .lbc em disco é o dict em JSON: serializa, recarrega, executa.
        mod = pipeline(FAT)
        raw = json.dumps(mod)
        mod2 = json.loads(raw)
        rep = verificar_dict(mod2)
        self.assertEqual(rep["erros"], [], rep)
        result, _ = exec_dict(mod2)
        self.assertEqual(result, 137)

    def test_loops_match(self):
        mod = pipeline(LOOPS)
        rep = verificar_dict(mod)
        self.assertEqual(rep["erros"], [], rep)
        result, _ = exec_dict(mod)
        self.assertEqual(result, 55 + 200)  # soma(10)=55 + classifica(2)=200

    def test_002_fatorial_result_match(self):
        """Fix A: lowering match Ok(v)/Err(e) + `?` — examples/002 na VM."""
        src = open(os.path.join(os.path.dirname(__file__), "..", "..",
                                "examples", "002_fatorial.lum"),
                   encoding="utf8").read()
        mod = pipeline(src)
        rep = verificar_dict(mod)
        self.assertEqual(rep["erros"], [], rep)
        _, out = exec_dict(mod)
        self.assertIn("5! = 120", out)

    def test_004_match_guards_or(self):
        """Fix A: variável `v` com guards + or-pattern — examples/004 na VM."""
        src = open(os.path.join(os.path.dirname(__file__), "..", "..",
                                "examples", "004_match.lum"),
                   encoding="utf8").read()
        mod = pipeline(src)
        rep = verificar_dict(mod)
        self.assertEqual(rep["erros"], [], rep)
        _, out = exec_dict(mod)
        self.assertEqual(out, ["zero", "pequeno", "negativo", "grande", "médio"])

    def test_verificador_captura_pilha_vazia(self):
        mod = pipeline("fn main() -> int { return 7; }")
        bad = json.loads(json.dumps(mod))
        bad["functions"]["main"]["bytecodes"].insert(0, ["STORE", "x"])
        bad["functions"]["main"]["locals"].append("x")
        rep = verificar_dict(bad)
        self.assertTrue(rep["erros"], rep)

    def test_verificador_const_invalido(self):
        mod = pipeline("fn main() -> int { return 7; }")
        bad = json.loads(json.dumps(mod))
        bad["functions"]["main"]["bytecodes"].insert(0, ["CONST", 9999])
        rep = verificar_dict(bad)
        self.assertTrue(any("CONST" in e for e in rep["erros"]), rep)

    def test_verificador_avisa_call_desconhecida(self):
        mod = pipeline("fn main() -> int { return 7; }")
        bad = json.loads(json.dumps(mod))
        bad["functions"]["main"]["bytecodes"].insert(
            0, ["CALL", "fantasma_xyz"])
        rep = verificar_dict(bad)
        self.assertEqual(rep["erros"], [], rep)
        self.assertTrue(any("fantasma_xyz" in a for a in rep["avisos"]), rep)

    def test_wat_valido(self):
        ps = Parser(tokenize(FAT))
        prog = ps.parse()
        mir = Baixador().baixar(prog)
        wat = gerar_wat(mir)
        self.assertEqual(validar_wat(wat, ["fat", "main"]), [])
        self.assertIn("call $fat", wat)

    def test_wat_invalido(self):
        self.assertTrue(validar_wat("(module (func", ["f"]))

    def test_spawn_await_fut_pronta_async_vm(self):
        """P5.2: spawn de função + await Future pronta via codegen (SPAWN/AWAIT_FUT)."""
        import copy
        from compiler.middle.ir import ModuloIR, FuncaoIR, Bloco, Instr
        from runtime.threads import Future
        # Future pronta com valor 777
        fut = Future()
        fut.set_result(777)
        # Coroutine que faz await da Future pronta e imprime o valor
        b_coro = Bloco("entry")
        t_fut = "%fut"
        t_val = "%v"
        t_ret = "%r"
        b_coro.instrs.append(Instr("const", t_fut, [], fut))
        b_coro.instrs.append(Instr("await_fut", t_val, [t_fut]))
        b_coro.instrs.append(Instr("print", "", [t_val]))
        b_coro.instrs.append(Instr("const", t_ret, [], 0))
        b_coro.instrs.append(Instr("ret", "", [t_ret]))
        coro = FuncaoIR("coro", [], [b_coro])
        # Main faz spawn da coroutine e retorna
        b_main = Bloco("entry")
        t0 = "%t0"
        b_main.instrs.append(Instr("spawn", "", ["coro"]))
        b_main.instrs.append(Instr("const", t0, [], 0))
        b_main.instrs.append(Instr("ret", "", [t0]))
        main = FuncaoIR("main", [], [b_main])
        mod_ir = ModuloIR("test_async", [coro, main])
        mod = gerar_dict(mod_ir, "main")
        rep = verificar_dict(mod)
        self.assertEqual(rep["erros"], [], rep)
        # VM: entry HALT bloquearia prontas; trocar HALT final por RET para drenar fila
        mod_exec = copy.deepcopy(mod)
        code = mod_exec["functions"]["main"]["bytecodes"]
        if code and code[-1][0] == "HALT":
            code[-1] = ["RET", code[-1][1]]
        vm = VM()
        vm.executar(mod_exec)
        # coro foi spawnado e seu AWAIT_FUT pronto imprimiu 777
        self.assertIn("777", vm.output)
        # também valida variant Call spawn/await legado (b path)
        b2 = Bloco("entry")
        b2.instrs.append(Instr("const", "%a", [], fut))
        b2.instrs.append(Instr("call", "%b", ["await", "%a"]))
        b2.instrs.append(Instr("print", "", ["%b"]))
        b2.instrs.append(Instr("const", "%c", [], 0))
        b2.instrs.append(Instr("ret", "", ["%c"]))
        coro2 = FuncaoIR("coro2", [], [b2])
        b_main2 = Bloco("entry")
        b_main2.instrs.append(Instr("call", "%x", ["spawn", "coro2"]))
        b_main2.instrs.append(Instr("const", "%y", [], 0))
        b_main2.instrs.append(Instr("ret", "", ["%y"]))
        mod_ir2 = ModuloIR("test_legado", [coro2, FuncaoIR("main", [], [b_main2])])
        # Ajuste nome main duplication: usar main2
        mod_ir2.funcoes[1].nome = "main"
        mod2 = gerar_dict(mod_ir2, "main")
        # verificar deve aceitar SPAWN/AWAIT_FUT emitidos via call legado
        rep2 = verificar_dict(mod2)
        self.assertEqual(rep2["erros"], [], rep2)
        # checar que bytecode contém SPAWN/AWAIT_FUT
        has_spawn = any(op == "SPAWN" for op, _ in mod2["functions"]["main"]["bytecodes"])
        has_await = any(op == "AWAIT_FUT" for op, _ in mod2["functions"]["coro2"]["bytecodes"])
        self.assertTrue(has_spawn, "codegen não emitiu SPAWN via Call spawn")
        self.assertTrue(has_await, "codegen não emitiu AWAIT_FUT via Call await")

    @unittest.skipUnless(
        any(shutil.which(t) for t in ("cc", "cl", "gcc")),
        "compilador C indisponível (cc/cl/gcc)")
    def test_c_compila_e_roda(self):
        ps = Parser(tokenize(FAT))
        prog = ps.parse()
        mir = Baixador().baixar(prog)
        rt, code = gerar_c(mir)
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "lumen_rt.h"), "w").write(rt)
            open(os.path.join(d, "main.c"), "w").write(code)
            open(os.path.join(d, "Makefile"), "w").write(gerar_makefile())
            # Windows/PE: o binário gerado é sempre <nome>.exe, então `./app`
            # não resolve (WinError 2); no POSIX o nome é `app` (sem sufixo).
            # Alguns toolchains ignoram `-o`/sufixo: localiza o binário real
            # entre os candidatos em vez de assumir o nome.
            exe = "app.exe" if os.name == "nt" else "app"
            r = subprocess.run(["cc", "-std=c99", "-O2", "-Wall",
                                "-o", exe, "main.c"],
                               cwd=d, capture_output=True, text=True,
                               timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            cands = [exe, "app", "app.exe", "a.out", "a.exe", "main", "main.exe"]
            achado = next((c for c in cands
                           if os.path.isfile(os.path.join(d, c))), None)
            self.assertIsNotNone(achado, f"binário ausente em {d}: {os.listdir(d)}")
            r2 = subprocess.run([os.path.join(d, achado)],
                                capture_output=True, text=True, timeout=30)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertEqual(r2.stdout.strip(), "137")


if __name__ == "__main__":
    unittest.main()
