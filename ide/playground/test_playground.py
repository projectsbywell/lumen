"""Testes do playground web (v0.4): marcadores do index.html + sintaxe JS.

Valida share via #c=, WASM opt-in com fallback JS e sintaxe dos
arquivos JS (node --check quando disponível). Sem dependências.
Rode: python3 -m unittest ide.playground.test_playground
"""
import base64
import os
import re
import shutil
import subprocess
import sys
import unittest

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(BASE, "..", "..")
INDEX = os.path.join(BASE, "index.html")
WASM_RT = os.path.join(REPO, "compiler", "backend", "wasm", "runtime.js")


def read_index():
    with open(INDEX, encoding="utf-8") as fh:
        return fh.read()


class TestPlaygroundHTML(unittest.TestCase):
    def test_share_hash(self):
        html = read_index()
        self.assertIn("getElementById('share')", html)
        self.assertIn("location.hash='c='+b64e(editor.value)", html)
        self.assertIn("function b64e(s)", html)
        self.assertIn("function b64d(s)", html)
        # carrega de volta do hash ao abrir
        self.assertIn("location.hash.startsWith('#c=')", html)

    def test_wasm_optin_com_fallback(self):
        html = read_index()
        self.assertIn("lumen.wasm", html)
        self.assertIn("fallback", html)
        # tenta WASM, cai para o interpretador JS em erro
        self.assertRegex(html, r"wasmRun.*fallback|fallback.*wasmRun|"
                               r"catch\(e\)\{\s*/\* fallback")

    def test_interpretador_js_minimo(self):
        html = read_index()
        self.assertIn("interpretador", html.lower())
        for kw in ("let", "print", "match"):
            self.assertIn(kw, html)

    def test_html_bem_formado(self):
        html = read_index()
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("</html>", html.lower())
        for tag in ("<script>", "</script>", "<textarea", "<button"):
            self.assertIn(tag, html)


class TestPlaygroundShareFallback(unittest.TestCase):
    def test_share_roundtrip_b64(self):
        html = read_index()
        # b64 unicode-safe nos dois sentidos (encodeURIComponent/escape)
        self.assertIn("encodeURIComponent", html)
        self.assertIn("decodeURIComponent", html)
        # share escreve #c= com b64e, init lê com b64d
        self.assertIn("b64e(editor.value)", html)
        self.assertIn("b64d(location.hash.slice(3))", html)
        # roundtrip em Python com a mesma semântica (utf-8 -> b64)
        amostras = ["let x = 2 + 3;", "olá, mundo 🌍 — match ✓",
                    "fib(10) // 55\nprintln(\"ação\")"]
        for s in amostras:
            b64 = base64.b64encode(s.encode("utf-8")).decode("ascii")
            volta = base64.b64decode(b64).decode("utf-8")
            self.assertEqual(volta, s)
        # hash inicial do init usa prefixo #c=
        self.assertIn("startsWith('#c=')", html)

    def test_fallback_sem_wasm(self):
        html = read_index()
        # badge padrão é JS (sem lumen.wasm carregado)
        self.assertIn("motor: JS", html)
        # tryLoadWasm nunca propaga: fetch/compile/instantiate em try + fallback
        self.assertIn("tryLoadWasm", html)
        self.assertIn("/* fallback", html)
        # runCurrent tenta WASM e cai para o interpretador JS em erro
        m = re.search(r"function runCurrent\(src\)\{(.*?)\n\}", html, re.S)
        self.assertIsNotNone(m, "runCurrent ausente")
        corpo = m.group(1)
        self.assertIn("wasmRun", corpo)
        self.assertIn("runLumen(src)", corpo)
        self.assertIn("try", corpo)
        self.assertIn("catch", corpo)


class TestPlaygroundJS(unittest.TestCase):
    def _check(self, path):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node indisponível")
        r = subprocess.run([node, "--check", path], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_runtime_js_sintaxe(self):
        self._check(WASM_RT)

    def test_index_inline_js_sintaxe(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node indisponível")
        html = read_index()
        blocos = re.findall(r"<script>(.*?)</script>", html, re.S)
        self.assertTrue(blocos, "sem <script> inline")
        import tempfile
        for i, js in enumerate(blocos):
            with tempfile.NamedTemporaryFile("w", suffix=".js",
                                             delete=False) as tf:
                tf.write(js)
                tmp = tf.name
            try:
                r = subprocess.run([node, "--check", tmp],
                                   capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0,
                                 f"bloco {i}: {r.stderr[:500]}")
            finally:
                os.unlink(tmp)


if __name__ == "__main__":
    unittest.main()
