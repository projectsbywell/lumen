#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lumen-pkg — gerenciador de pacotes do Lumen (Python puro, stdlib apenas).

Subcomandos
-----------
  init   [DIR]           cria um novo projeto (nome = basename do diretório)
  new    NOME [DIR]      cria um novo projeto com nome explícito
  add    NOME[@SPEC]     adiciona dependência a [dependencies]
  remove NOME            remove dependência
  resolve                resolve o grafo de dependências (MVS) e imprime
  install                resolve, baixa para o cache e escreve lumen.lock
  pack   [--out F]       empacota o projeto em .lumepkg (zip + manifesto)
  publish [--registry U] empacota e publica no registry
  verify ARQUIVO         verifica sha256 + assinatura HMAC de um .lumepkg
  audit                  audita lumen.lock (sha256 + HMAC) — OFFLINE por
                         design: usa apenas o cache local, sem rede e sem
                         opção --registry
  keygen                 gera chave HMAC demo em ~/.lumen/hmac.key
  keygen --tls [--dir D] gera cert+key self-signed DEV-ONLY (loopback), via
                         openssl; sem openssl grava script auxiliar

Semver suportado: ^ ~ = >= > <= <  *, 1.x, 1.2.x, intervalos com "," (AND)
e "||" (OR). Resolução por MVS (Minimal Version Selection).

Ambiente
--------
  LUMEN_HOME        raiz de usuário (padrão ~/.lumen)
  LUMEN_CACHE_DIR   cache de pacotes (padrão $LUMEN_HOME/cache)
  LUMEN_REGISTRY    URL padrão do registry
  LUMEN_HMAC_KEY    chave HMAC (hex), sobrescreve o arquivo de chave
  LUMEN_REGISTRY_TOKEN  token para PUT no registry
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from fnmatch import fnmatch
from functools import total_ordering
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

__version__ = "1.0.0"

DEFAULT_REGISTRY = "http://127.0.0.1:8765"
DEMO_HMAC_KEY = b"lumen-demo-hmac-key-2026"
MAX_RESOLVE_ITER = 2000


class PkgError(Exception):
    """Erro de domínio do lumen-pkg."""


class RegistryError(PkgError):
    pass


class ResolutionError(PkgError):
    pass


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------

def lumen_home() -> Path:
    return Path(os.environ.get("LUMEN_HOME", str(Path.home() / ".lumen")))


def cache_dir() -> Path:
    return Path(os.environ.get("LUMEN_CACHE_DIR", str(lumen_home() / "cache")))


def hmac_key_path() -> Path:
    return lumen_home() / "hmac.key"


def load_toml(path) -> dict:
    if tomllib is None:  # pragma: no cover
        raise PkgError("tomllib indisponível — Python 3.11+ é necessário")
    with open(path, "rb") as f:
        return tomllib.load(f)


def project_toml(project_dir: Path):
    p = Path(project_dir) / "lumen.toml"
    if not p.is_file():
        raise PkgError(f"{p} não encontrado (rode 'lumen-pkg init')")
    return p, load_toml(p)


def escape_toml(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def unescape_toml(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(n, n))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# semver
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(
    r"^[vV]?(\d+)\.(\d+)\.(\d+)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


@total_ordering
class SemVer:
    """Versão semver 2.0.0 (build metadata ignorada em precedência)."""

    __slots__ = ("major", "minor", "patch", "pre", "build")

    def __init__(self, major, minor, patch, pre=(), build=""):
        self.major = int(major)
        self.minor = int(minor)
        self.patch = int(patch)
        self.pre = tuple(str(p) for p in (pre or ()))
        self.build = str(build or "")

    @classmethod
    def parse(cls, s):
        m = _SEMVER_RE.match(str(s).strip())
        if not m:
            raise PkgError(f"versão semver inválida: {s!r}")
        pre = tuple(m.group(4).split(".")) if m.group(4) else ()
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                   pre, m.group(5) or "")

    @classmethod
    def try_parse(cls, s):
        try:
            return cls.parse(s)
        except PkgError:
            return None

    @property
    def is_prerelease(self):
        return bool(self.pre)

    def __str__(self):
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            s += "-" + ".".join(self.pre)
        if self.build:
            s += "+" + self.build
        return s

    def __repr__(self):
        return f"SemVer({self})"

    @staticmethod
    def _ident_key(i):
        return (0, int(i)) if i.isdigit() else (1, i)

    def _pre_key(self):
        # sem pre-release == release (maior que qualquer pré-release)
        if not self.pre:
            return (1,)
        return (0, tuple(self._ident_key(x) for x in self.pre))

    def key(self):
        return (self.major, self.minor, self.patch, self._pre_key())

    def __eq__(self, other):
        if not isinstance(other, SemVer):
            return NotImplemented
        return self.key() == other.key()

    def __hash__(self):
        return hash(self.key())

    def __lt__(self, other):
        if not isinstance(other, SemVer):
            return NotImplemented
        return self.key() < other.key()


def as_versions(seq):
    """Converte sequência mista (str/SemVer) em lista ordenada de SemVer."""
    out = []
    for v in seq:
        if isinstance(v, SemVer):
            out.append(v)
        else:
            sv = SemVer.try_parse(str(v))
            if sv:
                out.append(sv)
    return sorted(out)


def min_satisfying(versions, spec):
    """Menor versão (MVS) que satisfaz o spec, ou None."""
    r = spec if isinstance(spec, Range) else Range(spec)
    for v in as_versions(versions):
        if r.matches(v):
            return v
    return None


# ---------------------------------------------------------------------------
# ranges / specs
# ---------------------------------------------------------------------------

_RANGE_VER = re.compile(
    r"""
    ^[vV]?
    (?P<maj>\d+)
    (?:\.(?P<min>\d+|[xX*]))?
    (?:\.(?P<pat>\d+|[xX*]))?
    (?P<pre>-[0-9A-Za-z.-]+)?
    (?P<build>\+[0-9A-Za-z.-]+)?
    $
    """, re.VERBOSE)

_RANGE_ATOM = re.compile(
    r"""
    ^\s*(?P<op>\^|~|>=|<=|>|<|=)?\s*
    (?P<ver>[vV]?\d+\.\d+\.(?:[xX*])
          |[vV]?\d+\.(?:[xX*])
          |[vV]?\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?
          |[*xX])
    \s*$
    """, re.VERBOSE)


def _sat(op, v, ref):
    if op == "=":
        return v == ref
    if op == ">=":
        return v >= ref
    if op == ">":
        return v > ref
    if op == "<=":
        return v <= ref
    if op == "<":
        return v < ref
    return True


class Range:
    """Intervalo semver. ',' = AND, '||' = OR, espaços entre comparadores = AND.

    Exemplos: "^1.2.3", "~1.2", "=1.2.3", ">=1.0.0 <2.0.0", "1.2.x",
              "^1.0.0 || ^2.0.0", "*".
    """

    def __init__(self, raw):
        self.raw = (raw or "").strip()
        self.groups = []  # OR de grupos; cada grupo = [(op, SemVer), ...]
        if not self.raw:
            raise PkgError("spec vazio (use '*' para qualquer versão)")
        for alt in re.split(r"\s*\|\|\s*", self.raw):
            group = []
            for atom in self._split_and(alt):
                m = _RANGE_ATOM.match(atom)
                if not m:
                    raise PkgError(f"spec inválido: {self.raw!r} (átomo {atom!r})")
                group.extend(self._expand(m.group("op") or "", m.group("ver")))
            # group vazio = "casa qualquer versão" (ex.: "*")
            self.groups.append(group)

    @staticmethod
    def _split_and(s):
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if len(parts) > 1:
            return parts
        if " " in s:
            sp = [p.strip() for p in s.split() if p.strip()]
            if sp and all(_RANGE_ATOM.match(p) for p in sp):
                return sp
        return parts or [s]

    @staticmethod
    def _range_ver(ver):
        return _RANGE_VER.match(ver)

    def _expand(self, op, ver):
        """Expande um átomo de range em comparadores (op, SemVer)."""
        v = ver.strip()
        if v in ("*", "x", "X"):
            if op in ("^", "~"):
                raise PkgError(f"operador '{op}' não combina com wildcard em {self.raw!r}")
            if op in ("", "="):
                return []  # casa qualquer versão
            return [(op, SemVer(0, 0, 0))]
        m = self._range_ver(v)
        if not m:
            raise PkgError(f"spec inválido: {self.raw!r} (versão {ver!r})")
        maj = int(m.group("maj"))
        min_s, pat_s = m.group("min"), m.group("pat")
        minor = 0 if min_s in (None, "x", "X", "*") else int(min_s)
        patch = 0 if pat_s in (None, "x", "X", "*") else int(pat_s)
        has_min = min_s not in (None, "x", "X", "*")
        has_pat = pat_s not in (None, "x", "X", "*")
        full = has_min and has_pat
        pre = tuple((m.group("pre") or "")[1:].split(".")) if m.group("pre") else ()
        base = SemVer(maj, minor, patch, pre)
        if pre and not full:
            raise PkgError(f"pré-release exige versão completa: {ver!r}")

        if op in ("", "="):
            if full:
                return [("=", base)]
            if has_min:
                return [(">=", SemVer(maj, minor, 0)), ("<", SemVer(maj, minor + 1, 0))]
            return [(">=", SemVer(maj, 0, 0)), ("<", SemVer(maj + 1, 0, 0))]
        if op == "^":
            return self._caret(base)
        if op == "~":
            if full:
                return [(">=", base), ("<", SemVer(maj, minor + 1, 0))]
            if has_min:
                return [(">=", SemVer(maj, minor, 0)), ("<", SemVer(maj, minor + 1, 0))]
            return [(">=", SemVer(maj, 0, 0)), ("<", SemVer(maj + 1, 0, 0))]
        if op in (">=", ">", "<=", "<"):
            return [(op, base)]
        raise PkgError(f"operador inválido {op!r} em {self.raw!r}")

    @staticmethod
    def _caret(base):
        if base.major > 0:
            return [(">=", base), ("<", SemVer(base.major + 1, 0, 0))]
        if base.minor > 0:
            return [(">=", base), ("<", SemVer(0, base.minor + 1, 0))]
        if base.patch > 0:
            return [(">=", base), ("<", SemVer(0, 0, base.patch + 1))]
        return []

    def matches(self, v):
        if not isinstance(v, SemVer):
            sv = SemVer.try_parse(str(v))
            if sv is None:
                return False
            v = sv
        for group in self.groups:
            if all(_sat(op, v, ref) for op, ref in group):
                return True
        return False

    def __repr__(self):
        return f"Range({self.raw!r})"


# ---------------------------------------------------------------------------
# lockfile (toml-like simples)
# ---------------------------------------------------------------------------

def parse_scalar(s):
    s = s.strip()
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return unescape_toml(s[1:-1])
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1]
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s  # valor "bare"


