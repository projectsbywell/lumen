#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registry HTTP mínimo do Lumen (Python puro, http.server).

Rotas
-----
  PUT /pkg/<nome>/<versao>   publica um .lumepkg (corpo = bytes do zip)
  GET /pkg/<nome>/<versao>   baixa um .lumepkg
  GET /index                 lista {name: [versões...]} em JSON
  GET /health                healthcheck

Armazenamento em ./registry_data/<nome>/<nome>-<versao>.lumepkg.

Uso
---
  python3 registry.py [--host 127.0.0.1] [--port 8765] [--dir ./registry_data]
                      [--tls-cert CERT.pem --tls-key KEY.pem] [--tls-only]

Com --tls-cert/--tls-key serve HTTPS. O par gerado por
`lumen-pkg keygen --tls` é self-signed DEV-ONLY: serve apenas para
desenvolvimento local (loopback), nunca produção.

--tls-cert e --tls-key formam um par: com apenas um deles o registry
aborta com erro (exit 2) em vez de cair em HTTP silencioso.
--tls-only recusa servir HTTP: exige o par PEM e serve apenas HTTPS.

Se LUMEN_REGISTRY_TOKEN estiver definido, o PUT exige
`Authorization: Bearer <token>`.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
VER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_-]*$")
MAX_BODY = 64 * 1024 * 1024  # 64 MiB


class RegistryError(Exception):
    pass


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


class RegistryHandler(BaseHTTPRequestHandler):
    server_version = "LumenRegistry/1.0"
    data_dir = Path("registry_data")  # sobrescrito pelo servidor
    token = None

    # ------------------------------------------------------------------ util
    def _send(self, code, body=b"", ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Server", self.server_version)
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, indent=1, sort_keys=True) + "\n")

    def _parse_pkg_path(self):
        """Valida /pkg/<name>/<version> e retorna (name, version)."""
        parts = self.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "pkg":
            return None
        name, version = parts[1], parts[2]
        if not NAME_RE.match(name) or name in (".", ".."):
            return None
        if not VER_RE.match(version) or version in (".", ".."):
            return None
        return name, version

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return self.rfile.read()  # até EOF
        if length > MAX_BODY:
            raise RegistryError("corpo maior que o limite (64 MiB)")
        return self.rfile.read(length)

    def _check_auth(self):
        if not self.token:
            return True
        header = self.headers.get("Authorization", "")
        return header == "Bearer " + self.token

    def log_message(self, fmt, *args):
        sys.stdout.write(f"[{_now()}] {self.address_string()} "
                         f"{fmt % args}\n")
        sys.stdout.flush()

    # ---------------------------------------------------------------- rotas
    def do_PUT(self):
        if self.path == "/health":
            self._json(200, {"ok": True})
            return
        pp = self._parse_pkg_path()
        if not pp:
            self._json(400, {"ok": False, "erro": "rota inválida "
                                                   "(esperado /pkg/<n>/<v>)"})
            return
        name, version = pp
        if not self._check_auth():
            self._json(401, {"ok": False, "erro": "token ausente/inválido"})
            return
        try:
            body = self._read_body()
        except RegistryError as e:
            self._json(413, {"ok": False, "erro": str(e)})
            return
        if not body:
            self._json(400, {"ok": False, "erro": "corpo vazio"})
            return
        d = self.data_dir / name
        d.mkdir(parents=True, exist_ok=True)
        target = d / f"{name}-{version}.lumepkg"
        tmp = d / f".{name}-{version}.tmp-{os.getpid()}-{threading.get_ident()}-{uuid.uuid4().hex[:8]}"
        try:
            tmp.write_bytes(body)
            os.replace(tmp, target)
        except OSError as e:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            self._json(500, {"ok": False, "erro": str(e)})
            return
        sha = hashlib.sha256(body).hexdigest()
        self._json(201, {"ok": True, "name": name, "version": version,
                         "sha256": sha})

    def do_GET(self):
        if self.path == "/index":
            self._json(200, {"ok": True, "packages": self._index()})
            return
        if self.path == "/health":
            self._json(200, {"ok": True})
            return
        pp = self._parse_pkg_path()
        if not pp:
            self._json(400, {"ok": False, "erro": "rota inválida"})
            return
        name, version = pp
        target = self.data_dir / name / f"{name}-{version}.lumepkg"
        if not target.is_file():
            self._json(404, {"ok": False, "erro": "pacote não encontrado"})
            return
        data = target.read_bytes()
        self._send(200, data, ctype="application/octet-stream")

    do_HEAD = do_GET

    def _index(self):
        packages = {}
        if self.data_dir.is_dir():
            for d in sorted(self.data_dir.iterdir()):
                if not d.is_dir():
                    continue
                vers = []
                prefix = d.name + "-"
                for f in sorted(d.glob("*.lumepkg")):
                    stem = f.stem
                    if stem.startswith(prefix):
                        vers.append(stem[len(prefix):])
                if vers:
                    packages[d.name] = sorted(vers)
        return packages


class RegistryServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler_cls, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        handler_cls.data_dir = self.data_dir
        handler_cls.token = os.environ.get("LUMEN_REGISTRY_TOKEN")
        super().__init__(addr, handler_cls)


def tls_server_context(cert: str, key: str):
    """Contexto TLS servidor a partir de cert/key PEM (dev-only, loopback)."""
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    return ctx


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="registry.py",
                                 description="Registry HTTP mínimo do Lumen")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--dir", default="./registry_data")
    ap.add_argument("--tls-cert", default=None,
                    help="certificado PEM para HTTPS")
    ap.add_argument("--tls-key", default=None,
                    help="chave privada PEM para HTTPS")
    ap.add_argument("--tls-only", action="store_true",
                    help="recusa servir HTTP: exige --tls-cert/--tls-key "
                         "e serve apenas HTTPS (loopback dev-only)")
    args = ap.parse_args(argv)

    # --tls-cert/--tls-key formam um par: com apenas um, aborta (exit 2)
    # em vez de cair em HTTP silencioso.
    if bool(args.tls_cert) != bool(args.tls_key):
        ap.error("--tls-cert e --tls-key devem vir JUNTOS (par PEM: "
                 "certificado + chave privada). Com apenas um deles o "
                 "registry não pode servir HTTPS e aborta em vez de "
                 "cair em HTTP silencioso")
    if args.tls_only and not (args.tls_cert and args.tls_key):
        ap.error("--tls-only exige --tls-cert e --tls-key: sem o par PEM "
                 "não há como servir HTTPS, e --tls-only recusa servir "
                 "HTTP")

    server = RegistryServer((args.host, args.port), RegistryHandler,
                            args.dir)
    if args.tls_cert and args.tls_key:
        ctx = tls_server_context(args.tls_cert, args.tls_key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    else:
        scheme = "http"
    host, port = server.server_address[:2]
    print(f"lumen registry em {scheme}://{host}:{port}  "
          f"(dados: {server.data_dir})", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nencerrando registry…", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())