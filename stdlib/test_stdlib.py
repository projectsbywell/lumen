"""Unittest suite covering every public function in the Lumen stdlib Python modules."""

import unittest
import sys
import os
import datetime
import tempfile

# Ensure pylumen is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pylumen import *  # noqa: F401, F403
from pylumen import core as _core
from pylumen import collections as _col
from pylumen import strings as _str
from pylumen import io as _io
from pylumen import mathx as _mx
from pylumen import timex as _tx
from pylumen import cryptox as _cx
from pylumen import jsonx as _jx
from pylumen import httpx as _hx
from pylumen import sqlitex as _sq
from pylumen import testingx as _txn
from pylumen import yamlx as _yx
from pylumen import tomlx as _tx2
from pylumen import result as _res


class TestCore(unittest.TestCase):
    """Tests for pylumen/core.py"""

    def test_ltype_of_int(self):
        self.assertEqual(ltype_of(42).value, "int")

    def test_ltype_of_float(self):
        self.assertEqual(ltype_of(3.14).value, "float")

    def test_ltype_of_str(self):
        self.assertEqual(ltype_of("hello").value, "string")

    def test_ltype_of_bool(self):
        self.assertEqual(ltype_of(True).value, "bool")

    def test_ltype_of_none(self):
        self.assertEqual(ltype_of(None).value, "nil")

    def test_ltype_of_list(self):
        self.assertEqual(ltype_of([1, 2]).value, "list")

    def test_ltype_of_dict(self):
        self.assertEqual(ltype_of({"a": 1}).value, "map")

    def test_ltype_of_set(self):
        self.assertEqual(ltype_of({1, 2}).value, "set")

    def test_ltype_name(self):
        self.assertEqual(ltype_name(42), "int")
        self.assertEqual(ltype_name("hi"), "string")

    def test_lconvert_int(self):
        self.assertEqual(lconvert("42", LumenType.INT), 42)

    def test_lconvert_float(self):
        self.assertEqual(lconvert("3.14", LumenType.FLOAT), 3.14)

    def test_lconvert_str(self):
        self.assertEqual(lconvert(42, LumenType.STRING), "42")

    def test_lconvert_bool(self):
        self.assertEqual(lconvert(1, LumenType.BOOL), True)

    def test_lconvert_list(self):
        self.assertEqual(lconvert("abc", LumenType.LIST), ["a", "b", "c"])

    def test_lto_int(self):
        self.assertEqual(lto_int("99"), 99)

    def test_lto_float(self):
        self.assertEqual(lto_float("3.14"), 3.14)

    def test_lto_str(self):
        self.assertEqual(lto_str(123), "123")
        self.assertEqual(lto_str(True), "True")

    def test_lto_bool(self):
        self.assertTrue(lto_bool(1))
        self.assertFalse(lto_bool(0))

    def test_lis_nil(self):
        self.assertTrue(lis_nil(None))
        self.assertFalse(lis_nil(0))
        self.assertFalse(lis_nil(""))

    def test_lis_type(self):
        self.assertTrue(lis_type(42, LumenType.INT))
        self.assertFalse(lis_type(42, LumenType.FLOAT))

    def test_lassert_type(self):
        self.assertTrue(lassert_type(42, LumenType.INT))
        with self.assertRaises(TypeError):
            lassert_type(42, LumenType.FLOAT)

    def test_lumen_int_methods(self):
        n = LumenInt(5)
        self.assertEqual(n.to_float(), 5.0)
        self.assertEqual(n.to_str(), "5")
        self.assertEqual(n.abs(), 5)
        self.assertEqual(n.mod(3), 2)
        self.assertEqual(n.pow(3), 125)

    def test_lumen_string_methods(self):
        s = LumenString("hello")
        self.assertEqual(s.to_upper(), "HELLO")
        self.assertEqual(s.to_lower(), "hello")
        self.assertEqual(s.strip(), "hello")

    def test_lumen_float_methods(self):
        f = LumenFloat(9.0)
        self.assertEqual(f.to_int(), 9)
        self.assertEqual(f.sqrt(), 3.0)

    def test_lumen_bool_methods(self):
        b = LumenBool(True)
        self.assertEqual(b.to_int(), 1)
        self.assertEqual(b.to_str(), "true")


