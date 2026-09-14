"""Lexer Lumen — unicode + tokens contextuais + posições."""
from __future__ import annotations
from dataclasses import dataclass

KEYWORDS = {"module","import","pub","fn","let","mut","const","if","else","match","for",
    "while","return","struct","enum","trait","impl","true","false","in","as",
    "async","await","spawn","macro","where","loop","break","continue","use",
    "self","Self","type","super","crate"}

# Palavras contextuais: agora vazias porque as 5 foram promovidas a keywords reais.
# Mantido para compatibilidade com is_contextual() — sempre falso.
CONTEXTUAL = set()

def is_contextual(val: str) -> bool:
    return val in CONTEXTUAL

SYMS2 = {"=>":"FATARROW","->":"ARROW","::":"COLON2","==":"EQ2","!=":"NEQ",
    "<=":"LE",">=":"GE","&&":"AND2","||":"OR2","..":"DOT2","+=":"PLUSEQ",
    "-=":"MINUSEQ","*=":"MULEQ","/=":"DIVEQ"}
SYMS1 = {"+":"PLUS","-":"MINUS","*":"STAR","/":"SLASH","%":"PERC","=":"EQ",
    "<":"LT",">":"GT","!":"BANG","&":"AMP","|":"PIPE","^":"CARET","~":"TILDE",
    "?":"QMARK",".":"DOT",",":"COMMA",";":"SEMI",":":"COLON","(":"LP",
    ")":"RP","{":"LB","}":"RB","[":"LBK","]":"RBK","_":"UNDER","#":"HASH"}

@dataclass
class Token:
    kind: str; val: str; line: int; col: int; suffix: str = ""; raw: bool = False
    def __repr__(self): return f"Token({self.kind},{self.val!r},{self.line}:{self.col},suffix={self.suffix!r},raw={self.raw})"

class LexError(Exception): pass

def format_lex_error(src: str, msg: str, line: int, col: int) -> str:
    """Erro de alta qualidade: `arquivo:linha:col: msg` + snippet + cursor."""
    lines = src.splitlines()
    row = lines[line - 1] if 1 <= line <= len(lines) else ""
    pointer = " " * max(col - 1, 0) + "^"
    return f"{line}:{col}: {msg}\n  {row}\n  {pointer}"

