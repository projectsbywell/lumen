#!/usr/bin/env python3
"""gen.py — gerador de documentação do Lumen.

Extrai comentários de documentação `///` de arquivos `.lum` (e `.py`)
e gera páginas Markdown + índice.

Uso:
    python3 docs/gen.py --src docs/stdlib_api.lum --merge docs/API.md
    python3 docs/gen.py --src docs/stdlib_api.lum --src examples --out docs/ref
    python3 docs/gen.py --src ../stdlib --src ../examples --out docs/ref --merge docs/API.md

Por padrão (sem --src), procura `../stdlib`, `../examples`, `../compiler`,
`../runtime` e `../tools` a partir do diretório deste script.
"""
from __future__ import annotations

import argparse

import os
import re
import sys

ITEM_RE = re.compile(
    r"^\s*(pub\s+)?(fn|struct|enum|mod|macro|trait|impl|const|type)\b\s*(.*)$"
)
NAME_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)")
MOD_RE = re.compile(r"^\s*(pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{\s*$")
ATTR_RE = re.compile(r"^\s*#\[.*\]\s*$")
SPEC_VERSION = "0.5.4"


def parse_file(path: str) -> dict:
    """Extrai itens documentados de um arquivo .lum/.py.

    Retorna dict com: path, module_doc, items[{kind,name,qname,sig,doc,attrs}].
    """
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    module_doc: list[str] = []
    items: list[dict] = []
    pending: list[str] = []
    pending_attrs: list[str] = []
    mod_stack: list[tuple[str, int]] = []  # (nome, depth_antes_do_bloco)
    depth = 0
    seen_item = False
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        # fecha blocos de módulo pelo nível de chaves
        new_depth = depth + raw.count("{") - raw.count("}")
        while mod_stack and new_depth <= mod_stack[-1][1]:
            mod_stack.pop()
        depth = new_depth

        if stripped.startswith("///"):
            pending.append(stripped[3:].lstrip())
            i += 1
            continue
        if not stripped or stripped.startswith("//"):
            # linha em branco ou comentário comum quebra a associação
            if stripped == "":
                if pending and not seen_item and not items:
                    module_doc.extend(pending)
                pending = []
                pending_attrs = []
            i += 1
            continue
        if ATTR_RE.match(raw):
            pending_attrs.append(stripped)
            i += 1
            continue

        m = MOD_RE.match(raw)
        if m:
            prefix = "::".join(m_[0] for m_ in mod_stack)
            qname = f"{prefix}::{m.group(2)}" if prefix else m.group(2)
            items.append({
                "kind": "mod", "name": m.group(2), "qname": qname,
                "sig": stripped, "doc": list(pending), "attrs": list(pending_attrs),
            })
            seen_item = True
            # depth já inclui o `{` desta linha; o bloco começou em depth-1
            mod_stack.append((m.group(2), depth - 1))
            pending, pending_attrs = [], []
            i += 1
            continue

        m = ITEM_RE.match(raw)
        if m:
            kind = m.group(2)
            rest = (m.group(3) or "").strip()
            nm = NAME_RE.match(rest)
            if kind == "impl":
                name = nm.group(1) if nm else rest.split("{")[0].strip()
            else:
                name = nm.group(1) if nm else "(anônimo)"
            # assinatura pode continuar em várias linhas até equilibrar parênteses
            sig = stripped
            if kind in ("fn", "macro", "trait"):
                balance = sig.count("(") - sig.count(")")
                j = i + 1
                while balance > 0 and j < n:
                    sig += " " + lines[j].strip()
                    balance += lines[j].count("(") - lines[j].count(")")
                    j += 1
            prefix = "::".join(m_[0] for m_ in mod_stack)
            qname = f"{prefix}::{name}" if prefix else name
            if kind == "impl" and prefix:
                qname = f"{prefix}::{name}"
            items.append({
                "kind": kind, "name": name, "qname": qname,
                "sig": sig, "doc": list(pending), "attrs": list(pending_attrs),
            })
            seen_item = True
            pending, pending_attrs = [], []
            i += 1
            continue

        # doc órfã antes do primeiro item vira doc do módulo
        if pending and not seen_item and not items:
            module_doc.extend(pending)
        pending, pending_attrs = [], []
        i += 1

    return {"path": os.path.abspath(path), "module_doc": module_doc, "items": items}


def collect_sources(srcs: list[str]) -> list[str]:
    out: list[str] = []
    for s in srcs:
        if os.path.isfile(s) and s.endswith((".lum", ".py")):
            out.append(s)
        elif os.path.isdir(s):
            for root, _, files in os.walk(s):
                for f in sorted(files):
                    if f.endswith((".lum", ".py")):
                        out.append(os.path.join(root, f))
    return sorted(out)


def page_names(docs: list[dict]) -> dict[int, str]:
    """Nome de página por doc; desambigua basename repetido com o diretório pai."""
    counts: dict[str, int] = {}
    for d in docs:
        base = os.path.splitext(os.path.basename(d["path"]))[0]
        counts[base] = counts.get(base, 0) + 1
    pages: dict[int, str] = {}
    for i, d in enumerate(docs):
        base = os.path.splitext(os.path.basename(d["path"]))[0]
        if counts[base] > 1:
            parent = os.path.basename(os.path.dirname(d["path"]))
            pages[i] = f"{parent}_{base}.md"
        else:
            pages[i] = f"{base}.md"
    return pages