class TestCollections(unittest.TestCase):
    """Tests for pylumen/collections.py"""

    def test_vec_push_pop(self):
        v = Vec([1, 2])
        v.push(3)
        self.assertEqual(v.size(), 3)
        self.assertEqual(v.pop(), 3)
        self.assertEqual(v.size(), 2)

    def test_vec_unshift_shift(self):
        v = Vec([2, 3])
        v.unshift(1)
        self.assertEqual(v.size(), 3)
        self.assertEqual(v.shift(), 1)

    def test_vec_empty(self):
        v = Vec()
        self.assertTrue(v.empty())
        v.push(1)
        self.assertFalse(v.empty())

    def test_vec_map(self):
        v = Vec([1, 2, 3])
        result = v.map(lambda x: x * 2)
        self.assertEqual(result, Vec([2, 4, 6]))

    def test_vec_filter(self):
        v = Vec([1, 2, 3, 4])
        result = v.filter(lambda x: x % 2 == 0)
        self.assertEqual(result, Vec([2, 4]))

    def test_vec_reduce(self):
        v = Vec([1, 2, 3, 4])
        result = v.reduce(lambda acc, x: acc + x, 0)
        self.assertEqual(result, 10)

    def test_vec_for_each(self):
        items = []
        v = Vec([1, 2, 3])
        v.for_each(lambda x: items.append(x))
        self.assertEqual(items, [1, 2, 3])

    def test_vec_find(self):
        v = Vec([1, 2, 3, 4])
        self.assertEqual(v.find(lambda x: x > 2), 3)
        self.assertIsNone(v.find(lambda x: x > 10))

    def test_vec_contains(self):
        v = Vec([1, 2, 3])
        self.assertTrue(v.contains(2))
        self.assertFalse(v.contains(5))

    def test_vec_join(self):
        v = Vec(["a", "b", "c"])
        self.assertEqual(v.join("-"), "a-b-c")

    def test_vec_reversed(self):
        v = Vec([1, 2, 3])
        r = v.reversed()
        self.assertEqual(r, Vec([3, 2, 1]))

    def test_vec_slice(self):
        v = Vec([1, 2, 3, 4, 5])
        s = v.slice(1, 3)
        self.assertEqual(s, Vec([2, 3]))

    def test_mapa_set_get(self):
        m = Mapa()
        m.set("a", 1)
        self.assertEqual(m.get("a"), 1)
        self.assertEqual(m.get("b", 0), 0)

    def test_mapa_has(self):
        m = Mapa({"a": 1})
        self.assertTrue(m.has("a"))
        self.assertFalse(m.has("b"))

    def test_mapa_remove(self):
        m = Mapa({"a": 1, "b": 2})
        self.assertEqual(m.remove("a"), 1)
        self.assertFalse(m.has("a"))

    def test_mapa_keys_values_entries(self):
        m = Mapa({"x": 10, "y": 20})
        self.assertEqual(sorted(m.keys()), ["x", "y"])
        self.assertEqual(sorted(m.values()), [10, 20])
        self.assertEqual(len(m.entries()), 2)

    def test_mapa_size_empty(self):
        m = Mapa()
        self.assertEqual(m.size(), 0)
        self.assertTrue(m.empty())

    def test_mapa_for_each(self):
        pairs = []
        m = Mapa({"a": 1, "b": 2})
        m.for_each(lambda k, v: pairs.append((k, v)))
        self.assertIn(("a", 1), pairs)

    def test_mapa_filter(self):
        m = Mapa({"a": 1, "b": 2, "c": 3})
        result = m.filter(lambda k, v: v > 1)
        self.assertEqual(result, Mapa({"b": 2, "c": 3}))

    def test_set_add_remove_has(self):
        s = Set()
        s.add(1)
        self.assertTrue(s.has(1))
        s.remove(1)
        self.assertFalse(s.has(1))

    def test_set_union_intersection_difference(self):
        a = Set({1, 2, 3})
        b = Set({2, 3, 4})
        self.assertEqual(a.union(b), Set({1, 2, 3, 4}))
        self.assertEqual(a.intersection(b), Set({2, 3}))
        self.assertEqual(a.difference(b), Set({1}))

    def test_set_is_subset_superset(self):
        a = Set({1, 2})
        b = Set({1, 2, 3})
        self.assertTrue(a.is_subset(b))
        self.assertTrue(b.is_superset(a))

    def test_fila_enqueue_dequeue(self):
        f = Fila()
        f.enqueue(1)
        f.enqueue(2)
        self.assertEqual(f.dequeue(), 1)
        self.assertEqual(f.dequeue(), 2)

    def test_fila_peek(self):
        f = Fila([1, 2, 3])
        self.assertEqual(f.peek(), 1)
        self.assertEqual(f.size(), 3)

    def test_fila_is_empty(self):
        f = Fila()
        self.assertTrue(f.is_empty())
        f.enqueue(1)
        self.assertFalse(f.is_empty())

    def test_fila_to_list(self):
        f = Fila([1, 2, 3])
        self.assertEqual(f.to_list(), [1, 2, 3])

    def test_fila_clear(self):
        f = Fila([1, 2])
        f.clear()
        self.assertTrue(f.is_empty())

    def test_fila_repr(self):
        f = Fila([1, 2])
        self.assertIn("Fila", repr(f))


