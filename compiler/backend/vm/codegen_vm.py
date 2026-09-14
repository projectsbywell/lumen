"""Gerador IR -> bytecode executável (formato dict da runtime/vm.py).

Formato de saída:
    {"entry": "main",
     "functions": {nome: {"bytecodes": [[op, arg], ...],
                           "consts": [...],
                           "locals": [params..., ...],
                           "arity": N}}}
Cada função carrega nas consts os metadados __func__ de todas as
funções (é assim que a VM resolve CALL).

Contrato P5.2 async (escolha documentada):
 - AST já possui nós para `spawn` (Call fn="spawn") / `await` (UnOp op="await")
   e `async fn` (Fn.async_=True). O Baixador atual ainda baixa `await`
   como `copy` e `spawn` como `call spawn`, portanto o codegen precisa
   reconhecer AMBOS os padrões para ser mínimo viável:
   * (a) IR direto futuro: op == "spawn" -> SPAWN, op in ("await","await_fut") -> AWAIT_FUT,
     op == "await_ch" -> AWAIT_CH, op == "yield" -> YIELD
   * (b) compat IR atual: op == "call" com args[0] == "spawn" -> SPAWN,
     args[0] in ("await","await_fut") -> AWAIT_FUT,
     args[0] == "await_ch" -> AWAIT_CH
   O teste e2e usa (a) via ModuloIR manual com const Future pronta + SPAWN
   literal "worker", que é o caminho mínimo que valida VM round-robin e
   contrato (SPAWN nome com metadata __func__, AWAIT_* com topo stack).
   `async fn` não exige opcode próprio: é função normal chamável via SPAWN.
"""
from __future__ import annotations

_OPS_BIN = {"add": "ADD", "sub": "SUB", "mul": "MUL", "div": "DIV",
            "mod": "MOD", "eq": "EQ", "neq": "NEQ", "lt": "LT",
            "gt": "GT", "le": "LE", "ge": "GE"}


