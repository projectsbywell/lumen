"""Parser Lumen com recuperação de erro."""
from __future__ import annotations
from compiler.frontend.lexer import Token
from compiler.frontend import ast_nodes as A
from compiler.frontend.ast_nodes import Span, Attr

class ParseError(Exception):
    def __init__(self, msg, tok):
        super().__init__(f"{msg} em {tok.line}:{tok.col} (recebido {tok.kind} {tok.val!r})")
        self.tok = tok

class Parser:
    IDENT_LIKE = ("IDENT", "SELF", "SELF_TYPE", "TYPE", "SUPER", "CRATE")
    def __init__(self, toks: list[Token]):
        self.t = toks; self.i = 0; self.errs: list[str] = []
        self.last = toks[0] if toks else None
        self.macros: dict[str, A.Fn] = {}
    def peek(self): return self.t[self.i]
    def next(self):
        x = self.t[self.i]; self.i = min(self.i+1, len(self.t)-1); self.last = x; return x
    def sp(self, tok=None) -> Span:
        t = tok or self.last or self.peek()
        return Span(t.line, t.col, t.line, t.col + max(len(t.val), 1))
    def format_errors(self, src: str = "") -> list[str]:
        if not src: return list(self.errs)
        out = []
        for e in self.errs: out.append(e)
        return out
    def eat(self, k):
        if self.peek().kind == k: return self.next()
        raise ParseError(f"esperado {k}", self.peek())
    def accept(self, k):
        if self.peek().kind == k: return self.next()
        return None
    def eat_ident(self):
        """Consome IDENT ou keyword promovida que pode atuar como ident (self/Self/type/super/crate)."""
        tok = self.peek()
        if tok.kind in self.IDENT_LIKE:
            return self.next()
        raise ParseError("esperado identificador", tok)
    def accept_ident(self):
        tok = self.peek()
        if tok.kind in self.IDENT_LIKE:
            return self.next()
        return None
    def _peek_is_ident(self):
        return self.peek().kind in self.IDENT_LIKE
    DECL = ("PUB", "FN", "ASYNC", "STRUCT", "ENUM", "MACRO", "TRAIT",
            "IMPL", "USE", "IMPORT", "MODULE", "CONST")

    def sync(self):
        if self.peek().kind in ("RB", "SEMI", "EOF") + self.DECL:
            if self.peek().kind not in ("EOF",) + self.DECL:
                self.next()
            return
        while self.peek().kind not in ("SEMI", "RB", "EOF") + self.DECL:
            self.next()
        if self.peek().kind == "SEMI":
            self.next()

    def attrs(self):
        out = []
        while self.peek().kind == "HASH" and self.i+1 < len(self.t) and self.t[self.i+1].kind == "LBK":
            self.next(); self.next()
            while self.peek().kind not in ("RBK", "EOF"):
                # pula vírgulas e espaços
                if self.peek().kind == "COMMA":
                    self.next(); continue
                if self.peek().kind in self.IDENT_LIKE:
                    name = self.next().val
                    args = []
                    if self.peek().kind == "LP":
                        self.next()
                        while self.peek().kind not in ("RP", "EOF", "RBK"):
                            if self.peek().kind == "COMMA":
                                self.next(); continue
                            if self.peek().kind in ("IDENT", "STRING", "INT", "FLOAT", "SELF", "SELF_TYPE", "TYPE", "SUPER", "CRATE"):
                                args.append(self.next().val)
                            elif self.peek().kind in ("HASH", "LBK", "RBK"):
                                break
                            else:
                                # para args como "should_panic" etc, consome como val
                                # se for outro token, consome e coleta seu val se houver
                                tok = self.next()
                                if tok.val:
                                    args.append(tok.val)
                            # vírgula opcional já tratada no topo
                        if self.peek().kind == "RP":
                            self.next()
                    out.append(Attr(name, args))
                elif self.peek().kind == "IDENT":
                    # compat: ident simples
                    name = self.next().val
                    args = []
                    if self.peek().kind == "LP":
                        self.next()
                        while self.peek().kind not in ("RP", "EOF", "RBK"):
                            if self.peek().kind == "COMMA":
                                self.next(); continue
                            if self.peek().kind not in ("RP", "RBK", "EOF"):
                                args.append(self.next().val)
                            else:
                                break
                        if self.peek().kind == "RP":
                            self.next()
                    out.append(Attr(name, args))
                else:
                    self.next()
            if self.peek().kind == "RBK": self.next()
        return out

    def parse(self) -> A.Programa:
        p = A.Programa()
        try:
            if self.peek().kind == "MODULE":
                self.next()
                # suporte a `module a.b.c`
                mod_path = self.eat_ident().val
                while self.accept("DOT"):
                    mod_path += "." + self.eat_ident().val
                p.mod = mod_path
                self.accept("SEMI")
            while self.peek().kind == "IMPORT":
                self.next()
                path = self.eat_ident().val
                while self.accept("DOT"): path += "." + self.eat_ident().val
                p.imports.append(A.Import(self.sp(), path))
                self.accept("SEMI")
            while self.peek().kind == "USE":
                self.next()
                path = self.eat_ident().val
                while self.accept("COLON2"): path += "::" + self.eat_ident().val
                while self.accept("DOT"): path += "." + self.eat_ident().val
                p.imports.append(A.Import(self.sp(), path))
                self.accept("SEMI")
            while self.peek().kind != "EOF":
                if self.peek().kind in ("DOC", "SEMI", "RB"):
                    self.next(); continue
                try:
                    if self.peek().kind in ("USE", "IMPORT"):
                        self.next()
                        path = self.eat_ident().val
                        while True:
                            if self.accept("COLON2"): path += "::" + self.eat_ident().val
                            elif self.accept("DOT"): path += "." + self.eat_ident().val
                            else: break
                        p.imports.append(A.Import(self.sp(), path))
                        self.accept("SEMI"); continue
                    a = self.attrs()
                    if self.peek().kind == "EOF": break
                    it = self.item()
                    # atribui attrs ao nó (para retenção de args)
                    try:
                        if hasattr(it, "attrs"):
                            it.attrs = list(a)
                    except: pass
                    if "test" in a and type(it).__name__ == "Fn":
                        it.test = True
                        # coleta args do atributo test
                        for attr in a:
                            if isinstance(attr, Attr) and str(attr) == "test":
                                it.test_args = list(getattr(attr, "args", []))
                            elif isinstance(attr, str) and attr == "test":
                                it.test_args = []
                    p.itens.append(it)
                except ParseError as e:
                    self.errs.append(str(e) + " — trecho ignorado até ';', '}' ou próximo item")
                    self.sync()
                    p.itens.append(A.ErrorNode(self.sp(), str(e)))
        except ParseError as e:
            self.errs.append(str(e))
        return p

    def item(self):
        pub = self.accept("PUB") is not None
        k = self.peek().kind
        if k == "FN": return self.fn(pub)
        if k == "ASYNC":
            self.next()
            f = self.fn(pub); f.async_ = True; return f
        if k == "STRUCT": return self.struct(pub)
        if k == "ENUM": return self.enum(pub)
        if k == "TRAIT" or (k == "IDENT" and self.peek().val == "trait"):
            return self.trait(pub)
        if k == "IMPL" or (k == "IDENT" and self.peek().val == "impl"):
            return self.impl(pub)
        if k == "MACRO":
            return self.macro(pub)
        if k == "CONST":
            return self.const(pub)
        raise ParseError("esperado fn/struct/enum", self.peek())

    def trait(self, pub):
        # v0.2: retém assinaturas exigidas `fn nome(params) -> ret;`.
        self.next(); nm = self.eat_ident().val
        self.eat("LB"); req = []
        while self.peek().kind not in ("RB", "EOF"):
            if self.peek().kind in ("DOC", "SEMI"):
                self.next(); continue
            if self.peek().kind == "FN":
                self.next(); mn = self.eat_ident().val
                if self.accept("LT"):  # genéricos: ignora conteúdo
                    depth = 1
                    while depth and self.peek().kind != "EOF":
                        x = self.next()
                        if x.kind == "LT": depth += 1
                        elif x.kind == "GT": depth -= 1
                pars = []
                if self.accept("LP"):
                    while self.peek().kind not in ("RP", "EOF"):
                        if self.peek().kind == "MUT":
                            self.next()
                        if not self._peek_is_ident():
                            self.next(); continue
                        pn = self.next().val; pt = "?"
                        if self.accept("COLON"):
                            pt = self.tipo()
                        pars.append((pn, pt))
                        if not self.accept("COMMA"):
                            break
                    self.accept("RP")
                rt = "?"
                if self.accept("ARROW"):
                    rt = self.tipo()
                if self.accept("LB"):  # corpo default: pula bloco
                    depth = 1
                    while depth and self.peek().kind != "EOF":
                        x = self.next()
                        if x.kind == "LB": depth += 1
                        elif x.kind == "RB": depth -= 1
                else:
                    self.accept("SEMI")
                req.append((mn, len(pars), rt))
            else:
                self.next()
        self.eat("RB")
        st = A.Struct(self.sp(), "trait:" + nm, [])
        st.required = req
        return st

    def impl(self, pub):
        self.next(); tn = self.eat_ident().val
        self.eat("LB"); fns = []
        while self.peek().kind != "RB":
            if self.peek().kind in ("DOC", "SEMI"): self.next(); continue
            a = self.attrs()
            if self.peek().kind in ("PUB", "FN", "ASYNC"):
                f = self.item()
                if type(f).__name__ == "Fn":
                    f.name = tn + "::" + f.name; fns.append(f)
            else: self.next()
        self.eat("RB")
        st = A.Struct(self.sp(), "impl:" + tn, [])
        st.methods = fns
        return st

    def const(self, pub):
        self.eat("CONST"); nm = self.eat_ident().val; tp = ""
        if self.accept("COLON"): tp = self.tipo()
        self.eat("EQ"); e = self.expr(); self.accept("SEMI")
        return A.Let(self.sp(), nm, tp, e, False)

    def macro(self, pub):
        self.eat("MACRO"); nm = self.eat_ident().val
        self.accept("BANG")
        self.eat("LP"); params = []
        while self.peek().kind != "RP":
            params.append((self.eat_ident().val, ""))
            if not self.accept("COMMA"): break
        self.eat("RP")
        self.eat("LB"); body = self.bloco(); self.eat("RB")
        f = A.Fn(self.sp(), nm + "!", params, "", body, pub)
        # armazena para higiene fase-1
        self.macros[nm + "!"] = f
        return f

    def tipo(self):
        if self.peek().kind == "MUT":
            self.next()
        if self.peek().kind == "LB":
            # v0.2: tipo registro `{f1: t1, f2: t2}` (base da subtipagem).
            self.next(); fs = []
            while self.peek().kind not in ("RB", "EOF"):
                fn2 = self.eat_ident().val
                self.eat("COLON")
                fs.append(f"{fn2}: {self.tipo()}")
                if not self.accept("COMMA"):
                    break
            self.eat("RB")
            return "{" + ", ".join(fs) + "}"
        # tipo pode ser keyword promovida usada como nome? ex.: Self
        t = self.next().val
        while self.accept("COLON2"):
            t += "::" + self.eat_ident().val
        if self.accept("LT"):
            depth = 1
            t += "<"
            while depth and self.peek().kind != "EOF":
                x = self.next()
                if x.kind == "LT": depth += 1
                elif x.kind == "GT": depth -= 1
                t += x.val
            t = t.replace(" ", "")
        return t

    def fn(self, pub):
        self.eat("FN"); nm = self.eat_ident().val
        bounds = []
        if self.accept("LT"):
            # v0.2: retém bounds genéricos `T` ou `T: TraitA + TraitB`.
            cur, cur_bounds, cur_t = "", [], ""
            depth = 1
            while depth and self.peek().kind != "EOF":
                x = self.next()
                if x.kind == "LT":
                    depth += 1; cur_t += x.val; continue
                if x.kind == "GT":
                    depth -= 1
                    if depth == 0:
                        break
                    cur_t += x.val; continue
                if depth == 1 and x.kind == "COMMA":
                    if cur_t.strip():
                        bounds.append(self._bound(cur_t))
                    cur_t = ""
                else:
                    cur_t += x.val
            if cur_t.strip():
                bounds.append(self._bound(cur_t))
        self.eat("LP"); params = []
        while self.peek().kind != "RP":
            if self.peek().kind == "MUT": self.next()
            # param pode ser `self`, `&self`, `&mut self`, `Self`
            # Trata casos com & ou Self
            # Se for `self`/`Self` sem tipo, aceita direto, mas se tiver COLON trata como ident comum
            if self.peek().kind in ("SELF", "SELF_TYPE"):
                # lookahead para `self: tipo` (uso como ident comum)
                nxt = self.t[self.i+1] if self.i+1 < len(self.t) else None
                if nxt is not None and nxt.kind == "COLON":
                    pn = self.next().val
                    pt = "int"
                    if self.accept("COLON"): pt = self.tipo()
                    params.append((pn, pt))
                    if not self.accept("COMMA"): break
                    continue
                pn = self.next().val
                # tipo do self é Self/self
                pt = pn
                params.append((pn, pt))
                if not self.accept("COMMA"): break
                continue
            if self.peek().kind == "AMP":
                # pode ser &self ou &mut self
                # consome & e verifica se próximo é self
                self.next()
                if self.peek().kind == "MUT":
                    self.next()
                    if self.peek().kind in ("SELF", "SELF_TYPE"):
                        pn = self.next().val
                        params.append((pn, "&mut Self"))
                        if not self.accept("COMMA"): break
                        continue
                    else:
                        # fallback: &mut T
                        # já consumimos &mut, espera ident
                        if self._peek_is_ident():
                            pn = self.next().val
                            pt = "?"
                            if self.accept("COLON"): pt = self.tipo()
                            params.append((pn, pt))
                            if not self.accept("COMMA"): break
                            continue
                else:
                    if self.peek().kind in ("SELF", "SELF_TYPE"):
                        pn = self.next().val
                        params.append((pn, "&Self"))
                        if not self.accept("COMMA"): break
                        continue
                    else:
                        if self._peek_is_ident():
                            pn = self.next().val
                            pt = "?"
                            if self.accept("COLON"): pt = self.tipo()
                            params.append((pn, pt))
                            if not self.accept("COMMA"): break
                            continue
            pn = self.eat_ident().val; pt = "int"
            if self.accept("COLON"): pt = self.tipo()
            params.append((pn, pt))
            if not self.accept("COMMA"): break
        self.eat("RP"); ret = "int"
        if self.accept("ARROW"): ret = self.tipo()
        self.eat("LB"); body = self.bloco()
        self.eat("RB")
        fn = A.Fn(self.sp(), nm, params, ret, body, pub)
        fn.bounds = bounds
        return fn

    def _bound(self, txt):
        """`T` ou `T: A + B` -> (T, [bounds])."""
        txt = txt.strip()
        if ":" not in txt:
            return (txt, [])
        t, _, bs = txt.partition(":")
        return (t.strip(), [b.strip() for b in bs.replace("+", " ").split()
                            if b.strip()])

    def struct(self, pub):
        self.eat("STRUCT"); nm = self.eat_ident().val
        self.eat("LB"); fs = []
        while self.peek().kind != "RB":
            fn2 = self.eat_ident().val; self.eat("COLON")
            ft = self.next().val; fs.append((fn2, ft))
            self.accept("COMMA"); self.accept("SEMI")
        self.eat("RB"); return A.Struct(self.sp(), nm, fs)

    def enum(self, pub):
        self.eat("ENUM"); nm = self.eat_ident().val
        self.eat("LB"); vs = []
        while self.peek().kind != "RB":
            vs.append(self.eat_ident().val)
            if self.accept("LP"):
                while self.peek().kind != "RP": self.next()
                self.eat("RP")
            self.accept("COMMA")
        self.eat("RB"); return A.Enum(self.sp(), nm, vs)

    def bloco(self):
        out = []
        while self.peek().kind not in ("RB","EOF"):
            if self.peek().kind in ("DOC", "SEMI"):
                self.next(); continue
            if self.peek().kind == "HASH":
                self.attrs(); continue
            try: out.append(self.stmt())
            except ParseError as e:
                self.errs.append(str(e) + " — stmt ignorado até ';' ou '}'")
                self.sync(); out.append(A.ErrorNode(self.sp(), str(e)))
        return out

    def stmt(self):
        k = self.peek().kind
        if k == "LET": return self.let()
        if k == "IF": return self.if_()
        if k == "MATCH": return self.match()
        if k == "FOR": return self.for_()
        if k == "WHILE": return self.while_()
        if k == "RETURN":
            self.next(); e = None
            if self.peek().kind not in ("SEMI","RB"): e = self.expr()
            self.accept("SEMI"); return A.Return(self.sp(), e)
        if self._peek_is_ident() and self.i+1 < len(self.t) and self.t[self.i+1].kind in ("EQ","PLUSEQ","MINUSEQ","MULEQ","DIVEQ"):
            nm = self.next().val; op = self.next().val
            e = self.expr(); self.accept("SEMI")
            return A.BinOp(self.sp(), op, A.Lit(self.sp(),"id",nm), e)
        e = self.expr()
        if self.peek().kind in ("EQ","PLUSEQ","MINUSEQ","MULEQ","DIVEQ"):
            op = self.next().val; r = self.expr()
            self.accept("SEMI")
            return A.BinOp(self.sp(), op, e, r)
        self.accept("SEMI"); return e

    def let(self):
        self.eat("LET"); mut_ = self.accept("MUT") is not None
        nm = self.eat_ident().val; tp = ""
        if self.accept("COLON"): tp = self.tipo()
        self.eat("EQ"); e = self.expr(); self.accept("SEMI")
        return A.Let(self.sp(), nm, tp, e, mut_)

    def if_(self):
        self.eat("IF"); c = self.expr(); self.eat("LB"); t = self.bloco(); self.eat("RB")
        el = []
        if self.accept("ELSE"):
            if self.peek().kind == "IF": el = [self.if_()]
            else: self.eat("LB"); el = self.bloco(); self.eat("RB")
        return A.If(self.sp(), c, t, el)

    def padrao(self):
        if self.peek().kind in ("INT","STRING","UNDER"):
            return self.next().val
        if self._peek_is_ident():
            p = self.next().val
            while self.accept("COLON2"): p += "::" + self.eat_ident().val
            if self.accept("LP"):
                inner = []
                while self.peek().kind != "RP":
                    inner.append(self.padrao_atom())
                    if not self.accept("COMMA"): break
                self.eat("RP")
                p += "(" + ",".join(inner) + ")"
            return p
        raise ParseError("padrão inválido", self.peek())

    def padrao_atom(self):
        if self.peek().kind in ("INT","STRING","UNDER") or self._peek_is_ident():
            return self.next().val
        raise ParseError("padrão inválido", self.peek())

    def match(self):
        self.eat("MATCH"); a = self.expr(); self.eat("LB"); bs = []
        while self.peek().kind != "RB":
            pat = self.padrao()
            while self.accept("PIPE"):
                pat += "|" + self.padrao()
            gd = None
            if self.peek().kind == "IF":
                self.next(); gd = self.expr()
            self.eat("FATARROW")
            if self.peek().kind == "RETURN":
                self.next()
                e = None
                if self.peek().kind not in ("COMMA", "RB"):
                    e = self.expr()
            else:
                e = self.expr()
            self.accept("COMMA"); bs.append(A.MatchBraco(self.sp(), pat, e, gd))
        self.eat("RB"); return A.Match(self.sp(), a, bs)

    def for_(self):
        self.eat("FOR"); v = self.eat_ident().val
        self.eat("IN"); it = self.expr()
        self.eat("LB"); b = self.bloco(); self.eat("RB")
        return A.For(self.sp(), v, it, b)

    def while_(self):
        self.eat("WHILE"); c = self.expr()
        self.eat("LB"); b = self.bloco(); self.eat("RB")
        return A.While(self.sp(), c, b)

    def if_expr(self):
        c = self.expr(); self.eat("LB"); t = self.bloco(); self.eat("RB")
        el = []
        if self.accept("ELSE"):
            if self.peek().kind == "IF": self.next(); el = [self.if_expr()]
            else: self.eat("LB"); el = self.bloco(); self.eat("RB")
        return A.If(self.sp(), c, t, el)

    def expr(self, prec=0):
        precs = {"||":1,"&&":2,"==":3,"!=":3,"<":4,">":4,"<=":4,">=":4,"+":5,"-":5,"*":6,"/":6,"%":6}
        l = self.un()
        if self.peek().kind == "DOT2":
            self.next(); r = self.expr(7)
            return A.BinOp(self.sp(), "..", l, r)
        while self.peek().val in precs and precs[self.peek().val] > prec:
            op = self.next().val
            r = self.expr(precs[op])
            l = A.BinOp(self.sp(), op, l, r)
        return l

    def un(self):
        if self.peek().kind in ("MINUS","BANG"):
            op = self.next().val; return A.UnOp(self.sp(), op, self.un())
        if self.peek().kind == "AMP":
            self.next()
            if self.peek().kind == "MUT":
                self.next()
                return A.UnOp(self.sp(), "&mut", self.un())
            return A.UnOp(self.sp(), "&", self.un())
        if self.peek().kind == "STAR":
            self.next(); return A.UnOp(self.sp(), "*", self.un())
        if self.peek().kind == "AWAIT":
            self.next(); return A.UnOp(self.sp(), "await", self.un())
        if self.peek().kind == "SPAWN":
            self.next(); return A.Call(self.sp(), "spawn", [self.un()])
        e = self.prim()
        while self.accept("QMARK"):
            e = A.UnOp(self.sp(), "?", e)
        if self.peek().kind == "AS":
            self.next(); self.tipo()
            e = A.UnOp(self.sp(), "as", e)
        return e

    def _pct(self, fn, args):
        node = A.Call(self.sp(), fn, args)
        while self.accept("DOT"):
            part = self.eat_ident().val
            if self.accept("LP"):
                nargs = []
                while self.peek().kind != "RP":
                    nargs.append(self.expr())
                    if not self.accept("COMMA"): break
                self.eat("RP")
                if type(node).__name__ == "Call" and isinstance(node.fn, str) and "." not in node.fn and node.fn == fn:
                    node = A.Call(self.sp(), node.fn + "." + part, nargs)
                else:
                    node = A.Call(self.sp(), "metodo", [node] + nargs)
            else:
                node = A.Field(self.sp(), node, part)
        return node

    def prim(self):
        t = self.peek()
        if t.kind == "MATCH":
            return self.match()
        if t.kind == "IF":
            self.next(); return self.if_expr()
        if t.kind == "INT":
            self.next()
            suf = getattr(t, "suffix", "")
            return A.Lit(self.sp(),"int",int(t.val), suffix=suf, raw=False)
        if t.kind == "FLOAT":
            self.next()
            suf = getattr(t, "suffix", "")
            return A.Lit(self.sp(),"float",float(t.val), suffix=suf, raw=False)
        if t.kind == "STRING":
            self.next()
            raw = getattr(t, "raw", False)
            suf = getattr(t, "suffix", "")
            return A.Lit(self.sp(),"str",t.val, suffix=suf, raw=raw)
        if t.kind in ("TRUE","FALSE"): self.next(); return A.Lit(self.sp(),"bool",t.kind=="TRUE")
        if t.kind in self.IDENT_LIKE:
            self.next(); nm = t.val
            while self.accept("COLON2"):
                nm += "::" + self.eat_ident().val
            if self.accept("BANG"):
                # macro invocation: parse args conforme delimitador
                if self.peek().kind == "LBK":
                    self.next()
                    elems = []
                    while self.peek().kind != "RBK":
                        elems.append(self.expr())
                        if not self.accept("COMMA"): break
                    self.eat("RBK")
                    # tenta higiene se for macro de usuário (não vec!/map! builtin)
                    macro_key = nm + "!"
                    if macro_key in self.macros and nm not in ("vec","map","set"):
                        try:
                            from compiler.frontend.higiene import higienizar
                            exp = higienizar(self.macros[macro_key], elems)
                            if exp is not None:
                                return exp
                        except Exception:
                            pass
                    return self._pct(nm + "!", elems)
                if self.peek().kind == "LB":
                    self.next(); depth = 1
                    while depth and self.peek().kind != "EOF":
                        x = self.next()
                        if x.kind == "LB": depth += 1
                        elif x.kind == "RB": depth -= 1
                    # para braced macro, tenta higiene com args vazios
                    macro_key = nm + "!"
                    if macro_key in self.macros:
                        try:
                            from compiler.frontend.higiene import higienizar
                            exp = higienizar(self.macros[macro_key], [])
                            if exp is not None:
                                return exp
                        except Exception:
                            pass
                    return A.Call(self.sp(), nm + "!", [])
                self.eat("LP")
                args = []
                while self.peek().kind != "RP":
                    args.append(self.expr())
                    if not self.accept("COMMA"): break
                self.eat("RP")
                macro_key = nm + "!"
                if macro_key in self.macros and nm not in ("vec","map","set"):
                    try:
                        from compiler.frontend.higiene import higienizar
                        exp = higienizar(self.macros[macro_key], args)
                        if exp is not None:
                            return exp
                    except Exception:
                        pass
                return self._pct(nm + "!", args)
            if self.accept("LBK"):
                elems = []
                while self.peek().kind != "RBK":
                    elems.append(self.expr())
                    if not self.accept("COMMA"): break
                self.eat("RBK"); return self._pct(nm, elems)
            if self.accept("LP"):
                args = []
                while self.peek().kind != "RP":
                    args.append(self.expr())
                    if not self.accept("COMMA"): break
                self.eat("RP"); return self._pct(nm, args)
            base = A.Lit(self.sp(),"id",nm)
            while self.accept("DOT"):
                part = self.eat_ident().val
                if type(base).__name__ == "Lit" and isinstance(base.val, str):
                    base = A.Lit(self.sp(), "id", base.val + "." + part)
                else:
                    base = A.Field(self.sp(), base, part)
            if self.peek().kind == "LP" and type(base).__name__ == "Lit" and isinstance(base.val, str) and "." in base.val:
                self.next()
                args = []
                while self.peek().kind != "RP":
                    args.append(self.expr())
                    if not self.accept("COMMA"): break
                self.eat("RP")
                return self._pct(base.val, args)
            if self.peek().kind == "LB" and type(base).__name__ == "Lit" and isinstance(base.val, str) and "." not in base.val and "::" not in base.val:
                la = self.t[self.i+1] if self.i+1 < len(self.t) else None
                lb = self.t[self.i+2] if self.i+2 < len(self.t) else None
                is_lit = (la is not None and la.kind == "RB") or (
                    la is not None and lb is not None and la.kind in self.IDENT_LIKE and lb.kind == "COLON")
                if is_lit:
                    self.next()
                    inits = []
                    while self.peek().kind != "RB":
                        self.eat_ident(); self.eat("COLON")
                        inits.append(self.expr())
                        if not self.accept("COMMA"): break
                    self.eat("RB")
                    return self._pct(nm, inits)
            # path qualificado nu (ex.: Estado::Novo): mantém o Lit como está
            return base
        if t.kind == "LP":
            self.next()
            if self.peek().kind == "RP":
                self.next(); return A.Lit(self.sp(), "unit", None)
            e = self.expr(); self.eat("RP"); return e
        if t.kind == "LB":
            self.next()
            out = []
            while self.peek().kind not in ("RB", "EOF"):
                if self.peek().kind in ("DOC", "SEMI"):
                    self.next(); continue
                if self.peek().kind == "HASH":
                    self.attrs(); continue
                try: out.append(self.stmt())
                except ParseError as e: self.errs.append(str(e)); self.sync()
            self.eat("RB")
            return A.Block(self.sp(), out)
        raise ParseError("expressão inválida", t)

def parse(toks) -> A.Programa:
    p = Parser(toks); return p.parse()
