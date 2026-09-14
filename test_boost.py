"""Testes de cobertura extra: io, httpx, timex, registry live. Rode: python3 test_boost.py"""
import io as _io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdlib"))

from pylumen import io as LIO
from pylumen import httpx as HX
from pylumen import timex as TX
from pylumen import testingx as TTX
from tools.pkg import registry as REG


class TestMocksExtra(unittest.TestCase):
    def test_mock_all(self):
        m = TTX.mock(soma=10)
        m.quando("nome", retorno="ana")
        self.assertEqual(m.soma(1, 2), 10)
        self.assertEqual(m.nome(), "ana")
        self.assertIsNone(m.outro())
        self.assertTrue(m.foi_chamado())
        self.assertTrue(m.foi_chamado("soma"))
        self.assertFalse(m.foi_chamado("zz"))
        self.assertEqual(m.vezes_chamado("soma"), 1)
        m.reset()
        self.assertFalse(m.foi_chamado())

    def test_stub_restore(self):
        class C:
            def f(self):
                return 1
        c = C()
        r = TTX.stub(c, "f", lambda: 99)
        self.assertEqual(c.f(), 99)
        r()
        self.assertEqual(c.f(), 1)


class TestIOExtra(unittest.TestCase):
    def test_lumenio_write(self):
        s = _io.StringIO()
        o = LIO.LumenIO(s)
        self.assertEqual(o.write("ab"), 2)
        self.assertEqual(s.getvalue(), "ab")

    def test_lumenio_writeline_flush(self):
        s = _io.StringIO()
        o = LIO.LumenIO(s)
        o.writeline("x")
        o.flush()
        self.assertEqual(s.getvalue(), "x\n")

    def test_lumenio_default_stdout(self):
        o = LIO.LumenIO()
        self.assertIs(o._stream, None)
        n = o.write("")
        self.assertEqual(n, 0)

    def test_lumenfile_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.txt")
            with LIO.LumenFile(p, "w") as f:
                f.write("olá")
                f.writelines(["\n", "mundo"])
            with LIO.LumenFile(p) as f:
                self.assertEqual(f.read(), "olá\nmundo")
            with LIO.LumenFile(p) as f:
                self.assertEqual(f.readline().strip(), "olá")
                self.assertEqual(len(f.readlines()), 1)
            with LIO.LumenFile(p) as f:
                self.assertEqual(list(iter(f))[0].strip(), "olá")

    def test_file_funcs(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.txt")
            LIO.write_file(p, "xy")
            self.assertEqual(LIO.read_file(p), "xy")
            LIO.write_lines(p, ["a\n", "b\n"])
            self.assertEqual(LIO.read_lines(p), ["a\n", "b\n"])

    def test_print_funcs(self):
        LIO.print_stdout("s")
        LIO.print_err("e")
        LIO.stdout.writeline("l1")
        LIO.stderr.writeline("l2")
        LIO.stdout.flush()
        LIO.stderr.flush()


class FakeResp:
    def __init__(self, status=200, body=b'{"a": 1}'):
        self.status = status
        self._body = body

    def getheaders(self):
        return [("Content-Type", "application/json")]

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestHttpxExtra(unittest.TestCase):
    def test_response(self):
        r = HX.LumenResponse(FakeResp())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(r.json, {"a": 1})
        self.assertIn("a", r.text())
        self.assertTrue(r.is_success())
        self.assertFalse(r.is_redirect())
        self.assertFalse(r.is_error())

    def test_response_kinds(self):
        self.assertTrue(HX.LumenResponse(FakeResp(302, b"")).is_redirect())
        self.assertTrue(HX.LumenResponse(FakeResp(404, b"")).is_error())

    def test_build_request(self):
        c = HX.HTTPClient(timeout=5, headers={"X-A": "1"})
        q = c._build_request("http://x/", "POST", {"k": "v"}, {"X-B": "2"})
        self.assertEqual(q.get_header("X-a"), "1")
        self.assertEqual(q.get_header("X-b"), "2")
        self.assertTrue(q.data)

    def test_client_methods_mocked(self):
        real = urllib.request.urlopen
        urllib.request.urlopen = lambda req, timeout=30: FakeResp()
        try:
            c = HX.HTTPClient()
            self.assertTrue(c.get("http://x/").is_success())
            self.assertTrue(c.post("http://x/", {"a": 1}).is_success())
            self.assertTrue(HX.get("http://x/").is_success())
            self.assertTrue(HX.post("http://x/").is_success())
            self.assertTrue(HX.put("http://x/").is_success())
            self.assertTrue(HX.delete("http://x/").is_success())
            self.assertTrue(HX.request("GET", "http://x/").is_success())
        finally:
            urllib.request.urlopen = real


class TestTimexExtra(unittest.TestCase):
    def test_parts(self):
        import datetime
        dt = datetime.datetime(2024, 2, 29, 10, 30)
        self.assertEqual(TX.year(dt), 2024)
        self.assertEqual(TX.month(dt), 2)
        self.assertEqual(TX.day(dt), 29)
        self.assertEqual(TX.weekday(dt), 3)
        self.assertEqual(TX.days_in_month(2024, 2), 29)
        self.assertEqual(TX.days_in_month(2023, 2), 28)

    def test_parse_from(self):
        dt = TX.parse_date("2024-06-15 10:30:00")
        self.assertEqual((dt.year, dt.month, dt.day), (2024, 6, 15))
        self.assertIsNotNone(TX.from_timestamp(0))
        TX.sleep(0)


class TestRegistryLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.srv = REG.RegistryServer(("127.0.0.1", 0), REG.RegistryHandler, cls.tmp.name)
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.th.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def _url(self, path, data=None, method="GET"):
        req = urllib.request.Request(self.base + path, data=data, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read()
        except Exception as e:
            return getattr(e, "code", 0), b""

    def test_health_index_empty(self):
        code, body = self._url("/health")
        self.assertEqual(code, 200)
        code, body = self._url("/index")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["packages"], {})

    def test_put_get_roundtrip(self):
        payload = b"PK-falso"
        code, _ = self._url("/pkg/demo/0.1.0", data=payload, method="PUT")
        self.assertEqual(code, 201)
        code, body = self._url("/pkg/demo/0.1.0")
        self.assertEqual(code, 200)
        self.assertEqual(body, payload)
        code, body = self._url("/index")
        self.assertIn("demo", json.loads(body)["packages"])

    def test_bad_routes(self):
        code, _ = self._url("/pkg/somente")
        self.assertEqual(code, 400)
        code, _ = self._url("/pkg/ausente/9.9.9")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
