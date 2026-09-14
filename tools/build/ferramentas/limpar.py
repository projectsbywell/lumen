#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exemplo: remove dist/ (saídas de build). --check apenas verifica."""
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
dist = root / "dist"

if "--check" in sys.argv[1:]:
    if dist.is_dir():
        print("limpar --check: dist/ existe")
    else:
        print("limpar --check: dist/ ausente")
    sys.exit(0)

if dist.is_dir():
    shutil.rmtree(dist)
    print("limpar: dist/ removido")
else:
    print("limpar: nada a fazer")