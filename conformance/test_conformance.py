"""Conformidade como código (v0.2): os 50 casos da spec como unittest.

Cada caso de `suite.py` vira um subTest executável no CI, além de
meta-testes (cobertura de categorias da spec, ids únicos, relatório).
Rode: python3 -m unittest conformance.test_conformance
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import suite
from suite import CASES, SPEC_VERSION, run_suite

CATEGORIAS_ESPERADAS = {"lexer", "parser", "tipos", "match", "struct_enum",
                        "bytecode", "backends", "runtime", "stdlib"}


class TestConformanceCode(unittest.TestCase):
    def test_casos_todos_passam(self):
        self.assertGreaterEqual(len(CASES), 50,
                                f"suíte encolheu: {len(CASES)} casos")
        for c in CASES:
            with self.subTest(c["id"]):
                try:
                    actual = c["run"](c["src"])
                except Exception as e:  # noqa: BLE001
                    self.fail(f"{c['id']}: EXC {type(e).__name__}: {e}")
                self.assertEqual(actual, c["expected"],
                                 f"{c['id']} ({c['category']}) {c['name']}")

    def test_categorias_cobrem_spec(self):
        cats = {c["category"] for c in CASES}
        for cat in CATEGORIAS_ESPERADAS:
            self.assertIn(cat, cats, f"categoria sem casos: {cat}")

    def test_ids_unicos(self):
        ids = [c["id"] for c in CASES]
        self.assertEqual(len(ids), len(set(ids)), "ids duplicados")

    def test_run_suite_100(self):
        results = run_suite()
        fails = [r for r in results if r["status"] != "PASS"]
        self.assertEqual(fails, [], [r["id"] for r in fails])
        self.assertEqual(len(results), len(CASES))

    def test_versao_spec(self):
        self.assertRegex(SPEC_VERSION, r"^\d+\.\d+\.\d+$")

    def test_main_cli(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "r.json")
            rc = suite.main(["--filter", "lexer", "--json", out])
            self.assertEqual(rc, 0)
            rep = json.load(open(out, encoding="utf-8"))
            self.assertEqual(rep["passed"], rep["total"])
            self.assertTrue(rep["success"])


class TestSuiteInternals(unittest.TestCase):
    """v0.2: exercita os internos da suíte (lexer, parser, aval previous,
    codegens de referência, run_main) — mira de cobertura ≥ 80%."""

    # -- lexer ------------------------------------------------------
    def test_lex_comentarios(self):
        self.assertEqual(suite.toks_simple("/* bloco */ 1_000 // linha"),
                         [("INT", 1000)])

    def test_lex_erros(self):
        for bad in ('"ab', '"a\\qb"', "'ab'", '"a\nb"', "/* sem fim"):
            with self.subTest(bad[:8]):
                with self.assertRaises(SyntaxError):
                    suite.lex(bad)

    def test_lex_escapes(self):
        self.assertEqual(suite.toks_simple(r'"a\nb"'), [("STR", "a\nb")])
        self.assertEqual(suite.toks_simple("'\\n'"), [("CHAR", "\n")])

    # -- parser -----------------------------------------------------
    def test_parse_helpers(self):
        self.assertEqual(
            suite.parse_struct_def("pub struct P { x: f64 }"),
            {"name": "P", "fields": ["x"]})
        self.assertEqual(
            suite.parse_enum_def("pub enum E { A, B(i32) }"),
            {"name": "E", "variants": [("A", 0), ("B", 1)]})
        self.assertEqual(suite.parse_macro_def("macro m(a) { a }")["name"],
                         "m")
        f = suite.parse_fn_def(
            "async fn f(x: i32) -> i32 { return x; }")
        self.assertTrue(f["async"])
        self.assertEqual(f["ret"], "i32")

    def test_parse_erro(self):
        with self.assertRaises(SyntaxError):
            suite.parse_expr_src("[1, 2]")

    # -- avaliador --------------------------------------------------
    def test_ev_div_zero(self):
        with self.assertRaises(suite.LumenPanic):
            suite.ev(suite.parse_expr_src("1 / 0"), suite.base_env())

    def test_ev_tipos(self):
        self.assertEqual(suite.tinfer(
            suite.parse_expr_src("true && false"), {}), "bool")
        self.assertEqual(
            suite.to_py(suite.ev(suite.parse_expr_src("Ok(1)"),
                                 suite.base_env())),
            ("Ok", [1]))
        self.assertEqual(
            suite.to_py(suite.ev(suite.parse_expr_src("None"),
                                 suite.base_env())),
            ("None", []))

    def test_pmatch(self):
        self.assertEqual(suite.pmatch(("pvar", "n"), ("i32", 3), {}),
                         {"n": ("i32", 3)})
        self.assertIsNone(suite.pmatch(("plit", 1), ("i32", 2), {}))
        self.assertIsNotNone(suite.pmatch(("pwild",), ("i32", 2), {}))

    def test_ev_match(self):
        subj = suite.parse_expr_src("2")
        arms = [[("por", [("plit", 1), ("plit", 2)]), None,
                 suite.parse_expr_src("10")],
                [("pwild",), None, suite.parse_expr_src("99")]]
        self.assertEqual(suite.to_py(suite.ev_match(
            subj, arms, suite.base_env())), 10)
        with self.assertRaises(suite.LumenPanic):
            suite.ev_match(suite.parse_expr_src("5"),
                           [[("plit", 1), None,
                             suite.parse_expr_src("1")]],
                           suite.base_env())

    # -- run_main ---------------------------------------------------
    def test_run_main_ok(self):
        out, code, err = suite.run_main(
            "fn id(x: int) -> int { return x; } "
            "fn main() { println(id(7)); }")
        self.assertEqual((out, code), ("7\n", 0))

    def test_run_main_panic(self):
        out, code, err = suite.run_main('fn main() { panic("x"); }')
        self.assertEqual(code, 1)

    def test_run_main_sem_main(self):
        self.assertEqual(suite.run_main("fn f() { return 1; }")[1], 2)

    def test_run_main_err_nao_tratado(self):
        out, code, err = suite.run_main(
            "fn main() -> int { return math::fat(0 - 1)?; }")
        self.assertEqual(code, 1)
        self.assertIn("n negativo", err)

    # -- codegens de referência -------------------------------------
    def test_codegen_vm_roundtrip(self):
        code, consts = suite.compile_expr(
            suite.parse_expr_src("10 - 3 * 2"))
        self.assertIn("MUL", suite.disasm(code, consts))
        _stack, val = suite.vm_run(code, consts)
        self.assertEqual(suite.to_py(val), 4)

    def test_codegen_c(self):
        c = suite.codegen_c(suite.parse_expr_src("1 + 2"))
        self.assertIn("int32_t", c)
        with self.assertRaises(suite.LumenTypeErr):
            suite.codegen_c(suite.parse_expr_src('"a"'))

    def test_codegen_wasm(self):
        w = suite.codegen_wasm(suite.parse_expr_src("7"))
        self.assertIn('export "main"', w)
        with self.assertRaises(suite.LumenTypeErr):
            suite.codegen_wasm(suite.parse_expr_src("true"))


class TestSuiteEvalPaths(unittest.TestCase):
    """v0.2b: caminhos do avaliador de referência (struct/range/campo,
    unários, strings, coleções, if/match como expressão, builtins)."""

    def ok(self, src):
        return suite._ok(src)

    def test_struct_literal_e_campo(self):
        v = self.ok("Ponto { x: 1, y: 2 }")
        self.assertEqual(v, {"x": 1, "y": 2})

    def test_range(self):
        self.assertEqual(self.ok("1..5"), [1, 2, 3, 4])
        self.assertEqual(self.ok("1..=3"), [1, 2, 3])

    def test_unarios(self):
        self.assertEqual(self.ok("-(4 + 1)"), -5)
        self.assertEqual(self.ok("!false"), True)
        with self.assertRaises(suite.LumenTypeErr):
            self.ok('-"a"')
        with self.assertRaises(suite.LumenTypeErr):
            self.ok("!1")

    def test_strings_e_comparacoes(self):
        self.assertEqual(self.ok('"a" + "b"'), "ab")
        self.assertEqual(self.ok("3 % 2"), 1)
        self.assertEqual(self.ok("2 < 3"), True)
        self.assertEqual(self.ok("2 == 2"), True)

    def test_colecoes(self):
        self.assertEqual(self.ok("vec![1, 2]"), [1, 2])
        self.assertEqual(self.ok('map!{"a": 1}'), {"a": 1})
        self.assertEqual(self.ok("vec::len(vec![1,2,3])"), 3)

    def test_if_match_expr(self):
        self.assertEqual(self.ok("if true { 1 } else { 2 }"), 1)
        self.assertEqual(self.ok("match 1 { 1 => 10, _ => 99 }"), 10)

    def test_builtins(self):
        self.assertEqual(self.ok("math::sqrt(9)"), ("Ok", 3.0))
        self.assertEqual(self.ok('str::len("ola")'), 3)

    def test_var_indefinida(self):
        with self.assertRaises(NameError):
            self.ok("zz_top_inexistente")

    # -- run_stmts / call_user_fn ---------------------------------
    def test_run_atribuicao(self):
        out, code, _ = suite.run_main(
            "fn main() { let x = 1; x = x + 41; println(x); }")
        self.assertEqual((out, code), ("42\n", 0))

    def test_run_match_stmt(self):
        out, code, _ = suite.run_main(
            "fn main() { match 2 { 1 => println(1), _ => println(99) }; }")
        self.assertEqual((out, code), ("99\n", 0))

    def test_run_chamadas_aninhadas(self):
        out, code, _ = suite.run_main(
            "fn soma(a: int, b: int) -> int { return a + b; } "
            "fn main() { println(soma(soma(1, 2), 39)); }")
        self.assertEqual((out, code), ("42\n", 0))

    def test_run_aridade(self):
        with self.assertRaises(suite.LumenTypeErr):
            suite.run_main("fn f(a: int, b: int) -> int { return a; } "
                           "fn main() { println(f(1)); }")


if __name__ == "__main__":
    unittest.main()