def dump_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return f'"{escape_toml(str(v))}"'


def _lock_sections(text):
    """Retorna (sections, kv_root) do formato toml-like do lockfile."""
    sections, current, root = [], None, {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[[") and line.endswith("]]"):
            current = {"_header": line[2:-2].strip(), "_kv": {}}
            sections.append(current)
        elif line.startswith("["):
            current = {"_header": line[1:-1].strip(), "_kv": {}}
            sections.append(current)
        elif "=" in line and current is not None:
            k, v = line.split("=", 1)
            current["_kv"][k.strip()] = parse_scalar(v)
        elif "=" in line:
            k, v = line.split("=", 1)
            root[k.strip()] = parse_scalar(v)
    return sections, root


def read_lockfile(path) -> dict:
    """Lê lumen.lock → {"lockfile-version": str, "packages": [dict, ...]}"""
    p = Path(path)
    if not p.is_file():
        raise PkgError(f"lockfile não encontrado: {p}")
    sections, root = _lock_sections(p.read_text(encoding="utf-8"))
    packages = [sec["_kv"] for sec in sections if sec["_header"] == "package"]
    return {"lockfile-version": root.get("lockfile-version", "1.0"),
            "packages": packages}


def write_lockfile(path, packages, lockfile_version="2.0"):
    """Escreve lumen.lock no formato toml-like simples (v2.0).

    Cada [[package]] guarda o grafo resolvido por aresta: `deps` lista
    `nome@versão-resolvida` (não specs), mais `sha256` (digest da árvore)
    e `artifact` (sha256 do .lumepkg baixado, quando houver).
    """
    lines = [f"# lumen.lock — gerado por lumen-pkg",
              f'lockfile-version = "{lockfile_version}"', ""]
    for pkg in packages:
        lines.append("[[package]]")
        for k in ("name", "version", "sha256", "artifact", "source", "deps"):
            if k in pkg and pkg[k] not in (None, ""):
                lines.append(f"{k} = {dump_scalar(pkg[k])}")
        lines.append("")
    Path(path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _parse_lock_deps(deps) -> list[tuple[str, str]]:
    """`deps` do lock -> [(nome, versão)] (formato v2: nome@versão exata)."""
    out = []
    for part in str(deps or "").split(";"):
        part = part.strip()
        if not part or "@" not in part:
            continue
        n, _, v = part.partition("@")
        out.append((n.strip(), v.strip()))
    return out


def validate_lock(root_deps, lock_path) -> tuple[bool, list[str]]:
    """Valida um lumen.lock contra as deps raiz atuais.

    Retorna (ok, problemas). Locks legados (v1, com specs em `deps`)
    são considerados obsoletos e forçam re-resolução (migração p/ v2).
    """
    problems: list[str] = []
    try:
        lock = read_lockfile(lock_path)
    except PkgError as e:
        return False, [str(e)]
    if str(lock.get("lockfile-version", "1.0")) != "2.0":
        return False, [f"lockfile legado (versão "
                       f"{lock.get('lockfile-version', '?')}); re-resolva"]
    by_name = {p.get("name"): p
               for p in lock.get("packages", []) if p.get("name")}
    for n, spec in (root_deps or {}).items():
        e = by_name.get(str(n))
        if e is None:
            problems.append(f"dependência raiz `{n}` ausente no lock")
            continue
        try:
            locked_ver = SemVer.parse(str(e.get("version", "0")))
            if not Range(str(spec)).matches(locked_ver):
                problems.append(f"`{n}`: lock tem {e.get('version')}, "
                                f"spec pede `{spec}`")
        except PkgError as ex:
            problems.append(f"`{n}`: versão/spec inválidos ({ex})")
    for p in lock.get("packages", []):
        for dname, dver in _parse_lock_deps(p.get("deps", "")):
            try:
                SemVer.parse(dver)  # aresta v2 exige versão exata
            except PkgError:
                problems.append(f"`{p.get('name')}`: aresta legada "
                                f"`{dname}@{dver}` (sem versão resolvida)")
                continue
            e2 = by_name.get(dname)
            if e2 is None:
                problems.append(f"`{p.get('name')}`: aresta para "
                                f"`{dname}@{dver}` fora do lock")
            elif str(e2.get("version")) != dver:
                problems.append(f"`{p.get('name')}`: aresta `{dname}@{dver}` "
                                f"diverge do lock ({e2.get('version')})")
    return (not problems), problems


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

class Cache:
    """Cache local em <root>/<nome>/<versao> (extraído) + <versao>.lumepkg."""

    def __init__(self, root=None):
        self.root = Path(root or cache_dir())

    def package_dir(self, name, version):
        return self.root / name / str(version)

    def archive_path(self, name, version):
        return self.root / name / f"{version}.lumepkg"

    def has_dir(self, name, version):
        return (self.package_dir(name, version) / "lumen.toml").is_file()

    def has_archive(self, name, version):
        return self.archive_path(name, version).is_file()

    def available_versions(self, name):
        base = self.root / name
        vers = set()
        if base.is_dir():
            for p in sorted(base.iterdir()):
                if p.is_dir() and (p / "lumen.toml").is_file():
                    sv = SemVer.try_parse(p.name)
                    if sv:
                        vers.add(sv)
                elif p.is_file() and p.suffix == ".lumepkg":
                    sv = SemVer.try_parse(p.stem)
                    if sv:
                        vers.add(sv)
        return sorted(vers)

    def store_archive(self, name, version, data: bytes) -> str:
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{version}.lumepkg").write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def extract(self, name, version) -> Path:
        dest = self.package_dir(name, version)
        if self.has_dir(name, version):
            return dest
        ap = self.archive_path(name, version)
        if not ap.is_file():
            raise PkgError(f"sem arquivo em cache: {name}@{version}")
        tmp = Path(tempfile.mkdtemp(prefix="lumen-extract-"))
        try:
            with zipfile.ZipFile(ap) as zf:
                safe_extract(zf, tmp)
            if not (tmp / "lumen.toml").is_file():
                raise PkgError(f"{name}@{version} não contém lumen.toml")
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp), str(dest))
        finally:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
        return dest


