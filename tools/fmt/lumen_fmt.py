#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lumen fmt — formatador determinístico .lum (stdlib, sem deps).

Regras:
  - indent 4
  - espaços ao redor de `=(){},;:` (normalizado via tabela no_space_before/after)
  - quebras após `{` / `}` / `;`
  - preserva strings (incl. raw), char, DOC (`///`), comentários `//` e `/* */`
  - idempotente: fmt(fmt(x)) == fmt(x)
  - erro léxico com linha:col limpo (propaga LexError do lexer)
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# validação via lexer real (para erros)
try:
    from compiler.frontend.lexer import tokenize, LexError
except Exception:  # fallback se import falhar (ex: execução isolada)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from compiler.frontend.lexer import tokenize, LexError  # type: ignore

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Scanner que preserva comentários/DOC/strings
# ---------------------------------------------------------------------------

def _scan(src: str):
    """Retorna lista de (kind, text) preservando comentários e strings.
    kinds: DOC, LINE_COMMENT, BLOCK_COMMENT, STRING, CHAR, RAW_STRING,
           IDENT, NUMBER, OP, PUNCT
    Levanta LexError em string/bloco não terminado ou char inválido.
    """
    toks = []
    n = len(src)
    i = 0
    while i < n:
        # DOC: /// até fim da linha
        if src.startswith("///", i):
            j = src.find("\n", i)
            if j == -1:
                j = n
            toks.append(("DOC", src[i:j]))
            i = j
            continue
        # Line comment // (já tratou ///)
        if src.startswith("//", i):
            j = src.find("\n", i)
            if j == -1:
                j = n
            toks.append(("LINE_COMMENT", src[i:j]))
            i = j
            continue
        # Block comment /* aninhado */
        if src.startswith("/*", i):
            start = i
            depth = 1
            i += 2
            while i < n and depth > 0:
                if src.startswith("/*", i):
                    depth += 1
                    i += 2
                elif src.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth != 0:
                # tenta achar linha/col do início
                line = src[:start].count("\n") + 1
                col = start - src.rfind("\n", 0, start)
                raise LexError(f"bloco não terminado em {line}:{col}")
            toks.append(("BLOCK_COMMENT", src[start:i]))
            continue
        c = src[i]
        # String "
        if c == '"':
            start = i
            line = src[:start].count("\n") + 1
            col = start - src.rfind("\n", 0, start)
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    # valida escapes como lexer faria, mas preserva raw
                    # Se \u{...} etc, apenas consome
                    if src[i+1] == "u" and i+2 < n and src[i+2] == "{":
                        j = src.find("}", i)
                        if j == -1:
                            raise LexError(f"\\u{{}} não terminado em {line}:{col}")
                        hexpart = src[i+3:j]
                        if not hexpart:
                            raise LexError(f"escape unicode inválido em {line}:{col}")
                        try:
                            cp = int(hexpart, 16)
                            if cp < 0 or cp > 0x10FFFF:
                                raise ValueError()
                        except ValueError:
                            raise LexError(f"escape unicode inválido em {line}:{col}")
                        i = j + 1
                        continue
                    elif src[i+1] == "u":
                        if i+6 > n:
                            raise LexError(f"escape unicode inválido em {line}:{col}")
                        hexpart = src[i+2:i+6]
                        try:
                            int(hexpart, 16)
                        except ValueError:
                            raise LexError(f"escape unicode inválido em {line}:{col}")
                        i += 6
                        continue
                    i += 2
                elif src[i] == "\n":
                    raise LexError(f"string não terminada em {line}:{col}")
                else:
                    i += 1
            if i >= n:
                raise LexError(f"string não terminada em {line}:{col}")
            i += 1  # fecha "
            toks.append(("STRING", src[start:i]))
            continue
        # Char '
        if c == "'":
            start = i
            line = src[:start].count("\n") + 1
            col = start - src.rfind("\n", 0, start)
            i += 1
            while i < n and src[i] != "'":
                if src[i] == "\\" and i+1 < n:
                    i += 2
                elif src[i] == "\n":
                    raise LexError(f"char não terminado em {line}:{col}")
                else:
                    i += 1
            if i >= n:
                raise LexError(f"char não terminado em {line}:{col}")
            i += 1
            toks.append(("CHAR", src[start:i]))
            continue
        # Raw string r#"..."# etc
        if c == "r" and i+1 < n and (src[i+1] == '"' or src[i+1] == '#'):
            j = i + 1
            h = 0
            while j < n and src[j] == "#":
                h += 1
                j += 1
            if j < n and src[j] == '"':
                start = i
                line = src[:start].count("\n") + 1
                col = start - src.rfind("\n", 0, start)
                end = '"' + '#' * h
                i = j + 1
                k = src.find(end, i)
                if k == -1:
                    raise LexError(f"raw string não terminada em {line}:{col}")
                i = k + len(end)
                toks.append(("RAW_STRING", src[start:i]))
                continue
        # whitespace -> skip (será normalizado)
        if c in " \t\r\n":
            i += 1
            continue
        # multi-char ops (maior primeiro)
        if src.startswith("..=", i):
            toks.append(("OP", "..="))
            i += 3
            continue
        two = src[i:i+2]
        if two in ("=>", "->", "::", "==", "!=", "<=", ">=", "&&", "||", "..", "+=", "-=", "*=", "/="):
            toks.append(("OP", two))
            i += 2
            continue
        # Ident (unicode)
        if c.isalpha() or c == "_" or ord(c) > 127:
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_" or ord(src[j]) > 127):
                j += 1
            toks.append(("IDENT", src[i:j]))
            i = j
            continue
        # Number
        if c.isdigit():
            j = i
            while j < n and (src[j].isdigit() or src[j] == "_"):
                j += 1
            if j < n and src[j] == "." and j+1 < n and src[j+1].isdigit():
                j += 1
                while j < n and (src[j].isdigit() or src[j] == "_"):
                    j += 1
                if j < n and src[j] in ("e", "E"):
                    k = j+1
                    if k < n and src[k] in ("+", "-"):
                        k += 1
                    while k < n and (src[k].isdigit() or src[k] == "_"):
                        k += 1
                    j = k
            # sufixo
            k = j
            while k < n and (src[k].isalpha() or src[k] == "_" or src[k].isdigit()):
                # só considera sufixo se começa com alpha/_
                if k == j and not (src[k].isalpha() or src[k] == "_"):
                    break
                k += 1
            if k != j:
                j = k
            toks.append(("NUMBER", src[i:j]))
            i = j
            continue
        # Single punct/ops
        if c in "=(){},;:[]#.<>+-*/%&|^~!?":
            # ':' já tratado ::, mas single ':' fica aqui
            # '.' já tratado .., ..=, single '.' fica aqui
            toks.append(("PUNCT", c))
            i += 1
            continue
        # inválido
        line = src[:i].count("\n") + 1
        col = i - src.rfind("\n", 0, i)
        raise LexError(f"char inválido {c!r} em {line}:{col}")
    return toks


