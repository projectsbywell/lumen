#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exemplo: lê src/dados.txt e gera dist/dados.txt numerado."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src = root / "src" / "dados.txt"
out = root / "dist" / "dados.txt"
out.parent.mkdir(parents=True, exist_ok=True)

linhas = src.read_text(encoding="utf-8").splitlines() if src.exists() \
    else ["(sem entrada)"]
out.write_text("\n".join(f"{i + 1}: {l}" for i, l in enumerate(linhas)) + "\n",
               encoding="utf-8")
print(f"build_dados: {len(linhas)} linha(s) -> dist/dados.txt")