def safe_extract(zf: zipfile.ZipFile, dest: Path):
    """Extrai zip sem permitir path traversal."""
    dest = dest.resolve()
    for member in zf.infolist():
        name = member.filename
        if name.startswith("/") or ".." in Path(name).parts:
            raise PkgError(f"entrada insegura no zip: {name!r}")
        target = (dest / name).resolve()
        if not str(target).startswith(str(dest) + os.sep) and target != dest:
            raise PkgError(f"entrada fora do destino: {name!r}")
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)


# ---------------------------------------------------------------------------
# registry client
# ---------------------------------------------------------------------------

def _host_permite_http(host: str) -> bool:
    return (host or "").lower() in ("localhost", "127.0.0.1", "::1")


class RegistryClient:
    """Cliente do registry HTTP do Lumen (PUT/GET /pkg/<n>/<v>, GET /index).

    v0.2: exige HTTPS, exceto loopback (localhost/127.0.0.1/::1) ou
    LUMEN_ALLOW_INSECURE=1 (redes locais de teste).
    v0.4: insecure=True (flag --insecure ou LUMEN_ALLOW_INSECURE=1) também
    desce a verificação TLS para https dev-only (cert self-signed loopback):
    usa ssl._create_unverified_context() nas chamadas _req. Sem insecure,
    a verificação padrão permanece — cert self-signed falha com
    RegistryError (registro da auditoria: CERTIFICATE_VERIFY_FAILED).
    """

    def __init__(self, base_url, token=None, timeout=15, insecure=False):
        from urllib.parse import urlparse
        self.base = str(base_url).rstrip("/")
        u = urlparse(self.base)
        self._allow_insecure = insecure or os.environ.get(
            "LUMEN_ALLOW_INSECURE", "").strip() in ("1", "true", "yes")
        if u.scheme == "http" and not _host_permite_http(u.hostname or "") \
                and not self._allow_insecure:
            raise RegistryError(
                f"registry sem TLS recusado: {self.base} (use https:// "
                f"ou defina LUMEN_ALLOW_INSECURE=1 ou --insecure em rede local)")
        self.token = token or os.environ.get("LUMEN_REGISTRY_TOKEN")
        self.timeout = timeout
        self._ssl_context = self._https_insecure_context(u.scheme)

    def _https_insecure_context(self, scheme):
        """Contexto TLS sem verificação para https dev-only (self-signed).

        Só quando insecure está ativo (--insecure ou LUMEN_ALLOW_INSECURE=1)
        e o scheme é https; caso contrário retorna None → verificação padrão.
        Import ssl local e defensivo: se algo falhar, cai na verificação
        padrão (fail-closed).
        """
        if scheme != "https" or not self._allow_insecure:
            return None
        try:
            import ssl
        except Exception:  # pragma: no cover — ssl é stdlib
            return None
        try:
            ctx = ssl._create_unverified_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE  # self-signed dev-only loopback
            return ctx
        except Exception:  # pragma: no cover — defensivo, fail-closed
            return None

    def _req(self, method, path, data=None):
        url = self.base + path
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("User-Agent", f"lumen-pkg/{__version__}")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        if data is not None:
            req.add_header("Content-Type", "application/octet-stream")
        kwargs = {}
        if self._ssl_context is not None:
            kwargs["context"] = self._ssl_context
        try:
            with urllib.request.urlopen(req, timeout=self.timeout,
                                        **kwargs) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except OSError as e:
            raise RegistryError(f"registry {self.base} inacessível: {e}")

    def publish(self, name, version, data: bytes) -> dict:
        status, body = self._req("PUT", f"/pkg/{name}/{version}", data)
        if status not in (200, 201):
            raise RegistryError(
                f"publicação {name}@{version} falhou: HTTP {status}: "
                f"{body[:200].decode(errors='replace')}")
        try:
            return json.loads(body)
        except ValueError:
            return {"ok": True}

    def fetch(self, name, version) -> bytes:
        status, body = self._req("GET", f"/pkg/{name}/{version}")
        if status != 200:
            raise RegistryError(f"{name}@{version} não encontrado no registry "
                                f"(HTTP {status})")
        return body

    def index(self) -> dict:
        status, body = self._req("GET", "/index")
        if status != 200:
            return {}
        try:
            return json.loads(body)
        except ValueError:
            return {}

    def __repr__(self):
        return f"RegistryClient({self.base})"


