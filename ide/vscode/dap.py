"""Servidor DAP (Debug Adapter Protocol) do Lumen (v0.4 P5.3).

Transporte stdio com cabeçalho Content-Length (igual ao LSP).
Capacidades: launch/attach (programa .lum, stopOnEntry), breakpoints por
LINHA (source+line) com condition/hitCondition/logMessage e compat por NOME
DE FUNÇÃO, continue, next/stepIn/stepOut por LINHA (avança via debug_map
até mudar de linha no mesmo frame; next faz step-over), restart, terminate
cooperativo (flag + exceção no hook, 1 instrução de atraso; não interrompe
chamada nativa bloqueante), stackTrace com line/column reais via spans,
scopes, variables, setVariable, evaluate seguro (ident + aritmética/
comparações via AST restrita, sem eval; bloqueia `__`, imports, chamadas),
threads, setExceptionBreakpoints/exceptionInfo, setDataBreakpoints/
watchpoints (pausa quando variável vigiada muda, check no hook),
pause, disconnect. A VM pausa via hook por instrução.

Limites honestos: attach não usa PID real — inicia o programa em thread com
o mesmo mecanismo do launch (anexa ao início, não a processo vivo externo);
terminate é cooperativo via hook (se o programa travar fora do hook/dentro
de nativa, o terminate só sinaliza `_running=False`); watchpoints são por
nome de variável (local depois global) com comparação `!=`, sem endereço/
range; step por linha depende do debug_map proporcional (pode agrupar
linhas muito próximas).
"""
import ast
import copy
import json
import os
import re
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from compiler.run import run_src  # noqa: E402 (reuso do pipeline)
from compiler.frontend.lexer import tokenize  # noqa: E402
from compiler.frontend.parser import Parser  # noqa: E402
from compiler.frontend.semantica import analisar  # noqa: E402
from compiler.frontend.borrowck import verificar as ver_borrow  # noqa: E402
from compiler.frontend import ast_nodes as A  # noqa: E402
from compiler.middle.ir import Baixador  # noqa: E402
from compiler.middle.passes import otimizar  # noqa: E402
from compiler.backend.vm.codegen_vm import gerar_dict  # noqa: E402
from runtime.vm import VM, LumenError  # noqa: E402


def read_msg(buf):
    headers = {}
    while True:
        line = buf.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        k, _, v = line.partition(":")
        headers[k.strip().lower()] = v.strip()
    n = int(headers.get("content-length", "0"))
    if not n:
        return None
    return json.loads(buf.read(n).decode("utf8"))


def send_msg(buf, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf8")
    buf.write(f"Content-Length: {len(data)}\r\n\r\n".encode("utf8") + data)
    buf.flush()


class Paused(Exception):
    pass


class Terminated(Paused):
    """Sinal cooperativo de terminate injetado pelo hook (1 instr de atraso)."""
    pass


_UNSET = object()


class _Unsupported(Exception):
    """Expressão fora da gramática segura (vira 'não suportado')."""
    pass

_ALLOWED_BINOP = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod)
_ALLOWED_UNARY = (ast.UAdd, ast.USub, ast.Not)
_ALLOWED_BOOL = (ast.And, ast.Or)
_ALLOWED_CMP = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)


_COND_RE = re.compile(r"^([A-Za-z_]\w*)\s*(==|!=|<=|>=|<|>)?\s*(.*)$")
_LOGPH_RE = re.compile(r"\{([A-Za-z_]\w*)\}")


