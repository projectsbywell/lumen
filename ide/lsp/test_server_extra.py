"""Cobertura extra do servidor LSP via Session.handle. Rode: python3 -m unittest ide.lsp.test_server_extra"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import Session

DOC = 'module demo\nfn soma(a: int, b: int) -> int {\n  return a + b;\n}\nfn main() -> int {\n  let r = soma(1, 2);\n  return r;\n}\n'
URI = "file:///demo.lum"


def req(mid, method, params):
    return {"jsonrpc": "2.0", "id": mid, "method": method, "params": params}


class TestSessionExtra(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.s.handle(req(1, "initialize", {"capabilities": {}}))
        self.s.handle({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        self.s.handle(req(2, "textDocument/didOpen",
                          {"textDocument": {"uri": URI, "text": DOC}}))

    def test_completion(self):
        r = self.s.handle(req(3, "textDocument/completion", {
            "textDocument": {"uri": URI},
            "position": {"line": 4, "character": 11}}))
        items = r["result"]
        self.assertTrue(items)
        snips = [i for i in items if "( $0)" in i.get("insertText", "") or "($0)" in i.get("insertText", "")]
        for i in snips:
            self.assertEqual(i.get("insertTextFormat"), 2)

    def test_hover(self):
        r = self.s.handle(req(3, "textDocument/hover", {
            "textDocument": {"uri": URI},
            "position": {"line": 1, "character": 4}}))
        self.assertIsNotNone(r)

    def test_definition_references(self):
        d = self.s.handle(req(3, "textDocument/definition", {
            "textDocument": {"uri": URI},
            "position": {"line": 5, "character": 11}}))
        self.assertIsNotNone(d)
        r = self.s.handle(req(4, "textDocument/references", {
            "textDocument": {"uri": URI},
            "position": {"line": 1, "character": 4},
            "context": {"includeDeclaration": True}}))
        self.assertIsNotNone(r)

    def test_diagnostics(self):
        bad = 'fn f() -> int {\n "aberta;\n}'
        self.s.handle({"jsonrpc": "2.0", "method": "textDocument/didChange",
                       "params": {"textDocument": {"uri": URI},
                                  "contentChanges": [{"text": bad}]}})
        r = self.s.handle(req(5, "textDocument/hover", {
            "textDocument": {"uri": URI},
            "position": {"line": 0, "character": 1}}))
        self.assertIsNotNone(r)
        self.s.handle({"jsonrpc": "2.0", "method": "textDocument/didClose",
                       "params": {"textDocument": {"uri": URI}}})

    def test_formatting(self):
        r = self.s.handle(req(6, "textDocument/formatting", {
            "textDocument": {"uri": URI}, "options": {}}))
        self.assertIsNotNone(r)
        if r["result"]:
            rng = r["result"][0]["range"]
            self.assertGreaterEqual(rng["end"]["line"], 0)

    def test_rename(self):
        r = self.s.handle(req(7, "textDocument/rename", {
            "textDocument": {"uri": URI},
            "position": {"line": 1, "character": 4},
            "newName": "soma2"}))
        self.assertIsNotNone(r)
        bad = self.s.handle(req(8, "textDocument/rename", {
            "textDocument": {"uri": URI},
            "position": {"line": 1, "character": 4},
            "newName": "2bad"}))
        self.assertIn("error", bad)

    def test_codeaction(self):
        r = self.s.handle(req(9, "textDocument/codeAction", {
            "textDocument": {"uri": URI},
            "range": {"start": {"line": 0, "character": 0},
                      "end": {"line": 0, "character": 1}},
            "context": {"diagnostics": []}}))
        self.assertIsNotNone(r)

    def test_unknown_shutdown(self):
        r = self.s.handle(req(10, "nada/metodo", {}))
        self.assertIn("error", r)
        self.s.handle(req(11, "shutdown", {}))
        with self.assertRaises(SystemExit):
            self.s.handle({"jsonrpc": "2.0", "method": "exit", "params": {}})


if __name__ == "__main__":
    unittest.main()