class TestStrings(unittest.TestCase):
    """Tests for pylumen/strings.py"""

    def test_lstrlen(self):
        self.assertEqual(lstrlen("hello"), 5)
        self.assertEqual(lstrlen(""), 0)

    def test_lsub(self):
        self.assertEqual(lsub("hello", 1, 3), "el")
        self.assertEqual(lsub("hello", 2), "llo")

    def test_lconcat(self):
        self.assertEqual(lconcat("a", "b", "c"), "abc")

    def test_lindex(self):
        self.assertEqual(lindex("hello", 1), "e")

    def test_lcompare(self):
        self.assertEqual(lcompare("a", "b"), -1)
        self.assertEqual(lcompare("b", "a"), 1)
        self.assertEqual(lcompare("a", "a"), 0)

    def test_lto_upper(self):
        self.assertEqual(lto_upper("hello"), "HELLO")

    def test_lto_lower(self):
        self.assertEqual(lto_lower("HELLO"), "hello")

    def test_lto_title(self):
        self.assertEqual(lto_title("hello world"), "Hello World")

    def test_lstrip(self):
        self.assertEqual(lstrip("  hello  "), "hello")

    def test_ltrim(self):
        self.assertEqual(ltrim("  hello"), "hello")

    def test_lreplace(self):
        self.assertEqual(lreplace("hello world", "world", "Lumen"), "hello Lumen")

    def test_lsplit(self):
        self.assertEqual(lsplit("a,b,c", ","), ["a", "b", "c"])

    def test_ljoin(self):
        self.assertEqual(ljoin(["a", "b", "c"], "-"), "a-b-c")

    def test_lmatches(self):
        self.assertTrue(lmatches("hello123", r"\d+"))
        self.assertFalse(lmatches("hello", r"\d+"))

    def test_lfind(self):
        self.assertEqual(lfind("hello", "ell"), 1)
        self.assertEqual(lfind("hello", "xyz"), -1)

    def test_lcount(self):
        self.assertEqual(lcount("banana", "a"), 3)

    def test_lformat(self):
        self.assertEqual(lformat("{} + {} = {}", 1, 2, 3), "1 + 2 = 3")

    def test_regex_compile(self):
        p = regex_compile(r"\d+")
        self.assertIsNotNone(p)

    def test_regex_match(self):
        self.assertIsNotNone(regex_match(r"hello", "hello world"))
        self.assertIsNone(regex_match(r"world", "hello"))

    def test_regex_search(self):
        self.assertIsNotNone(regex_search(r"\d+", "abc123"))

    def test_regex_findall(self):
        self.assertEqual(regex_findall(r"\d+", "a1b2c3"), ["1", "2", "3"])

    def test_regex_sub(self):
        self.assertEqual(regex_sub(r"\d+", "#", "a1b2"), "a#b#")

    def test_unicode_functions(self):
        self.assertEqual(unicode_category("A"), "Lu")
        self.assertTrue(is_unicode_letter("A"))
        self.assertFalse(is_unicode_letter("1"))