def default_registries(cfg=None, insecure=False) -> list:
    url = None
    if cfg:
        url = (cfg.get("registry") or {}).get("url")
    url = url or os.environ.get("LUMEN_REGISTRY") or DEFAULT_REGISTRY
    return [RegistryClient(url, insecure=insecure)]


# ---------------------------------------------------------------------------
# pack / verify
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDES = [
    ".git", ".svn", ".hg", "__pycache__", "*.pyc", "*.pyo", "*.pyw",
    ".lumen", "dist", "vendor", "*.lumepkg", "lumen.lock", ".DS_Store",
    "build_plugins", "node_modules",
]


def _excluded(rel, patterns):
    base = os.path.basename(rel)
    return any(fnmatch(rel, p) or fnmatch(base, p) for p in patterns)


def collect_files(root, include=None, exclude=None):
    """Lista arquivos do projeto (caminhos relativos, ordenados).

    Os rel paths são o formato canônico do pacote (chaves do manifesto e
    arcnames do zip): SEMPRE com '/' (spec do zip), nunca com os.sep.
    `rel.replace(os.sep, "/")` é no-op no POSIX (os.sep == "/") e no Windows
    converte as barras invertidas do os.walk — sem isso, o arcname gravado
    não casa com a chave do manifesto (ex.: `src\\mod.lumen` no zip vs
    `src/mod.lumen` esperado pelo verificador).
    """
    root = Path(root)
    excludes = list(DEFAULT_EXCLUDES) + [str(e) for e in (exclude or [])]
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rdir = os.path.relpath(dirpath, root)
        kept = []
        for d in sorted(dirnames):
            rel = os.path.join(rdir, d) if rdir != "." else d
            if _excluded(rel, excludes):
                continue
            kept.append(d)
        dirnames[:] = kept
        for fn in sorted(filenames):
            rel = os.path.join(rdir, fn) if rdir != "." else fn
            if _excluded(rel, excludes):
                continue
            if include and not any(fnmatch(rel, p) for p in include):
                continue
            files.append(rel.replace(os.sep, "/"))
    return sorted(files)


