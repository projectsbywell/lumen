#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lumen — CLI unificada do Lumen (v0.4.0).

Entry point de `pip install .` (`[project.scripts] lumen = "lumen_cli:main"`)
e do binário nativo gerado pelo PyInstaller (infra/ci.yml, job
build-release: `pyinstaller --onefile --name lumen lumen_cli.py`).

Mapeia subcomandos para os drivers Python reais:

  run <arq.lum>            compila e executa na VM        (compiler/run.py)
  build <arq.lum> <alvo>   .lum -> ir|lbc|wat|c           (compiler/lumenc.py)
  test [dir]               runner @test + cobertura       (tools/test/lumen_test.py)
  pkg ...                  gerenciador de pacotes         (tools/pkg/lumen_pkg.py)
  repl [-c '...']          REPL interativo                (tools/repl/repl.py)
  conformance [--filter X] suíte 50/50                    (conformance/suite.py)
  doc                      regenera docs/API.md           (docs/gen.py, árvore-fonte)
  examples [--verbose]     smoke dos exemplos             (tools/test/check_examples.py)
  fmt <arq.lum>            formata .lum                   (tools/fmt/lumen_fmt.py)

`run`/`build`/`test`/`pkg`/`repl` funcionam de qualquer diretório (os
arquivos `.lum` são argumentos). `doc`/`examples`/`conformance` dependem
da árvore-fonte (exemplos, docs, allowlist) e reportam erro amigável se
os dados não existirem na instalação.
"""
import importlib
import importlib.metadata
import os
import sys

__version__ = "0.4.0"

HELP = f"""uso: lumen <run|build|test|pkg|repl|conformance|doc|examples|fmt|help> [args...]

  run <arq.lum> [entry]      compila e executa na VM (compiler/run.py)
  build <arq.lum> <alvo>     compila: ir | lbc | wat | c (compiler/lumenc.py)
  test [dir] [-v]            runner @test + cobertura (tools/test/lumen_test.py)
  pkg <init|add|install|audit|...>   gerenciador de pacotes (tools/pkg/)
  repl [-c 'expr']           REPL interativo (tools/repl/repl.py)
  conformance [--filter X]   suíte de conformidade (conformance/suite.py)
  doc                        regenera docs/API.md (precisa da árvore-fonte)
  examples [--verbose]       smoke dos exemplos (precisa da árvore-fonte)
  fmt <arq.lum> [--check|--diff] formata .lum (tools/fmt/lumen_fmt.py)
  version                    imprime a versão

  help                       esta ajuda
"""


def _version() -> str:
    """Versão instalada (pip) ou a versão embutida (binário PyInstaller)."""
    try:
        return importlib.metadata.version("lumen")
    except importlib.metadata.PackageNotFoundError:  # binário / fonte
        return __version__


def _run_driver(module: str, fn: str, argv: list, prog: str) -> int:
    """Importa o driver real e chama `fn` com `argv` como sys.argv.

    Os drivers têm assinaturas diferentes (alguns leem sys.argv via
    argparse, outros recebem argv posicional); aqui padronizamos
    definindo sys.argv = [prog] + argv e chamando `fn()` sem argumentos
    quando a fn não declara parâmetro, ou `fn(argv)` quando aceita.
    """
    mod = importlib.import_module(module)
    fn = getattr(mod, fn)
    old = sys.argv
    sys.argv = [prog] + argv
    try:
        import inspect
        if len(inspect.signature(fn).parameters) == 0:
            return fn()
        return fn(argv)
    finally:
        sys.argv = old


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    if args[0] in ("-V", "--version", "version"):
        print(f"lumen {_version()}")
        return 0
    cmd, rest = args[0], args[1:]

    if cmd == "run":
        from compiler.run import main as f
        return f(["lumen-run"] + rest)
    if cmd == "build":
        from compiler.lumenc import main as f
        return f(["lumen-build"] + rest)
    if cmd == "test":
        return _run_driver("tools.test.lumen_test", "main", rest, "lumen-test")
    if cmd == "pkg":
        return _run_driver("tools.pkg.lumen_pkg", "main", rest, "lumen-pkg")
    if cmd == "repl":
        return _run_driver("tools.repl.repl", "main", rest, "lumen-repl")
    if cmd == "conformance":
        # No binário onefile o diretório do módulo é um caminho fake
        # (_MEIxxxx): default da suíte geraria o relatório ali. Força
        # --json para o cwd quando o usuário não pediu outro destino.
        if "--json" not in rest:
            rest = rest + ["--json", "conformance_report.json"]
        return _run_driver("conformance.suite", "main", rest, "lumen-conformance")
    if cmd == "doc":
        try:
            return _run_driver("docs.gen", "main", rest, "lumen-doc")
        except ImportError:
            print("lumen doc: requer a árvore-fonte (docs/gen.py não está "
                  "empacotado). Use a partir do checkout do repo.", file=sys.stderr)
            return 1
    if cmd == "examples":
        return _run_driver("tools.test.check_examples", "main", rest,
                           "lumen-examples")
    if cmd == "fmt":
        return _run_driver("tools.fmt.lumen_fmt", "main", rest, "lumen-fmt")
    print(f"lumen: subcomando desconhecido: {cmd}\n{HELP}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())