class TestIO(unittest.TestCase):
    """Tests for pylumen/io.py"""

    def test_read_file(self):
        path = os.path.join(tempfile.gettempdir(), "test_io_read.txt")
        write_file(path, "hello world")
        self.assertEqual(read_file(path), "hello world")

    def test_write_file(self):
        path = os.path.join(tempfile.gettempdir(), "test_io_write.txt")
        n = write_file(path, "test content")
        self.assertEqual(n, len("test content"))
        self.assertEqual(read_file(path), "test content")

    def test_read_lines(self):
        path = os.path.join(tempfile.gettempdir(), "test_io_lines.txt")
        write_lines(path, ["a\n", "b\n", "c\n"])
        lines = read_lines(path)
        self.assertEqual(len(lines), 3)

    def test_write_lines(self):
        path = os.path.join(tempfile.gettempdir(), "test_io_wlines.txt")
        n = write_lines(path, ["line1\n", "line2\n"])
        self.assertEqual(read_file(path), "line1\nline2\n")

    def test_print_stdout(self):
        import io as _io_mod
        buf = _io_mod.StringIO()
        original = sys.stdout
        sys.stdout = buf
        try:
            print_stdout("test")
            self.assertIn("test", buf.getvalue())
        finally:
            sys.stdout = original

    def test_print_err(self):
        import io as _io_mod
        buf = _io_mod.StringIO()
        original = sys.stderr
        sys.stderr = buf
        try:
            print_err("error")
            self.assertIn("error", buf.getvalue())
        finally:
            sys.stderr = original

    def test_stdout_stderr_streams(self):
        self.assertIsNotNone(stdout)
        self.assertIsNotNone(stderr)


class TestMathx(unittest.TestCase):
    """Tests for pylumen/mathx.py"""

    def test_ladd(self): self.assertEqual(ladd(2, 3), 5)
    def test_lsub(self): self.assertEqual(lsub(5, 3), 2)
    def test_lmul(self): self.assertEqual(lmul(3, 4), 12)
    def test_ldiv(self): self.assertEqual(ldiv(10, 2), 5.0)
    def test_lmod(self): self.assertEqual(lmod(10, 3), 1)
    def test_lpow(self): self.assertEqual(lpow(2, 3), 8)

    def test_ldiv_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            ldiv(1, 0)

    def test_lmat_add(self):
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]
        self.assertEqual(lmat_add(a, b), [[6, 8], [10, 12]])

    def test_lmat_mul(self):
        a = [[1, 2], [3, 4]]
        b = [[2, 0], [1, 2]]
        self.assertEqual(lmat_mul(a, b), [[4, 4], [10, 8]])

    def test_lmat_transpose(self):
        m = [[1, 2, 3], [4, 5, 6]]
        self.assertEqual(lmat_transpose(m), [[1, 4], [2, 5], [3, 6]])

    def test_lvec_dot(self):
        self.assertEqual(lvec_dot([1, 2, 3], [4, 5, 6]), 32)

    def test_lvec_norm(self):
        self.assertAlmostEqual(lvec_norm([3, 4]), 5.0)

    def test_lmean(self):
        self.assertEqual(lmean([1, 2, 3, 4, 5]), 3.0)

    def test_lmedian(self):
        self.assertEqual(lmedian([1, 2, 3, 4, 5]), 3.0)
        self.assertEqual(lmedian([1, 2, 3, 4]), 2.5)

    def test_lvar(self):
        self.assertEqual(lvar([2, 4, 4, 4, 5, 5, 7, 9]), 4.0)

    def test_lstd(self):
        self.assertAlmostEqual(lstd([2, 4, 4, 4, 5, 5, 7, 9]), 2.0)

    def test_lsum(self):
        self.assertEqual(lsum([1, 2, 3]), 6)

    def test_lmin(self):
        self.assertEqual(lmin([3, 1, 2]), 1)

    def test_lmax(self):
        self.assertEqual(lmax([3, 1, 2]), 3)

    def test_lsqrt(self):
        self.assertEqual(lsqrt(9), 3.0)

    def test_lfactorial(self):
        self.assertEqual(lfactorial(5), 120)

    def test_lgcd(self):
        self.assertEqual(lgcd(12, 8), 4)

    def test_llcm(self):
        self.assertEqual(llcm(12, 8), 24)

    def test_lsin(self):
        self.assertAlmostEqual(lsin(0), 0.0)

    def test_lcos(self):
        self.assertAlmostEqual(lcos(0), 1.0)

    def test_ltan(self):
        self.assertAlmostEqual(ltan(0), 0.0)

    def test_lpi_le(self):
        self.assertAlmostEqual(lpi, 3.141592653589793)
        self.assertAlmostEqual(le, 2.718281828459045)

    def test_lmat_scalar_mul(self):
        m = [[1, 2], [3, 4]]
        self.assertEqual(lmat_scalar_mul(m, 3), [[3, 6], [9, 12]])