# ---------------------------------------------------------------------------
# Formatter core
# ---------------------------------------------------------------------------

# tokens que não levam espaço antes
_NO_SPACE_BEFORE = {",", ";", ":", ")", "]", "}", ".", "!", "?", "(", "[", "#", "::", "<", ">"}
# tokens que não levam espaço depois (próximo token não leva espaço)
_NO_SPACE_AFTER = {"(", "[", ".", "!", "?", "#", "::", "<"}

def _needs_space(prev: str | None, cur: str) -> bool:
    if prev is None:
        return False
    if cur in _NO_SPACE_BEFORE:
        return False
    if prev in _NO_SPACE_AFTER:
        return False
    return True

def format_code(src: str) -> str:
    """Formata código .lum determinístico.

    - indent 4
    - espaços ao redor de `=(){},;:` normalizados
    - quebras após `{` / `}` / `;`
    - preserva strings/comentários/DOC
    - idempotente
    Levanta LexError em erro léxico.
    """
    if src.strip() == "":
        return ""
    # validação léxica via lexer real (erro limpo)
    try:
        tokenize(src)
    except LexError:
        raise
    except Exception as e:
        # fallback: repassa como LexError
        raise LexError(str(e))

    toks = _scan(src)

    out_lines: list[str] = []
    cur = ""
    prev_tok: str | None = None
    indent = 0

    def flush_cur():
        nonlocal cur, prev_tok
        if cur.strip() == "":
            cur = ""
            prev_tok = None
            return
        # cur já contém conteúdo sem indent; adiciona indent ao emitir
        out_lines.append("    " * indent + cur.rstrip())
        cur = ""
        prev_tok = None

    for kind, text in toks:
        # DOC / line comment
        if kind in ("DOC", "LINE_COMMENT"):
            txt = text.rstrip()
            # se tem código pendente na linha, anexa como trailing
            if cur.strip() != "":
                # trailing comment no mesmo statement (antes do ; flush?)
                # adiciona espaço e comentário na mesma linha
                if not cur.endswith(" "):
                    cur += " "
                cur += txt
                # flush linha com código + comentário
                out_lines.append("    " * indent + cur.rstrip())
                cur = ""
                prev_tok = None
            else:
                # linha standalone
                out_lines.append("    " * indent + txt)
                # prev_tok reset
                prev_tok = None
            continue
        if kind == "BLOCK_COMMENT":
            # preserva bloco; se multiline, emite como linhas próprias
            if "\n" in text:
                if cur.strip() != "":
                    out_lines.append("    " * indent + cur.rstrip())
                    cur = ""
                    prev_tok = None
                # split preservando linhas
                lines = text.split("\n")
                for idx, l in enumerate(lines):
                    # remove trailing ws mas preserva conteúdo
                    l = l.rstrip()
                    if l == "" and idx == len(lines)-1:
                        continue
                    # Para idempotência, normaliza indent interno? Mantém como está mas com indent base
                    # Se linha original já tem indent, mantemos stripped? Melhor emitir sem indent extra além do base
                    # Para simplicidade, emite com indent base se não vazia
                    if l.strip() == "":
                        out_lines.append("")
                    else:
                        # Se primeira linha, já com indent
                        out_lines.append("    " * indent + l.strip())
                prev_tok = None
                continue
            else:
                txt = text.strip()
                if cur.strip() != "":
                    if not cur.endswith(" "):
                        cur += " "
                    cur += txt
                    prev_tok = txt
                else:
                    # standalone mas mantém em cur para não flush imediato (permite código após)
                    # Se cur vazio, inicia cur com comentário
                    cur = txt
                    prev_tok = txt
                continue

        # Strings/chars/raw: trata como valor
        if kind in ("STRING", "CHAR", "RAW_STRING"):
            txt = text
            if cur == "":
                cur = txt
            else:
                if _needs_space(prev_tok, txt):
                    cur += " " + txt
                else:
                    cur += txt
            prev_tok = txt
            continue

        # Código: IDENT, NUMBER, OP, PUNCT
        txt = text
        # Casos especiais de quebra
        if txt == "{":
            if cur == "":
                cur = "{"
            else:
                if _needs_space(prev_tok, "{"):
                    cur += " {"
                else:
                    # garante espaço antes de { se não houver (ex: ) {)
                    if cur.endswith(" "):
                        cur += "{"
                    else:
                        # se precisa espaço mas _needs_space deu False (ex: "{" está em no_space_before? não está)
                        # então adiciona espaço
                        cur += " {" if not cur.endswith(" ") else "{"
            out_lines.append("    " * indent + cur.rstrip())
            cur = ""
            prev_tok = None
            indent += 1
            continue
        if txt == "}":
            if cur.strip() != "":
                out_lines.append("    " * indent + cur.rstrip())
                cur = ""
                prev_tok = None
            indent = max(0, indent - 1)
            out_lines.append("    " * indent + "}")
            prev_tok = None
            continue
        if txt == ";":
            if cur == "":
                cur = ";"
            else:
                # sem espaço antes de ;
                if cur.endswith(" "):
                    cur = cur.rstrip() + ";"
                else:
                    cur += ";"
            out_lines.append("    " * indent + cur.rstrip())
            cur = ""
            prev_tok = None
            continue

        # Demais tokens: ",", ":", "::", "(", ")", "[", "]", "=", "=>", etc, IDENT, NUMBER
        if cur == "":
            cur = txt
        else:
            if _needs_space(prev_tok, txt):
                cur += " " + txt
            else:
                cur += txt
        prev_tok = txt

    # flush restante
    if cur.strip() != "":
        out_lines.append("    " * indent + cur.rstrip())

    # pós-processamento: collapse >1 linhas vazias, remove trailing ws já feito, garante newline final
    cleaned: list[str] = []
    blanks = 0
    for l in out_lines:
        if l.strip() == "":
            blanks += 1
            if blanks <= 1:
                cleaned.append("")
        else:
            blanks = 0
            cleaned.append(l.rstrip())
    # remove blanks no início/fim excessivos
    while cleaned and cleaned[0] == "":
        cleaned.pop(0)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    if not cleaned:
        return ""
    return "\n".join(cleaned) + "\n"


