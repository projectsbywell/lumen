#!/usr/bin/env python3
"""Tests for the Lumen LSP server (protocol + features).

Run:  python3 test_lsp.py   /   pytest test_lsp.py
"""

import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import (Session, analyze_diagnostics, format_document,
                    find_definitions, find_references, get_completions,
                    get_hover, read_message, send_message, word_at_position)

URI = "file:///tmp/exemplo.lumen"


def protocol_roundtrip(messages):
    """Feed raw LSP messages through Session.handle with real framing."""
    sess = Session()
    raw_in = b""
    for m in messages:
        body = json.dumps(m).encode()
        raw_in += f"Content-Length: {len(body)}\r\n\r\n".encode() + body
    stdin = io.BytesIO(raw_in)
    responses = []

    class BufReader(io.BufferedReader):
        pass

    # read_message expects .readline/.read — BytesIO qualifies; wrap calls directly
    reader = io.BufferedReader(stdin)  # type: ignore
    out_buf = io.BytesIO()
    writer = io.BufferedWriter(out_buf)  # type: ignore
    while True:
        msg = read_message(reader)  # type: ignore
        if msg is None:
            break
        resp = sess.handle(msg)
        if resp is not None:
            if resp.get("id") is not None or "method" not in resp:
                responses.append(resp)
            else:
                responses.append(resp)  # server->client notification
    return sess, responses


class TestCompletion(unittest.TestCase):
    def test_completion_contem_fn(self):
        items = get_completions("")
        labels = [i["label"] for i in items]
        self.assertIn("fn", labels)
        self.assertIn("match", labels)
        self.assertIn("struct", labels)

    def test_completion_prefix(self):
        labels = [i["label"] for i in get_completions("f")]
        self.assertIn("fn", labels)
        self.assertIn("false", labels)
        self.assertNotIn("let", labels)

    def test_completion_via_protocolo(self):
        sess = Session()
        sess.did_open(URI, "fn soma() {}\n")
        resp = sess.handle({
            "jsonrpc": "2.0", "id": 1, "method": "textDocument/completion",
            "params": {"textDocument": {"uri": URI},
                       "position": {"line": 1, "character": 0}}})
        labels = [i["label"] for i in resp["result"]]
        self.assertIn("fn", labels)


class TestHover(unittest.TestCase):
    def test_hover_keyword(self):
        h = get_hover("fn")
        self.assertIsNotNone(h)
        self.assertIn("fn", h["contents"]["value"])

    def test_hover_match(self):
        h = get_hover("match")
        self.assertIsNotNone(h)

    def test_hover_unknown_none(self):
        self.assertIsNone(get_hover("minhaVariavel"))

    def test_hover_via_protocolo(self):
        sess = Session()
        sess.did_open(URI, "fn main() {}\n")
        resp = sess.handle({
            "jsonrpc": "2.0", "id": 2, "method": "textDocument/hover",
            "params": {"textDocument": {"uri": URI},
                       "position": {"line": 0, "character": 1}}})
        self.assertIsNotNone(resp["result"])
        self.assertIn("fn", resp["result"]["contents"]["value"])


class TestDiagnostics(unittest.TestCase):
    def test_detecta_string_nao_terminada(self):
        diags = analyze_diagnostics('let x = "abc;\n')
        codes = [d["code"] for d in diags]
        self.assertIn("unterminated-string", codes)

    def test_detecta_caractere_lexico_invalido(self):
        diags = analyze_diagnostics("let preço$ = 1;\n")
        self.assertTrue(any(d["code"] == "invalid-char" for d in diags),
                        f"esperava invalid-char, obteve: {diags}")

    def test_detecta_delimitador_desbalanceado(self):
        diags = analyze_diagnostics("fn f() {\n  let x = (1 + 2;\n")
        self.assertTrue(any(d["code"] == "unbalanced-delimiter" for d in diags))

    def test_codigo_limpo_sem_diagnosticos(self):
        diags = analyze_diagnostics('fn main() {\n  let x = 1;\n  print(x);\n}\n')
        self.assertEqual(diags, [])

    def test_did_open_publica_diagnostics(self):
        sess = Session()
        resp = sess.handle({
            "jsonrpc": "2.0", "method": "textDocument/didOpen",
            "params": {"textDocument": {
                "uri": URI, "languageId": "lumen", "version": 1,
                "text": 'let x = "ab;\n'}}})
        self.assertEqual(resp["method"], "textDocument/publishDiagnostics")
        self.assertTrue(len(resp["params"]["diagnostics"]) >= 1)


class TestNavegacao(unittest.TestCase):
    TEXT = "fn soma(a: int) {\n  let total = a;\n  return total;\n}\n"

    def test_definition(self):
        locs = find_definitions(self.TEXT, "soma")
        self.assertEqual(len(locs), 1)
        self.assertEqual(locs[0]["range"]["start"]["line"], 0)

    def test_references(self):
        locs = find_references(self.TEXT, "total")
        self.assertEqual(len(locs), 2)

    def test_rename(self):
        sess = Session()
        sess.did_open(URI, self.TEXT)
        resp = sess.handle({
            "jsonrpc": "2.0", "id": 5, "method": "textDocument/rename",
            "params": {"textDocument": {"uri": URI},
                       "position": {"line": 1, "character": 8},
                       "newName": "soma_total"}})
        edits = resp["result"]["changes"][URI]
        self.assertEqual(len(edits), 2)
        self.assertTrue(all(e["newText"] == "soma_total" for e in edits))


class TestFormatCodeAction(unittest.TestCase):
    def test_formatting(self):
        out = format_document("fn f() {\nlet x=1;   \n}\n")
        self.assertTrue(out.endswith("\n"))
        self.assertNotIn("   \n", out)
        self.assertIn("    let x=1;", out)

    def test_code_action_quickfix_string(self):
        sess = Session()
        sess.did_open(URI, 'let x = "abc;\n')
        resp = sess.handle({
            "jsonrpc": "2.0", "id": 7, "method": "textDocument/codeAction",
            "params": {"textDocument": {"uri": URI},
                       "range": {"start": {"line": 0, "character": 0},
                                 "end": {"line": 0, "character": 5}},
                       "context": {"diagnostics":
                                   analyze_diagnostics('let x = "abc;\n')}}})
        titles = [a["title"] for a in resp["result"]]
        self.assertIn("Fechar string com aspas", titles)

    def test_framing_roundtrip(self):
        body = {"jsonrpc": "2.0", "id": 9, "method": "initialize", "params": {}}
        raw = json.dumps(body).encode()
        stream = io.BytesIO(f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw)
        msg = read_message(io.BufferedReader(stream))  # type: ignore
        self.assertEqual(msg["method"], "initialize")
        out = io.BytesIO()
        w = io.BufferedWriter(out)  # type: ignore
        send_message(w, {"jsonrpc": "2.0", "id": 9, "result": None})  # type: ignore
        w.flush()
        self.assertIn(b"Content-Length:", out.getvalue())


class TestWordAtPosition(unittest.TestCase):
    def test_bordas(self):
        self.assertEqual(word_at_position(["fn soma"], 0, 1), "fn")
        self.assertEqual(word_at_position(["fn soma"], 0, 99), "soma")
        self.assertEqual(word_at_position([], 0, 0), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
