#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do lumen-build: grafo topológico, ciclo, build incremental por
hash mtime, plugins, dry-run, clean e parser toml de fallback."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lumen_build
from lumen_build import (BuildError, build_project, _mini_toml,
                         normalize_tasks, topo_order, load_toml)


def write_tree(base: Path, files: dict):
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


PROJ_TOML = """\
[package]
name = "demo"
version = "0.1.0"
build = ["gen", "build"]

[tasks]
gen = { cmd = "python3 ferramentas/gen.py", inputs = ["src/data.txt"], outputs = ["dist/gen.txt"], desc = "gera dist/gen.txt" }
build = { cmd = "python3 ferramentas/build.py", deps = ["gen"], outputs = ["dist/final.txt"], desc = "gera dist/final.txt" }
"""

# variante sem [package].build: TODAS as tarefas (incl. de plugins) rodam
PROJ_TOML_ALL = """\
[package]
name = "demo"
version = "0.1.0"

[tasks]
gen = { cmd = "python3 ferramentas/gen.py", inputs = ["src/data.txt"], outputs = ["dist/gen.txt"], desc = "gera dist/gen.txt" }
build = { cmd = "python3 ferramentas/build.py", deps = ["gen"], outputs = ["dist/final.txt"], desc = "gera dist/final.txt" }
"""

GEN_PY = """\
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
out = root / "dist" / "gen.txt"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text((root / "src" / "data.txt").read_text(encoding="utf-8"))
with open(root / "build.log", "a", encoding="utf-8") as f:
    f.write("gen\\n")
print("gen ok")
"""

BUILD_PY = """\
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
src = (root / "dist" / "gen.txt").read_text(encoding="utf-8")
(root / "dist" / "final.txt").write_text(src.upper(), encoding="utf-8")
with open(root / "build.log", "a", encoding="utf-8") as f:
    f.write("build\\n")
print("build ok")
"""


class BuildFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        write_tree(self.root, {
            "lumen.toml": PROJ_TOML,
            "src/data.txt": "um\ndois\ntres\n",
            "ferramentas/gen.py": GEN_PY,
            "ferramentas/build.py": BUILD_PY,
        })

    def tearDown(self):
        self.tmp.cleanup()

    def log_lines(self):
        log = self.root / "build.log"
        if not log.is_file():
            return []
        return log.read_text(encoding="utf-8").splitlines()

    def test_topo_order_and_build(self):
        res = build_project(self.root / "lumen.toml")
        self.assertEqual(res.executed, ["gen", "build"])
        self.assertEqual(res.skipped, [])
        self.assertTrue((self.root / "dist" / "final.txt").is_file())
        self.assertEqual(self.log_lines(), ["gen", "build"])
        idx_gen = res.executed.index("gen")
        idx_build = res.executed.index("build")
        self.assertLess(idx_gen, idx_build)

    def test_incremental_skips_second_run(self):
        build_project(self.root / "lumen.toml")
        res = build_project(self.root / "lumen.toml")
        self.assertEqual(res.executed, [])
        self.assertEqual(res.skipped, ["gen", "build"])
        self.assertEqual(self.log_lines(), ["gen", "build"])

    def test_input_change_triggers_rerun(self):
        build_project(self.root / "lumen.toml")
        src = self.root / "src" / "data.txt"
        src.write_text("mudou\n", encoding="utf-8")
        res = build_project(self.root / "lumen.toml")
        self.assertEqual(res.executed, ["gen", "build"])
        self.assertEqual(self.log_lines(),
                         ["gen", "build", "gen", "build"])
        # conteúdo refletido
        self.assertEqual((self.root / "dist" / "final.txt")
                         .read_text(encoding="utf-8"), "MUDOU\n")

    def test_mtime_touch_triggers_rerun(self):
        build_project(self.root / "lumen.toml")
        src = self.root / "src" / "data.txt"
        st = src.stat()
        os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
        res = build_project(self.root / "lumen.toml")
        self.assertEqual(res.executed, ["gen", "build"])
        self.assertEqual(self.log_lines(),
                         ["gen", "build", "gen", "build"])

    def test_clean_removes_outputs_and_state(self):
        build_project(self.root / "lumen.toml")
        res = build_project(self.root / "lumen.toml", clean=True)
        self.assertEqual(res.executed, ["gen", "build"])  # rebuild completo
        state = self.root / ".lumen" / "build_state.json"
        self.assertTrue(state.is_file())  # regravado após o build
        # outputs regenerados pelo rebuild
        self.assertTrue((self.root / "dist" / "final.txt").is_file())
        self.assertTrue((self.root / "dist" / "gen.txt").is_file())
        # segunda execução: incremental de novo
        res2 = build_project(self.root / "lumen.toml")
        self.assertEqual(res2.skipped, ["gen", "build"])

    def test_dry_run_does_nothing(self):
        res = build_project(self.root / "lumen.toml", dry_run=True)
        self.assertEqual(res.dry_run_tasks, ["gen", "build"])
        self.assertEqual(self.log_lines(), [])
        self.assertFalse((self.root / "dist" / "gen.txt").exists())
        self.assertFalse((self.root / ".lumen" / "build_state.json")
                         .exists())

    def test_missing_input_fails(self):
        (self.root / "src" / "data.txt").unlink()
        with self.assertRaises(BuildError):
            build_project(self.root / "lumen.toml")

    def test_state_corruption_rebuilds(self):
        build_project(self.root / "lumen.toml")
        state = self.root / ".lumen" / "build_state.json"
        state.write_text("{corrompido", encoding="utf-8")
        res = build_project(self.root / "lumen.toml")
        self.assertEqual(res.executed, ["gen", "build"])