def manifest_for(root, name, version, files):
    """Retorna (sha256 por arquivo, digest canônico da árvore)."""
    root = Path(root)
    files_sha = {}
    for rel in files:
        files_sha[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    canonical = json.dumps({"name": name, "version": str(version),
                            "files": files_sha},
                           sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    return files_sha, digest


def _strict_hmac() -> bool:
    """Modo estrito via `lumen-pkg --strict-hmac` ou LUMEN_STRICT_HMAC=1."""
    return os.environ.get("LUMEN_STRICT_HMAC", "").strip() in ("1", "true", "yes")


def resolve_key(key=None, strict=None) -> bytes:
    """Ordem: argumento > LUMEN_HMAC_KEY > ~/.lumen/hmac.key > chave demo.

    Em modo estrito (`strict=True` ou LUMEN_STRICT_HMAC=1) falha com
    PkgError em vez de voltar para a chave demo (v0.2: sem chave
    silenciosa em produção).
    """
    if key:
        return key.encode() if isinstance(key, str) else bytes(key)
    env = os.environ.get("LUMEN_HMAC_KEY")
    if env:
        return env.encode()
    kp = hmac_key_path()
    if kp.is_file():
        content = kp.read_text().strip()
        if re.fullmatch(r"[0-9a-fA-F]{16,}", content):
            return bytes.fromhex(content)
        return content.encode()
    if strict if strict is not None else _strict_hmac():
        raise PkgError("sem chave HMAC configurada (modo estrito): defina "
                       "LUMEN_HMAC_KEY, rode `lumen-pkg keygen` ou passe "
                       "--key; a chave demo é recusada aqui")
    return DEMO_HMAC_KEY


def key_is_demo(key=None) -> bool:
    """True se a resolução cairia na chave demo (auditoria)."""
    if key or os.environ.get("LUMEN_HMAC_KEY") or hmac_key_path().is_file():
        return False
    return True


def pack_project(project_dir, out_path=None, key=None, strict=None):
    """Empacota projeto em .lumepkg (zip) com manifesto + assinatura HMAC."""
    project_dir = Path(project_dir)
    cfg_path, cfg = project_toml(project_dir)
    pkg = cfg.get("package", {}) or {}
    name = pkg.get("name")
    version = str(pkg.get("version", "0.1.0"))
    if not name or not re.fullmatch(r"[A-Za-z0-9._-]+", str(name)):
        raise PkgError("lumen.toml precisa de [package].name válido")
    include = pkg.get("include")
    exclude = pkg.get("exclude")
    files = collect_files(project_dir, include, exclude)
    files_sha, digest = manifest_for(project_dir, name, version, files)
    k = resolve_key(key, strict=strict)
    signature = hmac.new(k, digest.encode(), hashlib.sha256).hexdigest()
    manifest = {"name": name, "version": version, "digest": digest,
                "signature": signature, "files": files_sha}
    out = Path(out_path or project_dir / "dist"
               / f"{name}-{version}.lumepkg")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(".lumepkg.json",
                    json.dumps(manifest, indent=1, sort_keys=True))
        for rel in files:
            # arcname já vem normalizado por collect_files para '/' (spec do
            # zip); no Windows nunca usar os.sep aqui, senão o verificador
            # ('rel not in names', com '/') acusa 'faltando no zip'.
            zf.write(project_dir / rel, rel)
    return out, manifest


def verify_archive(archive_path, key=None, check_signature=True,
                     strict=None) -> dict:
    """Verifica sha256 dos arquivos, digest do manifesto e assinatura HMAC.

    `rep["demo_key"]` indica se a verificação usou a chave demo (auditoria
    v0.2); em modo estrito, chave demo é recusada com PkgError.
    """
    ap = Path(archive_path)
    rep = {"ok": False, "path": str(ap), "name": None, "version": None,
           "n_files": 0, "digest_ok": False, "signature_ok": None,
           "demo_key": key_is_demo(key), "errors": []}
    try:
        zf = zipfile.ZipFile(ap)
    except zipfile.BadZipFile as e:
        rep["errors"].append(f"zip inválido: {e}")
        return rep
    with zf:
        names = set(zf.namelist())
        if ".lumepkg.json" not in names:
            rep["errors"].append("sem manifesto .lumepkg.json")
            return rep
        try:
            manifest = json.loads(zf.read(".lumepkg.json"))
        except ValueError as e:
            rep["errors"].append(f"manifesto inválido: {e}")
            return rep
        files = manifest.get("files") or {}
        rep["name"] = manifest.get("name")
        rep["version"] = manifest.get("version")
        rep["n_files"] = len(files)
        digest = manifest.get("digest")
        signature = manifest.get("signature")
        for rel, expected in sorted(files.items()):
            if rel not in names:
                rep["errors"].append(f"faltando no zip: {rel}")
                continue
            actual = hashlib.sha256(zf.read(rel)).hexdigest()
            if actual != expected:
                rep["errors"].append(f"sha256 divergente: {rel}")
        canonical = json.dumps({"name": rep["name"], "version": rep["version"],
                                "files": files},
                               sort_keys=True, separators=(",", ":")).encode()
        recomputed = hashlib.sha256(canonical).hexdigest()
        rep["digest_ok"] = bool(digest) and recomputed == digest
        if not rep["digest_ok"]:
            rep["errors"].append("digest do manifesto não confere")
        if check_signature and digest:
            k = resolve_key(key, strict=strict)
            expected_sig = hmac.new(k, digest.encode(),
                                    hashlib.sha256).hexdigest()
            rep["signature_ok"] = bool(signature) and hmac.compare_digest(
                expected_sig, str(signature))
            if not rep["signature_ok"]:
                rep["errors"].append("assinatura HMAC não confere")
        rep["ok"] = (not rep["errors"]) if check_signature else (
            rep["digest_ok"] and not rep["errors"] and
            rep.get("signature_ok", True) is not False)
        return rep


# ---------------------------------------------------------------------------
# resolver (MVS)
# ---------------------------------------------------------------------------

class Resolver:
    """Resolução de dependências com Minimal Version Selection (MVS).

    Fontes: cache local + índice dos registries configurados. Metadados
    (lumen.toml de cada versão) são buscados sob demanda e cacheados.
    """

    def __init__(self, root_deps, cache, registries=None, log=None):
        self.root_deps = {str(k): str(v) for k, v in (root_deps or {}).items()}
        self.cache = cache
        self.registries = list(registries or [])
        self.log = log or (lambda msg: None)
        self.constraints = {n: [Range(s)] for n, s in self.root_deps.items()}
        self.selected = {}
        self._meta = {}
        self._index = None
        self._fetched = set()

    def _load_index(self):
        if self._index is None:
            idx = {}
            for r in self.registries:
                try:
                    data = r.index()
                except RegistryError as e:
                    self.log(f"aviso: registry {r.base} indisponível: {e}")
                    data = {}
                for n, vers in (data.get("packages") or {}).items():
                    idx.setdefault(str(n), set()).update(
                        s for s in as_versions(vers))
            self._index = {n: sorted(v) for n, v in idx.items()}
        return self._index

    def available_versions(self, name):
        vers = set(self.cache.available_versions(name))
        vers.update(self._load_index().get(str(name), []))
        return sorted(vers)

    def _ensure_fetched(self, name, version):
        key = (str(name), str(version))
        if key in self._fetched or self.cache.has_dir(name, version):
            self._fetched.add(key)
            return
        for r in self.registries:
            try:
                data = r.fetch(str(name), str(version))
            except RegistryError:
                continue  # tenta o próximo registry
            self.cache.store_archive(name, version, data)
            rep = verify_archive(self.cache.archive_path(name, version),
                                 check_signature=True)
            if not rep["ok"]:
                raise ResolutionError(
                    f"verificação falhou ao baixar {name}@{version}: "
                    + "; ".join(rep["errors"]))
            self.cache.extract(name, version)
            self._fetched.add(key)
            return
        raise ResolutionError(f"pacote indisponível em todas as fontes: "
                              f"{name}@{version}")

    def metadata_deps(self, name, version):
        key = (str(name), str(version))
        if key in self._meta:
            return self._meta[key]
        self._ensure_fetched(name, version)
        cfg = load_toml(self.cache.package_dir(name, version) / "lumen.toml")
        deps = {str(k): str(v)
                for k, v in (cfg.get("dependencies") or {}).items()}
        self._meta[key] = deps
        return deps

    def _pick(self, name):
        cs = self.constraints.get(name, [])
        for v in self.available_versions(name):
            if all(c.matches(v) for c in cs):
                return v
        return None

    def solve(self):
        """Retorna {nome: versão} resolvido (MVS) ou levanta ResolutionError."""
        self._load_index()
        # deps raiz
        for n in list(self.constraints):
            v = self._pick(n)
            if v is None:
                raise ResolutionError(
                    f"sem versão para {n} satisfazendo "
                    f"{[c.raw for c in self.constraints[n]]}")
            self.selected[n] = v
        # ponto-fixo: propaga dependências transitivas, apenas sobe versão
        for _ in range(MAX_RESOLVE_ITER):
            changed = False
            for n, ver in list(self.selected.items()):
                for dname, dspec in self.metadata_deps(n, ver).items():
                    if dname not in self.constraints:
                        self.constraints[dname] = [Range(dspec)]
                    else:
                        r = Range(dspec)
                        if not any(c.raw == r.raw
                                   for c in self.constraints[dname]):
                            self.constraints[dname].append(r)
                    if dname not in self.selected:
                        v = self._pick(dname)
                        if v is None:
                            raise ResolutionError(
                                f"{dname} (dependência de {n}@{ver}) "
                                f"insatisfazível: "
                                f"{[c.raw for c in self.constraints[dname]]}")
                        self.selected[dname] = v
                        changed = True
                    else:
                        cur = self.selected[dname]
                        if not all(c.matches(cur)
                                   for c in self.constraints[dname]):
                            v = self._pick(dname)
                            if v is None or v < cur:
                                raise ResolutionError(
                                    f"{dname}: MVS sem solução com "
                                    f"{[c.raw for c in self.constraints[dname]]}")
                            if v > cur:
                                self.selected[dname] = v
                                changed = True
            if not changed:
                break
        else:
            raise ResolutionError("resolução não convergiu "
                                 "(possível ciclo de versões)")
        return {n: str(v) for n, v in sorted(self.selected.items())}


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def _ensure_pkg(cache, regs, name, version, expected_sha=None,
                verbose=False):
    """Garante pacote no cache: baixa (com verificação) se ausente."""
    if not cache.has_dir(name, version):
        fetched = False
        last_err = "sem fontes"
        for r in regs:
            try:
                data = r.fetch(str(name), str(version))
            except RegistryError as e:
                last_err = str(e)
                continue
            cache.store_archive(name, version, data)
            rep = verify_archive(cache.archive_path(name, version),
                                 check_signature=True)
            if not rep["ok"]:
                raise ResolutionError(
                    f"verificação falhou ao baixar {name}@{version}: "
                    + "; ".join(rep["errors"]))
            cache.extract(name, version)
            fetched = True
            break
        if not fetched:
            raise ResolutionError(f"pacote indisponível em todas as fontes: "
                                  f"{name}@{version} ({last_err})")
    if expected_sha:
        pkg_dir = cache.package_dir(name, version)
        files = collect_files(pkg_dir)
        _, sha = manifest_for(pkg_dir, name, version, files)
        if sha != expected_sha:
            raise PkgError(f"sha do lock diverge para {name}@{version} "
                           f"(lock {expected_sha[:12]}… vs cache {sha[:12]}…)")
    if verbose:
        print(f"instalado {name}@{version} em {cache.package_dir(name, version)}")
    return cache.package_dir(name, version)


def install_project(project_dir, cache=None, registries=None, verbose=False,
                    frozen=False, force=False, insecure=False):
    """Resolve, baixa para o cache e escreve lumen.lock. Retorna pacotes.

    Se já existir um lumen.lock v2 válido (fresco) e `force` for falso,
    o lock é validado e reutilizado em vez de re-resolver (`--frozen`
    falha em vez de re-resolver quando o lock está obsoleto).
    """
    project_dir = Path(project_dir)
    cfg_path, cfg = project_toml(project_dir)
    deps = {str(k): str(v)
            for k, v in (cfg.get("dependencies") or {}).items()}
    lock_path = project_dir / "lumen.lock"
    if not deps:
        write_lockfile(lock_path, [])
        return []
    cache = cache or Cache()
    regs = registries
    if regs is None:
        regs = default_registries(cfg, insecure=insecure)
    if lock_path.is_file() and not force:
        ok, problems = validate_lock(deps, lock_path)
        if ok:
            lock = read_lockfile(lock_path)
            for p in lock["packages"]:
                _ensure_pkg(cache, regs, p["name"], p["version"],
                            expected_sha=p.get("sha256"), verbose=verbose)
            if verbose:
                print(f"lock fresco: {len(lock['packages'])} pacote(s) "
                      f"reutilizados de {lock_path}")
            return lock["packages"]
        if frozen:
            raise PkgError("lumen.lock desatualizado (--frozen): "
                           + "; ".join(problems))
        if verbose:
            print("lock obsoleto, re-resolvendo: " + "; ".join(problems))
    res = Resolver(deps, cache, regs,
                   log=(lambda m: print(m, flush=True)) if verbose else None)
    selected = res.solve()
    packages = []
    for name, ver in selected.items():
        res._ensure_fetched(name, ver)
        pkg_dir = cache.package_dir(name, ver)
        files = collect_files(pkg_dir)
        _, sha = manifest_for(pkg_dir, name, ver, files)
        ap = cache.archive_path(name, ver)
        artifact = (hashlib.sha256(ap.read_bytes()).hexdigest()
                    if ap.is_file() else "")
        meta_deps = res.metadata_deps(name, ver)
        edges = "; ".join(f"{k}@{selected.get(k, v)}"
                          for k, v in sorted(meta_deps.items()))
        packages.append({"name": name, "version": ver, "sha256": sha,
                         "artifact": artifact, "source": "registry",
                         "deps": edges})
        if verbose:
            print(f"instalado {name}@{ver} em {cache.package_dir(name, ver)}")
    write_lockfile(lock_path, packages)
    return packages


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

TEMPLATE = """# lumen.toml — projeto Lumen
[package]
name = "{name}"
version = "0.1.0"
description = ""

[dependencies]

[registry]
url = "{registry}"
"""


def init_project(path, name=None, registry=DEFAULT_REGISTRY):
    d = Path(path)
    d.mkdir(parents=True, exist_ok=True)
    name = name or d.resolve().name
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise PkgError(f"nome de projeto inválido: {name!r}")
    cfg = d / "lumen.toml"
    if cfg.exists():
        raise PkgError(f"{cfg} já existe")
    cfg.write_text(TEMPLATE.format(name=name, registry=registry),
                   encoding="utf-8")
    (d / "src").mkdir(exist_ok=True)
    return d


def _find_table(lines, table):
    for i, ln in enumerate(lines):
        if ln.strip() == f"[{table}]":
            return i
    return None


def _find_next_table(lines, start):
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s.endswith("]"):
            return i
    return None


def _is_key(line, name):
    return re.match(rf"^\s*{re.escape(name)}\s*=", line) is not None


def add_dependency(text, name, spec):
    """Insere/atualiza 'name = "spec"' na seção [dependencies] do texto."""
    lines = text.splitlines()
    dep_line = f'{name} = "{escape_toml(str(spec))}"'
    idx = _find_table(lines, "dependencies")
    if idx is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[dependencies]")
        lines.append(dep_line)
        lines.append("")
        return "\n".join(lines)
    end = _find_next_table(lines, idx + 1)
    span_end = end if end is not None else len(lines)
    for i in range(idx + 1, span_end):
        if _is_key(lines[i], name):
            indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            lines[i] = indent + dep_line
            return "\n".join(lines)
    insert_at = end if end is not None else len(lines)
    lines.insert(insert_at, dep_line)
    return "\n".join(lines)


def remove_dependency(text, name):
    """Remove 'name = ...' da seção [dependencies] do texto."""
    lines = text.splitlines()
    idx = _find_table(lines, "dependencies")
    if idx is None:
        return text
    end = _find_next_table(lines, idx + 1)
    span_end = end if end is not None else len(lines)
    out = [ln for i, ln in enumerate(lines)
           if not (idx < i < span_end and _is_key(ln, name))]
    return "\n".join(out)


def _load_project_deps(project_dir):
    cfg_path, cfg = project_toml(project_dir)
    return cfg_path, cfg


# ---- subcomandos ----------------------------------------------------------

def cmd_init(args):
    init_project(args.path, name=args.name, registry=args.registry)
    print(f"projeto criado: {Path(args.path).resolve()}/lumen.toml")


def cmd_new(args):
    init_project(args.path, name=args.name, registry=args.registry)
    print(f"projeto '{args.name}' criado: {Path(args.path).resolve()}")


def cmd_add(args):
    cfg_path, cfg = _load_project_deps(".")
    name, _, spec = args.pkg.partition("@")
    if not name:
        raise PkgError("informe NOME[@SPEC], ex.: lumen-pkg add foo@^1.2.0")
    if not spec:
        spec = "*"
    Range(spec)  # valida o spec antes de gravar
    text = cfg_path.read_text(encoding="utf-8")
    cfg_path.write_text(add_dependency(text, name, spec), encoding="utf-8")
    print(f"adicionado: {name} = \"{spec}\"")


def cmd_remove(args):
    cfg_path, cfg = _load_project_deps(".")
    text = cfg_path.read_text(encoding="utf-8")
    new = remove_dependency(text, args.name)
    if new == text:
        raise PkgError(f"dependência não encontrada: {args.name}")
    cfg_path.write_text(new, encoding="utf-8")
    print(f"removido: {args.name}")


def cmd_resolve(args):
    cfg_path, cfg = _load_project_deps(".")
    deps = {str(k): str(v)
            for k, v in (cfg.get("dependencies") or {}).items()}
    cache = Cache(Path(args.cache_dir) if args.cache_dir else None)
    res = Resolver(deps, cache, default_registries(cfg, insecure=args.insecure),
                   log=(lambda m: print(m, file=sys.stderr)))
    selected = res.solve()
    if args.json:
        print(json.dumps(selected, indent=1, sort_keys=True))
    else:
        for name, ver in selected.items():
            print(f"{name}={ver}")


def cmd_install(args):
    cache = Cache(Path(args.cache_dir) if args.cache_dir else None)
    packages = install_project(".", cache=cache, verbose=args.verbose,
                               frozen=args.frozen, force=args.force,
                               insecure=args.insecure)
    print(f"lumen.lock com {len(packages)} pacote(s)")


def cmd_pack(args):
    out, manifest = pack_project(args.dir, out_path=args.out, key=args.key,
                                 strict=args.strict_hmac)
    print(f"empacotado: {out}  ({manifest['version']}, "
          f"{len(manifest['files'])} arquivo(s))")
    if key_is_demo(args.key):
        print("aviso: empacotado com a chave HMAC demo — nunca use em "
              "produção (LUMEN_HMAC_KEY ou `lumen-pkg keygen`)",
              file=sys.stderr)


def cmd_publish(args):
    project_dir = Path(args.dir or ".")
    cfg_path, cfg = project_toml(project_dir)
    name = cfg.get("package", {}).get("name")
    version = str(cfg.get("package", {}).get("version", "0.1.0"))
    if not name:
        raise PkgError("lumen.toml sem [package].name")
    url = args.registry or (cfg.get("registry") or {}).get("url") \
        or os.environ.get("LUMEN_REGISTRY") or DEFAULT_REGISTRY
    with tempfile.TemporaryDirectory(prefix="lumen-pub-") as tmp:
        out, manifest = pack_project(project_dir, out_path=Path(tmp) / "p.lumepkg",
                                     strict=args.strict_hmac)
        data = out.read_bytes()
    client = RegistryClient(url, insecure=args.insecure)
    rep = client.publish(name, version, data)
    print(f"publicado: {url}/pkg/{name}/{version}  "
          f"(sha256={hashlib.sha256(data).hexdigest()[:12]}…, {rep.get('ok')})")


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

def audit_project(project_dir=".", cache_root=None, key=None, verbose=False):
    """Audita lumen.lock: verifica sha256 dos pacotes no cache e assinatura
    HMAC dos arquivos. Retorna dict com resultado da auditoria.

    OFFLINE por design — não há opção --registry: a auditoria usa apenas o
    cache local (sócio: `install` é quem fala com o registry; `audit`
    verifica o que já está em disco).
    """
    project_dir = Path(project_dir)
    lock_path = project_dir / "lumen.lock"

    result = {"ok": True, "lock_ok": False, "lock_version": None,
              "packages": [], "errors": [], "warnings": []}

    if not lock_path.is_file():
        result["warnings"].append("lumen.lock não encontrado — sem o que auditar")
        result["lock_ok"] = False
        return result

    try:
        lock = read_lockfile(lock_path)
    except PkgError as e:
        result["errors"].append(f"erro ao ler lock: {e}")
        result["ok"] = False
        return result

    result["lock_version"] = lock.get("lockfile-version", "?")
    if str(result["lock_version"]) != "2.0":
        result["errors"].append(
            f"lockfile versão {result['lock_version']} (esperado 2.0)")
        result["ok"] = False
        return result

    result["lock_ok"] = True
    c = Cache(cache_root)
    key_resolver = key  # pode ser None → resolve_key usa fallback

    for pkg in lock.get("packages", []):
        name = pkg.get("name", "?")
        version = pkg.get("version", "?")
        expected_sha = pkg.get("sha256", "")
        entry = {"name": name, "version": version, "sha_ok": False,
                 "archive_exists": False, "signature_ok": None,
                 "deps": _parse_lock_deps(pkg.get("deps", "")),
                 "source": pkg.get("source", ""), "errors": []}

        # 1) Verificar sha256 do diretório extraído no cache
        pkg_dir = c.package_dir(name, version)
        if pkg_dir.is_dir() and (pkg_dir / "lumen.toml").is_file():
            files = collect_files(pkg_dir)
            _, computed_sha = manifest_for(pkg_dir, name, version, files)
            if expected_sha:
                entry["sha_ok"] = computed_sha == expected_sha
                if not entry["sha_ok"]:
                    entry["errors"].append(
                        f"sha256 diverge: lock {expected_sha[:12]}… "
                        f"vs cache {computed_sha[:12]}…")
            else:
                entry["sha_ok"] = True  # sem sha no lock, não há o que comparar
        else:
            entry["errors"].append(f"pacote {name}@{version} não está no cache")

        # 2) Verificar assinatura HMAC do .lumepkg no cache
        archive = c.archive_path(name, version)
        if archive.is_file():
            entry["archive_exists"] = True
            try:
                rep = verify_archive(archive, key=key_resolver,
                                     check_signature=True)
                entry["signature_ok"] = rep.get("signature_ok")
                if not rep["ok"]:
                    for e in rep.get("errors", []):
                        entry["errors"].append(f"verify: {e}")
            except PkgError as e:
                entry["signature_ok"] = False
                entry["errors"].append(f"verify falhou: {e}")
        else:
            if expected_sha:
                # há sha no lock mas sem archive — só aviso
                pass

        if entry["errors"]:
            result["ok"] = False
        result["packages"].append(entry)

    return result


def cmd_audit(args):
    res = audit_project(
        args.dir, cache_root=Path(args.cache_dir) if args.cache_dir else None,
        key=args.key, verbose=args.verbose)
    print(f"lockfile  : v{res['lock_version'] or '?'}"
          f"  [{'OK' if res['lock_ok'] else 'FALHOU'}]")
    print(f"pacotes   : {len(res['packages'])}")
    for pkg in res["packages"]:
        sha_s = "OK" if pkg["sha_ok"] else "FALHOU"
        sig_s = ("OK" if pkg["signature_ok"]
                 else "FALHOU" if pkg["signature_ok"] is False
                 else "N/A")
        deps_str = ", ".join(f"{n}@{v}" for n, v in pkg["deps"])
        status = f"  {pkg['name']}@{pkg['version']}"
        status += f"  sha={sha_s}  hmac={sig_s}"
        if deps_str:
            status += f"  deps=[{deps_str}]"
        print(status)
        for e in pkg["errors"]:
            print(f"    erro: {e}")
    if res["warnings"]:
        for w in res["warnings"]:
            print(f"aviso: {w}")
    print("resultado :", "INTEGRO" if res["ok"] else "PROBLEMAS DETECTADOS")
    return 0 if res["ok"] else 1


def cmd_verify(args):
    rep = verify_archive(args.archive, key=args.key,
                         check_signature=not args.no_signature,
                         strict=args.strict_hmac)
    print(f"arquivo   : {rep['path']}")
    print(f"pacote    : {rep.get('name')}@{rep.get('version')}")
    print(f"arquivos  : {rep.get('n_files')}")
    print(f"digest    : {'OK' if rep['digest_ok'] else 'FALHOU'}")
    if rep.get("signature_ok") is not None:
        print(f"assinatura: {'OK' if rep['signature_ok'] else 'FALHOU'}")
    for e in rep["errors"]:
        print(f"erro      : {e}")
    print("resultado :", "VÁLIDO" if rep["ok"] else "INVÁLIDO")
    return 0 if rep["ok"] else 1


TLS_DEV_ONLY = (
    "DEV-ONLY: certificado SELF-SIGNED para desenvolvimento local "
    "(loopback 127.0.0.1). Não vale para produção — não distribua nem "
    "use fora da sua máquina."
)

GEN_TLS_SH = r"""#!/usr/bin/env bash
# Gera cert+key TLS self-signed DEV-ONLY para loopback (127.0.0.1).
# Uso: ./gen_tls_dev.sh [DESTINO]   (padrão: diretório deste script)
set -euo pipefail
DIR="${1:-$(dirname "$0")}"
CERT="$DIR/cert.pem"
KEY="$DIR/key.pem"
if ! command -v openssl >/dev/null 2>&1; then
  echo "erro: openssl não instalado (necessário p/ TLS dev-only)" >&2
  exit 1
fi
if ! openssl req -x509 -newkey rsa:2048 -keyout "$KEY" -out "$CERT" \
      -days 365 -nodes -subj '/CN=127.0.0.1' \
      -addext 'subjectAltName=IP:127.0.0.1' 2>/dev/null; then
  # openssl antigo (1.0.x) sem -addext
  openssl req -x509 -newkey rsa:2048 -keyout "$KEY" -out "$CERT" \
      -days 365 -nodes -subj '/CN=127.0.0.1'
fi
chmod 600 "$KEY"
echo "DEV-ONLY: certificado self-signed para desenvolvimento local apenas."
echo "cert: $CERT"
echo "key:  $KEY"
"""


def _openssl_disponivel():
    """Caminho do binário openssl, ou None se ausente/que não executa."""
    exe = shutil.which("openssl")
    if not exe:
        return None
    try:
        subprocess.run([exe, "version"], capture_output=True, timeout=10,
                       check=True)
        return exe
    except (OSError, subprocess.SubprocessError):
        return None


def gen_tls_dev_cert(dir_path=None):
    """Gera cert+key self-signed DEV-ONLY para loopback (127.0.0.1).

    A stdlib do Python não assina X.509 sozinha; usa o binário `openssl`
    do sistema. Sem openssl, grava um script auxiliar + instruções e
    levanta PkgError (o par NÃO foi gerado).
    """
    base = lumen_home() / "tls" if not dir_path else Path(dir_path)
    cert_p = base / "cert.pem"
    key_p = base / "key.pem"
    base.mkdir(parents=True, exist_ok=True)
    openssl = _openssl_disponivel()
    if openssl:
        cmd = [openssl, "req", "-x509", "-newkey", "rsa:2048",
               "-keyout", str(key_p), "-out", str(cert_p),
               "-days", "365", "-nodes", "-subj", "/CN=127.0.0.1"]
        try:
            subprocess.run(cmd + ["-addext", "subjectAltName=IP:127.0.0.1"],
                           capture_output=True, check=True, timeout=60)
        except subprocess.CalledProcessError:
            # openssl antigo (1.0.x) sem -addext: regenera sem SAN
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
        except subprocess.TimeoutExpired as e:
            raise PkgError(
                "openssl estourou o tempo limite (60s) gerando o par TLS "
                "dev-only") from e
        key_p.chmod(0o600)
        return cert_p, key_p
    script = base / "gen_tls_dev.sh"
    script.write_text(GEN_TLS_SH, encoding="utf-8")
    script.chmod(0o700)
    raise PkgError(
        f"openssl não encontrado — a geração TLS DEV-ONLY (self-signed, "
        f"loopback, nunca produção) exige o binário openssl, pois a stdlib "
        f"não assina X.509. Instale openssl e rode `lumen-pkg keygen --tls "
        f"--dir {base}` (ou o script auxiliar {script}); enquanto isso, use "
        f"o registry em http://127.0.0.1:8765 (loopback sem TLS).")


def cmd_keygen(args):
    if args.tls:
        cert_p, key_p = gen_tls_dev_cert(args.dir)
        print(TLS_DEV_ONLY)
        print(f"certificado dev-only: {cert_p}")
        print(f"chave privada dev-only: {key_p}   (use --tls-cert/--tls-key "
              f"do registry.py)")
        return 0
    key = os.urandom(32).hex()
    kp = hmac_key_path()
    kp.parent.mkdir(parents=True, exist_ok=True)
    kp.write_text(key + "\n", encoding="utf-8")
    os.chmod(kp, 0o600)
    print(f"chave HMAC gerada: {kp}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="lumen-pkg",
        description="Gerenciador de pacotes do Lumen (semver ^ ~ = + MVS, "
                    "cache, lockfile, pack/verify HMAC).")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--insecure", action="store_true",
                    help="permitir HTTP/self-signed TLS (sem LUMEN_ALLOW_INSECURE)")
    sub = p.add_subparsers(dest="cmd", metavar="COMANDO")

    def add(name, help_, fn):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        return sp

    sp = add("init", "cria novo projeto", cmd_init)
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--name")
    sp.add_argument("--registry", default=DEFAULT_REGISTRY)

    sp = add("new", "cria novo projeto com nome", cmd_new)
    sp.add_argument("name")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--registry", default=DEFAULT_REGISTRY)

    sp = add("add", "adiciona dependência", cmd_add)
    sp.add_argument("pkg", metavar="NOME[@SPEC]")

    sp = add("remove", "remove dependência", cmd_remove)
    sp.add_argument("name")

    sp = add("resolve", "resolve grafo de dependências (MVS)", cmd_resolve)
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--cache-dir")

    sp = add("install", "resolve, baixa e escreve lumen.lock", cmd_install)
    sp.add_argument("--cache-dir")
    sp.add_argument("--verbose", action="store_true")
    sp.add_argument("--frozen", action="store_true",
                    help="falha se o lumen.lock estiver obsoleto (CI)")
    sp.add_argument("--force", action="store_true",
                    help="ignora o lock existente e re-resolve")

    sp = add("pack", "empacota em .lumepkg", cmd_pack)
    sp.add_argument("dir", nargs="?", default=".")
    sp.add_argument("--out")
    sp.add_argument("--key", help="chave HMAC (hex/bytes)")
    sp.add_argument("--strict-hmac", action="store_true",
                    help="recusa a chave demo (exige chave configurada)")

    sp = add("publish", "publica no registry", cmd_publish)
    sp.add_argument("dir", nargs="?", default=".")
    sp.add_argument("--registry")
    sp.add_argument("--strict-hmac", action="store_true",
                    help="recusa a chave demo (exige chave configurada)")

    sp = add("verify", "verifica sha256 + assinatura HMAC", cmd_verify)
    sp.add_argument("archive", metavar="ARQUIVO.lumepkg")
    sp.add_argument("--key")
    sp.add_argument("--no-signature", action="store_true")
    sp.add_argument("--strict-hmac", action="store_true",
                    help="recusa a chave demo (exige chave configurada)")

    sp = add("keygen", "gera chave HMAC demo (--tls: cert TLS dev-only)",
             cmd_keygen)
    sp.add_argument("--tls", action="store_true",
                    help="gera cert+key self-signed DEV-ONLY para loopback "
                         "(127.0.0.1, apenas desenvolvimento local — nunca "
                         "produção) via openssl; sem openssl, grava script "
                         "auxiliar + instruções")
    sp.add_argument("--dir", default=None,
                    help="diretório de saída do par TLS (padrão ~/.lumen/tls)")

    sp = add("audit", "audita lumen.lock (sha256 + HMAC, offline por design: "
                      "só o cache local, sem --registry)", cmd_audit)
    sp.add_argument("dir", nargs="?", default=".")
    sp.add_argument("--cache-dir")
    sp.add_argument("--key")
    sp.add_argument("--verbose", action="store_true")

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 1
    try:
        rc = args.fn(args)
        return int(rc or 0)
    except PkgError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("abortado", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())