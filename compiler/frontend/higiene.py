"""Higiene fase-1 para macros Lumen.

Renomeação gensym dos bindings introduzidos pela macro para não capturar
(nem ser capturados por) variáveis do chamador. `vec!`/`map!` são builtins
e continuam funcionando sem higiene.

Implementação:
- coletar bindings introduzidos (let, for) no corpo da macro
- gerar nomes frescos via contador global
- substituir ocorrências no corpo
- substituir parâmetros pelos argumentos da chamada
"""
from __future__ import annotations
import copy

_counter = 0

def gensym(name: str) -> str:
    global _counter
    _counter += 1
    return f"{name}__hyg{_counter}"

def reset_counter():
    global _counter
    _counter = 0

def _collect_bindings(stmts, out=None):
    """Coleta nomes de bindings introduzidos no corpo da macro."""
    from compiler.frontend import ast_nodes as A
    if out is None:
        out = set()
    for st in stmts or []:
        if isinstance(st, A.Let):
            out.add(st.name)
            # também coleta dentro da expr? expr pode conter blocos que introduzem bindings
            # mas não considerado como binding da macro, só o let em si
        elif isinstance(st, A.For):
            out.add(st.var)
            _collect_bindings(getattr(st, "body", []), out)
        elif isinstance(st, A.Block):
            _collect_bindings(getattr(st, "stmts", []), out)
        elif isinstance(st, A.If):
            _collect_bindings(getattr(st, "then", []), out)
            _collect_bindings(getattr(st, "els", []), out)
        elif isinstance(st, A.While):
            _collect_bindings(getattr(st, "body", []), out)
        elif isinstance(st, A.Match):
            # pattern bindings como Ok(v) -> v
            for b in getattr(st, "bracos", []):
                pat = getattr(b, "pat", "")
                # extrai bindings de padrão: heurística simples
                # ex.: "Ok(v)" -> v ; "Forma::C(r)" -> r ; "x|y" -> x,y
                for alt in str(pat).split("|"):
                    a = alt.strip()
                    if "(" in a and a.endswith(")"):
                        inner = a[a.find("(")+1:a.rfind(")")]
                        for x in inner.split(","):
                            x = x.strip()
                            if x and x != "_" and x[:1].islower() and x.isidentifier():
                                out.add(x)
                    elif a and a.isidentifier() and (a[0].islower() or a[0]=="_") and a not in ("true","false","_"):
                        # padrão simples é binding? Ex.: "v" em match arm "v => ..."
                        # Conservador: não adiciona se for variável de topo já existente?
                        # Para higiene, consideramos que padrão introduz binding se não for constante.
                        # Heurística: se arm tem padrão simples e é minúsculo, é binding.
                        # Evita falsos positivos: só se pat for identificador único e não for literal numérico
                        if a not in ("_",):
                            # só adiciona se não for variante maiúscula (ex.: Ok)
                            if a[0].islower():
                                out.add(a)
                # expr do braço pode conter blocos
                body = getattr(b, "expr", None)
                if isinstance(body, A.Block):
                    _collect_bindings(body.stmts, out)
                elif isinstance(body, list):
                    _collect_bindings(body, out)
        # BinOp, Call, etc não introduzem bindings
    return out