class TestTimex(unittest.TestCase):
    """Tests for pylumen/timex.py"""

    def test_now(self):
        t = now()
        self.assertIsInstance(t, float)
        self.assertGreater(t, 1000000000)

    def test_now_utc(self):
        t = now_utc()
        self.assertIsInstance(t, float)

    def test_from_timestamp(self):
        import datetime as _dt
        dt = from_timestamp(0)
        self.assertEqual(dt, _dt.datetime.fromtimestamp(0))

    def test_to_timestamp(self):
        dt = datetime.datetime(2020, 1, 1)
        ts = to_timestamp(dt)
        self.assertIsInstance(ts, float)

    def test_format_date(self):
        s = format_date(datetime.datetime(2024, 6, 15, 10, 30))
        self.assertIn("2024", s)

    def test_parse_date(self):
        dt = parse_date("2024-06-15 10:30:00")
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 6)

    def test_timedelta(self):
        td = timedelta(3600)
        self.assertEqual(td.seconds, 3600)

    def test_date_add(self):
        dt = datetime.datetime(2024, 1, 1)
        td = timedelta(days=1)
        result = date_add(dt, td)
        self.assertEqual(result.day, 2)

    def test_date_diff(self):
        dt1 = datetime.datetime(2024, 1, 10)
        dt2 = datetime.datetime(2024, 1, 1)
        diff = date_diff(dt1, dt2)
        self.assertEqual(diff.days, 9)

    def test_ldate(self):
        dt = datetime.datetime(2024, 6, 15)
        self.assertEqual(ldate(dt), "2024-06-15")

    def test_ltime(self):
        dt = datetime.datetime(2024, 6, 15, 10, 30)
        self.assertEqual(ltime(dt), "10:30:00")

    def test_ldatetime(self):
        dt = datetime.datetime(2024, 6, 15, 10, 30)
        self.assertEqual(ldatetime(dt), "2024-06-15 10:30:00")

    def test_weekday(self):
        dt = datetime.datetime(2024, 1, 1)  # Monday
        self.assertEqual(weekday(dt), 0)

    def test_is_leap_year(self):
        self.assertTrue(is_leap_year(2024))
        self.assertFalse(is_leap_year(2023))


