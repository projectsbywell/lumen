"""
Lumen Runtime — Virtual Machine (VM) de bytecode.

Opcode set (síncrono):
    CONST idx       push constpool[idx]
    LOAD  name      push frame locals[name]
    STORE name      pop -> frame locals[name]
    ADD             pop b, pop a, push a + b
    SUB             pop b, pop a, push a - b
    MUL             pop b, pop a, push a * b
    DIV             pop b, pop a, push a / b  (ZeroDivisionError -> LumenError)
    JMP  offset     PC += offset  (offset relativo ao próximo instrução)
    BR   offset     pop cond; if truthy -> PC += offset
    CALL name       pop nargs args (ordem reversa), empilha frame, salta
    RET             pop frame, empilha retval no frame anterior
    PRINT           pop e imprime
    HALT            para a VM

Opcode set (async — P5.2):
    YIELD           cede execução: salva frame+stack na fila _prontas,
                    retorna controle ao loop round-robin.
    SPAWN name      cria coroutine-frame da função *name*, registra no Heap
                    (registrar_frame), enfileira em _prontas.  Pop *arity*
                    args da stack (inferido do metadata da função).
    AWAIT_FUT       pop Future: se pronta → push valor; se pendente →
                    suspende frame com waker que re-enfileira ao resolver.
    AWAIT_CH        pop Channel: se tem dado → push; se vazio → estaciona
                    frame como receptor (callback re-enfileira ao receber).
    CALL_NATIVE     (nativo/teste) arg=(name,nargs); chama Python callable
                    registrado em _native_calls, push resultado.

Formato do módulo bytecode (mod_bc):
    {
        "consts":   [ ... ],
        "globals":  [ "varname", ... ],
        "bytecodes":[ (opcode, arg?), ... ],
        "functions": {
            "nome": {
                "consts":   [...],
                "locals":   ["a","b",...],
                "bytecodes":[...],
                "arity":    N,
            }
        },
        "entry": "main",
    }
"""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Opcode constants
# ---------------------------------------------------------------------------
CONST  = "CONST"
LOAD   = "LOAD"
STORE  = "STORE"
ADD    = "ADD"
SUB    = "SUB"
MUL    = "MUL"
DIV    = "DIV"
MOD    = "MOD"
EQ     = "EQ"
NEQ    = "NEQ"
LT     = "LT"
GT     = "GT"
LE     = "LE"
GE     = "GE"
NOT    = "NOT"
JMP    = "JMP"
BR     = "BR"
CALL   = "CALL"
RET    = "RET"
PRINT  = "PRINT"
HALT   = "HALT"
# Async opcodes (P5.2)
YIELD      = "YIELD"
SPAWN      = "SPAWN"
AWAIT_FUT  = "AWAIT_FUT"
AWAIT_CH   = "AWAIT_CH"
CALL_NATIVE = "CALL_NATIVE"


# ---------------------------------------------------------------------------
# LumenError
# ---------------------------------------------------------------------------
class LumenError(Exception):
    """Exceção do runtime Lumen com stack trace."""

    def __init__(self, msg: str, trace: Optional[List[str]] = None):
        super().__init__(msg)
        self.trace: List[str] = trace or []

    def __str__(self) -> str:
        if self.trace:
            header = super().__str__()
            tb = "\n  ".join(self.trace)
            return f"{header}\nStack trace:\n  {tb}"
        return super().__str__()


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------
@dataclass
class Frame:
    """Frame de execução (chamada de função)."""
    func_name: str
    bytecode: List[Tuple[str, Any]]
    consts: List[Any]
    locals: Dict[str, Any] = field(default_factory=dict)
    pc: int = 0
    ret_addr: Optional[int] = None          # PC no frame chamador
    ret_frame: Optional["Frame"] = None     # frame chamador (para RET)
    coro_id: Optional[int] = None           # ID da coroutine (None = frame síncrono)