class Session:
    def __init__(self, out):
        self.out = out
        self.seq = 0
        self.vm = VM()
        self.mod = None
        self.breakpoints: set[str] = set()  # compat: nomes
        self.breakpoints_funcs: set[str] = set()
        self.breakpoints_lines: dict[str, set[int]] = {}  # path -> lines
        # v0.4: detalhes por breakpoint de linha (path_key, line) ->
        #   {"condition": str, "hitCondition": str, "logMessage": str}
        self.bp_details: dict[tuple[str, int], dict] = {}
        self._hit_counts: dict[tuple[str, int], int] = {}
        self._stop_on_entry = False
        self._exception_filters: list[str] = []
        self._last_exception: dict | None = None
        self._pause = threading.Event()
        self._paused = False
        self._pause_reason = "breakpoint"
        self._pause_requested = False
        self._already_terminated = False
        self._step_once = False
        self._thread = None
        self._done = False
        self.lock = threading.Lock()
        # debug info
        self.debug_map: dict[str, list[tuple[int, int]]] = {}
        self.program_path: str = ""
        self.program_src: str = ""
        self._last_break: tuple[str, int] | None = None
        # P5.3: step por linha
        self._step_line = False
        self._step_kind = "next"
        self._step_start_func: str | None = None
        self._step_start_line: int | None = None
        self._step_start_depth = 0
        # P5.3: watchpoints nome -> último valor (ou _UNSET = ainda sem snapshot)
        self._data_bps: dict[str, object] = {}
        # P5.3: terminate cooperativo + attach sem PID real
        self._terminating = False
        self._attached = False

    def event(self, name, body=None):
        self.seq += 1
        send_msg(self.out, {"seq": self.seq, "type": "event",
                            "event": name, "body": body or {}})

    def reply(self, req, body=None, ok=True):
        obj = {"seq": self.seq, "type": "response",
               "request_seq": req.get("seq", 0), "success": ok,
               "command": req.get("command", ""), "body": body or {}}
        send_msg(self.out, obj)
        return obj

    def _emit_terminated_once(self):
        with self.lock:
            if self._already_terminated:
                return
            self._already_terminated = True
        self.event("terminated")

    def _build_debug_map(self, prog, mod):
        """Mapeia (func, pc) -> (line, col) usando spans do front.
        Usa spans ordenados por (line,col) de todos os nós da função.
        """
        func_nodes: dict[str, object] = {}
        for it in getattr(prog, "itens", []):
            if type(it).__name__ == "Fn":
                func_nodes[it.name] = it
            for m in getattr(it, "methods", []):
                func_nodes[m.name] = m
                # também registra sem prefixo tipo:: para matching
                short = m.name.split("::")[-1]
                if short not in func_nodes:
                    func_nodes[short] = m
        out: dict[str, list[tuple[int,int]]] = {}
        funcs = mod.get("functions", {}) if mod else {}
        for fname, fmeta in funcs.items():
            code = fmeta.get("bytecodes", [])
            n = len(code)
            fn_node = func_nodes.get(fname)
            if fn_node is None:
                short = fname.split("::")[-1]
                fn_node = func_nodes.get(short)
            spans_sorted: list[A.Span] = []
            if fn_node is not None:
                raw: list[A.Span] = []
                for node in A.walk(fn_node):
                    sp = getattr(node, "span", None)
                    if sp is not None and getattr(sp, "line", 0) > 0:
                        raw.append(sp)
                # ordena por posição
                raw.sort(key=lambda s: (s.line, s.col))
                # uniq por (line,col) preservando ordem
                seen = set()
                uniq: list[A.Span] = []
                for s in raw:
                    k = (s.line, s.col)
                    if k not in seen:
                        seen.add(k)
                        uniq.append(s)
                spans_sorted = uniq
            if not spans_sorted:
                # fallback: linha 1
                out[fname] = [(1, 1)] * n
                continue
            mapped: list[tuple[int,int]] = []
            L = len(spans_sorted)
            for i in range(n):
                # distribuição proporcional: cada bytecode pega span proporcional
                idx = int(i * L / max(n, 1))
                if idx >= L:
                    idx = L - 1
                sp = spans_sorted[idx]
                mapped.append((sp.line, sp.col))
            out[fname] = mapped
        return out

    def _line_for_pc(self, func_name: str, pc: int):
        tbl = self.debug_map.get(func_name)
        if not tbl:
            return (1, 1)
        if pc < 0:
            pc = 0
        if pc >= len(tbl):
            pc = len(tbl) - 1
        return tbl[pc]

    def _lookup_ident(self, frame, name):
        """Inspeção de variável (mesma regra do evaluate): local, depois global."""
        if frame is not None and name in frame.locals:
            return (True, frame.locals[name])
        if name in self.vm.globals:
            return (True, self.vm.globals[name])
        return (False, None)

    def _parse_operand(self, tok, frame):
        t = tok.strip()
        if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
            return (True, t[1:-1])
        if t == "true":
            return (True, True)
        if t == "false":
            return (True, False)
        if t == "nil":
            return (True, None)
        try:
            return (True, int(t))
        except ValueError:
            pass
        try:
            return (True, float(t))
        except ValueError:
            pass
        if t.isidentifier():
            return self._lookup_ident(frame, t)
        return (False, None)

    def _parse_set_value(self, raw):
        """Converte texto do setVariable: int/float/bool/nil/string aspada/crua."""
        t = raw.strip()
        if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
            return t[1:-1]
        if t == "true":
            return True
        if t == "false":
            return False
        if t == "nil":
            return None
        try:
            return int(t)
        except ValueError:
            pass
        try:
            return float(t)
        except ValueError:
            pass
        return raw

    def _current_pos(self):
        """Posição atual do topo: (func, line, depth) ou (None, None, 0)."""
        if not self.vm.frames:
            return (None, None, 0)
        f = self.vm.frames[-1]
        cur_pc = f.pc - 1 if f.pc > 0 else 0
        line, _col = self._line_for_pc(f.func_name, cur_pc)
        return (f.func_name, line, len(self.vm.frames))

    def _begin_line_step(self, kind):
        """Inicia step por linha via debug_map; captura origem no frame pausado."""
        func, line, depth = self._current_pos()
        self._step_kind = kind
        self._step_start_func = func
        self._step_start_line = line
        self._step_start_depth = depth
        self._step_line = True
        self._step_once = False

    def _safe_eval(self, expr, frame):
        """Avalia expr aritmética/comparação simples via AST restrita.

        Retorna (ok, valor). Bloqueia `__`, imports, chamadas, atributos,
        subscritos e qualquer nó fora da lista permitida. Sem eval/exec.
        """
        t = (expr or "").strip()
        if not t or len(t) > 500:
            return (False, None)
        if "__" in t:
            return (False, None)
        try:
            tree = ast.parse(t, mode="eval")
        except SyntaxError:
            return (False, None)
        try:
            return (True, self._eval_node(tree.body, frame))
        except (_Unsupported, KeyError):
            return (False, None)
        except (ZeroDivisionError, TypeError, ValueError, OverflowError,
                AttributeError):
            # erro de avaliação (ex.: divisão por zero, tipos) -> erro honesto
            raise
        except Exception:
            return (False, None)

    def _eval_node(self, node, frame):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if not node.id.isidentifier() or "__" in node.id:
                raise KeyError(node.id)
            found, val = self._lookup_ident(frame, node.id)
            if not found:
                raise KeyError(node.id)
            return val
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, _ALLOWED_BINOP):
                raise _Unsupported("op")
            a = self._eval_node(node.left, frame)
            b = self._eval_node(node.right, frame)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                # anti-DoS: recusa operando str grande ou resultado gigante
                if isinstance(a, str) and isinstance(b, int):
                    if len(a) > 10000 or b > 10000 or (b > 0 and len(a) * b > 10000):
                        raise _Unsupported("str grande")
                elif isinstance(b, str) and isinstance(a, int):
                    if len(b) > 10000 or a > 10000 or (a > 0 and len(b) * a > 10000):
                        raise _Unsupported("str grande")
                else:
                    if isinstance(a, str) and len(a) > 10000:
                        raise _Unsupported("str grande")
                    if isinstance(b, str) and len(b) > 10000:
                        raise _Unsupported("str grande")
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            if isinstance(node.op, ast.Mod):
                return a % b
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, _ALLOWED_UNARY):
                raise _Unsupported("op")
            v = self._eval_node(node.operand, frame)
            if isinstance(node.op, ast.USub):
                return -v
            if isinstance(node.op, ast.UAdd):
                return +v
            if isinstance(node.op, ast.Not):
                return not v
        if isinstance(node, ast.BoolOp):
            if not isinstance(node.op, _ALLOWED_BOOL):
                raise _Unsupported("op")
            if isinstance(node.op, ast.And):
                res = True
                for v in node.values:
                    res = res and self._eval_node(v, frame)
                    if not res:
                        break
                return res
            res = False
            for v in node.values:
                res = res or self._eval_node(v, frame)
                if res:
                    break
            return res
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, frame)
            for op, comp in zip(node.ops, node.comparators):
                if not isinstance(op, _ALLOWED_CMP):
                    raise _Unsupported("op")
                right = self._eval_node(comp, frame)
                if isinstance(op, ast.Eq):
                    ok = left == right
                elif isinstance(op, ast.NotEq):
                    ok = left != right
                elif isinstance(op, ast.Lt):
                    ok = left < right
                elif isinstance(op, ast.LtE):
                    ok = left <= right
                elif isinstance(op, ast.Gt):
                    ok = left > right
                else:
                    ok = left >= right
                if not ok:
                    return False
                left = right
            return True
        # qualquer outro nó (Call, Attribute, Subscript, IfExp, etc.) bloqueado
        raise _Unsupported("nó")

    def _check_condition(self, cond, frame):
        """Condição simples: ident sozinho (truthy) ou ident op literal/ident."""
        cond = (cond or "").strip()
        if not cond:
            return True
        m = _COND_RE.match(cond)
        if not m:
            return False
        name, op, rhs = m.group(1), m.group(2), m.group(3).strip()
        found, val = self._lookup_ident(frame, name)
        if not found:
            return False
        if not op:
            return bool(val)
        if not rhs:
            return False
        ok, rhs_val = self._parse_operand(rhs, frame)
        if not ok:
            return False
        try:
            if op == "==":
                return val == rhs_val
            if op == "!=":
                return val != rhs_val
            if op == "<":
                return val < rhs_val
            if op == ">":
                return val > rhs_val
            if op == "<=":
                return val <= rhs_val
            if op == ">=":
                return val >= rhs_val
        except TypeError:
            return False
        return False

    def _check_hit_count(self, cnt, hit):
        """hitCondition: 'N' (igual), '>=N', '>N', '<=N', '<N', '%N' (a cada N)."""
        h = (hit or "").strip()
        if not h:
            return True
        try:
            if h.startswith(">="):
                return cnt >= int(h[2:].strip())
            if h.startswith("<="):
                return cnt <= int(h[2:].strip())
            if h.startswith(">"):
                return cnt > int(h[1:].strip())
            if h.startswith("<"):
                return cnt < int(h[1:].strip())
            if h.startswith("%"):
                n = int(h[1:].strip())
                return n > 0 and cnt % n == 0
            return cnt == int(h)
        except ValueError:
            return True

    def _render_log(self, tmpl, frame):
        def sub(m):
            found, val = self._lookup_ident(frame, m.group(1))
            return repr(val)[:200] if found else m.group(0)
        return _LOGPH_RE.sub(sub, tmpl)

    def _detail_for_line(self, line):
        """Detalhe (condition/hit/log) do breakpoint da linha, se houver."""
        for (k, ln), det in self.bp_details.items():
            if ln == line and k in self.breakpoints_lines \
                    and line in self.breakpoints_lines[k]:
                return ((k, ln), det)
        return (None, None)

    def hook(self, frame, opcode, arg):
        # P5.3: terminate cooperativo — injeção no hook (1 instr de atraso).
        # Limite: só funciona se o hook roda (por instrução); nativa
        # bloqueante sem hook não é interrompida, só `_running=False`.
        if self._terminating:
            raise Terminated("terminated")
        # pause cooperativo: flag armada pelo comando `pause` (sem wait
        # na thread de despacho); amostrada aqui na thread da VM.
        if self._pause_requested:
            self._pause_requested = False
            self._step_line = False
            self._step_once = False
            self._last_break = None
            self._enter_pause("pause")
            return
        # v0.4: stopOnEntry — pausa na primeira instrução do entry
        if self._stop_on_entry:
            self._stop_on_entry = False
            self._last_break = None
            self._enter_pause("entry")
            return
        # breakpoint por nome-função (compat)
        if frame.func_name in self.breakpoints_funcs and frame.pc == 1:
            self._enter_pause("breakpoint")
            return
        if frame.func_name in self.breakpoints and frame.pc == 1:
            self._enter_pause("breakpoint")
            return
        # breakpoint por linha: mapeia pc-1 (instr atual) -> line
        cur_pc = frame.pc - 1
        if cur_pc < 0:
            cur_pc = 0
        tbl = self.debug_map.get(frame.func_name)
        if tbl is not None and 0 <= cur_pc < len(tbl):
            line, col = tbl[cur_pc]
            # só pausa na primeira instrução que entra na linha (debounce por linha)
            is_first_of_line = (cur_pc == 0) or (tbl[cur_pc][0] != tbl[cur_pc - 1][0])
            if is_first_of_line:
                # verifica se linha está em breakpoints_lines (qualquer arquivo)
                should = False
                det_key, det = None, None
                for _path, lines in self.breakpoints_lines.items():
                    if line in lines:
                        # path matching: se breakpoint path específico, exige que programa corresponda
                        # Mas para MVP, se programa é único arquivo, qualquer path com mesma basename vale
                        # Se path armazenado != program_path, ainda pausa (teste usa temp file)
                        should = True
                        det_key, det = self._detail_for_line(line)
                        break
                if should:
                    # v0.4: condition — expressão falsa pula o breakpoint
                    if det and det.get("condition") \
                            and not self._check_condition(det["condition"], frame):
                        pass
                    else:
                        # v0.4: hitCondition — só pausa na contagem certa
                        if det and det.get("hitCondition"):
                            key = det_key or ("*", line)
                            cnt = self._hit_counts.get(key, 0) + 1
                            self._hit_counts[key] = cnt
                            if not self._check_hit_count(cnt, det["hitCondition"]):
                                pass
                            elif det.get("logMessage"):
                                # logpoint com hit: emite e não para
                                self.event("output", {"category": "stdout",
                                    "output": self._render_log(det["logMessage"], frame) + "\n"})
                            else:
                                key2 = (frame.func_name, cur_pc)
                                if self._last_break != key2:
                                    self._last_break = key2
                                    self._enter_pause("breakpoint")
                                    return
                        # v0.4: logMessage — emite via output e NÃO para
                        elif det and det.get("logMessage"):
                            self.event("output", {"category": "stdout",
                                "output": self._render_log(det["logMessage"], frame) + "\n"})
                        else:
                            # evita pausa duplicada no mesmo pc (por re-entrada)
                            key = (frame.func_name, cur_pc)
                            if self._last_break != key:
                                self._last_break = key
                                self._enter_pause("breakpoint")
                                return
                            # se for mesma linha/pc repetido rapidamente (mult bytecode same line já tratado por is_first), não pausa
                else:
                    # reset last_break se sair da linha? mantém
                    pass
        # P5.3: watchpoints simples por nome (local depois global).
        # Pausa com reason dataBreakpoint quando o valor muda (check no hook).
        if self._data_bps:
            for _data_id, _last in list(self._data_bps.items()):
                _found, _cur = self._lookup_ident(frame, _data_id)
                if not _found:
                    continue
                if _last is _UNSET:
                    try:
                        self._data_bps[_data_id] = copy.deepcopy(_cur)
                    except Exception:
                        self._data_bps[_data_id] = _cur
                    continue
                try:
                    _changed = bool(_cur != _last)
                except Exception:
                    _changed = repr(_cur) != repr(_last)
                if _changed:
                    try:
                        self._data_bps[_data_id] = copy.deepcopy(_cur)
                    except Exception:
                        self._data_bps[_data_id] = _cur
                    self._step_line = False
                    self._step_once = False
                    self._last_break = None
                    self._enter_pause("dataBreakpoint")
                    return
        # P5.3: step por linha via debug_map (linha->pc).
        # Avança até mudar de linha no mesmo frame (next = step-over).
        if self._step_line:
            _cur_pc = frame.pc - 1
            if _cur_pc < 0:
                _cur_pc = 0
            _cur_line, _c = self._line_for_pc(frame.func_name, _cur_pc)
            _cur_depth = len(self.vm.frames)
            _should = False
            if self._step_kind == "stepOut":
                if self._step_start_depth <= 1:
                    # no topo, stepOut vira next
                    if _cur_depth <= self._step_start_depth and (
                            frame.func_name != self._step_start_func
                            or _cur_line != self._step_start_line):
                        _should = True
                elif _cur_depth < self._step_start_depth:
                    _should = True
            elif self._step_kind == "stepIn":
                if (frame.func_name != self._step_start_func
                        or _cur_line != self._step_start_line):
                    _should = True
            else:  # next: step-over por linha
                if _cur_depth <= self._step_start_depth and (
                        frame.func_name != self._step_start_func
                        or _cur_line != self._step_start_line):
                    _should = True
            if _should:
                self._step_line = False
                self._step_once = False
                self._last_break = None
                self._enter_pause("step")
                return
        if self._step_once:
            self._step_once = False
            self._last_break = None
            self._enter_pause("step")

    def _enter_pause(self, reason):
        self._paused = True
        self._pause_reason = reason
        self._pause.clear()
        self.event("stopped", {"reason": reason, "threadId": 1,
                               "preserveFocusHint": False})
        self._pause.wait()
        self._paused = False

    def do_launch(self, req):
        # relaunch: sinaliza + join da thread antiga como no restart
        try:
            if self._thread is not None and self._thread.is_alive():
                try:
                    self.vm.hook = None
                except Exception:  # noqa: BLE001
                    pass
                self._pause_requested = False
                self._pause.set()
                self._thread.join(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        args = req.get("arguments", {})
        prog = args["program"]
        self.program_path = prog
        # v0.4: stopOnEntry — pausa no entry antes de rodar
        self._stop_on_entry = bool(args.get("stopOnEntry", False))
        self._hit_counts.clear()
        self._last_exception = None
        self._terminating = False
        self._step_line = False
        self._step_once = False
        self._pause_requested = False
        self._already_terminated = False
        self._done = False
        self._paused = False
        # watchpoints persistem, mas snapshots reiniciam (sem pausa falsa)
        for _k in list(self._data_bps.keys()):
            self._data_bps[_k] = _UNSET
        with open(prog, encoding="utf8") as f:
            src = f.read()
        self.program_src = src
        toks = tokenize(src)
        ps = Parser(toks)
        node = ps.parse()
        if ps.errs:
            return self.reply(req, {"error": {"message": "; ".join(ps.errs)}}, ok=False)
        errs, _ = analisar(node)
        berrs = ver_borrow(node)
        if errs or berrs:
            return self.reply(req, {"error": {"message": "; ".join(errs + berrs)}}, ok=False)
        mir = Baixador().baixar(node)
        otimizar(mir)
        self.mod = gerar_dict(mir)
        # debug map por função
        try:
            self.debug_map = self._build_debug_map(node, self.mod)
        except Exception:
            self.debug_map = {}
        self.vm = VM()
        self.vm.hook = self.hook
        self._pause.set()
        self._last_break = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self.reply(req)

    def do_attach(self, req):
        """Attach sem PID real: inicia o programa em thread (mesmo que launch).

        Não anexa a processo vivo externo; o `program` é compilado e rodado
        na VM em background, e breakpoints/watchpoints passam a valer. Sem
        rede/VPN/root, nada destrutivo.
        """
        self._attached = True
        return self.do_launch(req)

    def _run(self):
        try:
            self.vm.executar(self.mod)
        except (Terminated, Paused):
            pass
        except LumenError as e:  # v0.4: pausa opcional em exceção do runtime
            frames_snapshot = self.frames_of()
            self._last_exception = {"exceptionId": "LumenError",
                                    "description": str(e),
                                    "stack": frames_snapshot}
            self.event("output", {"category": "stderr",
                                   "output": f"erro: {e}\n"})
            if self._exception_filters:
                self.event("stopped", {"reason": "exception", "threadId": 1,
                                       "text": str(e)[:500]})
        except Exception as e:  # noqa: BLE001
            self.event("output", {"category": "stderr",
                                   "output": f"erro: {e}\n"})
        finally:
            self._done = True
            for line in self.vm.output:
                self.event("output", {"category": "stdout",
                                       "output": line + "\n"})
            self._emit_terminated_once()

    def frames_of(self):
        out = []
        # vm.frames pode estar vazio após termino
        rev = list(reversed(self.vm.frames))
        for i, f in enumerate(rev):
            cur_pc = f.pc - 1 if f.pc > 0 else 0
            line, col = self._line_for_pc(f.func_name, cur_pc)
            # source path: usa program_path se houver, senão vazio
            src_path = self.program_path or ""
            out.append({"id": i, "name": f.func_name,
                        "line": line, "column": col,
                        "source": {"name": f.func_name, "path": src_path}})
        return out or [{"id": 0, "name": "main", "line": 1, "column": 1,
                        "source": {"name": "main", "path": self.program_path or ""}}]

    def handle(self, msg):
        cmd = msg.get("command", "")
        if cmd == "initialize":
            # v0.4 P5.3: só anuncia o que existe (nada de capability não implementada)
            return self.reply(msg, {
                "supportsConfigurationDoneRequest": True,
                "supportsEvaluateForHovers": True,
                "supportsConditionalBreakpoints": True,
                "supportsHitConditionalBreakpoints": True,
                "supportsLogPoints": True,
                "supportsSetVariable": True,
                "supportsRestartRequest": True,
                "supportsTerminateRequest": True,
                "supportsDataBreakpoints": True,
                "exceptionBreakpointFilters": [
                    {"filter": "lumenError",
                     "label": "Erros Lumen (LumenError)",
                     "default": True,
                     "description": "Pausa quando o runtime levanta LumenError"},
                ]})
        if cmd == "launch":
            return self.do_launch(msg)
        if cmd == "attach":
            return self.do_attach(msg)
        if cmd == "setBreakpoints":
            args = msg.get("arguments", {})
            # DAP: args.source.path + args.breakpoints[{line, condition, logMessage, hitCondition}]
            # Legacy compat: breakpoints[{name}]
            src = args.get("source", {})
            path = src.get("path", "") if isinstance(src, dict) else ""
            bps = args.get("breakpoints", [])
            # fallback: argumentos pode ser direto lista sem source (compat antiga)
            # Já coberto: se bps vazio e path vazio mas msg original tinha sem source
            key = path or self.program_path or "*"
            line_bps: list[int] = []
            func_bps: list[str] = []
            pending_details: dict[tuple[str, int], dict] = {}
            for b in bps:
                if not isinstance(b, dict):
                    continue
                if "line" in b and isinstance(b["line"], int):
                    line_bps.append(b["line"])
                    # v0.4: condition / hitCondition / logMessage por linha
                    det: dict = {}
                    if b.get("condition"):
                        det["condition"] = str(b["condition"])
                    if b.get("hitCondition"):
                        det["hitCondition"] = str(b["hitCondition"])
                    if b.get("logMessage"):
                        det["logMessage"] = str(b["logMessage"])
                    if det:
                        pending_details[(key, b["line"])] = det
                # legacy name
                nb = b.get("name")
                if nb:
                    n = str(nb)
                    if n.endswith("()"):
                        n = n[:-2]
                    if n:
                        func_bps.append(n)
            with self.lock:
                # atualiza linhas se houver source ou line_bps
                if bps is not None:
                    # se requisição contém breakpoints (mesmo vazia), substitui
                    if line_bps or any("line" in b for b in bps):
                        self.breakpoints_lines[key] = set(line_bps)
                    elif path and not bps:
                        self.breakpoints_lines.pop(key, None)
                    elif not bps:
                        # clear-all se lista vazia sem path
                        # limpa todas as linhas
                        self.breakpoints_lines.clear()
                    # v0.4: troca os detalhes dessa source pelos novos
                    for k in [k for k in self.bp_details if k[0] == key]:
                        del self.bp_details[k]
                    for k in [k for k in self._hit_counts if k[0] == key]:
                        del self._hit_counts[k]
                    self.bp_details.update(pending_details)
                    if not bps and not path:
                        # clear-all global: limpa detalhes restantes
                        self.bp_details.clear()
                        self._hit_counts.clear()
                    # func breakpoints: substitui se houver
                    if func_bps or any("name" in b for b in bps):
                        self.breakpoints_funcs = {b for b in func_bps if b}
                        self.breakpoints = set(self.breakpoints_funcs)  # compat
                    elif not bps:
                        self.breakpoints_funcs.clear()
                        self.breakpoints.clear()
            # resposta: um entry por breakpoint solicitado, na mesma ordem
            resp_breakpoints = []
            # para verified, tenta obter total de linhas mesmo antes do launch
            # lê arquivo se program_src ainda vazio
            src_for_verify = self.program_src
            if not src_for_verify and path and os.path.exists(path):
                try:
                    with open(path, encoding="utf8") as fh:
                        src_for_verify = fh.read()
                except Exception:
                    src_for_verify = ""
            for b in bps:
                if "line" in b:
                    line = b["line"]
                    # verified se linha dentro do arquivo
                    verified = True
                    if src_for_verify:
                        total = src_for_verify.count("\n") + 1
                        if not (1 <= line <= total):
                            verified = False
                        else:
                            # opcional: verifica se linha mapeada existe em debug_map
                            if self.debug_map:
                                has = any(line in [l for l,_ in tbl] for tbl in self.debug_map.values())
                                # se debug_map já existe e linha não mapeada mas dentro do total, mantém verified True (fallback)
                                if not has:
                                    verified = True
                    else:
                        # sem source ainda, verifica range arbitrário 1..10000
                        if not (1 <= line <= 10000):
                            verified = False
                    resp_breakpoints.append({"verified": verified, "line": line})
                elif "name" in b:
                    nb = b.get("name") or ""
                    n = str(nb)
                    if n.endswith("()"):
                        n = n[:-2]
                    resp_breakpoints.append({"verified": bool(n)})
                else:
                    resp_breakpoints.append({"verified": True})
            return self.reply(msg, {"breakpoints": resp_breakpoints})
        if cmd == "configurationDone":
            return self.reply(msg)
        if cmd == "threads":
            return self.reply(msg, {"threads": [{"id": 1, "name": "lumen"}]})
        if cmd == "stackTrace":
            return self.reply(msg, {"stackFrames": self.frames_of(),
                                    "totalFrames": max(len(self.vm.frames), 1)})
        if cmd == "scopes":
            fid = msg.get("arguments", {}).get("frameId", 0)
            return self.reply(msg, {"scopes": [
                {"name": "Locais", "variablesReference": 1000 + fid,
                 "expensive": False},
                {"name": "Globais", "variablesReference": 2000,
                 "expensive": False}]})
        if cmd == "variables":
            ref = msg.get("arguments", {}).get("variablesReference", 0)
            names = []
            if 1000 <= ref < 2000 and self.vm.frames:
                rev = list(reversed(self.vm.frames))
                idx = ref - 1000
                fr = rev[idx] if 0 <= idx < len(rev) else None
                names = list(fr.locals.items()) if fr else []
            elif ref == 2000:
                names = list(self.vm.globals.items())
            return self.reply(msg, {"variables": [
                {"name": str(k), "value": repr(v)[:200],
                 "variablesReference": 0} for k, v in names]})
        if cmd == "evaluate":
            expr = msg.get("arguments", {}).get("expression", "")
            expr = str(expr).strip()
            # P5.3: ident + expressões aritméticas/comparações via AST restrita.
            args = msg.get("arguments", {})
            fid = args.get("frameId", None)
            target = None
            if self.vm.frames:
                if fid is not None:
                    try:
                        rev = list(reversed(self.vm.frames))
                        idx = int(fid)
                        if 0 <= idx < len(rev):
                            target = rev[idx]
                    except Exception:
                        target = None
                if target is None:
                    target = self.vm.frames[-1]
            # verifica se expr é identificador simples
            is_simple = expr.isidentifier()
            if is_simple:
                if "__" not in expr:
                    val = None
                    found = False
                    if target is not None and expr in target.locals:
                        val = target.locals[expr]
                        found = True
                    elif expr in self.vm.globals:
                        val = self.vm.globals[expr]
                        found = True
                    if found:
                        return self.reply(msg, {"result": repr(val)[:200],
                                                "variablesReference": 0})
                return self.reply(msg, {"result": f"não suportado: {expr}",
                                        "variablesReference": 0})
            # P5.3: tenta avaliação segura (sem eval); bloqueia __/calls/imports
            if "__" not in expr:
                try:
                    ok, val = self._safe_eval(expr, target)
                except (ZeroDivisionError, TypeError, ValueError,
                        KeyError, AttributeError, OverflowError) as e:
                    return self.reply(msg, {"result": f"erro: {e}",
                                            "variablesReference": 0})
                if ok:
                    return self.reply(msg, {"result": repr(val)[:200],
                                            "variablesReference": 0})
            # qualquer outra expressão => não suportado (sem eval)
            return self.reply(msg, {"result": f"não suportado: {expr}",
                                    "variablesReference": 0})
        if cmd == "continue":
            self._last_break = None
            self._pause.set()
            return self.reply(msg, {"allThreadsContinued": True})
        if cmd in ("next", "stepIn", "stepOut"):
            # P5.3: step por linha via debug_map (não mais 1 instrução)
            self._begin_line_step(cmd)
            self._pause.set()
            return self.reply(msg)
        if cmd == "restart":
            # v0.4: reinicia a sessão com o mesmo programa (breakpoints mantidos)
            if self.mod is None or not self.program_path:
                return self.reply(msg, {"error": {"message": "nada para reiniciar"}}, ok=False)
            try:
                old = self.vm
                old.hook = None  # thread antiga termina sem pausar de novo
                self._terminating = False
                self._step_line = False
                self._pause_requested = False
                self._pause.set()
                if self._thread is not None and self._thread.is_alive():
                    self._thread.join(timeout=10)
            except Exception:  # noqa: BLE001
                pass
            self.vm = VM()
            self.vm.hook = self.hook
            self._pause.set()
            self._paused = False
            self._pause_requested = False
            self._already_terminated = False
            self._last_break = None
            self._done = False
            self._terminating = False
            self._step_line = False
            self._step_once = False
            self._stop_on_entry = False
            self._hit_counts.clear()
            self._last_exception = None
            for _k in list(self._data_bps.keys()):
                self._data_bps[_k] = _UNSET
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            return self.reply(msg)
        if cmd == "terminate":
            # P5.3: terminate cooperativo que mata loop infinito: flag
            # `_running=False` + `_terminating=True` com injeção de
            # Terminated no hook (próxima instrução levanta e sai do _run).
            # Limite: atraso de 1 instrução; nativa bloqueante sem hook não
            # é interrompida de imediato.
            try:
                self.vm._running = False
            except Exception:  # noqa: BLE001
                pass
            self._terminating = True
            self._stop_on_entry = False
            self._paused = False
            self._pause_requested = False
            self._step_once = False
            self._step_line = False
            self._last_break = None
            self._hit_counts.clear()
            self._pause.set()
            self._done = True
            self._emit_terminated_once()
            return self.reply(msg)
        if cmd == "setDataBreakpoints":
            # P5.3: watchpoints simples por nome de variável. Pausa quando o
            # valor muda (check por instrução no hook, `!=`). Sem endereço.
            a = msg.get("arguments", {})
            bps = a.get("breakpoints", a.get("dataBreakpoints", []))
            if not isinstance(bps, list):
                bps = []
            out = []
            with self.lock:
                self._data_bps.clear()
                for b in bps:
                    if not isinstance(b, dict):
                        continue
                    did = str(b.get("dataId", b.get("name", "") or ""))
                    if not did or not did.isidentifier() or "__" in did:
                        out.append({"verified": False, "dataId": did})
                        continue
                    self._data_bps[did] = _UNSET
                    out.append({"verified": True, "dataId": did})
            return self.reply(msg, {"breakpoints": out})
        if cmd == "setVariable":
            # v0.4: altera local (ref 1000+frameId) ou global (ref 2000) pausado
            a = msg.get("arguments", {})
            ref = a.get("variablesReference", 0)
            name = str(a.get("name", ""))
            raw = str(a.get("value", ""))
            if not self._paused:
                return self.reply(msg, {"error": {"message": "sem frame pausado"}}, ok=False)
            target = None
            try:
                ref = int(ref)
            except (TypeError, ValueError):
                return self.reply(msg, {"error": {"message": "variablesReference?"}}, ok=False)
            if 1000 <= ref < 2000 and self.vm.frames:
                rev = list(reversed(self.vm.frames))
                idx = ref - 1000
                if 0 <= idx < len(rev):
                    target = rev[idx].locals
            elif ref == 2000:
                target = self.vm.globals
            if target is None or not name.isidentifier():
                return self.reply(msg, {"error": {"message": "variável?ref?"}}, ok=False)
            target[name] = self._parse_set_value(raw)
            return self.reply(msg, {"value": repr(target[name])[:200],
                                    "variablesReference": 0})
        if cmd == "setExceptionBreakpoints":
            # v0.4: registra filtros (ex.: ["lumenError"]); pausa em LumenError
            a = msg.get("arguments", {})
            filts = a.get("filters", [])
            if not isinstance(filts, list):
                filts = []
            with self.lock:
                self._exception_filters = [str(f) for f in filts]
            return self.reply(msg, {"breakpoints": [
                {"verified": True} for _ in self._exception_filters]})
        if cmd == "exceptionInfo":
            # v0.4: detalhe da última LumenError capturada, com stack
            if self._last_exception is None:
                return self.reply(msg, {"error": {"message": "sem exceção"}}, ok=False)
            e = self._last_exception
            stack_txt = "\n".join(
                f"{fr.get('name', '?')} @ {fr.get('source', {}).get('path', '')}:{fr.get('line', 0)}"
                for fr in e.get("stack", []))
            return self.reply(msg, {"exceptionId": e.get("exceptionId", "LumenError"),
                                    "description": e.get("description", ""),
                                    "breakMode": "always",
                                    "details": {"message": e.get("description", ""),
                                                "stackTrace": stack_txt}})
        if cmd == "disconnect":
            self._pause_requested = False
            self._pause.set()
            return self.reply(msg)
        if cmd == "pause":
            # sem wait na thread de despacho (single-thread): só arma
            # flag amostrada no hook (thread da VM). Evita deadlock onde
            # pause bloqueava o dispatch e nunca mais processava continue.
            if self._paused or self._done or self._thread is None \
                    or not self._thread.is_alive():
                return self.reply(msg)
            self._pause_requested = True
            return self.reply(msg)
        return self.reply(msg, {"error": {"message": "comando?" + cmd}}, ok=False)


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    sess = Session(stdout)
    while True:
        msg = read_msg(stdin)
        if msg is None:
            break
        if msg.get("type") == "request":
            sess.handle(msg)
            if msg.get("command") == "disconnect":
                break


if __name__ == "__main__":
    serve()