def _clone_subst(node, param_map, gensym_map):
    """Clona node substituindo params e gensym."""
    from compiler.frontend import ast_nodes as A
    from compiler.frontend.ast_nodes import Span
    if node is None:
        return None
    # Lit id -> substituição
    if isinstance(node, A.Lit) and getattr(node, "kind", "") == "id":
        v = str(node.val)
        # correspondência exata de param
        if v in param_map:
            # deep copy do arg
            return copy.deepcopy(param_map[v])
        # caso path com :: ou . contendo param? Trata base simples
        # Se v contém "." ou "::", verifica base
        # Simplifica: se v == param, já tratado; se v contém ponto, trata parte inicial?
        # Para higiene fase-1, basta exato.
        if v in gensym_map:
            # cria novo Lit com nome gensym
            return A.Lit(node.span, "id", gensym_map[v], getattr(node, "suffix", ""), getattr(node, "raw", False))
        # também trata vals pontilhados: "x.y" onde x é binding
        if "." in v:
            base, rest = v.split(".", 1)
            if base in param_map:
                # param não pode ser base de field? se param é expressão, não deveria ter field.
                # ignora
                pass
            elif base in gensym_map:
                return A.Lit(node.span, "id", gensym_map[base] + "." + rest, getattr(node, "suffix", ""), getattr(node, "raw", False))
        return copy.deepcopy(node)
    if isinstance(node, A.Let):
        new_name = gensym_map.get(node.name, node.name)
        new_expr = _clone_subst(node.expr, param_map, gensym_map) if node.expr is not None else None
        return A.Let(node.span, new_name, node.typ, new_expr, node.mut_)
    if isinstance(node, A.For):
        new_var = gensym_map.get(node.var, node.var)
        new_iter = _clone_subst(node.iter, param_map, gensym_map)
        new_body = [_clone_subst(s, param_map, gensym_map) for s in (node.body or [])]
        return A.For(node.span, new_var, new_iter, new_body)
    if isinstance(node, A.BinOp):
        return A.BinOp(node.span, node.op, _clone_subst(node.l, param_map, gensym_map), _clone_subst(node.r, param_map, gensym_map))
    if isinstance(node, A.UnOp):
        return A.UnOp(node.span, node.op, _clone_subst(node.e, param_map, gensym_map))
    if isinstance(node, A.Call):
        # fn é string, não substitui (mas se fn == param? raro)
        fn = node.fn
        if fn in param_map:
            # param como função? não esperado
            pass
        if fn in gensym_map:
            fn = gensym_map[fn]
        new_args = [_clone_subst(a, param_map, gensym_map) for a in (node.args or [])]
        return A.Call(node.span, fn, new_args)
    if isinstance(node, A.Field):
        new_base = _clone_subst(node.base, param_map, gensym_map)
        new_name = gensym_map.get(node.name, node.name)
        return A.Field(node.span, new_base, new_name)
    if isinstance(node, A.If):
        return A.If(node.span, _clone_subst(node.cond, param_map, gensym_map),
                    [_clone_subst(s, param_map, gensym_map) for s in (node.then or [])],
                    [_clone_subst(s, param_map, gensym_map) for s in (node.els or [])])
    if isinstance(node, A.While):
        return A.While(node.span, _clone_subst(node.cond, param_map, gensym_map),
                       [_clone_subst(s, param_map, gensym_map) for s in (node.body or [])])
    if isinstance(node, A.Match):
        new_alvo = _clone_subst(node.alvo, param_map, gensym_map)
        new_bracos = []
        for b in (node.bracos or []):
            # pat é string, precisa renomear bindings dentro do pat se houver gensym?
            pat = b.pat
            # renomeia ocorrências de bindings no pat string: simples replace de palavra isolada
            if isinstance(pat, str) and gensym_map:
                # substitui cada binding por gensym no texto do pat
                # usa replace com cuidado de boundaries
                import re
                for old, new in gensym_map.items():
                    # só substitui ocorrências como palavra completa
                    pat = re.sub(r'\b' + re.escape(old) + r'\b', new, pat)
                # também substitui param? param em padrão não faz sentido
            new_guard = _clone_subst(getattr(b, "guard", None), param_map, gensym_map)
            # b.expr pode ser Block, expr, Return, etc
            expr = b.expr
            if isinstance(expr, A.Block):
                new_expr = A.Block(expr.span, [_clone_subst(s, param_map, gensym_map) for s in expr.stmts])
            elif isinstance(expr, list):
                new_expr = [_clone_subst(s, param_map, gensym_map) for s in expr]
            else:
                new_expr = _clone_subst(expr, param_map, gensym_map)
            new_bracos.append(A.MatchBraco(b.span, pat, new_expr, new_guard))
        return A.Match(node.span, new_alvo, new_bracos)
    if isinstance(node, A.Block):
        return A.Block(node.span, [_clone_subst(s, param_map, gensym_map) for s in (node.stmts or [])])
    if isinstance(node, A.Return):
        return A.Return(node.span, _clone_subst(node.expr, param_map, gensym_map))
    if isinstance(node, A.Lit):
        # outros Lit (int, str etc) não precisam
        return copy.deepcopy(node)
    # Fallback: deepcopy
    return copy.deepcopy(node)

def higienizar(macro_fn, args):
    """Retorna bloco higienizado para a expansão da macro.

    macro_fn: Fn nó com nome terminado em "!" e corpo list[stmt]
    args: lista de expr nós correspondendo aos params
    """
    from compiler.frontend import ast_nodes as A
    from compiler.frontend.ast_nodes import Span
    # builtins vec!/map! não higienizam — se caller passar macro builtin, não deve chamar
    name = getattr(macro_fn, "name", "")
    if name in ("vec!", "map!", "set!"):
        # não higieniza builtins
        return None
    param_names = [p[0] for p in (getattr(macro_fn, "params", []) or [])]
    param_map = {}
    for pn, arg in zip(param_names, args or []):
        param_map[pn] = arg
    # coleta bindings
    bindings = _collect_bindings(getattr(macro_fn, "body", []))
    # remove params da lista de bindings (param não deve ser gensymed)
    bindings = {b for b in bindings if b not in param_map}
    gensym_map = {b: gensym(b) for b in bindings}
    # clona corpo
    new_stmts = []
    for st in (getattr(macro_fn, "body", []) or []):
        new_stmts.append(_clone_subst(st, param_map, gensym_map))
    if not new_stmts:
        return A.Block(Span(0,0), [])
    # Se corpo tem único statement que é expr pura, pode retornar o expr?
    # Mas para higiene, retornamos sempre Block para preservar escopo dos let gensymed
    # O chamador que esperava expr receberá Block, que é válido como expr de bloco
    return A.Block(Span(0,0), new_stmts)

def expandir(parser, nome, args):
    """Hook usado pelo parser: tenta expandir macro nome com args."""
    macro_fn = getattr(parser, "macros", {}).get(nome)
    if macro_fn is None:
        return None
    return higienizar(macro_fn, args)
