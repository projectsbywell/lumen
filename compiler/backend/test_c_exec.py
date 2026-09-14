"""Execução C real (cc; pula se ausente)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from compiler.lumenc import compilar

HAS_CC = shutil.which("cc") is not None


def run_c(src):
    h, c = compilar(src, "c")
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "lumen_rt.h"), "w").write(h)
        open(os.path.join(d, "main.c"), "w").write(c)
        exe = os.path.join(d, "app")
        r = subprocess.run(["cc", "-std=c99", "-O2", "-Wall", "-o", exe,
                            os.path.join(d, "main.c")],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:500]
        r = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stderr[:200]
        return r.stdout.strip().splitlines()


@unittest.skipUnless(HAS_CC, "cc ausente")
class TestCExec(unittest.TestCase):
    def test_arit(self):
        self.assertEqual(run_c("module t\npub fn main() -> int { return 2 + 3 * 4; }"), ["14"])

    def test_while(self):
        out = run_c("module t\npub fn main() -> int { "
                    "let mut s: int = 0; let mut i: int = 1; "
                    "while i <= 10 { s = s + i; i = i + 1; } return s; }")
        self.assertEqual(out, ["55"])

    def test_fat_rec(self):
        out = run_c("module t\nfn fat(n: int) -> int { "
                    "if n <= 1 { return 1; } return n * fat(n - 1); }\n"
                    "pub fn main() -> int { return fat(5); }")
        self.assertEqual(out, ["120"])

    def test_match_print(self):
        out = run_c("module t\npub fn main() -> int { "
                    "let x = match 2 { 0 => 10, _ => 20, }; "
                    "println(x); return x; }")
        self.assertEqual(out, ["20", "20"])


if __name__ == "__main__":
    unittest.main()
