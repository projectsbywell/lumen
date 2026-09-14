import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from compiler.frontend.lexer import tokenize
from compiler.frontend.parser import Parser
from compiler.middle.ir import Baixador
from compiler.backend.vm.bytecode import ModuloBC, verificar, link
from compiler.backend.vm.codegen_vm import gerar_dict
from compiler.backend.wasm.codegen_wasm import gerar_wat
from compiler.backend.c.codegen_c import gerar_c

SRC = 'module t\npub fn main() -> int { return 42; }\n'

class TBack(unittest.TestCase):
    def test_roundtrip(self):
        m = ModuloBC("t", [1, "a"], [("CONST", 0), ("HALT", 0)])
        self.assertEqual(ModuloBC.from_bytes(m.to_bytes()).consts, [1, "a"])
    def test_vm(self):
        mir = Baixador().baixar(Parser(tokenize(SRC)).parse())
        mod = gerar_dict(mir)
        self.assertIn("main", mod["functions"])
        self.assertEqual(mod["entry"], "main")
        last = mod["functions"]["main"]["bytecodes"][-1]
        self.assertEqual(last[0], "HALT")
    def test_wat(self):
        mir = Baixador().baixar(Parser(tokenize(SRC)).parse())
        self.assertIn('(export "main")', gerar_wat(mir))
    def test_c(self):
        mir = Baixador().baixar(Parser(tokenize(SRC)).parse())
        h, c = gerar_c(mir)
        self.assertIn("main", c)
    def test_link(self):
        a = ModuloBC("a", [1], [("CONST", 0), ("HALT", 0)])
        self.assertEqual(link([a]).consts, [1])

if __name__ == "__main__": unittest.main()