class GraphTest(unittest.TestCase):
    def test_cycle_detection(self):
        toml = ("[package]\nname = 'x'\n[tasks]\n"
                "a = { cmd = 'true', deps = ['b'] }\n"
                "b = { cmd = 'true', deps = ['a'] }\n")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "lumen.toml"
            p.write_text(toml, encoding="utf-8")
            with self.assertRaises(BuildError) as cm:
                build_project(p)
            self.assertIn("ciclo", str(cm.exception).lower())

    def test_missing_dep(self):
        with self.assertRaises(BuildError) as cm:
            normalize_tasks({"a": {"cmd": "true", "deps": ["bogus"]}})
        self.assertIn("bogus", str(cm.exception))

    def test_topo_stable_order(self):
        tasks = normalize_tasks({
            "lint": {"cmd": "true", "deps": []},
            "test": {"cmd": "true", "deps": ["build", "lint"]},
            "build": {"cmd": "true", "deps": ["gen"]},
            "gen": {"cmd": "true", "deps": []},
        })
        order = topo_order(tasks)
        self.assertLess(order.index("gen"), order.index("build"))
        self.assertLess(order.index("build"), order.index("test"))
        self.assertEqual(set(order), set(tasks))

    def test_task_filter_includes_deps(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, {
                "lumen.toml": PROJ_TOML,
                "src/data.txt": "x\n",
                "ferramentas/gen.py": GEN_PY,
                "ferramentas/build.py": BUILD_PY,
            })
            res = build_project(root / "lumen.toml", tasks=["build"])
            self.assertEqual(res.executed, ["gen", "build"])

    def test_failed_task_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, {
                "lumen.toml": "[package]\nname = 'x'\n[tasks]\n"
                              "bad = { cmd = 'python3 -c \"exit(3)\"' }\n",
            })
            with self.assertRaises(BuildError):
                build_project(root / "lumen.toml")

    def test_ignore_errors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, {
                "lumen.toml": "[package]\nname = 'x'\n[tasks]\n"
                              "bad = { cmd = 'python3 -c \"exit(3)\"', "
                              "ignore_errors = true }\n"
                              "ok = { cmd = 'python3 -c \"pass\"', "
                              "deps = ['bad'] }\n",
            })
            res = build_project(root / "lumen.toml")
            self.assertEqual(res.failed_ignored, ["bad"])
            self.assertEqual(res.by_task["ok"], "executed")

    def test_bad_plugin_does_not_break_build(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "proj"
            write_tree(root, {
                "lumen.toml": PROJ_TOML,
                "src/data.txt": "a\n",
                "ferramentas/gen.py": GEN_PY,
                "ferramentas/build.py": BUILD_PY,
                "build_plugins/quebrado.py":
                    "def before_build(ctx):\n    raise RuntimeError('boom')\n",
            })
            res = build_project(root / "lumen.toml")
            self.assertEqual(res.executed, ["gen", "build"])


class PluginTest(unittest.TestCase):
    def test_plugin_hooks_and_registered_tasks(self):
        plugin = '''\
import sys
from pathlib import Path
def before_build(ctx):
    (ctx.project_dir / "plugin.log").write_text("before\\n")
def after_task(ctx, task, status):
    with open(ctx.project_dir / "plugin.log", "a") as f:
        f.write("task:%s:%s\\n" % (task.get("desc", ""), status))
def register_tasks(ctx):
    return [{"extra": {"cmd": "python3 -c \\"open(\\'extra.txt\\',\\'w\\').write(\\'ok\\')\\"",
                       "deps": ["gen"]}}]
'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "proj"
            write_tree(root, {
                "lumen.toml": PROJ_TOML_ALL,  # sem build padrão -> extra roda
                "src/data.txt": "a\n",
                "ferramentas/gen.py": GEN_PY,
                "ferramentas/build.py": BUILD_PY,
                "build_plugins/marcador.py": plugin,
            })
            res = build_project(root / "lumen.toml")
            self.assertIn("extra", res.executed)
            self.assertTrue((root / "extra.txt").is_file())
            log = (root / "plugin.log").read_text(encoding="utf-8")
            self.assertTrue(log.startswith("before\n"))
            self.assertIn("task::executed", log)

    def test_bad_plugin_does_not_break_build(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "proj"
            write_tree(root, {
                "lumen.toml": PROJ_TOML,
                "src/data.txt": "a\n",
                "ferramentas/gen.py": GEN_PY,
                "ferramentas/build.py": BUILD_PY,
                "build_plugins/quebrado.py":
                    "def before_build(ctx):\n    raise RuntimeError('boom')\n",
            })
            res = build_project(root / "lumen.toml")
            self.assertEqual(res.executed, ["gen", "build"])

    def test_no_plugins_disables_plugins(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "proj"
            write_tree(root, {
                "lumen.toml": PROJ_TOML_ALL,
                "src/data.txt": "a\n",
                "ferramentas/gen.py": GEN_PY,
                "ferramentas/build.py": BUILD_PY,
                "build_plugins/quebrado.py":
                    "def before_build(ctx):\n    raise RuntimeError('boom')\n",
                "build_plugins/extra.py":
                    "def register_tasks(ctx):\n"
                    "    return [{'fora': {'cmd': 'python3 -c \"pass\"'}}]\n",
            })
            # com plugins: 'fora' (registrada por extra.py) roda
            res = build_project(root / "lumen.toml")
            self.assertIn("fora", res.executed)
            # com no_plugins=True: plugins ignorados, apenas gen+build no grafo
            res2 = build_project(root / "lumen.toml", no_plugins=True)
            self.assertNotIn("fora", res2.by_task)
            self.assertEqual(set(res2.by_task), {"gen", "build"})


class MiniTomlTest(unittest.TestCase):
    def test_mini_parser_matches_tomllib(self):
        sample = """\
# comentário
[package]
name = "demo"
version = "0.1.0"
enabled = true
count = 3
peso = 1.5

[tasks]
gen = { cmd = "python3 x.py", deps = [], outputs = ["dist/gen.txt"], inputs = ["src/data.txt"] }
build = { cmd = "python3 y.py", deps = ["gen"], outputs = ["dist/final.txt"] }
tags = ["a", "b", "c"]
"""
        from tomllib import loads
        expected = loads(sample)
        got = _mini_toml(sample)
        self.assertEqual(got, expected)

    def test_mini_multiline_array(self):
        sample = ('[tasks]\n'
                  'xs = [\n  "um",\n  "dois",\n]\n')
        from tomllib import loads
        self.assertEqual(_mini_toml(sample), loads(sample))


class CliSmokeTest(unittest.TestCase):
    def test_list(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "proj"
            write_tree(root, {
                "lumen.toml": PROJ_TOML,
                "src/data.txt": "a\n",
                "ferramentas/gen.py": GEN_PY,
                "ferramentas/build.py": BUILD_PY,
            })
            rc = lumen_build.main(["--file", str(root / "lumen.toml"),
                                   "--list"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()