# ---------------------------------------------------------------------------
# VM
# ---------------------------------------------------------------------------
class VM:
    """Máquina virtual de bytecode Lumen."""

    def __init__(self, heap=None) -> None:
        self.stack: List[Any] = []
        self.frames: List[Frame] = []
        self.globals: Dict[str, Any] = {}
        self.output: List[str] = []   # saída capturada (PRINT)
        self._running = False
        self.hook = None  # hook(frame, opcode, arg) — depuração (DAP)

        # GC wiring (v0.4) — import local para evitar ciclo
        from runtime.gc import Heap as _Heap
        self.heap = heap if heap is not None else _Heap(nursery_max=256, old_max=2048)
        self._gc_interval: int = 512
        self._opcodes_since_gc: int = 0

        # Async (P5.2) — fila de coroutines prontas e estado suspenso
        self._prontas: deque = deque()          # frames de coroutines prontas
        self._coro_counter: int = 0             # próximo coro_id
        self._coro_saved: Dict[int, Tuple[List[Frame], List[Any]]] = {}
        self._native_calls: Dict[str, Any] = {} # funções Python para CALL_NATIVE

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def executar(self, mod_bc: dict, entrada: Any = None,
                 globals_extra: Optional[Dict[str, Any]] = None) -> Any:
        """
        Executa um módulo bytecode.

        Parameters
        ----------
        mod_bc : dict
            Módulo compilado pelo backend VM.
        entrada : any
            Valor injetado como variável ``entrada`` no escopo global.
        globals_extra : dict, opcional
            Globals adicionais injetados antes da execução (usado em testes
            para injetar objetos Python como Future/Channel).

        Returns
        -------
        any
            Valor retornado pela função entry (ou resultado do stack top).
        """
        self.stack.clear()
        self.frames.clear()
        self.globals.clear()
        self.output.clear()
        self._running = True
        self._opcodes_since_gc = 0
        # Async (P5.2): limpar estado de coroutines
        self._prontas.clear()
        self._coro_saved.clear()
        self._coro_counter = 0

        if entrada is not None:
            self.globals["entrada"] = entrada
        if globals_extra:
            self.globals.update(globals_extra)

        # prepara frame do entry
        entry_name = mod_bc.get("entry", "main")
        entry_func = self._resolve_function(mod_bc, entry_name)

        frame = Frame(
            func_name=entry_name,
            bytecode=entry_func["bytecodes"],
            consts=entry_func.get("consts", mod_bc.get("consts", [])),
            locals={},
        )
        self.frames.append(frame)
        # v0.4: registrar entry frame no heap
        try:
            self.heap.registrar_frame(id(frame), frame.locals)
        except Exception:
            pass  # GC wiring nunca deve quebrar execução

        # executa loop principal
        result = self._run_loop()

        return result

    # ------------------------------------------------------------------
    # Loop principal (round-robin cooperativo para coroutines)
    # ------------------------------------------------------------------
    def _run_loop(self) -> Any:
        max_passos = 1_000_000  # limite defensivo
        passos = 0
        while self._running and passos < max_passos:
            passos += 1

            # Sem frame ativo → pega próxima coroutine da fila
            if not self.frames:
                if self._prontas:
                    root = self._prontas.popleft()
                    cid = root.coro_id
                    if cid is not None and cid in self._coro_saved:
                        self.frames, self.stack = self._coro_saved.pop(cid)
                    else:
                        self.frames = [root]
                        self.stack = []
                    continue
                else:
                    break  # sem frames e sem prontas → fim

            frame = self.frames[-1]
            if frame.pc >= len(frame.bytecode):
                # fim do frame sem RET implícito
                self._pop_frame(None)
                continue

            instr = frame.bytecode[frame.pc]
            opcode = instr[0]
            arg = instr[1] if len(instr) > 1 else None
            frame.pc += 1

            if self.hook is not None:
                self.hook(frame, opcode, arg)

            self._dispatch(opcode, arg)

            # v0.4: GC periódico defensivo
            self._opcodes_since_gc += 1
            if self._opcodes_since_gc >= self._gc_interval:
                try:
                    self.heap.coletar()
                except Exception:
                    pass  # GC nunca levanta para o programa
                self._opcodes_since_gc = 0

        if self.stack:
            return self.stack[-1]
        return None

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    def _dispatch(self, opcode: str, arg: Any) -> None:
        frame = self.frames[-1] if self.frames else None

        if opcode == CONST:
            val = frame.consts[arg]
            self.stack.append(val)

        elif opcode == LOAD:
            name = arg
            if name in frame.locals:
                self.stack.append(self._unwrap(frame.locals[name]))
            elif name in self.globals:
                self.stack.append(self._unwrap(self.globals[name]))
            else:
                raise self._error(f"Variável indefinida: '{name}'")

        elif opcode == STORE:
            name = arg
            val = self.stack.pop()
            if len(self.frames) <= 1:
                frame.locals[name] = val
                self.globals[name] = val  # nível módulo: local e global
                # v0.5: wrapping — aloca Objeto no heap e registra como root
                try:
                    from runtime.gc import Objeto
                    tipo = self._tipo_prim(val)
                    if tipo != "any":
                        obj = self.heap.alocar(tipo, val)
                        self.heap.definir_global(name, obj)
                    else:
                        self.heap.definir_global(name, None)
                except Exception:
                    pass  # GC wiring nunca deve quebrar execução
            else:
                frame.locals[name] = val  # função: só local (sem poluir globals)

        elif opcode == ADD:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(self._do_add(a, b))

        elif opcode == SUB:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(self._do_sub(a, b))

        elif opcode == MUL:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(self._do_mul(a, b))

        elif opcode == DIV:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(self._do_div(a, b))

        elif opcode == MOD:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(a % b)

        elif opcode == EQ:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(a == b)

        elif opcode == NEQ:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(a != b)

        elif opcode == LT:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(a < b)

        elif opcode == GT:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(a > b)

        elif opcode == LE:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(a <= b)

        elif opcode == GE:
            b = self._unwrap(self.stack.pop())
            a = self._unwrap(self.stack.pop())
            self.stack.append(a >= b)

        elif opcode == NOT:
            a = self._unwrap(self.stack.pop())
            self.stack.append(not self._is_truthy(a))

        elif opcode == JMP:
            frame.pc += arg  # arg é offset relativo ao próximo PC

        elif opcode == BR:
            cond = self._unwrap(self.stack.pop())
            if self._is_truthy(cond):
                frame.pc += arg

        elif opcode == CALL:
            func_name = arg
            # obtém metadata da função
            func_meta = self._resolve_function_by_name(func_name)
            arity = func_meta["arity"]

            # pop args (do topo: último arg primeiro na pilha)
            args: List[Any] = []
            for _ in range(arity):
                args.append(self.stack.pop())
            args.reverse()

            # mapeia para parâmetros
            param_names = func_meta.get("locals", [])
            local_vars: Dict[str, Any] = {}
            for i, pname in enumerate(param_names):
                if i < len(args):
                    local_vars[pname] = args[i]

            new_frame = Frame(
                func_name=func_name,
                bytecode=func_meta["bytecodes"],
                consts=func_meta.get("consts", frame.consts),
                locals=local_vars,
                ret_addr=frame.pc,
                ret_frame=frame,
            )
            self.frames.append(new_frame)
            # v0.4: registrar frame no heap
            try:
                self.heap.registrar_frame(id(new_frame), new_frame.locals)
            except Exception:
                pass  # GC wiring nunca deve quebrar execução

        elif opcode == RET:
            retval = self.stack.pop() if self.stack else None
            self._pop_frame(retval)

        elif opcode == PRINT:
            val = self._unwrap(self.stack.pop() if self.stack else None)
            s = self._lumen_str(val)
            self.output.append(s)

        elif opcode == HALT:
            self._running = False

        # ------------------------------------------------------------------
        # Async opcodes (P5.2)
        # ------------------------------------------------------------------
        elif opcode == YIELD:
            # Cede execução: salva frame+stack na fila _prontas
            if not self.frames:
                raise self._error("YIELD sem frame ativo")
            root = self._find_coro_root()
            if root is None:
                raise self._error("YIELD em frame não-corroutine")
            cid = root.coro_id
            self._coro_saved[cid] = (list(self.frames), list(self.stack))
            self._prontas.append(root)
            self.frames.clear()
            self.stack.clear()

        elif opcode == SPAWN:
            # Cria coroutine-frame e enfileira
            func_name = arg
            func_meta = self._resolve_function_by_name(func_name)
            arity = func_meta.get("arity", 0)

            # pop args da stack (ordem reversa → reversa)
            args: List[Any] = []
            for _ in range(arity):
                if not self.stack:
                    raise self._error(
                        f"SPAWN '{func_name}': stack underflow "
                        f"(faltam {arity} args)"
                    )
                args.append(self.stack.pop())
            args.reverse()

            param_names = func_meta.get("locals", [])
            local_vars: Dict[str, Any] = {}
            for i, pname in enumerate(param_names):
                if i < len(args):
                    local_vars[pname] = args[i]

            self._coro_counter += 1
            coro_id = self._coro_counter

            caller_consts = self.frames[-1].consts if self.frames else []
            new_coro = Frame(
                func_name=func_name,
                bytecode=func_meta.get("bytecodes", []),
                consts=func_meta.get("consts", caller_consts),
                locals=local_vars,
                coro_id=coro_id,
            )
            # registrar no heap (reusa infraestrutura v0.4)
            try:
                self.heap.registrar_frame(id(new_coro), new_coro.locals)
            except Exception:
                pass
            self._prontas.append(new_coro)

        elif opcode == AWAIT_FUT:
            # Pop Future: pronta → push valor; pendente → suspende com waker
            if not self.stack:
                raise self._error("AWAIT_FUT com stack vazia")
            future = self.stack.pop()
            from runtime.threads import Future as _Future
            from runtime.threads import EstadoFuture as _EF
            if not isinstance(future, _Future):
                raise self._error(
                    f"AWAIT_FUT: valor não é Future "
                    f"(recebeu {type(future).__name__})"
                )
            if future.poll() == _EF.PRONTO:
                self.stack.append(future.valor)
            else:
                root = self._find_coro_root()
                if root is None:
                    raise self._error("AWAIT_FUT em frame não-corroutine")
                cid = root.coro_id
                self._coro_saved[cid] = (
                    list(self.frames), list(self.stack)
                )
                # waker: quando future resolver, restaura frame na fila
                def _waker_fut(fut, _cid=cid):
                    saved = self._coro_saved.pop(_cid, None)
                    if saved:
                        fs, stk = saved
                        stk.append(fut.valor)
                        self._coro_saved[_cid] = (fs, stk)
                        self._prontas.append(fs[0])
                future._waker = _waker_fut
                self.frames.clear()
                self.stack.clear()

        elif opcode == AWAIT_CH:
            # Pop Channel: tem dado → push; vazio → estaciona receptor
            if not self.stack:
                raise self._error("AWAIT_CH com stack vazia")
            ch = self.stack.pop()
            from runtime.threads import Channel as _Ch
            if not isinstance(ch, _Ch):
                raise self._error(
                    f"AWAIT_CH: valor não é Channel "
                    f"(recebeu {type(ch).__name__})"
                )
            if ch.tamanho() > 0:
                self.stack.append(ch._buffer.popleft())
            else:
                root = self._find_coro_root()
                if root is None:
                    raise self._error("AWAIT_CH em frame não-corroutine")
                cid = root.coro_id
                self._coro_saved[cid] = (
                    list(self.frames), list(self.stack)
                )
                # callback: quando dado chegar, restaura frame na fila
                def _waker_ch(valor, _cid=cid):
                    saved = self._coro_saved.pop(_cid, None)
                    if saved:
                        fs, stk = saved
                        stk.append(valor)
                        self._coro_saved[_cid] = (fs, stk)
                        self._prontas.append(fs[0])
                ch._recebedores.append(_waker_ch)
                self.frames.clear()
                self.stack.clear()

        elif opcode == CALL_NATIVE:
            # (nativo/teste) arg=(name,nargs) ou name (nargs=0)
            if isinstance(arg, tuple) and len(arg) >= 2:
                native_name, nargs = arg[0], arg[1]
            elif isinstance(arg, str):
                native_name, nargs = arg, 0
            else:
                raise self._error(
                    f"CALL_NATIVE: arg inválido: {arg}"
                )
            func = self._native_calls.get(native_name)
            if func is None:
                raise self._error(
                    f"Função nativa não registrada: '{native_name}'"
                )
            native_args: List[Any] = []
            for _ in range(nargs):
                if not self.stack:
                    raise self._error(
                        f"CALL_NATIVE '{native_name}': stack underflow"
                    )
                native_args.append(self.stack.pop())
            native_args.reverse()
            try:
                result = func(*native_args)
            except Exception as e:
                raise self._error(
                    f"CALL_NATIVE '{native_name}' falhou: {e}"
                )
            if result is not None:
                self.stack.append(result)

        else:
            raise self._error(f"Opcode desconhecido: {opcode}")

    # ------------------------------------------------------------------
    # Wrapping / Unwrapping (P5.1)
    # ------------------------------------------------------------------
    @staticmethod
    def _unwrap(val: Any) -> Any:
        """Desembrulha Objeto primitivo para valor Python puro. Defensivo."""
        try:
            from runtime.gc import Objeto
            if isinstance(val, Objeto) and val.tipo in (
                "int", "float", "bool", "str", "none",
            ):
                return val.valor
        except Exception:
            pass
        return val

    @staticmethod
    def _tipo_prim(val: Any) -> str:
        """Infere o tipo primitivo de um valor Python puro."""
        if isinstance(val, bool):
            return "bool"
        if isinstance(val, int):
            return "int"
        if isinstance(val, float):
            return "float"
        if isinstance(val, str):
            return "str"
        if val is None:
            return "none"
        return "any"

    # ------------------------------------------------------------------
    # Operações aritméticas
    # ------------------------------------------------------------------
    @staticmethod
    def _do_add(a: Any, b: Any) -> Any:
        if isinstance(a, str) or isinstance(b, str):
            return str(a) + str(b)
        return a + b

    @staticmethod
    def _do_sub(a: Any, b: Any) -> Any:
        return a - b

    @staticmethod
    def _do_mul(a: Any, b: Any) -> Any:
        return a * b

    @staticmethod
    def _do_div(a: Any, b: Any) -> Any:
        if b == 0:
            raise LumenError("Divisão por zero")
        if isinstance(a, int) and isinstance(b, int) and a % b == 0:
            return a // b
        return a / b

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_truthy(val: Any) -> bool:
        if val is None:
            return False
        if val is False:
            return False
        if val == 0:
            return False
        if val == "":
            return False
        return True

    @staticmethod
    def _lumen_str(val: Any) -> str:
        if val is None:
            return "nil"
        if val is True:
            return "true"
        if val is False:
            return "false"
        return str(val)

    def _resolve_function(self, mod_bc: dict, name: str) -> dict:
        funcs = mod_bc.get("functions", {})
        if name in funcs:
            return funcs[name]
        # se não há funções definidas, monta um frame a partir do módulo
        return {
            "bytecodes": mod_bc.get("bytecodes", []),
            "consts": mod_bc.get("consts", []),
            "locals": [],
            "arity": 0,
        }

    def _resolve_function_by_name(self, name: str) -> dict:
        # procura os metadados __func__ nas consts de TODOS os frames vivos
        # (o frame do entry sobrevive à execução inteira e carrega tudo)
        for f in reversed(self.frames):
            for c in f.consts:
                if isinstance(c, dict) and c.get("__func__") == name:
                    return c
        # P5.2: buscar também em coroutines suspensas
        for _cid, (fs, _stk) in self._coro_saved.items():
            for f in fs:
                for c in f.consts:
                    if isinstance(c, dict) and c.get("__func__") == name:
                        return c
        # se não encontrou, cria stub com arity=0
        return {"bytecodes": [], "consts": [], "locals": [], "arity": 0, "__func__": name}

    def _pop_frame(self, retval: Any) -> None:
        if len(self.frames) <= 1:
            # v0.4: remover frame do heap
            if self.frames:
                try:
                    self.heap.remover_frame(id(self.frames[-1]))
                except Exception:
                    pass  # GC wiring nunca deve quebrar execução
            # P5.2: se há coroutines na fila, não para a VM
            if self._prontas:
                self.frames.clear()
                self.stack.clear()
                return
            self._running = False
            return
        frame = self.frames.pop()
        # v0.4: remover frame morto do heap (try/except defensivo)
        try:
            self.heap.remover_frame(id(frame))
        except Exception:
            pass  # GC wiring nunca deve quebrar execução
        caller = frame.ret_frame
        if caller is not None and frame.ret_addr is not None:
            caller.pc = frame.ret_addr
        if retval is not None:
            self.stack.append(retval)

    def _find_coro_root(self) -> Optional[Frame]:
        """Encontra a raiz coroutine (coro_id não-None) na pilha atual."""
        for f in self.frames:
            if f.coro_id is not None:
                return f
        return None

    def _error(self, msg: str) -> LumenError:
        trace: List[str] = []
        for f in reversed(self.frames):
            trace.append(f"{f.func_name} @ PC {f.pc}")
        return LumenError(msg, trace)


# ---------------------------------------------------------------------------
# Função auxiliar de conveniência
# ---------------------------------------------------------------------------
def executar(mod_bc: dict, entrada: Any = None,
             globals_extra: Optional[Dict[str, Any]] = None) -> Any:
    """Executa bytecode e retorna resultado."""
    vm = VM()
    return vm.executar(mod_bc, entrada, globals_extra=globals_extra)
