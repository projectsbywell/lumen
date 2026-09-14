#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lumen-build — sistema de build do Lumen (Python puro, stdlib).

Lê lumen.toml:
  [package]   name, version, build = lista de tarefas padrão
  [tasks]     nome_tarefa = "comando"  ou
              nome_tarefa = { cmd = "...", deps = [...], inputs = [...],
                              outputs = [...], desc = "...", always = false,
                              ignore_errors = false, env = {...},
                              timeout = N }

Comportamento
-------------
  * monta grafo de tarefas a partir de `deps`, ordena topologicamente,
    detecta ciclos;
  * build incremental por hash de mtime+size dos inputs (e do hash das
    dependências): tarefas com estado idêntico são puladas;
  * executa comandos shell com cwd no diretório do projeto;
  * plugins em build_plugins/*.py (ou --plugins DIR): módulos podem definir
    before_build(ctx), before_task(ctx, task), after_task(ctx, task, status),
    after_build(ctx) e register_tasks(ctx) -> [ {nome: spec}, ... ].

Uso
---
  python3 lumen_build.py [tarefa...] [--file lumen.toml] [--dry-run]
                         [--clean] [--verbose] [--list] [--plugins DIR]
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None


class BuildError(Exception):
    pass


# ---------------------------------------------------------------------------
# fallback toml minimalista (Python < 3.11) — tables simples, arrays,
# inline tables, strings '', "" e valores básicos.
# ---------------------------------------------------------------------------

def _mini_toml(s):
    """Parser toml minimalista; equivalente funcional ao tomllib para a
    gramática usada pelos projetos Lumen."""
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r":
            i += 1
        elif c == "\n":
            toks.append(("NL", None))
            i += 1
        elif c == "#":
            while i < n and s[i] != "\n":
                i += 1
        elif c in "[]{}=,":
            toks.append((c, None))
            i += 1
        elif c in "\"'":
            quote = c
            j = i + 1
            buf = []
            while j < n:
                if s[j] == "\\" and j + 1 < n:
                    buf.append(s[j:j + 2])
                    j += 2
                    continue
                if s[j] == quote:
                    break
                buf.append(s[j])
                j += 1
            if j >= n:
                raise ValueError("string sem fechamento no toml")
            toks.append(("STR", "".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and s[j] not in " \t\r\n[]{}=,":
                j += 1
            toks.append(("BARE", s[i:j]))
            i = j
    toks.append(("EOF", None))

    def scalar(tok):
        kind, val = tok
        if kind == "STR":
            return _mini_unescape(val)
        if kind != "BARE":
            raise ValueError(f"valor inesperado: {tok}")
        if val == "true":
            return True
        if val == "false":
            return False
        try:
            return int(val)
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            pass
        return val

    def parse_value(pos):
        kind, val = toks[pos][0], toks[pos][1]
        if kind == "[":
            arr, pos = [], pos + 1
            while toks[pos][0] != "]":
                if toks[pos][0] == "NL":
                    pos += 1
                    continue
                v, pos = parse_value(pos)
                arr.append(v)
                if toks[pos][0] == ",":
                    pos += 1
            return arr, pos + 1
        if kind == "{":
            d, pos = {}, pos + 1
            while toks[pos][0] != "}":
                if toks[pos][0] in ("NL", ","):
                    pos += 1
                    continue
                k = toks[pos][1]
                if toks[pos + 1][0] != "=":
                    raise ValueError("inline table sem '='")
                v, pos = parse_value(pos + 2)
                d[k] = v
                if toks[pos][0] == ",":
                    pos += 1
            return d, pos + 1
        return scalar(toks[pos]), pos + 1

    def skip_nl(pos):
        while toks[pos][0] == "NL":
            pos += 1
        return pos

    root = {}
    table = root
    pos = 0
    while toks[pos][0] != "EOF":
        pos = skip_nl(pos)
        if toks[pos][0] == "EOF":
            break
        if toks[pos][0] == "[":
            pos += 1
            target = root
            parts = []
            while toks[pos][0] not in ("]", "NL", "EOF"):
                parts.append(toks[pos][1])
                pos += 1
                if toks[pos][0] == ".":
                    pos += 1
            if toks[pos][0] != "]":
                raise ValueError("table sem fechamento")
            pos += 1
            for part in parts:
                if part not in target or not isinstance(target[part], dict):
                    target[part] = {}
                target = target[part]
            table = target
            continue
        key = toks[pos][1]
        if toks[pos + 1][0] != "=":
            raise ValueError(f"chave sem '=': {key}")
        val, pos = parse_value(pos + 2)
        table[key] = val
    return root


def _mini_unescape(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append({"n": "\n", "t": "\t", "b": "\b", "\\": "\\",
                        '"': '"', "'": "'"}.get(n, n))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def load_toml(path):
    if tomllib is not None:
        with open(path, "rb") as f:
            return tomllib.load(f)
    return _mini_toml(Path(path).read_text(encoding="utf-8"))  # pragma: no cover


# ---------------------------------------------------------------------------
# grafo de tarefas
# ---------------------------------------------------------------------------

def normalize_tasks(tasks_raw):
    """Converte spec bruto do toml em dict de tarefas normalizadas."""
    out = {}
    for name, spec in (tasks_raw or {}).items():
        if isinstance(spec, str):
            task = {"cmd": spec}
        elif isinstance(spec, dict):
            task = dict(spec)
        else:
            raise BuildError(f"tarefa {name!r}: spec deve ser string ou tabela")
        cmd = task.get("cmd", "")
        if not isinstance(cmd, str) or not cmd.strip():
            raise BuildError(f"tarefa {name!r} sem 'cmd' válido")
        task["cmd"] = cmd
        task["deps"] = _as_list(task.get("deps"))
        task["inputs"] = _as_list(task.get("inputs"))
        task["outputs"] = _as_list(task.get("outputs"))
        task["always"] = bool(task.get("always", False))
        task["ignore_errors"] = bool(task.get("ignore_errors", False))
        task.setdefault("desc", "")
        task.setdefault("env", {})
        task.setdefault("timeout", None)
        if not isinstance(task["env"], dict):
            raise BuildError(f"tarefa {name!r}: 'env' deve ser tabela")
        for d in task["deps"]:
            if d not in tasks_raw and d != name:
                raise BuildError(f"tarefa {name!r} depende de tarefa "
                                 f"inexistente: {d!r}")
        out[name] = task
    return out


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    if isinstance(v, list):
        return [str(x) for x in v]
    raise BuildError(f"esperado string ou lista, recebido {type(v).__name__}")


def topo_order(tasks):
    """Ordenação topológica com detecção de ciclo. Raises BuildError."""
    order = []
    visiting = set()
    visited = set()

    def visit(name, path):
        if name in visited:
            return
        if name in visiting:
            cycle = path[path.index(name):] + [name]
            raise BuildError("ciclo de tarefas: " + " -> ".join(cycle))
        visiting.add(name)
        path.append(name)
        for d in tasks[name]["deps"]:
            visit(d, path)
        path.pop()
        visiting.discard(name)
        visited.add(name)
        order.append(name)

    for name in tasks:
        visit(name, [])
    return order


# ---------------------------------------------------------------------------
# estado / incremental
# ---------------------------------------------------------------------------

class BuildState:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / ".lumen" / "build_state.json"
        self.data = {"format": 1, "tasks": {}}

    def load(self):
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("format") == 1 and isinstance(data.get("tasks"), dict):
                    self.data = data
            except (OSError, ValueError):
                pass  # estado corrompido -> rebuild
        return self

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True),
                       encoding="utf-8")
        os.replace(tmp, self.path)

    def clear(self):
        self.data = {"format": 1, "tasks": {}}
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def get_hash(self, name):
        return self.data["tasks"].get(name, {}).get("hash")

    def set_hash(self, name, h, cmd=None):
        self.data["tasks"][name] = {"hash": h, "cmd": cmd or "",
                                    "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def _sig_path(root: Path, rel: str):
    """Assinatura mtime+size de arquivo, ou árvore recursiva para diretório."""
    full = root / rel
    if not full.exists():
        raise BuildError(f"input faltando: {rel}")
    if full.is_dir():
        parts = []
        for dp, dns, fns in os.walk(full):
            for fn in sorted(fns):
                p = Path(dp) / fn
                st = p.stat()
                parts.append((str(p.relative_to(full)), st.st_mtime_ns,
                              st.st_size))
        return ("dir", sorted(parts))
    st = full.stat()
    return ("file", st.st_mtime_ns, st.st_size)


def task_hash(task, root, state) -> str:
    """Hash de uma tarefa: cmd + inputs (mtime/size) + outputs + hash das
    dependências (a partir do estado já atualizado na iteração em ordem
    topológica)."""
    h = hashlib.sha256()
    h.update(task["cmd"].encode("utf-8"))
    for i in sorted(task["inputs"]):
        sig = _sig_path(root, i)
        h.update(b"in\x00" + i.encode("utf-8") + b"\x00" +
                 repr(sig).encode("utf-8"))
    for o in sorted(task["outputs"]):
        h.update(b"out\x00" + o.encode("utf-8"))
    for d in sorted(task["deps"]):
        prev = state.get_hash(d) or "?"
        h.update(b"dep\x00" + d.encode("utf-8") + b"\x00" + prev.encode())
    return h.hexdigest()


def is_up_to_date(task, name, current_hash, state, root) -> bool:
    rec = state.get_hash(name)
    if rec != current_hash:
        return False
    if task.get("always"):
        return False
    for o in task["outputs"]:
        if not (root / o).exists():
            return False
    return True


# ---------------------------------------------------------------------------
# plugins
# ---------------------------------------------------------------------------

HOOKS = ("before_build", "before_task", "after_task", "after_build",
         "register_tasks")


class BuildContext:
    def __init__(self, project_dir, config, state, dry_run=False,
                 verbose=False):
        self.project_dir = Path(project_dir)
        self.config = config
        self.state = state
        self.dry_run = dry_run
        self.verbose = verbose
        self.results = {}
        self.env = dict(os.environ)

    def log(self, msg, level="info"):
        if level == "debug" and not self.verbose:
            return
        print(f"[build] {msg}", flush=True)


def load_plugins(project_dir, extra_dirs=()):
    """Importa build_plugins/*.py do projeto + diretórios extras."""
    dirs = [Path(project_dir) / "build_plugins"]
    dirs += [Path(d) for d in (extra_dirs or ())]
    seen, mods = set(), []
    for d in dirs:
        if not d.is_dir():
            continue
        for py in sorted(d.glob("*.py")):
            key = py.name
            if key in seen:
                continue
            seen.add(key)
            fname = f"lumen_build_plugin_{py.stem}"
            try:
                spec = importlib.util.spec_from_file_location(fname, py)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mods.append(mod)
            except Exception as e:  # plugin ruim não derruba o build
                print(f"[build] aviso: plugin {py.name} falhou ao carregar: {e}",
                      file=sys.stderr)
    return mods


def run_hook(plugins, hook, **kw):
    for mod in plugins:
        fn = getattr(mod, hook, None)
        if not fn:
            continue
        try:
            fn(**kw)
        except Exception as e:
            print(f"[build] aviso: hook {hook} de {mod.__name__} falhou: {e}",
                  file=sys.stderr)


# ---------------------------------------------------------------------------
# execução
# ---------------------------------------------------------------------------

class BuildResult:
    def __init__(self):
        self.executed = []
        self.skipped = []
        self.dry_run_tasks = []
        self.failed_ignored = []
        self.by_task = {}

    def summarize(self):
        return {"executadas": len(self.executed),
                "puladas": len(self.skipped), "dry_run": len(self.dry_run_tasks)}


def _run_cmd(task, ctx: BuildContext):
    env = dict(ctx.env)
    env.update({str(k): str(v) for k, v in (task.get("env") or {}).items()})
    kwargs = dict(shell=True, cwd=str(ctx.project_dir), env=env)
    if task.get("timeout"):
        kwargs["timeout"] = float(task["timeout"])
    if ctx.verbose:
        proc = subprocess.run(task["cmd"], **kwargs)
    else:
        proc = subprocess.run(task["cmd"], capture_output=True, **kwargs)
    if proc.returncode != 0:
        tail = proc.stdout[-4000:].decode(errors="replace")
        if proc.stderr:
            tail += proc.stderr[-2000:].decode(errors="replace")
        raise BuildError(f"comando falhou (exit {proc.returncode}): "
                         f"{tail.strip()[:2000]}")
    return proc.returncode


def _prepare_outputs(task, root):
    for o in task["outputs"]:
        (root / o).parent.mkdir(parents=True, exist_ok=True)


def _clean_outputs(tasks, root):
    root = root.resolve()
    for name, task in tasks.items():
        for o in task["outputs"]:
            target = (root / o).resolve()
            if not str(target).startswith(str(root) + os.sep):
                raise BuildError(f"output fora do projeto: {o}")
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            elif target.exists():
                target.unlink()


def build_project(toml_path="lumen.toml", tasks=None, dry_run=False,
                  clean=False, extra_plugins=(), verbose=False,
                  no_plugins=False) -> BuildResult:
    """Executa o build do projeto. Retorna BuildResult."""
    toml_path = Path(toml_path)
    if not toml_path.is_file():
        raise BuildError(f"arquivo de build não encontrado: {toml_path}")
    root = toml_path.resolve().parent
    config = load_toml(toml_path)
    pkg = config.get("package", {}) or {}
    tasks_raw = config.get("tasks", {}) or {}
    if not tasks_raw:
        raise BuildError("nenhuma tarefa em [tasks]")

    plugins = [] if no_plugins else load_plugins(root, extra_plugins)
    ctx = BuildContext(root, config, BuildState(root), dry_run=dry_run,
                       verbose=verbose)

    # plugins podem registrar tarefas extras
    extra = []
    for mod in plugins:
        fn = getattr(mod, "register_tasks", None)
        if fn:
            try:
                registered = fn(ctx) or []
                for item in registered:
                    if isinstance(item, dict) and item:
                        extra.append(item)
            except Exception as e:
                print(f"[build] aviso: register_tasks de {mod.__name__} "
                      f"falhou: {e}", file=sys.stderr)
    for item in extra:
        tasks_raw = {**tasks_raw, **item}

    graph = normalize_tasks(tasks_raw)
    order = topo_order(graph)

    state = ctx.state
    if clean:
        _clean_outputs(graph, root)
        state.clear()

    request = set(tasks) if tasks else None
    if request:
        # inclui dependências transitivas das tarefas pedidas
        for name in list(request):
            if name not in graph:
                raise BuildError(f"tarefa inexistente: {name}")
            for d in graph[name]["deps"]:
                request.add(d)
    if pkg.get("build") and request is None:
        request = set(_as_list(pkg.get("build")))
        if not request <= set(graph):
            raise BuildError("build padrão de [package] referencia "
                             "tarefa inexistente")
    chosen = [t for t in order if t in (request or set(order))]

    if not dry_run:
        state.load()
    run_hook(plugins, "before_build", ctx=ctx)
    result = BuildResult()

    try:
        for name in chosen:
            task = graph[name]
            cur_hash = task_hash(task, root, state)
            if not dry_run and is_up_to_date(task, name, cur_hash, state, root):
                result.skipped.append(name)
                result.by_task[name] = "skipped"
                ctx.results[name] = "skipped"
                run_hook(plugins, "after_task", ctx=ctx, task=task,
                         status="skipped")
                ctx.log(f"{name}: ok (up-to-date)")
                continue
            if dry_run:
                result.dry_run_tasks.append(name)
                result.by_task[name] = "dry-run"
                ctx.results[name] = "dry-run"
                run_hook(plugins, "after_task", ctx=ctx, task=task,
                         status="dry-run")
                ctx.log(f"{name}: seria executada")
                continue
            run_hook(plugins, "before_task", ctx=ctx, task=task)
            _prepare_outputs(task, root)
            try:
                rc = _run_cmd(task, ctx)
            except BuildError:
                if task.get("ignore_errors"):
                    result.failed_ignored.append(name)
                    result.by_task[name] = "failed-ignored"
                    ctx.results[name] = "failed-ignored"
                    state.set_hash(name, "")  # nunca up-to-date
                    ctx.log(f"{name}: falhou (ignore_errors=true)")
                    continue
                raise
            state.set_hash(name, cur_hash, cmd=task["cmd"])
            result.executed.append(name)
            result.by_task[name] = "executed"
            ctx.results[name] = "executed"
            run_hook(plugins, "after_task", ctx=ctx, task=task,
                     status="executed")
            ctx.log(f"{name}: ok")
    finally:
        if not dry_run:
            state.save()
    run_hook(plugins, "after_build", ctx=ctx)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lumen-build",
                                 description="Sistema de build do Lumen")
    ap.add_argument("tasks", nargs="*", metavar="TAREFA",
                    help="tarefas a executar (padrão: todas / [package].build)")
    ap.add_argument("--file", default="lumen.toml", help="arquivo de config")
    ap.add_argument("--dry-run", action="store_true", help="apenas mostra")
    ap.add_argument("--clean", action="store_true",
                    help="remove outputs e estado antes de buildar")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--list", action="store_true",
                    help="lista tarefas em ordem topológica e sai")
    ap.add_argument("--plugins", action="append", default=[],
                    metavar="DIR", help="diretório extra de plugins")
    ap.add_argument("--no-plugins", action="store_true")
    args = ap.parse_args(argv)

    try:
        # --list não precisa executar nada
        toml_path = Path(args.file)
        if not toml_path.is_file():
            raise BuildError(f"arquivo não encontrado: {args.file}")
        config = load_toml(toml_path)
        graph = normalize_tasks(config.get("tasks", {}) or {})
        order = topo_order(graph)
        if args.list:
            for name in order:
                desc = graph[name].get("desc") or ""
                print(f"{name}" + (f"  # {desc}" if desc else ""))
            return 0
        extra = [] if args.no_plugins else args.plugins
        result = build_project(toml_path, tasks=args.tasks,
                               dry_run=args.dry_run, clean=args.clean,
                               extra_plugins=extra, verbose=args.verbose,
                               no_plugins=args.no_plugins)
        for name, status in result.by_task.items():
            print(f"  {name}: {status}")
        print(f"resumo: {result.summarize()}")
        return 1 if result.failed_ignored else 0
    except BuildError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("abortado", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())