def format_file(path: Path) -> tuple[str, str]:
    """Lê arquivo, retorna (original, formatado). Levanta LexError."""
    src = path.read_text(encoding="utf-8")
    fmt = format_code(src)
    return src, fmt


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="lumen fmt",
        description="Formatador determinístico .lum (indent 4, espaços ao redor de =(){},;: , quebras após { } ;)",
    )
    ap.add_argument("files", nargs="*", help="arquivos .lum para formatar")
    ap.add_argument("--check", action="store_true", help="exit 1 se arquivo difere do formatado (não reescreve)")
    ap.add_argument("--diff", action="store_true", help="imprime diff unificado (não reescreve)")
    ap.add_argument("--stdin", action="store_true", help="lê stdin e imprime formatado em stdout")
    args = ap.parse_args(argv)

    # modo stdin (útil para testes)
    if args.stdin or not args.files:
        if not args.stdin and not args.files:
            ap.print_help()
            return 2
        if args.stdin:
            src = sys.stdin.read()
            try:
                out = format_code(src)
            except LexError as e:
                print(f"erro léxico: {e}", file=sys.stderr)
                return 1
            sys.stdout.write(out)
            return 0

    exit_code = 0
    for f in args.files:
        p = Path(f)
        if not p.is_file():
            print(f"lumen fmt: arquivo não encontrado: {f}", file=sys.stderr)
            return 2
        try:
            src, fmt = format_file(p)
        except LexError as e:
            print(f"{p}:{e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"lumen fmt: erro em {p}: {e}", file=sys.stderr)
            return 1

        if args.check:
            if src != fmt:
                print(f"{p}: não formatado", file=sys.stderr)
                exit_code = 1
            continue
        if args.diff:
            if src != fmt:
                diff = difflib.unified_diff(
                    src.splitlines(keepends=True),
                    fmt.splitlines(keepends=True),
                    fromfile=str(p),
                    tofile=str(p) + " (formatado)",
                )
                sys.stdout.writelines(diff)
                exit_code = 1
            continue
        # modo padrão: reescreve se diferente
        if src != fmt:
            p.write_text(fmt, encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