def gerar_dict(mod_ir, entry: str = "main") -> dict:
    funcs: dict[str, dict] = {}
    for f in mod_ir.funcoes:
        consts: list = []
        seen: dict = {}

        def C(v):
            key = ("c", type(v).__name__, str(v))
            if key in seen:
                return seen[key]
            consts.append(v)
            seen[key] = len(consts) - 1
            return seen[key]

        raw: list = []  # (op, arg) com arg de jump ainda simbólico
        stored: list[str] = []
        for bl in f.blocos:
            for i in bl.instrs:
                op = i.op
                if op == "label":
                    raw.append(("LABEL", i.args[0]))
                elif op == "const":
                    raw.append(("CONST", C(i.val)))
                    raw.append(("STORE", i.dst))
                    stored.append(i.dst)
                elif op == "copy":
                    raw.append(("LOAD", i.args[0]))
                    raw.append(("STORE", i.dst))
                    stored.append(i.dst)
                elif op in _OPS_BIN:
                    raw.append(("LOAD", i.args[0]))
                    raw.append(("LOAD", i.args[1]))
                    raw.append((_OPS_BIN[op], None))
                    raw.append(("STORE", i.dst))
                    stored.append(i.dst)
                elif op == "not":
                    raw.append(("LOAD", i.args[0]))
                    raw.append(("NOT", None))
                    raw.append(("STORE", i.dst))
                    stored.append(i.dst)
                elif op == "is_ok":
                    raw.append(("LOAD", i.args[0] if i.args else None))
                    raw.append(("IS_OK", None))
                    raw.append(("STORE", i.dst))
                    stored.append(i.dst)
                elif op == "unwrap":
                    raw.append(("LOAD", i.args[0] if i.args else None))
                    raw.append(("UNWRAP", None))
                    raw.append(("STORE", i.dst))
                    stored.append(i.dst)
                # --- async P5.2 (mínimo viável) ---
                elif op == "spawn":
                    func = i.args[0] if i.args else ""
                    # args extras (se houver) são valores reais a empilhar antes do SPAWN
                    for a in i.args[1:]:
                        raw.append(("LOAD", a))
                    raw.append(("SPAWN", func))
                    if i.dst:
                        raw.append(("CONST", C(0)))
                        raw.append(("STORE", i.dst))
                        stored.append(i.dst)
                elif op in ("await", "await_fut", "await_FUT", "AWAIT_FUT"):
                    src = i.args[0] if i.args else None
                    if src is not None:
                        raw.append(("LOAD", src))
                    raw.append(("AWAIT_FUT", None))
                    if i.dst:
                        raw.append(("STORE", i.dst))
                        stored.append(i.dst)
                elif op in ("await_ch", "AWAIT_CH"):
                    src = i.args[0] if i.args else None
                    if src is not None:
                        raw.append(("LOAD", src))
                    raw.append(("AWAIT_CH", None))
                    if i.dst:
                        raw.append(("STORE", i.dst))
                        stored.append(i.dst)
                elif op in ("yield", "YIELD"):
                    raw.append(("YIELD", None))
                    if i.dst:
                        raw.append(("CONST", C(0)))
                        raw.append(("STORE", i.dst))
                        stored.append(i.dst)
                elif op == "call":
                    tgt = i.args[0] if i.args else ""
                    if tgt == "spawn":
                        func = i.args[1] if len(i.args) > 1 else ""
                        extra = i.args[2:] if len(i.args) > 2 else []
                        for a in extra:
                            raw.append(("LOAD", a))
                        raw.append(("SPAWN", func))
                        if i.dst:
                            raw.append(("CONST", C(0)))
                            raw.append(("STORE", i.dst))
                            stored.append(i.dst)
                    elif tgt in ("await", "await_fut", "AWAIT_FUT"):
                        src = i.args[1] if len(i.args) > 1 else None
                        if src is not None:
                            raw.append(("LOAD", src))
                        raw.append(("AWAIT_FUT", None))
                        if i.dst:
                            raw.append(("STORE", i.dst))
                            stored.append(i.dst)
                    elif tgt in ("await_ch", "AWAIT_CH"):
                        src = i.args[1] if len(i.args) > 1 else None
                        if src is not None:
                            raw.append(("LOAD", src))
                        raw.append(("AWAIT_CH", None))
                        if i.dst:
                            raw.append(("STORE", i.dst))
                            stored.append(i.dst)
                    else:
                        for a in i.args[1:]:
                            raw.append(("LOAD", a))
                        raw.append(("CALL", i.args[0]))
                        raw.append(("STORE", i.dst))
                        stored.append(i.dst)
                elif op == "print":
                    raw.append(("LOAD", i.args[0]))
                    raw.append(("PRINT", None))
                elif op == "ret":
                    raw.append(("LOAD", i.args[0] if i.args else None))
                    raw.append(("RET", None))
                elif op == "jmp":
                    raw.append(("JMP", i.args[0]))
                elif op == "br":
                    raw.append(("LOAD", i.args[0]))
                    raw.append(("BR", i.args[1]))
                    raw.append(("JMP", i.args[2]))
                # phi/verificação: fora do escopo v0.2 (SSA já linear)

        # resolve labels -> offsets relativos
        pos: dict[str, int] = {}
        seq: list = []
        for op, arg in raw:
            if op == "LABEL":
                pos[arg] = len(seq)
            else:
                seq.append([op, arg])
        code: list = []
        for idx, (op, arg) in enumerate(seq):
            if op in ("JMP", "BR"):
                code.append([op, pos[arg] - (idx + 1)])
            else:
                code.append([op, arg])

        locs = list(f.params)
        for n in stored:
            if n not in locs:
                locs.append(n)
        funcs[f.nome] = {"bytecodes": code, "consts": consts,
                         "locals": locs, "arity": len(f.params)}

    # metadados __func__ visíveis de qualquer frame (snapshot das consts
    # ANTES de estender, senão a lista vira cíclica e o JSON quebra)
    metas = [{"__func__": n, "bytecodes": m["bytecodes"],
              "consts": list(m["consts"]), "locals": m["locals"],
              "arity": m["arity"]} for n, m in funcs.items()]
    for m in funcs.values():
        m["consts"].extend(metas)

    # entry: nunca retorna ao chamador — todo RET vira HALT com o
    # valor já empilhado pelo LOAD anterior (RET descartaria no topo).
    if entry in funcs:
        code = funcs[entry]["bytecodes"]
        code[:] = [["HALT", 0] if op == "RET" else [op, arg]
                   for op, arg in code]
        if not code or code[-1][0] != "HALT":
            code.append(["HALT", 0])
    return {"entry": entry, "functions": funcs}