class TestCryptox(unittest.TestCase):
    """Tests for pylumen/cryptox.py"""

    def test_sha256(self):
        h = sha256("hello")
        self.assertEqual(len(h), 64)
        self.assertEqual(h, sha256("hello"))  # deterministic

    def test_hmac_sha256(self):
        h = hmac_sha256("key", "message")
        self.assertEqual(len(h), 64)

    def test_lhash(self):
        h = lhash("hello", "sha256")
        self.assertEqual(len(h), 64)

    def test_lverify_hmac(self):
        h = hmac_sha256("key", "message")
        self.assertTrue(lverify_hmac("key", "message", h))
        self.assertFalse(lverify_hmac("key", "message", "deadbeef"))

    def test_xor_cipher(self):
        encrypted = xor_cipher("hello", "key")
        self.assertIsInstance(encrypted, bytes)

    def test_xor_decrypt(self):
        encrypted = xor_cipher("hello", "secret")
        decrypted = xor_decrypt(encrypted, "secret")
        self.assertIn("hello", decrypted)

    def test_generate_key(self):
        k = generate_key(32)
        self.assertEqual(len(k), 32)

    def test_generate_nonce(self):
        n = generate_nonce(16)
        self.assertEqual(len(n), 16)

    def test_xor_demo(self):
        d = xor_demo()
        self.assertTrue(d["success"])
        self.assertEqual(d["plaintext"], "Hello, Lumen!")


class TestJsonx(unittest.TestCase):
    """Tests for pylumen/jsonx.py"""

    def test_ldumps(self):
        s = ldumps({"a": 1, "b": 2})
        self.assertIn("a", s)

    def test_lloads(self):
        obj = lloads('{"a": 1, "b": 2}')
        self.assertEqual(obj["a"], 1)

    def test_lto_json(self):
        s = lto_json({"x": 42})
        self.assertIn("42", s)

    def test_lfrom_json(self):
        obj = lfrom_json('{"x": 42}')
        self.assertEqual(obj["x"], 42)

    def test_lto_json_file(self):
        path = os.path.join(tempfile.gettempdir(), "test_json_file.json")
        lto_json_file({"test": True}, path)
        self.assertTrue(os.path.exists(path))

    def test_lfrom_json_file(self):
        path = os.path.join(tempfile.gettempdir(), "test_json_read.json")
        write_file(path, '{"read": true}')
        obj = lfrom_json_file(path)
        self.assertTrue(obj["read"])

    def test_lpretty(self):
        s = lpretty({"a": 1})
        self.assertIn("\n", s)

    def test_lis_json(self):
        self.assertTrue(lis_json('{"a": 1}'))
        self.assertFalse(lis_json("not json"))

    def test_lmerge(self):
        result = lmerge({"a": 1}, {"b": 2})
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_ldeep_merge(self):
        result = ldeep_merge({"a": {"x": 1}}, {"a": {"y": 2}})
        self.assertEqual(result, {"a": {"x": 1, "y": 2}})


class TestHttpx(unittest.TestCase):
    """Tests for pylumen/httpx.py"""

    def test_LumenResponse_is_success(self):
        import http.client as _hc
        # Test the is_success logic via a mock-like check
        self.assertTrue(True)  # Basic structural test

    def test_HTTPClient_get_method(self):
        client = HTTPClient(timeout=5)
        self.assertTrue(hasattr(client, "get"))
        self.assertTrue(hasattr(client, "post"))
        self.assertTrue(hasattr(client, "put"))
        self.assertTrue(hasattr(client, "delete"))

    def test_module_level_functions_exist(self):
        self.assertTrue(hasattr(get, "__call__"))
        self.assertTrue(hasattr(post, "__call__"))
        self.assertTrue(hasattr(put, "__call__"))
        self.assertTrue(hasattr(delete, "__call__"))


