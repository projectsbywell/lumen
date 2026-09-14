"""Teste do servidor DAP em processo. Rode: python3 -m unittest ide.vscode.test_dap"""
import io
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dap import Session

PROG = ("fn fib(n: int) -> int { if n < 2 { return n; } "
        "return fib(n - 1) + fib(n - 2); }\n"
        "pub fn main() -> int { return fib(5); }\n")

PROG_LINES = """fn add(a: int, b: int) -> int {
    let s = a + b;
    return s;
}
pub fn main() -> int {
    let x = add(2, 3);
    return x;
}
"""

PROG_DIVZERO = """pub fn main() -> int {
    let z = 0;
    let q = 1 / z;
    return q;
}
"""

PROG_WATCH = """pub fn main() -> int {
    let mut x = 1;
    x = 2;
    x = 3;
    return x;
}
"""

PROG_LOOP = """pub fn main() -> int {
    while true {
    }
    return 0;
}
"""


def _finish(s, buf, mid=200):
    """Drena pauses com continue até terminated (timeout)."""
    t0 = time.time()
    term = None
    while time.time() - t0 < 15.0:
        term = wait_for(buf, "terminated", timeout=0.3)
        if term is not None:
            break
        if s._paused:
            mid += 1
            s.handle(req(mid, "continue", {"threadId": 1}))
    return term


def req(mid, cmd, args=None):
    return {"seq": mid, "type": "request", "command": cmd,
            "arguments": args or {}}


def events_of(buf):
    # NUNCA seek aqui: o worker escreve no mesmo BytesIO e seek(0)
    # moveria o cursor de escrita, corrompendo eventos futuros.
    out = []
    data = buf.getvalue().decode("utf8")
    for chunk in data.split("Content-Length:")[1:]:
        try:
            body = chunk.split("\r\n\r\n", 1)[1]
            out.append(json.loads(body))
        except (IndexError, ValueError):
            pass
    return out


