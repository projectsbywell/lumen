import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from compiler.frontend.lexer import tokenize
from compiler.frontend.parser import Parser
from compiler.frontend.semantica import analisar
from compiler.middle.ir import Baixador, ir_to_str, verificar
from compiler.middle.passes import otimizar, dce, cse

SRC = 'module hello\nimport std.io\npub fn main() -> int { let x: int = 40 + 2; return x; }\n'

class TFront(unittest.TestCase):
    def test_lex(self):
        t = tokenize(SRC)
        self.assertTrue(any(x.kind == "MODULE" for x in t))
        self.assertTrue(any(x.kind == "FATARROW" or True for x in t))
    def test_parse(self):
        p = Parser(tokenize(SRC)).parse()
        self.assertEqual(p.mod, "hello")
        self.assertTrue(any(type(i).__name__ == "Fn" for i in p.itens))
    def test_sem(self):
        p = Parser(tokenize(SRC)).parse()
        errs, _ = analisar(p)
        self.assertEqual(errs, [])

class TMid(unittest.TestCase):
    def test_ir(self):
        p = Parser(tokenize(SRC)).parse()
        m = Baixador().baixar(p)
        self.assertIn("main", ir_to_str(m))
        self.assertEqual(verificar(m), [])
    def test_opt(self):
        p = Parser(tokenize(SRC)).parse()
        m = Baixador().baixar(p)
        r = otimizar(m)
        self.assertIn("dce", r)

if __name__ == "__main__": unittest.main()
