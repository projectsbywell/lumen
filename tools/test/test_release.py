#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_release.py — T5: validação da release v0.4.0 (offline, stdlib apenas).

Cobre o item 4 da Parte 5 do release:

  1. `pyproject.toml` parseia com `tomllib` e expõe `[build-system]`
     setuptools + `[project]` com name/version/requires-python;
  2. a versão do `pyproject.toml` bate com o manifesto `lumen.toml`
     (fonte da verdade única — bump conjunto é obrigatório);
  3. o entry point `[project.scripts] lumen` aponta para `lumen_cli:main`
     e o módulo/função existem e são importáveis de verdade;
  4. `lumen_cli.main` é callable e retorna 0 para `--help`.

Nenhuma rede, nenhuma dependência externa: roda com
`PYTHONPATH=. python3 -m unittest tools.test.test_release`.
"""
from __future__ import annotations

import importlib
import inspect
import os
import sys
import unittest

try:
    import tomllib
except ImportError:  # pragma: no cover — Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PYPROJECT = os.path.join(ROOT, "pyproject.toml")
MANIFEST = os.path.join(ROOT, "lumen.toml")


def _load_toml(path: str) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


class TestReleaseV040(unittest.TestCase):
    maxDiff = None

    def test_pyproject_eh_toml_valido(self):
        """pyproject.toml parseia e tem build-system setuptools."""
        meta = _load_toml(PYPROJECT)
        bs = meta["build-system"]
        self.assertEqual(bs["build-backend"], "setuptools.build_meta")
        self.assertTrue(any("setuptools" in r for r in bs.get("requires", [])))
        self.assertEqual(meta["project"]["name"], "lumen")

    def test_versao_pyproject_bate_com_manifesto(self):
        """pyproject [project].version == lumen.toml [package].version.

        Comparação dinâmica (tomllib) — sem versão hardcoded: o bump
        conjunto é obrigatório e a checagem nunca deve expirar.
        """
        pyproject = _load_toml(PYPROJECT)["project"]
        manifesto = _load_toml(MANIFEST)["package"]
        self.assertEqual(pyproject["version"], manifesto["version"],
                         "pyproject.toml e lumen.toml com versões divergentes: "
                         "bump conjunto obrigatório")
        self.assertTrue(pyproject["requires-python"].startswith(">="))
        self.assertEqual(pyproject["license"], "MIT")

    def test_entry_point_lumen_aponta_para_main_importavel(self):
        """[project.scripts] lumen existe e `lumen_cli.main` é callable."""
        scripts = _load_toml(PYPROJECT)["project"]["scripts"]
        self.assertIn("lumen", scripts)
        mod_name, _, fn_name = scripts["lumen"].partition(":")
        self.assertEqual(fn_name, "main")

        # O módulo do entry point precisa estar no wheel: está listado em
        # [tool.setuptools] py-modules?
        tool = _load_toml(PYPROJECT).get("tool", {}).get("setuptools", {})
        self.assertIn("lumen_cli", tool.get("py-modules", []),
                      "lumen_cli precisa estar em [tool.setuptools] py-modules")

        # Importabilidade real (sem rede):
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        mod = importlib.import_module(mod_name)
        main = getattr(mod, fn_name)
        self.assertTrue(callable(main))
        self.assertTrue(hasattr(mod, "__version__"))
        self.assertEqual(mod.__version__, _load_toml(PYPROJECT)["project"]["version"])

    def test_cli_help_retorna_zero(self):
        """Smoke offline do entry point: `lumen --help` sai com 0."""
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from lumen_cli import main
        self.assertIsInstance(inspect.signature(main).parameters.get("argv"),
                              inspect.Parameter)
        self.assertEqual(main(["--help"]), 0)
        self.assertEqual(main(["version"]), 0)


if __name__ == "__main__":
    unittest.main()