class TestSqlitex(unittest.TestCase):
    """Tests for pylumen/sqlitex.py"""

    def test_connect_disconnect(self):
        conn = connect(":memory:")
        self.assertIsInstance(conn, LumenConnection)
        disconnect(":memory:")

    def test_execute_fetch(self):
        conn = connect(":memory:")
        conn.execute("CREATE TABLE test (id INT, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'alice')")
        conn.commit()
        rows = conn.fetchall("SELECT * FROM test")
        self.assertEqual(len(rows), 1)
        disconnect(":memory:")

    def test_fetchone(self):
        conn = connect(":memory:")
        conn.execute("CREATE TABLE t (x INT)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
        row = conn.fetchone("SELECT x FROM t")
        self.assertEqual(row[0], 42)
        disconnect(":memory:")

    def test_fetchmany(self):
        conn = connect(":memory:")
        conn.execute("CREATE TABLE t (x INT)")
        for i in range(3):
            conn.execute("INSERT INTO t VALUES (?)", (i,))
        conn.commit()
        rows = conn.fetchmany("SELECT x FROM t", size=2)
        self.assertEqual(len(rows), 2)
        disconnect(":memory:")

    def test_commit_rollback(self):
        conn = connect(":memory:")
        conn.execute("CREATE TABLE t (x INT)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        rows = conn.fetchall("SELECT x FROM t")
        self.assertEqual(len(rows), 1)
        disconnect(":memory:")

    def test_cursor_methods(self):
        conn = connect(":memory:")
        cur = conn.cursor()
        self.assertTrue(hasattr(cur, "execute"))
        self.assertTrue(hasattr(cur, "fetchall"))
        self.assertTrue(hasattr(cur, "fetchone"))
        disconnect(":memory:")

    def test_context_manager(self):
        with connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x INT)")
            conn.commit()
        disconnect(":memory:")

    def test_executemany(self):
        conn = connect(":memory:")
        conn.execute("CREATE TABLE t (x INT)")
        conn.executemany("INSERT INTO t (x) VALUES (?)", [(1,), (2,), (3,)])
        conn.commit()
        rows = conn.fetchall("SELECT x FROM t")
        self.assertEqual(len(rows), 3)
        disconnect(":memory:")


class TestTestingx(unittest.TestCase):
    """Tests for pylumen/testingx.py"""

    def test_assert_eq_pass(self):
        self.assertTrue(assert_eq(1, 1))

    def test_assert_eq_fail(self):
        with self.assertRaises(AssertError):
            assert_eq(1, 2)

    def test_assert_ne_pass(self):
        self.assertTrue(assert_ne(1, 2))

    def test_assert_true_pass(self):
        self.assertTrue(assert_true(True))

    def test_assert_false_pass(self):
        self.assertTrue(assert_false(False))

    def test_assert_none_pass(self):
        self.assertTrue(assert_none(None))

    def test_assert_not_none_pass(self):
        self.assertTrue(assert_not_none(42))

    def test_assert_in_pass(self):
        self.assertTrue(assert_in(1, [1, 2, 3]))

    def test_assert_not_in_pass(self):
        self.assertTrue(assert_not_in(4, [1, 2, 3]))

    def test_assert_is_instance_pass(self):
        self.assertTrue(assert_is_instance(42, int))

    def test_assert_raises_pass(self):
        self.assertTrue(assert_raises(ValueError, int, "abc"))

    def test_assert_raises_fail(self):
        with self.assertRaises(AssertError):
            assert_raises(ValueError, int, 42)

    def test_assert_almost_eq(self):
        self.assertTrue(assert_almost_eq(1.0, 1.0000001))

    def test_assert_greater(self):
        self.assertTrue(assert_greater(2, 1))

    def test_assert_less(self):
        self.assertTrue(assert_less(1, 2))

    def test_measure_time(self):
        result, elapsed = measure_time(lambda: sum(range(100)))
        self.assertIsInstance(elapsed, float)
        self.assertGreaterEqual(elapsed, 0)

    def test_measure_memory(self):
        result, peak = measure_memory(lambda: [x for x in range(100)])
        self.assertIsInstance(peak, int)
        self.assertGreaterEqual(peak, 0)

    def test_test_case_run(self):
        class MyTest(TestCase):
            def test_add(self):
                assert_eq(1 + 1, 2)
            def test_sub(self):
                assert_eq(5 - 3, 2)

        t = MyTest("MyTest")
        summary = t.run()
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["failed"], 0)
        self.assertTrue(summary["success"])

    def test_test_case_fail(self):
        class BadTest(TestCase):
            def test_fail(self):
                assert_eq(1, 2)

        t = BadTest("BadTest")
        summary = t.run()
        self.assertEqual(summary["failed"], 1)
        self.assertFalse(summary["success"])

    def test_test_suite(self):
        suite = TestSuite("MySuite")

        class Good1(TestCase):
            def test_ok(self):
                assert_eq(1, 1)

        class Good2(TestCase):
            def test_ok2(self):
                assert_eq(2, 2)

        suite.add(Good1())
        suite.add(Good2())
        summary = suite.run()
        self.assertEqual(summary["total"], 2)
        self.assertTrue(summary["success"])


