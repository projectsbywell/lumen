#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exemplo: empacota dist/dados.txt em dist/pacote.txt com sha256."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
dados = root / "dist" / "dados.txt"
pacote = root / "dist" / "pacote.txt"

pacote.write_text(json.dumps({
    "fonte": "dados.txt",
    "sha256": hashlib.sha256(dados.read_bytes()).hexdigest(),
    "bytes": dados.stat().st_size,
}, indent=1) + "\n", encoding="utf-8")
print("empacotar: dist/pacote.txt gerado")