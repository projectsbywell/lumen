"""Cobertura extra do front-end/middle/backends + lumenc nos 16 exemplos."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from compiler.frontend.lexer import tokenize, LexError, KEYWORDS
from compiler.frontend.parser import Parser
from compiler.frontend.semantica import analisar
from compiler.frontend import ast_nodes as A
from compiler.middle.ir import ModuloIR, FuncaoIR, Bloco, Instr, Baixador, ir_to_str, verificar
from compiler.middle import passes as P
from compiler.backend.vm.bytecode import ModuloBC, verificar as ver_bc, link
from compiler.lumenc import compilar

EXDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples")
HELLO = 'module hello\nimport std.io\nuse std::io\npub fn main() -> int { let x: int = 40 + 2; return x; }\n'


def parse1(src):
    ps = Parser(tokenize(src))
    prog = ps.parse()
    return ps, prog


class TestLexerExtra(unittest.TestCase):
    def test_all_keywords(self):
        for kw in sorted(KEYWORDS):
            toks = tokenize(kw)
            self.assertEqual(toks[0].kind, kw.upper(), kw)

    def test_syms2(self):
        toks = tokenize("=> -> :: == != <= >= && || .. += -= *= /=")
        kinds = [t.kind for t in toks[:-1]]
        self.assertIn("FATARROW", kinds)
        self.assertIn("ARROW", kinds)
        self.assertIn("COLON2", kinds)
        self.assertIn("DOT2", kinds)

    def test_misc_tokens(self):
        toks = tokenize('/// doc\n"x" \'c\' 1_000 3.14 _x')
        kinds = [t.kind for t in toks]
        self.assertIn("DOC", kinds)
        self.assertIn("CHAR", kinds)
        self.assertIn("IDENT", kinds)  # `_x` e `_` isolado: ramo IDENT

    def test_unicode_ident(self):
        toks = tokenize("olá")
        self.assertEqual(toks[0].kind, "IDENT")

    def test_unterminated(self):
        with self.assertRaises(LexError):
            tokenize('"abc')
        with self.assertRaises(LexError):
            tokenize("'a")
        with self.assertRaises(LexError):
            tokenize("@")

    def test_hash(self):
        toks = tokenize("#[test]")
        self.assertEqual([t.kind for t in toks][:-1], ["HASH", "LBK", "IDENT", "RBK"])


class TestParserExtra(unittest.TestCase):
    def test_hello_full(self):
        ps, prog = parse1(HELLO)
        self.assertEqual(ps.errs, [])
        self.assertEqual(prog.mod, "hello")
        self.assertEqual(len(prog.imports), 2)
        self.assertEqual(prog.itens[0].name, "main")

    def test_items(self):
        src = ('struct P { x: int }\nenum E { A, B(int) }\n'
               'trait T { }\nimpl P { fn m(self) -> int { return 1; } }\n'
               '#[test]\nmacro dobrar!(x) { x }\nasync fn f() -> int { return 1; }\n')
        ps, prog = parse1(src)
        self.assertEqual(ps.errs, [], ps.errs[:2])
        kinds = [type(i).__name__ for i in prog.itens]
        self.assertIn("Struct", kinds)
        self.assertIn("Enum", kinds)
        self.assertIn("Fn", kinds)

    def test_match_patterns(self):
        ps, prog = parse1('fn f(x: int) -> int { return match x { 0 => 1, 1 | 2 => 3, v if v < 0 => 4, _ => 5, } }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        m = prog.itens[0].body[0].expr
        self.assertEqual(len(m.bracos), 4)
        self.assertEqual(m.bracos[1].pat, "1|2")
        self.assertIsNotNone(m.bracos[2].guard)

    def test_ctor_patterns(self):
        ps, prog = parse1('fn f(x: int) -> int { return match x { Ok(v) => v, Forma::C(r) => r, } }')
        self.assertEqual(ps.errs, [], ps.errs[:2])

    def test_struct_literal_vs_while(self):
        ps, prog = parse1('fn f() -> int { let mut i: int = 0; while i < 3 { i = i + 1; } return i; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        ps2, prog2 = parse1('struct P { x: int }\nfn f() -> int { let p = P { x: 1 }; return 1; }')
        self.assertEqual(ps2.errs, [], ps2.errs[:2])

    def test_calls(self):
        ps, prog = parse1('fn f() -> int { let a = vec![1, 2]; let b = m!{ }; let c = g!(1); let d = o.m(2); return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])

    def test_ops(self):
        ps, prog = parse1('fn f(a: int) -> int { let b = -a + !a; let c = a?; let d = spawn g(a); let e = await h; let r = 0..a; return b; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])

    def test_assign_ifexpr_block(self):
        ps, prog = parse1('fn f(a: int) -> int { let mut x: int = 1; x = 2; x += 3; let y = if a { 1 } else { 2 }; let z = match a { _ => { let q: int = 1; q } }; return x; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])

    def test_recovery(self):
        ps, prog = parse1('} ;;; ! ;;; fn ok() -> int { return 1; } ! ! fn ok2() -> int { return 2; }')
        names = [i.name for i in prog.itens if type(i).__name__ == "Fn"]
        self.assertIn("ok", names)
        self.assertIn("ok2", names)
        self.assertTrue(ps.errs)

    def test_unit_empty(self):
        ps, prog = parse1('fn f() -> int { return Ok(()); }')
        self.assertEqual(ps.errs, [], ps.errs[:2])

    def test_generics(self):
        ps, prog = parse1('fn id<T>(x: T) -> T { return x; }\nfn f() -> Result<i32, str> { return id(1); }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        self.assertEqual(prog.itens[1].ret, "Result<i32,str>")


class TestSemanticaExtra(unittest.TestCase):
    def test_forward_ref(self):
        _, prog = parse1('fn a() -> int { return b(); }\nfn b() -> int { return 1; }')
        errs, _ = analisar(prog)
        self.assertEqual(errs, [])

    def test_undefined(self):
        _, prog = parse1('fn a() -> int { return zzz; }')
        errs, _ = analisar(prog)
        self.assertTrue(any("zzz" in e for e in errs))

    def test_externals_ok(self):
        _, prog = parse1('fn a() -> int { let x = math::sqrt(4); let y = vec; return Ok(1); }')
        errs, _ = analisar(prog)
        self.assertEqual(errs, [])


class TestTraitsSubtipos(unittest.TestCase):
    """v0.2: bounds de traits + subtipagem estrutural."""
    def an(self, src):
        ps, prog = parse1(src)
        self.assertEqual(ps.errs, [], ps.errs[:2])
        errs, _ = analisar(prog)
        return errs

    def test_trait_completa_ok(self):
        errs = self.an('trait N { fn nada(self) -> int; } '
                       'struct N { x: int } '
                       'impl N { fn nada(self) -> int { return 1; } } '
                       'fn main() -> int { return 1; }')
        self.assertEqual(errs, [])

    def test_trait_metodo_faltando(self):
        errs = self.an('trait N { fn a(self) -> int; fn b(self) -> int; } '
                       'struct N { x: int } '
                       'impl N { fn a(self) -> int { return 1; } } '
                       'fn main() -> int { return 1; }')
        self.assertTrue(any("rapido" in e or "b" in e for e in errs), errs)

    def test_trait_aridade(self):
        errs = self.an('trait N { fn a(self, v: int) -> int; } '
                       'struct N { x: int } '
                       'impl N { fn a(self) -> int { return 1; } } '
                       'fn main() -> int { return 1; }')
        self.assertTrue(any("aridade" in e for e in errs), errs)

    def test_impl_tipo_fantasma(self):
        errs = self.an('impl Fantasma { fn m() -> int { return 1; } } '
                       'fn main() -> int { return 1; }')
        self.assertTrue(any("não declarado" in e for e in errs), errs)

    def test_bound_ok(self):
        errs = self.an('trait N { fn m(self) -> int; } '
                       'fn usa<T: N>(x: T) -> int { return 1; } '
                       'fn main() -> int { return 1; }')
        self.assertEqual(errs, [])

    def test_bound_fantasma(self):
        errs = self.an('fn usa<T: Fantasma>(x: T) -> int { return 1; } '
                       'fn main() -> int { return 1; }')
        self.assertTrue(any("Fantasma" in e for e in errs), errs)

    def test_subtipo_largura_ok(self):
        errs = self.an('struct Ponto { x: float, y: float } '
                       'fn f(p: Ponto) -> int { '
                       'let q: {x: float} = p; return 1; }')
        self.assertEqual(errs, [])

    def test_subtipo_campo_ausente(self):
        errs = self.an('struct Ponto { x: float, y: float } '
                       'fn f(p: Ponto) -> int { '
                       'let q: {x: float, z: int} = p; return 1; }')
        self.assertTrue(any("incompatível" in e for e in errs), errs)

    def test_subtipo_campo_tipo_errado(self):
        errs = self.an('struct Ponto { x: float, y: float } '
                       'fn f(p: Ponto) -> int { '
                       'let q: {x: str} = p; return 1; }')
        self.assertTrue(any("incompatível" in e for e in errs), errs)


class TestMiddleExtra(unittest.TestCase):
    def _mod(self):
        _, prog = parse1(HELLO)
        return Baixador().baixar(prog)

    def test_str_verify(self):
        m = self._mod()
        s = ir_to_str(m)
        self.assertIn("fn main", s)
        self.assertEqual(verificar(m), [])

    def test_passes_all(self):
        m = self._mod()
        self.assertIn("dce", P.otimizar(m))
        self.assertIsInstance(P.inline(m), int)
        self.assertEqual(P.loop_hoist(m), 0)

    def test_constfold_real(self):
        m = ModuloIR("t", [FuncaoIR("f", [], [Bloco("e", [
            Instr("const", "%a", [], None), Instr("add", "%c", ["#2", "#3"])])])])
        m.funcoes[0].blocos[0].instrs[0].args = []
        m.funcoes[0].blocos[0].instrs[0].val = 0
        self.assertGreaterEqual(P.constfold(m), 1)
        self.assertGreaterEqual(P.cse(m), 0)
        self.assertGreaterEqual(P.dce(m), 0)


class TestBackendsExtra(unittest.TestCase):
    def test_bc_verify_fail(self):
        self.assertTrue(ver_bc(ModuloBC("x", [], [("CONST", 0)])))
        self.assertEqual(ver_bc(ModuloBC("x", [], [("HALT", 0)])), [])

    def test_link_multi(self):
        a = ModuloBC("a", [1], [("CONST", 0), ("HALT", 0)])
        b = ModuloBC("b", [1, 2], [("CONST", 1), ("HALT", 0)])
        self.assertEqual(link([a, b]).consts, [1, 2])

    def test_lumenc_targets(self):
        self.assertIn("main", compilar(HELLO, "ir"))
        mod = compilar(HELLO, "vm")
        self.assertIn("main", mod["functions"])
        mod2 = compilar(HELLO, "lbc")
        self.assertEqual(mod2["entry"], "main")
        self.assertIn("module", compilar(HELLO, "wat"))
        _, c = compilar(HELLO, "c")
        self.assertIn("main", c)
        with self.assertRaises(ValueError):
            compilar(HELLO, "java")

    def test_all_examples(self):
        files = sorted(f for f in os.listdir(EXDIR) if f.endswith(".lum"))
        self.assertGreaterEqual(len(files), 16)
        for f in files:
            with open(os.path.join(EXDIR, f), encoding="utf8") as fh:
                src = fh.read()
            for tgt in ("ir", "vm", "wat", "c"):
                try:
                    compilar(src, tgt)
                except Exception as e:
                    self.fail(f"{f}[{tgt}]: {e}")


class TestFrontendV03(unittest.TestCase):
    """v0.3: higiene, keywords, module dotted, attrs com args, literais."""
    def parse1(self, src):
        ps = Parser(tokenize(src))
        prog = ps.parse()
        return ps, prog

    # 1. Higiene fase-1: gensym
    def test_higiene_gensym(self):
        src = 'macro inc_tmp(x) { let tmp = x + 1; tmp }\nfn main() -> int { let tmp: int = 100; let y = inc_tmp!(tmp); return y; }'
        ps, prog = self.parse1(src)
        self.assertEqual(ps.errs, [], ps.errs[:2])
        # verifica que macro foi armazenada
        self.assertIn("inc_tmp!", ps.macros)
        macro_fn = ps.macros["inc_tmp!"]
        # higienizar deve renomear tmp interno
        from compiler.frontend.higiene import higienizar
        arg = A.Lit(A.Span(1,1), "id", "tmp")
        exp = higienizar(macro_fn, [arg])
        self.assertIsNotNone(exp)
        # exp é Block com stmts higienizados
        self.assertEqual(exp.__class__.__name__, "Block")
        # o let interno deve ter nome gensymizado diferente de "tmp"
        let_nodes = [s for s in exp.stmts if type(s).__name__ == "Let"]
        self.assertTrue(let_nodes)
        self.assertNotEqual(let_nodes[0].name, "tmp")
        self.assertTrue(let_nodes[0].name.startswith("tmp__hyg"))
        # uso do tmp no final também gensymizado
        # o último stmt deve referir ao gensym
        last = exp.stmts[-1]
        # pode ser Lit id com nome gensym
        if isinstance(last, A.Lit) and last.kind == "id":
            self.assertEqual(last.val, let_nodes[0].name)

    def test_higiene_nao_captura_caller(self):
        src = 'macro foo(x) { let y = x; y }\nfn f() -> int { let y: int = 5; let z = foo!(y); return z; }'
        ps, prog = self.parse1(src)
        self.assertEqual(ps.errs, [], ps.errs)
        # o y da macro não deve capturar y do caller após higiene (nome diferente)
        from compiler.frontend.higiene import higienizar
        macro_fn = ps.macros["foo!"]
        arg = A.Lit(A.Span(1,1), "id", "y")
        exp = higienizar(macro_fn, [arg])
        let_y = [s for s in exp.stmts if type(s).__name__ == "Let"][0]
        self.assertNotEqual(let_y.name, "y")
        # argumento y do caller deve permanecer "y"
        # o let gensymizado tem expr que é o arg "y" (não gensymizado)
        self.assertEqual(let_y.expr.val, "y")

    def test_vec_map_continuam(self):
        ps, prog = self.parse1('fn f() -> int { let a = vec![1, 2]; let b = map![1, 2]; return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        # verifica que vec! e map! parsearam como Call e não foram higienizados (não estão em macros)
        self.assertNotIn("vec!", ps.macros)
        self.assertNotIn("map!", ps.macros)

    # 2. Keywords reais
    def test_keywords_self_param(self):
        ps, prog = self.parse1('struct P { x: int }\nimpl P { fn m(self) -> int { return 1; } }\nfn f(self: int) -> int { return self; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        # verifica que self como param não virou erro
        errs, _ = analisar(prog)
        # self param não deve ser considerado indefinido
        self.assertNotIn("nome indefinido", ";".join(errs))

    def test_keywords_self_field_access(self):
        ps, prog = self.parse1('fn f() -> int { let s = self.x; let t = super.y; let u = crate::z; return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])

    def test_keywords_use_paths(self):
        ps, prog = self.parse1('use crate::foo\nuse super::bar\nuse self::baz\nfn main() -> int { return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        self.assertEqual(len(prog.imports), 3)
        self.assertTrue(any("crate::foo" in imp.path for imp in prog.imports))
        self.assertTrue(any("super::bar" in imp.path for imp in prog.imports))
        self.assertTrue(any("self::baz" in imp.path for imp in prog.imports))

    def test_old_self_as_ident_comum(self):
        # código antigo que usava `self` como identificador comum deve continuar parseando
        ps, prog = self.parse1('fn f() -> int { let self: int = 5; let Self: int = 6; return self + Self; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        # lexer deve ter promovido para keyword, mas parser aceita como ident em let
        # verifica que let nomes foram parseados
        fn = prog.itens[0]
        self.assertEqual(fn.body[0].name, "self")
        self.assertEqual(fn.body[1].name, "Self")

    def test_raw_identifier(self):
        toks = tokenize('r#type r#self')
        self.assertEqual(toks[0].kind, "IDENT")
        self.assertEqual(toks[0].val, "type")
        self.assertEqual(toks[1].kind, "IDENT")
        self.assertEqual(toks[1].val, "self")
        ps, prog = self.parse1('fn f() -> int { let r#type: int = 1; return r#type; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])

    def test_module_dotted(self):
        ps, prog = self.parse1('module a.b.c\nfn main() -> int { return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        self.assertEqual(prog.mod, "a.b.c")
        ps2, prog2 = self.parse1('module foo\nfn main() -> int { return 1; }')
        self.assertEqual(prog2.mod, "foo")

    # 3. Atributos com args
    def test_attr_com_args(self):
        ps, prog = self.parse1('#[test(foo, bar)]\nfn minha() -> int { return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        fn = prog.itens[0]
        self.assertTrue(hasattr(fn, "attrs"))
        self.assertTrue(any(str(a) == "test" for a in fn.attrs))
        # verifica args retidos
        attr_test = [a for a in fn.attrs if str(a) == "test"][0]
        self.assertEqual(getattr(attr_test, "args", []), ["foo", "bar"])
        self.assertEqual(getattr(fn, "test_args", []), ["foo", "bar"])

    def test_attr_sem_args(self):
        ps, prog = self.parse1('#[test]\nfn outra() -> int { return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        fn = prog.itens[0]
        attr_test = [a for a in fn.attrs if str(a) == "test"][0]
        self.assertEqual(getattr(attr_test, "args", []), [])

    def test_attr_multi(self):
        ps, prog = self.parse1('#[test(should_panic)]\n#[bench]\nfn f() -> int { return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        fn = prog.itens[0]
        self.assertEqual(len(fn.attrs), 2)

    # 4. Literais
    def test_int_suffix(self):
        toks = tokenize('42i32 100u64')
        self.assertEqual(toks[0].kind, "INT")
        self.assertEqual(toks[0].val, "42")
        self.assertEqual(toks[0].suffix, "i32")
        self.assertEqual(toks[1].suffix, "u64")
        ps, prog = self.parse1('fn f() -> int { let x = 42i32; return x; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        lit = prog.itens[0].body[0].expr
        self.assertEqual(lit.kind, "int")
        self.assertEqual(lit.val, 42)
        self.assertEqual(lit.suffix, "i32")

    def test_float_suffix(self):
        toks = tokenize('3.0f64 2.5float')
        self.assertEqual(toks[0].kind, "FLOAT")
        self.assertEqual(toks[0].suffix, "f64")
        ps, prog = self.parse1('fn f() -> float { let x = 3.0f64; return x; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        lit = prog.itens[0].body[0].expr
        self.assertEqual(lit.suffix, "f64")

    def test_raw_string(self):
        toks = tokenize('r#"hello"# r##"a#b"##')
        self.assertEqual(len([t for t in toks if t.kind == "STRING"]), 2)
        self.assertEqual(toks[0].val, "hello")
        self.assertTrue(toks[0].raw)
        self.assertEqual(toks[1].val, "a#b")
        # via parser
        ps, prog = self.parse1('fn f() -> int { let s = r#"raw"#; return 1; }')
        self.assertEqual(ps.errs, [], ps.errs[:2])
        lit = prog.itens[0].body[0].expr
        self.assertEqual(lit.val, "raw")
        self.assertTrue(lit.raw)

    def test_raw_string_hashes_balanceados(self):
        toks = tokenize('r###"x"###')
        self.assertEqual(toks[0].val, "x")
        self.assertTrue(toks[0].raw)
        # não terminado deve erro
        with self.assertRaises(LexError):
            tokenize('r#"abc')

    def test_unicode_escape(self):
        toks = tokenize('"\\u{1F600}"')
        self.assertEqual(toks[0].val, "😀")
        toks2 = tokenize('"\\u0041"')
        self.assertEqual(toks2[0].val, "A")
        ps, prog = self.parse1('fn f() -> str { let s = "\\u{41}"; return s; }')
        lit = prog.itens[0].body[0].expr
        self.assertEqual(lit.val, "A")

    def test_block_comment_nested(self):
        src = '/* outer /* inner */ outer */ fn f() -> int { return 1; }'
        ps, prog = self.parse1(src)
        self.assertEqual(ps.errs, [], ps.errs[:2])
        self.assertEqual(len(prog.itens), 1)
        # profundo
        src2 = '/* a /* b /* c */ b */ a */ fn g() -> int { return 1; }'
        ps2, prog2 = self.parse1(src2)
        self.assertEqual(ps2.errs, [], ps2.errs[:2])

    def test_lex_error_portugues(self):
        try:
            tokenize('/* nao fechado')
            self.fail("deveria levantar LexError")
        except LexError as e:
            self.assertIn("bloco não terminado", str(e))
        try:
            tokenize('"nao fechada')
            self.fail()
        except LexError as e:
            self.assertIn("string não terminada", str(e))


if __name__ == "__main__":
    unittest.main()