def tokenize(src: str) -> list[Token]:
    toks: list[Token] = []
    i, line, col, n = 0, 1, 1, len(src)
    def adv(k=1):
        nonlocal i, line, col
        for _ in range(k):
            if i < n and src[i] == "\n": line += 1; col = 1
            else: col += 1
            i += 1
    while i < n:
        c = src[i]
        if c in " \t\r\n": adv(); continue
        if c == "/" and i+1 < n and src[i+1] == "/":
            if i+2 < n and src[i+2] == "/":
                s = i
                while i < n and src[i] != "\n": adv()
                toks.append(Token("DOC", src[s:i], line, col)); continue
            while i < n and src[i] != "\n": adv()
            continue
        if c == "/" and i+1 < n and src[i+1] == "*":  # /* aninhado */
            l, cc = line, col; adv(2); depth = 1
            while i < n and depth:
                if src[i:i+2] == "/*": depth += 1; adv(2)
                elif src[i:i+2] == "*/": depth -= 1; adv(2)
                else: adv()
            if depth: raise LexError(f"bloco não terminado em {l}:{cc}")
            continue
        # raw string: r, r#, r##, r### ... + '"'
        if c == "r" and i+1 < n and (src[i+1] == '"' or src[i+1] == '#'):
            # conta #s
            j = i+1
            h = 0
            while j < n and src[j] == "#":
                h += 1; j += 1
            if j < n and src[j] == '"':
                l, cc = line, col
                # consome r + #*h + "
                adv(1 + h + 1)
                end = '"' + '#' * h
                s = i
                # conteúdo começa em i (após adv)
                s_content = i
                while i < n and src[i:i+len(end)] != end:
                    adv()
                if i >= n: raise LexError(f"raw string não terminada em {l}:{cc}")
                content = src[s_content:i]
                toks.append(Token("STRING", content, l, cc, suffix="", raw=True)); adv(len(end)); continue
            # se não for raw string (ex.: r#type como raw ident), trata como IDENT
            # cai no ramo de ident abaixo — não consome aqui
            pass
        if c == '"':
            l, cc, s = line, col, i; adv(); buf = ""
            while i < n and src[i] != '"':
                if src[i] == "\\" and i+1 < n:
                    nxt = src[i+1]
                    if nxt == "u" and i+2 < n and src[i+2] == "{":
                        j = src.find("}", i)
                        if j < 0: raise LexError(f"\\u{{}} não terminado em {l}:{cc}")
                        hexpart = src[i+3:j]
                        if not hexpart: raise LexError(f"escape unicode inválido em {l}:{cc}")
                        try:
                            # permite até 6 hex dígitos, valida range unicode
                            cp = int(hexpart, 16)
                            if cp < 0 or cp > 0x10FFFF: raise ValueError()
                            buf += chr(cp)
                        except ValueError: raise LexError(f"escape unicode inválido em {l}:{cc}")
                        adv(j - i + 1)
                    elif nxt == "u":
                        # \uXXXX com 4 hex dígitos
                        if i+6 > n: raise LexError(f"escape unicode inválido em {l}:{cc}")
                        hexpart = src[i+2:i+6]
                        try:
                            buf += chr(int(hexpart, 16))
                        except ValueError: raise LexError(f"escape unicode inválido em {l}:{cc}")
                        adv(6)
                    elif nxt == "n":
                        buf += "\n"; adv(2)
                    elif nxt == "t":
                        buf += "\t"; adv(2)
                    elif nxt == "r":
                        buf += "\r"; adv(2)
                    elif nxt == "\\":
                        buf += "\\"; adv(2)
                    elif nxt == '"':
                        buf += '"'; adv(2)
                    elif nxt == "'":
                        buf += "'"; adv(2)
                    elif nxt == "0":
                        buf += "\0"; adv(2)
                    else:
                        buf += src[i:i+2]; adv(2)
                else: buf += src[i]; adv()
            if i >= n: raise LexError(f"string não terminada em {l}:{cc}")
            adv()
            toks.append(Token("STRING", buf, l, cc)); continue
        if c == "'":
            l, cc = line, col; adv(); buf = ""
            while i < n and src[i] != "'":
                if src[i] == "\\" and i+1 < n:
                    nxt = src[i+1]
                    if nxt == "n":
                        buf += "\n"; adv(2)
                    elif nxt == "t":
                        buf += "\t"; adv(2)
                    elif nxt == "r":
                        buf += "\r"; adv(2)
                    elif nxt == "\\":
                        buf += "\\"; adv(2)
                    elif nxt == "'":
                        buf += "'"; adv(2)
                    elif nxt == '"':
                        buf += '"'; adv(2)
                    elif nxt == "u" and i+2 < n and src[i+2] == "{":
                        j = src.find("}", i)
                        if j < 0: raise LexError(f"\\u{{}} não terminado em {l}:{cc}")
                        hexpart = src[i+3:j]
                        try:
                            cp = int(hexpart, 16)
                            if cp < 0 or cp > 0x10FFFF: raise ValueError()
                            buf += chr(cp)
                        except ValueError: raise LexError(f"escape unicode inválido em {l}:{cc}")
                        adv(j - i + 1)
                    elif nxt == "u":
                        if i+6 > n: raise LexError(f"escape unicode inválido em {l}:{cc}")
                        hexpart = src[i+2:i+6]
                        try:
                            buf += chr(int(hexpart, 16))
                        except ValueError: raise LexError(f"escape unicode inválido em {l}:{cc}")
                        adv(6)
                    else:
                        buf += src[i+1]; adv(2)
                else:
                    buf += src[i]; adv()
            if i >= n: raise LexError(f"char não terminado em {l}:{cc}")
            adv(); toks.append(Token("CHAR", buf, l, cc)); continue
        if c.isdigit():
            l, cc, s = line, col, i
            while i < n and (src[i].isdigit() or src[i] == "_"): adv()
            isf = False
            if i < n and src[i] == "." and i+1 < n and src[i+1].isdigit():
                isf = True; adv()
                while i < n and (src[i].isdigit() or src[i] == "_"): adv()
                # exponente opcional: e/E [+/-] digits
                if i < n and src[i] in ("e","E"):
                    # verifica se há dígito a frente
                    if i+1 < n and (src[i+1].isdigit() or src[i+1] in ("+","-")):
                        adv()
                        if i < n and src[i] in ("+","-"): adv()
                        while i < n and (src[i].isdigit() or src[i] == "_"): adv()
            num = src[s:i].replace("_", "")
            # sufixo: sequência alfanumérica colada (ex.: 42i32, 3.0f64)
            # No lexer original era `while isalpha or _` mas sufixo pode conter dígitos: i32, f64
            suf = ""
            if i < n and (src[i].isalpha() or src[i] == "_"):
                ss = i
                while i < n and (src[i].isalnum() or src[i] == "_"): adv()
                suf = src[ss:i]
                num_no_suf = num
                # num já não contém sufixo, suf separado
            toks.append(Token("FLOAT" if isf else "INT", num, l, cc, suffix=suf)); continue
        if c.isalpha() or c == "_" or ord(c) > 127:
            l, cc, s = line, col, i
            while i < n and (src[i].isalnum() or src[i] == "_" or ord(src[i]) > 127): adv()
            w = src[s:i]
            # raw identifier r#foo: se w começa com r# e depois ident, trata como IDENT sem r#
            # Mas nosso ramo raw string já tratou r# + ". Para r#type etc., o lexer
            # teria tokenizado 'r' como IDENT? Na verdade acima, w pode ser "r" e depois "#" não faz parte de ident (pois # não é alnum). Então "r#type" seria tokenizado como IDENT "r", HASH, IDENT "type". Precisamos suportar raw identifier: r#ident
            # Detecta padrão r#ident: se w == "r" e i < n e src[i] == "#" e src[i+1:i+2].isalpha() etc, consome.
            # Simplificação: trata "r#foo" como IDENT "foo" com flag raw_ident
            # Para cumprir spec, qualquer keyword prefixada com r# vira IDENT.
            # Como nosso ramo ident já consumiu apenas "r", precisamos olhar ahead.
            if w == "r" and i < n and src[i] == "#":
                # verifica se depois tem ident
                j = i+1
                if j < n and (src[j].isalpha() or src[j] == "_" or ord(src[j]) > 127):
                    # consome # e ident
                    adv()  # consome #
                    ls, cs = line, col  # posição original?
                    s2 = i
                    while i < n and (src[i].isalnum() or src[i] == "_" or ord(src[i]) > 127): adv()
                    w2 = src[s2:i]
                    # w2 é o ident real, sem r#
                    toks.append(Token("IDENT", w2, l, cc)); continue
            # determina kind: keyword ou ident
            if w in KEYWORDS:
                toks.append(Token(w.upper(), w, l, cc)); continue
            toks.append(Token("IDENT", w, l, cc)); continue
        two = src[i:i+2]
        if two in SYMS2:
            toks.append(Token(SYMS2[two], two, line, col)); adv(2); continue
        if c in SYMS1:
            toks.append(Token(SYMS1[c], c, line, col)); adv(); continue
        raise LexError(f"char inválido {c!r} em {line}:{col}")
    toks.append(Token("EOF", "", line, col))
    return toks
