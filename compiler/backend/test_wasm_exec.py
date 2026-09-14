"""Execução WASM real (wasmtime; pula se ausente)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

try:
    import wasmtime
    from compiler.lumenc import compilar
    HAS_WASM = True
except ImportError:
    HAS_WASM = False


def run_wasm(src, fn="main", args=(), fuel=2_000_000):
    cfg = wasmtime.Config()
    cfg.consume_fuel = True
    store = wasmtime.Store(wasmtime.Engine(cfg))
    store.set_fuel(fuel)
    wat = compilar(src, "wat")
    mod = wasmtime.Module(store.engine, wat)
    prints = []
    linker = wasmtime.Linker(store.engine)
    linker.define_func("lumen", "print",
                       wasmtime.FuncType([wasmtime.ValType.i32()], []),
                       lambda x: prints.append(x))
    inst = linker.instantiate(store, mod)
    return inst.exports(store)[fn](store, *args), prints


@unittest.skipUnless(HAS_WASM, "wasmtime ausente")
class TestWasmExec(unittest.TestCase):
    def test_arit(self):
        r, _ = run_wasm("module t\npub fn main() -> int { return 2 + 3 * 4; }")
        self.assertEqual(r, 14)

    def test_while(self):
        r, _ = run_wasm("module t\npub fn main() -> int { "
                        "let mut s: int = 0; let mut i: int = 1; "
                        "while i <= 10 { s = s + i; i = i + 1; } return s; }")
        self.assertEqual(r, 55)

    def test_fib_rec(self):
        r, _ = run_wasm("module t\nfn fib(n: int) -> int { "
                        "if n < 2 { return n; } "
                        "return fib(n - 1) + fib(n - 2); }\n"
                        "pub fn main() -> int { return fib(10); }")
        self.assertEqual(r, 55)

    def test_if_match_print(self):
        r, out = run_wasm("module t\npub fn main() -> int { "
                          "let x = match 2 { 0 => 10, 1 | 2 => 20, _ => 30, }; "
                          "println(x); return x; }")
        self.assertEqual(r, 20)
        self.assertEqual(out, [20])


if __name__ == "__main__":
    unittest.main()