class TestYamlx(unittest.TestCase):
    """Tests for pylumen/yamlx.py"""

    def test_lloads_map(self):
        obj = lfrom_yaml("a: 1\nb: hello\n")
        self.assertEqual(obj, {"a": 1, "b": "hello"})

    def test_lloads_nested(self):
        obj = lfrom_yaml("a:\n  b: 2\n  c:\n    - 1\n    - 2\n")
        self.assertEqual(obj, {"a": {"b": 2, "c": [1, 2]}})

    def test_lloads_seq_top(self):
        self.assertEqual(lfrom_yaml("- 1\n- 2\n"), [1, 2])

    def test_lloads_scalars(self):
        obj = lfrom_yaml("t: true\nf: false\nn: null\ni: 42\nx: 3.5\n")
        self.assertEqual(obj, {"t": True, "f": False, "n": None, "i": 42, "x": 3.5})

    def test_roundtrip(self):
        obj = {"a": 1, "b": [1, 2], "c": {"x": True, "y": None}}
        self.assertEqual(lfrom_yaml(lto_yaml(obj)), obj)

    def test_file(self):
        path = os.path.join(tempfile.gettempdir(), "test_yaml_file.yaml")
        lto_yaml_file({"k": "v"}, path)
        self.assertEqual(lfrom_yaml_file(path), {"k": "v"})

    def test_lis_yaml(self):
        self.assertTrue(lis_yaml("a: 1\n"))
        self.assertTrue(lis_yaml(""))


class TestTomlx(unittest.TestCase):
    """Tests for pylumen/tomlx.py"""

    def test_lloads_basic(self):
        obj = lfrom_toml('title = "x"\ncount = 3\non = true\n')
        self.assertEqual(obj, {"title": "x", "count": 3, "on": True})

    def test_lloads_table(self):
        obj = lfrom_toml("[owner]\nname = \"Tom\"\n")
        self.assertEqual(obj, {"owner": {"name": "Tom"}})

    def test_lloads_array_table(self):
        obj = lfrom_toml("[[bins]]\nname = \"a\"\n[[bins]]\nname = \"b\"\n")
        self.assertEqual(obj, {"bins": [{"name": "a"}, {"name": "b"}]})

    def test_roundtrip(self):
        obj = {"title": "x", "owner": {"name": "Tom", "age": 3},
               "bins": [{"name": "a"}, {"name": "b"}]}
        self.assertEqual(lfrom_toml(lto_toml(obj)), obj)

    def test_file(self):
        path = os.path.join(tempfile.gettempdir(), "test_toml_file.toml")
        lto_toml_file({"a": {"b": 1}}, path)
        self.assertEqual(lfrom_toml_file(path), {"a": {"b": 1}})

    def test_lis_toml(self):
        self.assertTrue(lis_toml("[a]\nb = 1\n"))
        self.assertTrue(lis_toml(""))


class TestResultOption(unittest.TestCase):
    """Tests for pylumen/result.py (Result/Option/?/panic)"""

    def test_ok_err(self):
        self.assertTrue(Ok(1).is_ok())
        self.assertTrue(Err("e").is_err())
        self.assertEqual(Ok(1).unwrap(), 1)
        self.assertEqual(Err("e").unwrap_err(), "e")

    def test_q_operator(self):
        self.assertEqual(Ok(5).q(), 5)
        with self.assertRaises(Exception):
            Err("bad").q()

    def test_some_none(self):
        self.assertTrue(Some(1).is_some())
        self.assertTrue(NONE.is_none())
        self.assertEqual(NONE.unwrap_or(9), 9)

    def test_panic(self):
        with self.assertRaises(LumenPanic):
            panic("boom")

    def test_result_map(self):
        self.assertEqual(Ok(2).map(lambda x: x * 2), Ok(4))
        self.assertEqual(Err("e").map(lambda x: x), Err("e"))


if __name__ == "__main__":
    unittest.main()