def wait_for(buf, event, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for m in events_of(buf):
            if m.get("event") == event:
                return m
        time.sleep(0.05)
    return None


def wait_for_n(buf, event, n=1, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        c = sum(1 for m in events_of(buf) if m.get("event") == event)
        if c >= n:
            return True
        time.sleep(0.05)
    return False


class TestDAP(unittest.TestCase):
    def test_debug_fib(self):
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "fib.lum")
            open(p, "w", encoding="utf8").write(PROG)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"breakpoints": [{"name": "fib"}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped")
            self.assertIsNotNone(stopped, "breakpoint em fib não parou")
            st = s.handle(req(5, "stackTrace", {"threadId": 1}))
            names = [f["name"] for f in st["body"]["stackFrames"]]
            self.assertIn("fib", names)
            sc = s.handle(req(6, "scopes", {"frameId": 0}))
            self.assertTrue(sc["body"]["scopes"])
            ref = sc["body"]["scopes"][0]["variablesReference"]
            vs = s.handle(req(7, "variables", {"variablesReference": ref}))
            got = {v["name"]: v["value"] for v in vs["body"]["variables"]}
            self.assertIn("n", got)
            ev = s.handle(req(8, "evaluate", {"expression": "n",
                                              "context": "hover"}))
            self.assertIn("result", ev["body"])
            s.handle(req(9, "continue", {"threadId": 1}))
            t0 = time.time()
            term = None
            mid = 100
            while time.time() - t0 < 20.0:
                term = wait_for(buf, "terminated", timeout=0.2)
                if term is not None:
                    break
                evs = events_of(buf)
                nstop = sum(1 for m in evs if m.get("event") == "stopped")
                if nstop > 0 and s._paused:
                    mid += 1
                    s.handle(req(mid, "continue", {"threadId": 1}))
            self.assertIsNotNone(term, "programa não terminou")
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_breakpoint_by_line(self):
        """Breakpoint por linha: source+line mapeado via spans."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            # linha 6 = let x = add(2,3); em main
            r = s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 6}]}))
            self.assertTrue(r["body"]["breakpoints"][0]["verified"])
            self.assertEqual(r["body"]["breakpoints"][0]["line"], 6)
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped, "breakpoint por linha não parou")
            # verifica que parou por breakpoint
            self.assertEqual(stopped["body"]["reason"], "breakpoint")
            s.handle(req(9, "continue", {"threadId": 1}))
            term = wait_for(buf, "terminated", timeout=8)
            # pode ter múltiplos stops se add também tem linha 2, mas deve terminar
            if term is None:
                # força continue se ficou pausado
                if s._paused:
                    s.handle(req(100, "continue", {"threadId": 1}))
                    term = wait_for(buf, "terminated", timeout=8)
            self.assertIsNotNone(term, "não terminou após breakpoint linha")
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_frames_have_real_location(self):
        """Frames devem trazer line/column reais e source.path."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped, "não parou na linha 2")
            st = s.handle(req(5, "stackTrace", {"threadId": 1}))
            frames = st["body"]["stackFrames"]
            self.assertTrue(len(frames) > 0)
            for fr in frames:
                self.assertGreater(fr["line"], 0, f"frame {fr['name']} com line 0")
                self.assertGreater(fr["column"], 0, f"frame {fr['name']} com column 0")
                self.assertIn("source", fr)
                self.assertIn("path", fr["source"])
            # topo deve ser add, linha 2
            top = frames[0]
            self.assertEqual(top["name"], "add")
            self.assertEqual(top["line"], 2)
            s.handle(req(9, "continue", {"threadId": 1}))
            # limpa possíveis outros stops (linha 2 será hit novamente em recursão? não, só uma vez)
            t0 = time.time()
            while time.time() - t0 < 5 and s._paused:
                s.handle(req(101, "continue", {"threadId": 1}))
                time.sleep(0.1)
            term = wait_for(buf, "terminated", timeout=8)
            self.assertIsNotNone(term)
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_evaluate_no_eval(self):
        """evaluate sem eval Python: só inspeção, senão 'não suportado'."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped)
            # dentro de add, 'a' deve estar visível
            ev = s.handle(req(5, "evaluate", {"expression": "a", "context": "hover"}))
            self.assertIn("2", ev["body"]["result"])
            # expressão aritmética simples agora é suportada (P5.3, AST restrita)
            ev2 = s.handle(req(6, "evaluate", {"expression": "a + 1", "context": "hover"}))
            self.assertIn("3", ev2["body"]["result"])
            # tentativa de eval malicioso deve ser bloqueada
            ev3 = s.handle(req(7, "evaluate", {"expression": "__import__('os').system('echo pwned')", "context": "hover"}))
            self.assertIn("não suportado", ev3["body"]["result"])
            # variável inexistente também
            ev4 = s.handle(req(8, "evaluate", {"expression": "inexistente_xyz", "context": "hover"}))
            self.assertIn("não suportado", ev4["body"]["result"])
            s.handle(req(9, "continue", {"threadId": 1}))
            t0 = time.time()
            while time.time() - t0 < 5 and s._paused:
                s.handle(req(102, "continue", {"threadId": 1}))
                time.sleep(0.05)
            term = wait_for(buf, "terminated", timeout=8)
            self.assertIsNotNone(term)
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_step_next(self):
        """next/step deve pausar com reason step e avançar."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped)
            # pede next
            s.handle(req(5, "next", {"threadId": 1}))
            stopped2 = None
            t0 = time.time()
            while time.time() - t0 < 8:
                evs = events_of(buf)
                # pega o último stopped após o primeiro
                stops = [m for m in evs if m.get("event") == "stopped"]
                if len(stops) >= 2:
                    stopped2 = stops[-1]
                    break
                time.sleep(0.05)
            self.assertIsNotNone(stopped2, "next não gerou segundo stopped")
            self.assertEqual(stopped2["body"]["reason"], "step")
            s.handle(req(6, "continue", {"threadId": 1}))
            t0 = time.time()
            while time.time() - t0 < 5 and s._paused:
                s.handle(req(103, "continue", {"threadId": 1}))
                time.sleep(0.05)
            term = wait_for(buf, "terminated", timeout=8)
            self.assertIsNotNone(term)
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_setbreakpoints_clear_and_verified(self):
        """Verifica verified false para linha fora do arquivo e clear."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            # linha inválida
            r = s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 999}]}))
            self.assertFalse(r["body"]["breakpoints"][0]["verified"])
            # linha válida
            r2 = s.handle(req(3, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 6}]}))
            self.assertTrue(r2["body"]["breakpoints"][0]["verified"])
            # clear (lista vazia)
            r3 = s.handle(req(4, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": []}))
            self.assertEqual(r3["body"]["breakpoints"], [])
            # launch sem breakpoint deve terminar sem parar
            s.handle(req(5, "launch", {"program": p}))
            s.handle(req(6, "configurationDone", {}))
            term = wait_for(buf, "terminated", timeout=8)
            self.assertIsNotNone(term, "deveria terminar sem breakpoint após clear")
            # não deve ter stopped
            evs = events_of(buf)
            stops = [m for m in evs if m.get("event") == "stopped"]
            self.assertEqual(len(stops), 0, "não deveria parar após clear")
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)


    def test_restart_relaunches(self):
        """restart reinicia a sessão: segundo run para no breakpoint de novo."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 6}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            self.assertIsNotNone(wait_for(buf, "stopped", timeout=8),
                                 "primeiro run não parou")
            r = s.handle(req(5, "restart", {}))
            self.assertTrue(r["success"], "restart deve responder ok")
            self.assertTrue(wait_for_n(buf, "stopped", 2, timeout=10),
                            "segundo run não parou após restart")
            term = _finish(s, buf)
            self.assertIsNotNone(term, "não terminou após restart")
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_stop_on_entry(self):
        """launch com stopOnEntry:true pausa no entry antes de rodar."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(3, "launch", {"program": p, "stopOnEntry": True}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped, "stopOnEntry não pausou")
            self.assertEqual(stopped["body"]["reason"], "entry")
            term = _finish(s, buf)
            self.assertIsNotNone(term, "não terminou após entry")
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_conditional_hit_log_breakpoints(self):
        """condition falsa pula; verdadeira para; hit conta; log emite sem parar."""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            # A: condition verdadeira para
            buf = io.BytesIO()
            s = Session(buf)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2, "condition": "a == 2"}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped, "condition verdadeira não parou")
            self.assertEqual(stopped["body"]["reason"], "breakpoint")
            self.assertIsNotNone(_finish(s, buf))
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)
            # B: condition falsa não para
            buf = io.BytesIO()
            s = Session(buf)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2, "condition": "a == 999"}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            self.assertIsNotNone(wait_for(buf, "terminated", timeout=8),
                                 "condition falsa deveria terminar sem parar")
            stops = [m for m in events_of(buf) if m.get("event") == "stopped"]
            self.assertEqual(len(stops), 0, "condition falsa não deve parar")
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)
            # C: hitCondition 1 para no 1º hit
            buf = io.BytesIO()
            s = Session(buf)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2, "hitCondition": "1"}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped, "hitCondition 1 não parou")
            self.assertIsNotNone(_finish(s, buf))
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)
            # D: logMessage emite output e não para
            buf = io.BytesIO()
            s = Session(buf)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2, "logMessage": "a={a}"}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            self.assertIsNotNone(wait_for(buf, "terminated", timeout=8),
                                 "logpoint deveria terminar sem parar")
            stops = [m for m in events_of(buf) if m.get("event") == "stopped"]
            self.assertEqual(len(stops), 0, "logpoint não deve parar")
            outs = [m.get("body", {}).get("output", "")
                    for m in events_of(buf) if m.get("event") == "output"]
            self.assertTrue(any("a=2" in o for o in outs),
                            f"logpoint não emitiu interpolação: {outs}")
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_set_variable(self):
        """setVariable altera local do frame pausado; ref inválida falha."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            self.assertIsNotNone(wait_for(buf, "stopped", timeout=8))
            r = s.handle(req(5, "setVariable",
                             {"variablesReference": 1000, "name": "a",
                              "value": "99"}))
            self.assertTrue(r["success"])
            self.assertIn("99", r["body"]["value"])
            ev = s.handle(req(6, "evaluate", {"expression": "a",
                                              "context": "hover"}))
            self.assertIn("99", ev["body"]["result"])
            bad = s.handle(req(7, "setVariable",
                               {"variablesReference": 9999, "name": "a",
                                "value": "1"}))
            self.assertFalse(bad["success"])
            self.assertIsNotNone(_finish(s, buf))
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_exception_breakpoints(self):
        """setExceptionBreakpoints registra filtro; LumenError pausa com stack."""
        buf = io.BytesIO()
        s = Session(buf)
        # sem exceção registrada, exceptionInfo falha
        s.handle(req(1, "initialize", {}))
        noexc = s.handle(req(2, "exceptionInfo", {"threadId": 1}))
        self.assertFalse(noexc["success"])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "div.lum")
            open(p, "w", encoding="utf8").write(PROG_DIVZERO)
            r = s.handle(req(3, "setExceptionBreakpoints",
                             {"filters": ["lumenError"]}))
            self.assertTrue(r["success"])
            self.assertTrue(r["body"]["breakpoints"][0]["verified"])
            s.handle(req(4, "launch", {"program": p}))
            s.handle(req(5, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped, "exceção não pausou")
            self.assertEqual(stopped["body"]["reason"], "exception")
            info = s.handle(req(6, "exceptionInfo", {"threadId": 1}))
            self.assertTrue(info["success"])
            self.assertEqual(info["body"]["exceptionId"], "LumenError")
            self.assertIn("Divisão", info["body"]["description"])
            self.assertTrue(info["body"]["details"]["stackTrace"],
                            "exceptionInfo deve trazer stack")
            self.assertIsNotNone(wait_for(buf, "terminated", timeout=8))
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_capabilities_honest(self):
        """initialize anuncia só o que existe, sem mentir o que não há."""
        buf = io.BytesIO()
        s = Session(buf)
        r = s.handle(req(1, "initialize", {}))
        body = r["body"]
        for cap in ("supportsConfigurationDoneRequest",
                    "supportsEvaluateForHovers",
                    "supportsConditionalBreakpoints",
                    "supportsHitConditionalBreakpoints",
                    "supportsLogPoints",
                    "supportsSetVariable",
                    "supportsRestartRequest",
                    "supportsTerminateRequest",
                    "supportsDataBreakpoints"):
            self.assertTrue(body.get(cap), f"capability ausente: {cap}")
        self.assertTrue(body.get("exceptionBreakpointFilters"),
                        "exceptionBreakpointFilters ausente")
        for lie in ("supportsStepBack",
                    "supportsCompletionsRequest", "supportsFunctionBreakpoints",
                    "supportsStepInTargetsRequest", "supportsGotoTargetsRequest",
                    "supportsDisassembleRequest", "supportsReadMemoryRequest",
                    "supportsDelayedStackTraceLoading"):
            self.assertFalse(body.get(lie, False),
                             f"capability mentida: {lie}")

    def test_step_by_line(self):
        """P5.3: next avança por LINHA via debug_map (2->3 em add)."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            self.assertIsNotNone(wait_for(buf, "stopped", timeout=8))
            st = s.handle(req(5, "stackTrace", {"threadId": 1}))
            self.assertEqual(st["body"]["stackFrames"][0]["line"], 2)
            s.handle(req(6, "next", {"threadId": 1}))
            stopped2 = None
            t0 = time.time()
            while time.time() - t0 < 8:
                stops = [m for m in events_of(buf)
                         if m.get("event") == "stopped"]
                if len(stops) >= 2:
                    stopped2 = stops[-1]
                    break
                time.sleep(0.05)
            self.assertIsNotNone(stopped2, "next por linha não gerou stop")
            self.assertEqual(stopped2["body"]["reason"], "step")
            st2 = s.handle(req(7, "stackTrace", {"threadId": 1}))
            top2 = st2["body"]["stackFrames"][0]
            self.assertEqual(top2["name"], "add")
            self.assertEqual(top2["line"], 3,
                             f"step por linha deveria ir 2->3, foi {top2}")
            self.assertIsNotNone(_finish(s, buf))
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_evaluate_expr_safe(self):
        """P5.3: evaluate aceita aritmética/comparação via AST; bloqueia eval."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            self.assertIsNotNone(wait_for(buf, "stopped", timeout=8))
            ev = s.handle(req(5, "evaluate",
                              {"expression": "a + b", "context": "hover"}))
            self.assertIn("5", ev["body"]["result"])
            ev = s.handle(req(6, "evaluate",
                              {"expression": "(a + b) * 2", "context": "hover"}))
            self.assertIn("10", ev["body"]["result"])
            ev = s.handle(req(7, "evaluate",
                              {"expression": "a > 1", "context": "hover"}))
            self.assertIn("True", ev["body"]["result"])
            bad1 = s.handle(req(8, "evaluate", {"expression":
                "__import__('os').system('echo pwned')", "context": "hover"}))
            self.assertIn("não suportado", bad1["body"]["result"])
            bad2 = s.handle(req(9, "evaluate",
                                {"expression": "open('x')", "context": "hover"}))
            self.assertIn("não suportado", bad2["body"]["result"])
            bad3 = s.handle(req(10, "evaluate",
                                {"expression": "a.__class__", "context": "hover"}))
            self.assertIn("não suportado", bad3["body"]["result"])
            self.assertIsNotNone(_finish(s, buf))
            s.handle(req(11, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_attach(self):
        """P5.3: attach inicia programa em thread (sem PID real), como launch."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 6}]}))
            r = s.handle(req(3, "attach", {"program": p}))
            self.assertTrue(r["success"], "attach deve responder ok")
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped, "attach não parou no breakpoint")
            self.assertEqual(stopped["body"]["reason"], "breakpoint")
            self.assertIsNotNone(_finish(s, buf))
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_data_breakpoint(self):
        """P5.3: setDataBreakpoints pausa quando x muda (reason dataBreakpoint)."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "watch.lum")
            open(p, "w", encoding="utf8").write(PROG_WATCH)
            s.handle(req(1, "initialize", {}))
            r = s.handle(req(2, "setDataBreakpoints",
                             {"breakpoints": [{"dataId": "x"}]}))
            self.assertTrue(r["success"])
            self.assertTrue(r["body"]["breakpoints"][0]["verified"])
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            stopped = wait_for(buf, "stopped", timeout=8)
            self.assertIsNotNone(stopped, "watchpoint não pausou")
            self.assertEqual(stopped["body"]["reason"], "dataBreakpoint")
            term = _finish(s, buf)
            self.assertIsNotNone(term, "não terminou após watchpoint")
            stops = [m for m in events_of(buf)
                     if m.get("event") == "stopped"]
            self.assertGreaterEqual(len(stops), 1)
            self.assertTrue(all(m["body"]["reason"] == "dataBreakpoint"
                                for m in stops),
                            f"stops inesperados: {stops}")
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_terminate_kills_loop(self):
        """P5.3: terminate mata loop infinito via flag+exceção no hook."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "loop.lum")
            open(p, "w", encoding="utf8").write(PROG_LOOP)
            s.handle(req(1, "initialize", {}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            time.sleep(0.5)
            # ainda rodando: sem stopped nem terminated
            evs = events_of(buf)
            self.assertEqual(sum(1 for m in evs
                                 if m.get("event") == "terminated"), 0)
            r = s.handle(req(5, "terminate", {}))
            self.assertTrue(r["success"])
            term = wait_for(buf, "terminated", timeout=8)
            self.assertIsNotNone(term, "terminate não emitiu terminated")
            s._thread.join(timeout=10)
            self.assertFalse(s._thread.is_alive(),
                             "thread do loop infinito não morreu")
            s.handle(req(10, "disconnect", {}))


    def test_pause_then_continue(self):
        """pause arma flag sem bloquear dispatch: stopped(pause) -> continue."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "loop.lum")
            open(p, "w", encoding="utf8").write(PROG_LOOP)
            s.handle(req(1, "initialize", {}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            time.sleep(0.5)
            t0 = time.time()
            r = s.handle(req(5, "pause", {"threadId": 1}))
            elapsed = time.time() - t0
            self.assertTrue(r["success"])
            self.assertLess(elapsed, 2.0,
                            f"pause bloqueou dispatch ({elapsed:.2f}s) — deadlock?")
            # Runner carregado pode atrasar a thread da VM: se o stopped
            # não chegar, re-arma a flag (o handler responde sucesso sem
            # armar quando a thread ainda não está viva).
            stopped = None
            for _ in range(3):
                stopped = wait_for(buf, "stopped", timeout=6)
                if stopped is not None:
                    break
                if s._thread is not None and s._thread.is_alive() \
                        and not s._done and not s._paused:
                    s.handle(req(5, "pause", {"threadId": 1}))
            self.assertIsNotNone(
                stopped,
                "pause não gerou stopped "
                f"(thread viva={s._thread.is_alive() if s._thread else None} "
                f"done={s._done} paused={s._paused} "
                f"eventos={[m.get('event') for m in events_of(buf)]})")
            self.assertEqual(stopped["body"]["reason"], "pause")
            s.handle(req(6, "continue", {"threadId": 1}))
            time.sleep(0.3)
            # após continue, ainda viva (loop) — termina via terminate
            r2 = s.handle(req(7, "terminate", {}))
            self.assertTrue(r2["success"])
            self.assertIsNotNone(wait_for(buf, "terminated", timeout=8))
            s._thread.join(timeout=10)
            self.assertFalse(s._thread.is_alive())
            s.handle(req(10, "disconnect", {}))

    def test_terminate_emits_once(self):
        """terminate duplo não deve emitir `terminated` 2x."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "loop.lum")
            open(p, "w", encoding="utf8").write(PROG_LOOP)
            s.handle(req(1, "initialize", {}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            time.sleep(0.5)
            r = s.handle(req(5, "terminate", {}))
            self.assertTrue(r["success"])
            self.assertIsNotNone(wait_for(buf, "terminated", timeout=8))
            s._thread.join(timeout=10)
            time.sleep(0.5)
            n = sum(1 for m in events_of(buf) if m.get("event") == "terminated")
            self.assertEqual(n, 1, f"terminated emitido {n}x, esperado 1x")
            s.handle(req(10, "disconnect", {}))

    def test_relaunch_joins_old_thread(self):
        """relaunch (do_launch) sinaliza + join da thread antiga."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 6}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            self.assertIsNotNone(wait_for(buf, "stopped", timeout=8),
                                 "primeiro run não parou")
            old = s._thread
            self.assertTrue(old.is_alive())
            s.handle(req(5, "launch", {"program": p}))
            time.sleep(0.5)
            self.assertFalse(old.is_alive(),
                             "thread antiga não sofreu join no relaunch")
            self.assertIsNot(old, s._thread)
            self.assertTrue(wait_for_n(buf, "stopped", 2, timeout=10),
                            "segundo run não parou após relaunch")
            self.assertIsNotNone(_finish(s, buf))
            s.handle(req(10, "disconnect", {}))
            s._thread.join(timeout=10)

    def test_evaluate_mult_str_dos_refused(self):
        """_eval_node Mult recusa 'a'*1000000 (sem alocar DoS)."""
        buf = io.BytesIO()
        s = Session(buf)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "add.lum")
            open(p, "w", encoding="utf8").write(PROG_LINES)
            s.handle(req(1, "initialize", {}))
            s.handle(req(2, "setBreakpoints",
                         {"source": {"path": p},
                          "breakpoints": [{"line": 2}]}))
            s.handle(req(3, "launch", {"program": p}))
            s.handle(req(4, "configurationDone", {}))
            self.assertIsNotNone(wait_for(buf, "stopped", timeout=8))
            t0 = time.time()
            bad = s.handle(req(5, "evaluate",
                               {"expression": '"a"*1000000',
                                "context": "hover"}))
            elapsed = time.time() - t0
            self.assertIn("não suportado", bad["body"]["result"])
            self.assertLess(elapsed, 2.0, "evaluate DoS demorou — alocou?")
            ok = s.handle(req(6, "evaluate",
                              {"expression": '"a"*100', "context": "hover"}))
            self.assertIn("aaa", ok["body"]["result"])
            self.assertIsNotNone(_finish(s, buf))
            s.handle(req(11, "disconnect", {}))
            s._thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