# Formato .lbc legado (struct-packed) mantido em bytecode.py.
# gerar() antigo removido em favor de gerar_dict().
def gerar(mod_ir, entry: str = "main") -> dict:
    return gerar_dict(mod_ir, entry)


# ---------------------------------------------------------------------------
# Verificador do formato dict executável (v0.2: tracking de operandos).
# ---------------------------------------------------------------------------

_BINOPS = {"ADD", "SUB", "MUL", "DIV", "MOD", "EQ", "NEQ", "LT",
           "GT", "LE", "GE"}


def verificar_dict(mod: dict) -> dict:
    """Verifica um módulo dict (saída de gerar_dict).

    Checa por função: índices CONST dentro de `consts`, LOAD/STORE com
    nomes declarados em `locals`, CALL com alvo conhecido, profundidade
    da pilha de operandos consistente em todos os caminhos (worklist
    sobre pcs, saltos relativos resolvidos) e HALT final no entry.

    Retorna {"erros": [...], "avisos": [...]}. CALL para função
    desconhecida é aviso (a VM cria stub arity=0 em runtime).
    """
    erros: list[str] = []
    avisos: list[str] = []
    funcs = mod.get("functions", {})
    entry = mod.get("entry")
    if entry not in funcs:
        erros.append(f"entry `{entry}` não encontrado em functions")
    arity_of = {n: m.get("arity", 0) for n, m in funcs.items()}
    for fname, f in funcs.items():
        code = f.get("bytecodes", [])
        consts = f.get("consts", [])
        locs = set(f.get("locals", []))
        n = len(code)

        def alvo(idx, off):
            return idx + 1 + int(off)

        # profundidades já visitadas por pc (detecta inconsistência).
        seen: dict[int, int] = {}
        work = [(0, 0)] if n else []
        while work:
            pc, depth = work.pop()
            if pc < 0 or pc >= n:
                erros.append(f"{fname}: salto para pc inválido {pc}")
                continue
            if pc in seen:
                if seen[pc] != depth:
                    erros.append(
                        f"{fname}: profundidade inconsistente em pc={pc} "
                        f"({seen[pc]} vs {depth})")
                continue
            seen[pc] = depth
            op, arg = code[pc][0], code[pc][1]
            if op == "CONST":
                if not isinstance(arg, int) or arg < 0 or arg >= len(consts):
                    erros.append(f"{fname}: CONST com índice inválido {arg!r} em pc={pc}")
                work.append((pc + 1, depth + 1))
            elif op == "LOAD":
                if arg not in locs:
                    erros.append(f"{fname}: LOAD de local desconhecido `{arg}` em pc={pc}")
                work.append((pc + 1, depth + 1))
            elif op == "STORE":
                if arg not in locs:
                    erros.append(f"{fname}: STORE em local desconhecido `{arg}` em pc={pc}")
                if depth < 1:
                    erros.append(f"{fname}: STORE com pilha vazia em pc={pc}")
                    work.append((pc + 1, 0))
                else:
                    work.append((pc + 1, depth - 1))
            elif op in _BINOPS:
                if depth < 2:
                    erros.append(f"{fname}: {op} com operandos insuficientes em pc={pc}")
                    work.append((pc + 1, 0))
                else:
                    work.append((pc + 1, depth - 1))
            elif op == "NOT":
                if depth < 1:
                    erros.append(f"{fname}: NOT com pilha vazia em pc={pc}")
                work.append((pc + 1, depth))
            elif op in ("IS_OK", "UNWRAP"):
                if depth < 1:
                    erros.append(f"{fname}: {op} com pilha vazia em pc={pc}")
                    work.append((pc + 1, 0))
                else:
                    work.append((pc + 1, depth))
            elif op == "CALL":
                _BUILTIN_ARITY = {"Ok": 1, "Err": 1, "str::from_int": 1,
                                  "assert_eq": 2, "assert_ne": 2, "assert": 1,
                                  "assert_almost_eq": 2, "len": 1, "str": 1,
                                  "int": 1, "float": 1, "bool": 1, "panic": 1}
                if arg not in arity_of:
                    avisos.append(f"{fname}: CALL para função desconhecida `{arg}` em pc={pc}")
                    ar = _BUILTIN_ARITY.get(arg, 0)
                else:
                    ar = arity_of[arg]
                if depth < ar:
                    erros.append(f"{fname}: CALL `{arg}` com operandos insuficientes em pc={pc}")
                    work.append((pc + 1, 0))
                else:
                    work.append((pc + 1, depth - ar + 1))
            elif op == "PRINT":
                if depth < 1:
                    erros.append(f"{fname}: PRINT com pilha vazia em pc={pc}")
                    work.append((pc + 1, 0))
                else:
                    work.append((pc + 1, depth - 1))
            elif op == "JMP":
                work.append((alvo(pc, arg), depth))
            elif op == "BR":
                if depth < 1:
                    erros.append(f"{fname}: BR com pilha vazia em pc={pc}")
                    work.append((alvo(pc, arg), 0))
                else:
                    work.append((alvo(pc, arg), depth - 1))
                    work.append((pc + 1, depth - 1))
            elif op == "YIELD":
                work.append((pc + 1, depth))
            elif op == "SPAWN":
                ar = arity_of.get(arg, 0) if isinstance(arg, str) else 0
                if depth < ar:
                    erros.append(f"{fname}: SPAWN `{arg}` com operandos insuficientes em pc={pc}")
                    work.append((pc + 1, 0))
                else:
                    work.append((pc + 1, depth - ar))
            elif op in ("AWAIT_FUT", "AWAIT_CH"):
                if depth < 1:
                    erros.append(f"{fname}: {op} com pilha vazia em pc={pc}")
                    work.append((pc + 1, 0))
                else:
                    work.append((pc + 1, depth))  # pop 1 push 1 -> depth igual
            elif op == "CALL_NATIVE":
                # arg pode ser (name, nargs) ou str
                if isinstance(arg, (list, tuple)) and len(arg) >= 2:
                    try:
                        ar = int(arg[1])
                    except Exception:
                        ar = 0
                else:
                    ar = 0
                if depth < ar:
                    erros.append(f"{fname}: CALL_NATIVE com operandos insuficientes em pc={pc}")
                    work.append((pc + 1, 0))
                else:
                    # push 1 (resultado) se nargs -> depth - ar +1
                    work.append((pc + 1, depth - ar + 1))
            elif op in ("RET", "HALT"):
                pass  # fim de caminho
            else:
                erros.append(f"{fname}: opcode desconhecido `{op}` em pc={pc}")
                work.append((pc + 1, depth))
        if fname == entry and n:
            if code[-1][0] != "HALT":
                erros.append(f"{fname}: entry não termina com HALT")
    return {"erros": erros, "avisos": avisos}


