"""Testes do borrow checker v0.2-lite."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from compiler.frontend.lexer import tokenize
from compiler.frontend.parser import Parser
from compiler.frontend.borrowck import verificar


def bk(src):
    ps = Parser(tokenize(src))
    prog = ps.parse()
    assert ps.errs == [], ps.errs[:2]
    return verificar(prog)


class TestBorrow(unittest.TestCase):
    def test_copy_ok(self):
        self.assertEqual(bk("fn f() -> int { let x: int = 1; let y = x; return x + y; }"), [])

    def test_unknown_copy(self):
        self.assertEqual(bk("fn f(a: T) -> int { let b = a; return 1; }"), [])

    def test_move_ok_once(self):
        self.assertEqual(bk('fn f() -> int { let s: str = "a"; let t = s; return 1; }'), [])

    def test_use_after_move(self):
        errs = bk('fn f() -> int { let s: str = "a"; let t = s; println(s); return 1; }')
        self.assertTrue(any("move" in e for e in errs), errs)

    def test_double_move_call(self):
        errs = bk("fn g(x: str) -> int { return 1; }\nfn f() -> int { let s: str = \"a\"; g(s); g(s); return 1; }")
        self.assertTrue(any("move" in e for e in errs), errs)

    def test_borrow_then_read_ok(self):
        self.assertEqual(bk('fn f() -> int { let s: str = "a"; let r = &s; println(s); return 1; }'), [])

    def test_borrow_moved(self):
        errs = bk('fn f() -> int { let s: str = "a"; let t = s; let r = &s; return 1; }')
        self.assertTrue(any("movido" in e for e in errs), errs)

    def test_mut_exclusion(self):
        errs = bk('fn f() -> int { let s: str = "a"; let a = &s; let b = &mut s; return 1; }')
        self.assertTrue(any("mut" in e for e in errs), errs)

    def test_reassign_ends_borrow(self):
        self.assertEqual(bk('fn f() -> int { let mut s: str = "a"; let r = &s; s = "b"; println(s); return 1; }'), [])

    def test_amp_syntax(self):
        self.assertEqual(bk('fn f() -> int { let s: str = "a"; let r = &mut s; return 1; }'), [])

    # -- NLL (v0.2): empréstimo termina no último uso -----------------
    def test_nll_move_after_last_use(self):
        # r morre após println(s); o move de s depois é legal.
        self.assertEqual(bk('fn f() -> int { let s: str = "a"; let r = &s; println(s); let t = s; return 1; }'), [])

    def test_nll_borrow_dead_without_reads(self):
        # empréstimo nunca usado + referente nunca lido: move legal.
        self.assertEqual(bk('fn f() -> int { let s: str = "a"; let r = &s; let t = s; return 1; }'), [])

    def test_nll_live_conflict_still_errors(self):
        # &mut enquanto o empréstimo ainda está vivo (s lido depois).
        errs = bk('fn f() -> int { let s: str = "a"; let r = &s; let b = &mut s; println(s); return 1; }')
        self.assertTrue(any("mut" in e for e in errs), errs)

    def test_nll_use_after_move_still_errors(self):
        errs = bk('fn f() -> int { let s: str = "a"; let r = &s; let t = s; println(s); return 1; }')
        self.assertTrue(errs, errs)


if __name__ == "__main__":
    unittest.main()

class TestConst(unittest.TestCase):
    def _comp(self, src):
        from compiler.lumenc import compilar
        return compilar(src, "vm")

    def test_const_basic(self):
        from compiler.run import run_src
        r, _ = run_src('module t\nconst N: int = 40 + 2;\npub fn main() -> int { return N; }')
        self.assertEqual(r, 42)

    def test_const_reuse(self):
        from compiler.run import run_src
        r, _ = run_src('module t\nconst S: str = "ab";\npub fn main() -> int { println(S); println(S); return 1; }')
        self.assertEqual(r, 1)

    def test_const_borrow(self):
        self.assertEqual(bk('const V: str = "x";\nfn f() -> int { println(V); println(V); return 1; }'), [])