def render_page(doc: dict, root: str) -> str:
    rel = os.path.relpath(doc["path"], root) if root else doc["path"]
    L = [f"# `{rel}`", ""]
    if doc["module_doc"]:
        L.extend(doc["module_doc"])
        L.append("")
    if not doc["items"]:
        L.append("_Nenhum item documentado com `///` neste arquivo._")
        L.append("")
        return "\n".join(L)
    L.append("## Índice")
    L.append("")
    for it in doc["items"]:
        anchor = it["qname"].lower().replace("::", "").replace("_", "-")
        L.append(f"- `{it['kind']}` [{it['qname']}](#{anchor})")
    L.append("")
    for it in doc["items"]:
        L.append(f"## `{it['kind']}` {it['qname']}")
        L.append("")
        L.append("```lum")
        L.append(it["sig"])
        L.append("```")
        L.append("")
        if it["attrs"]:
            L.append("Atributos: " + ", ".join(f"`{a}`" for a in it["attrs"]))
            L.append("")
        if it["doc"]:
            L.extend(it["doc"])
            L.append("")
        else:
            L.append("_Sem documentação `///`._")
            L.append("")
    return "\n".join(L)


def render_index(docs: list[dict], root: str, pages: dict[int, str]) -> str:
    # Determinístico de propósito: sem data corrente para `git diff --exit-code`
    # no CI passar em qualquer dia (reproducible docs).
    L = ["# Índice da documentação Lumen", "",
         f"Gerado por `docs/gen.py` · spec v{SPEC_VERSION}.", "",
         "| Arquivo | Itens documentados |", "|---|---|"]
    for i, d in enumerate(docs):
        rel = os.path.relpath(d["path"], root) if root else d["path"]
        names = ", ".join(f"`{it['qname']}`" for it in d["items"]) or "—"
        L.append(f"| [{rel}]({pages[i]}) | {names} |")
    L.append("")
    return "\n".join(L)


def render_merge(docs: list[dict], title: str, root: str) -> str:
    # Determinístico de propósito: ver render_index.
    L = [f"# {title}", "",
         f"> Gerado por `docs/gen.py` · spec Lumen v{SPEC_VERSION}.",
         "> Para regenerar: `python3 docs/gen.py --src <fontes> --merge docs/API.md`",
         "> (quando `stdlib/` estiver populada: `--src stdlib`).", ""]
    for d in docs:
        rel = os.path.relpath(d["path"], root) if root else d["path"]
        L.append(f"<!-- fonte: {rel} -->")
        if d["module_doc"]:
            L.extend(d["module_doc"])
            L.append("")
        for it in d["items"]:
            L.append(f"## `{it['kind']}` {it['qname']}")
            L.append("")
            L.append("```lum")
            L.append(it["sig"])
            L.append("```")
            L.append("")
            if it["attrs"]:
                L.append("Atributos: " + ", ".join(f"`{a}`" for a in it["attrs"]))
                L.append("")
            L.extend(it["doc"] if it["doc"] else ["_Sem documentação `///`._"])
            L.append("")
    return "\n".join(L)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Gerador de docs Lumen a partir de `///`.")
    ap.add_argument("--src", action="append", default=[], help="Arquivo ou diretório fonte (.lum/.py). Repetível.")
    ap.add_argument("--out", default=None, help="Diretório de saída (páginas + INDEX.md).")
    ap.add_argument("--merge", default=None, help="Arquivo Markdown único com tudo (ex.: docs/API.md).")
    ap.add_argument("--title", default="Referência da API Lumen (stdlib v0.1)")
    args = ap.parse_args(argv)

    base = os.path.dirname(os.path.abspath(__file__))
    srcs = args.src or [os.path.join(base, "..", d)
                        for d in ("stdlib", "examples", "compiler", "runtime", "tools")]
    srcs = [s for s in srcs if os.path.exists(s)]
    files = collect_sources(srcs)
    if not files:
        print("gen.py: nenhuma fonte .lum/.py encontrada em:", srcs, file=sys.stderr)
        return 1

    docs = [parse_file(f) for f in files]
    total_items = sum(len(d["items"]) for d in docs)
    root = os.path.commonpath(
        [os.path.abspath(f) for f in files] + [os.path.abspath(base)])

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        out_root = os.path.commonpath(
            [os.path.abspath(f) for f in files] + [os.path.abspath(args.out)])
        pages = page_names(docs)
        for i, d in enumerate(docs):
            with open(os.path.join(args.out, pages[i]), "w", encoding="utf-8") as fh:
                fh.write(render_page(d, out_root))
        with open(os.path.join(args.out, "INDEX.md"), "w", encoding="utf-8") as fh:
            fh.write(render_index(docs, out_root, pages))
        print(f"gen.py: {len(docs)} páginas + INDEX.md em {args.out} ({total_items} itens).")

    if args.merge:
        with open(args.merge, "w", encoding="utf-8") as fh:
            fh.write(render_merge(docs, args.title, root))
        print(f"gen.py: merge com {total_items} itens em {args.merge}.")

    if not args.out and not args.merge:
        for d in docs:
            print(f"== {d['path']}: {len(d['items'])} itens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
