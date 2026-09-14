#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""8 testes do fmt: indent, idempotência, strings, comentários, match, vazio, erro léxico, CLI."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# garante import
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.fmt.lumen_fmt import format_code, main as fmt_main
from compiler.frontend.lexer import LexError


class TestFmt(unittest.TestCase):

    def test_indent(self):
        """indent 4 dentro de chaves."""
        src = "fn f(){\nlet x=1;\n}\n"
        out = format_code(src)
        # deve ter 4 espaços antes de let
        self.assertIn("    let x = 1;", out)
        # fn linha deve terminar com { e próxima linha indentada
        lines = out.splitlines()
        self.assertTrue(lines[0].strip().endswith("{"))
        self.assertTrue(lines[1].startswith("    "))

    def test_idempotencia(self):
        """fmt(fmt(x)) == fmt(x)."""
        samples = [
            'fn f(){let x=1;}\n',
            'fn g(a:i32,b:i32)->i32{return a+b;}\n',
            'let s="a = b; { }";\n',
            '/// doc\nfn h(){}\n',
            'match x{0=>1,1|2=>2,_=>3}\n',
        ]
        for s in samples:
            a = format_code(s)
            b = format_code(a)
            self.assertEqual(a, b, f"não idempotente para {s!r}: {a!r} vs {b!r}")

    def test_strings_preservadas(self):
        """conteúdo de strings não é reformatado."""
        src = 'let s = "a = b; { } ( ) , ; :";\n'
        out = format_code(src)
        # string literal deve permanecer exatamente
        self.assertIn('"a = b; { } ( ) , ; :"', out)
        # parte fora da string deve ter espaços normalizados
        self.assertIn('let s = "', out)

        src2 = 'let r = r#"raw { } = ;"#;\n'
        out2 = format_code(src2)
        self.assertIn('r#"raw { } = ;"#', out2)

        src3 = "let c = 'x';\n"
        out3 = format_code(src3)
        self.assertIn("'x'", out3)

    def test_comentarios(self):
        """preserva //, /// DOC e /* */."""
        src = "/// DOC exemplo\nfn f(){\n// comentario com = {}\nlet x=1;/* bloco { } */\n}\n"
        out = format_code(src)
        self.assertIn("/// DOC exemplo", out)
        self.assertIn("// comentario com = {}", out)
        self.assertIn("/* bloco { } */", out)
        # garante que comentário não foi deletado nem alterado (exceto indent)
        self.assertIn("let x = 1;", out)

        src2 = "/* multi\n   linha */\nfn g(){}\n"
        out2 = format_code(src2)
        self.assertIn("multi", out2)

    def test_match_arms(self):
        """formatação de match com | e => mantém quebras e indent."""
        src = "fn f(x:i32)->str{return match x{0=>\"zero\",1|2=>\"pequeno\",_=>\"outro\"};}\n"
        out = format_code(src)
        self.assertIn("match x {", out)
        self.assertIn("=>", out)
        # deve ter quebra após { e ;
        self.assertIn("    return match x {", out)
        # idempotência específica de match
        self.assertEqual(out, format_code(out))

    def test_arquivo_vazio(self):
        """arquivo vazio permanece vazio e não quebra."""
        self.assertEqual(format_code(""), "")
        self.assertEqual(format_code("   \n  \n"), "")
        self.assertEqual(format_code("\n"), "")
        # só comentário DOC vazio? deve preservar?
        self.assertEqual(format_code("/// doc\n"), "/// doc\n")

    def test_erro_lexico_limpo(self):
        """string não terminada e char inválido geram LexError com linha:col."""
        with self.assertRaises(LexError) as ctx:
            format_code('let x = "abc;\n')
        msg = str(ctx.exception)
        self.assertIn(":", msg)  # linha:col
        self.assertIn("string", msg.lower())

        with self.assertRaises(LexError):
            format_code('let x = `invalido`;\n')

        with self.assertRaises(LexError):
            format_code('let x = "unterminated;\n')

        # bloco não terminado
        with self.assertRaises(LexError):
            format_code('/* bloco sem fim\nfn f(){}\n')

    def test_cli_exit_codes(self):
        """CLI --check e --diff retornam códigos corretos."""
        # arquivo já formatado
        with tempfile.TemporaryDirectory() as td:
            p_ok = Path(td) / "ok.lum"
            src_ok = format_code('fn f(){let x=1;}\n')
            p_ok.write_text(src_ok, encoding="utf-8")
            # --check deve ser 0
            rc = fmt_main([str(p_ok), "--check"])
            self.assertEqual(rc, 0)
            # --diff deve ser 0 e sem saída
            rc = fmt_main([str(p_ok), "--diff"])
            self.assertEqual(rc, 0)

            p_bad = Path(td) / "bad.lum"
            p_bad.write_text('fn f(){let x=1;}\n', encoding="utf-8")
            # se o formatado é diferente do original, --check deve ser 1 (já que fn f(){...} vai mudar)
            # mas nosso exemplo acima já mostra que format_code muda; então bad deve ser 1
            # Para garantir diferença, usa conteúdo não formatado
            bad_src = 'fn f(){let x=1;}\n'
            # se bad_src já é diferente de format_code(bad_src), então --check deve ser 1
            if bad_src != format_code(bad_src):
                rc = fmt_main([str(p_bad), "--check"])
                self.assertEqual(rc, 1)
                rc = fmt_main([str(p_bad), "--diff"])
                self.assertEqual(rc, 1)
            else:
                # se por acaso for igual, checa inverso com arquivo ok mas conteúdo bad proposital
                p_bad.write_text('fn  f  (  )  {  let  x  =  1  ;  }\n', encoding="utf-8")
                rc = fmt_main([str(p_bad), "--check"])
                self.assertEqual(rc, 1)

        # arquivo inexistente
        rc = fmt_main(["/tmp/nao_existe_xyz.lum"])
        self.assertEqual(rc, 2)
        # erro léxico via CLI deve ser 1
        with tempfile.TemporaryDirectory() as td:
            p_err = Path(td) / "err.lum"
            p_err.write_text('let x = "abc;\n', encoding="utf-8")
            rc = fmt_main([str(p_err)])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
