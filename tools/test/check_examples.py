#!/usr/bin/env python3
"""check_examples.py — smoke da infra de exemplos (AGENTE D).

Parseia + checa semanticamente todos os `.lum` de `examples/001-050/`
e `examples/*.lum` com o front-end real (`lumenc.compilar`, target `ir`).
Sem dependências externas (stdlib apenas).

Uso:
    python3 tools/test/check_examples.py            # tudo, saída curta
    python3 tools/test/check_examples.py --verbose  # um PASS/FAIL por arquivo
    python3 tools/test/check_examples.py --strict   # allowlist também reprova

Falhas listadas em `tools/test/smoke_allowlist.txt` (migração ativa,
dono: compilador/exemplos) são relatadas como [XFAIL] e não quebram
o CI; qualquer outra falha retorna 1.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT)

from compiler.lumenc import compilar  # noqa: E402


def load_allowlist() -> dict[str, str]:
    path = os.path.join(ROOT, "tools", "test", "smoke_allowlist.txt")
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                rel, _, reason = line.partition(":")
                out[rel.strip()] = reason.strip()
    except FileNotFoundError:
        pass
    return out


def check(paths: list[str], verbose: bool) -> tuple[int, int, list[str]]:
    ok, fail, errors = 0, 0, []
    for p in sorted(paths):
        try:
            src = open(p, encoding="utf-8").read()
            compilar(src, "ir")
            ok += 1
            if verbose:
                print(f"[PASS] {os.path.relpath(p, ROOT)}")
        except Exception as e:  # noqa: BLE001 — smoke: qualquer erro reprova
            # Normaliza para `/` (spec de paths do repo): no Windows
            # `relpath` devolve `\` e a allowlist usa `/` (senão XFAIL
            # conhecido vira FAIL inesperado só no Windows).
            rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
            fail += 1
            errors.append(f"{rel}: {e}")
            print(f"[FAIL] {rel}: {e}")
    return ok, fail, errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Smoke: todos os exemplos compilam (front-end).")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="Ignora a allowlist: qualquer falha reprova.")
    args = ap.parse_args(argv)

    dirs = [os.path.join(ROOT, "examples", "001-050"), os.path.join(ROOT, "examples")]
    paths: list[str] = []
    for d in dirs:
        paths.extend(glob.glob(os.path.join(d, "*.lum")))
    paths = sorted(set(paths))

    allow = {} if args.strict else load_allowlist()
    ok, fail, errors = check(paths, args.verbose)
    if not errors:
        print(f"check_examples: {ok}/{ok + fail} exemplos OK (front-end: lex+parse+semântica).")
        return 0
    unexpected = [e for e in errors
                  if e.split(":")[0] not in allow]
    for e in errors:
        rel = e.split(":")[0]
        if rel in allow:
            print(f"[XFAIL] {e}  (allowlist: {allow[rel]})")
    n_xfail = len(errors) - len(unexpected)
    print(f"check_examples: {ok}/{ok + fail} OK, "
          f"{n_xfail} XFAIL (allowlist) + {len(unexpected)} FAIL.")
    return 0 if not unexpected else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