def gerar_lbc(mod_ir, nome: str = "main", entry: str = "main"):
    """Ponte dict executável -> .lbc struct-packed (bytecode.ModuloBC).

    Achata a função `entry` em (opcode, arg) com consts próprias;
    LOAD/STORE por nome viram índices de registradores; CALL vira
    índice na tabela de funções anexada ao fim das consts.
    """
    from compiler.backend.vm.bytecode import ModuloBC
    mod = gerar_dict(mod_ir, entry)
    f = mod["functions"][entry]
    reg: dict[str, int] = {}
    for loc in f["locals"]:
        reg[loc] = len(reg)
    consts = list(f["consts"])
    code: list[tuple[str, int]] = []
    seq = f["bytecodes"]
    for idx, (op, arg) in enumerate(seq):
        if op == "CONST":
            code.append(("CONST", int(arg)))
        elif op in ("LOAD", "STORE"):
            code.append((op, reg.setdefault(arg, len(reg)) % 256))
        elif op == "CALL":
            code.append(("CALL", 0))
        elif op in ("JMP", "BR"):
            code.append((op, int(arg)))
        elif op in ("ADD", "SUB", "MUL", "DIV", "MOD", "EQ", "LT", "GT"):
            code.append((op, 0))
        elif op == "PRINT":
            code.append(("PRINT", 0))
        elif op == "RET":
            code.append(("RET", 0))
        elif op == "HALT":
            # HALT só fecha o módulo; HALTs intermediários (de cada
            # `return` do entry) viram RET no formato .lbc.
            code.append(("HALT", 0) if idx == len(seq) - 1 else ("RET", 0))
    return ModuloBC(nome, consts, code)
