#!/usr/bin/env python3
"""Shim `lumen` para a imagem Docker (v0.5, stdlib apenas).

Mapeia subcomandos para os drivers Python reais do repo (/opt/lumen).
Fora do Docker, prefira chamar os scripts diretamente (ver README.md).
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/opt/lumen" if os.path.isdir("/opt/lumen") else os.path.normpath(
    os.path.join(_HERE, ".."))

HELP = """uso: lumen <run|build|test|conformance|doc|examples> [args...]

  run <arq.lum> [args]   compila e executa na VM (compiler/run.py)
  build <arq.lum> <alvo> .lum -> ir|lbc|wat|c (compiler/lumenc.py)
  test                   612 testes unitários (mesma lista do CI)
  conformance [--filter X]  suíte 50/50 (conformance/suite.py)
  doc                    regenera docs/API.md (docs/gen.py)
  examples               smoke dos 70 exemplos (tools/test/check_examples.py)
"""


def main(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    cmd, rest = argv[0], argv[1:]

    if cmd == "run":
        return subprocess.call([sys.executable, f"{ROOT}/compiler/run.py"] + rest)
    if cmd == "build":
        return subprocess.call([sys.executable, f"{ROOT}/compiler/lumenc.py"] + rest)
    if cmd == "test":
        # Mesma lista do CI (infra/ci.yml, passo "Testes unitários (v0.5)"):
        # unit + borrow/release/dap/playground/conformance/boost.
        return subprocess.call(
            [sys.executable, "-m", "unittest", "compiler.test_compiler",
             "compiler.backend.test_backends", "compiler.backend.test_e2e",
             "compiler.test_front_extra", "compiler.test_borrow",
             "runtime.test_runtime", "stdlib.test_stdlib", "tools.pkg.test_pkg",
             "tools.build.test_build", "tools.test.test_runner_self",
             "tools.test.test_release",
             "ide.lsp.test_lsp", "ide.lsp.test_server_extra",
             "ide.vscode.test_dap", "ide.playground.test_playground",
             "conformance.test_conformance", "tools.fmt.test_fmt",
             "test_boost"],
            cwd=ROOT)
    if cmd == "conformance":
        return subprocess.call([sys.executable, f"{ROOT}/conformance/suite.py"] + rest)
    if cmd == "doc":
        return subprocess.call(
            [sys.executable, f"{ROOT}/docs/gen.py", "--src",
             f"{ROOT}/docs/stdlib_api.lum", "--merge", f"{ROOT}/docs/API.md"])
    if cmd == "examples":
        return subprocess.call(
            [sys.executable, f"{ROOT}/tools/test/check_examples.py"] + rest)
    print(f"lumen: subcomando desconhecido: {cmd}\n{HELP}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
