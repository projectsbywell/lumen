#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do lumen-pkg: semver, ranges, resolver MVS, lockfile roundtrip,
pack/verify (sha256 + HMAC), registry HTTP, install end-to-end, CLI."""

import contextlib
import io
import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lumen_pkg
from lumen_pkg import (Cache, PkgError, Range, RegistryClient, RegistryError,
                       Resolver, SemVer, add_dependency, min_satisfying,
                       pack_project, remove_dependency, resolve_key,
                       validate_lock,
                       verify_archive, write_lockfile, read_lockfile,
                       install_project, safe_extract, TEMPLATE, main,
                       init_project, audit_project, collect_files, manifest_for)
import registry
from registry import RegistryServer, RegistryHandler


class SemVerTest(unittest.TestCase):
    def test_parse_roundtrip(self):
        for s in ("1.2.3", "v2.3.4", "0.0.1-alpha", "1.2.3-beta.1",
                  "1.2.3+build.5", "1.2.3-rc.1+build.7",
                  "10.20.30-alpha.beta.1"):
            self.assertEqual(str(SemVer.parse(s)), s.lstrip("v"))

    def test_invalid(self):
        for s in ("1.2", "1", "abc", "1.2.3.4", "1..2", "-1.0.0"):
            self.assertIsNone(SemVer.try_parse(s))

    def test_ordering_release(self):
        a = SemVer.parse("1.0.0")
        self.assertLess(a, SemVer.parse("1.0.1"))
        self.assertLess(a, SemVer.parse("1.1.0"))
        self.assertLess(a, SemVer.parse("2.0.0"))

    def test_ordering_prerelease(self):
        seq = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta",
               "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
               "1.0.0-rc.1", "1.0.0"]
        vers = [SemVer.parse(s) for s in seq]
        for i in range(len(vers) - 1):
            self.assertLess(vers[i], vers[i + 1],
                            f"{seq[i]} < {seq[i + 1]}")

    def test_build_metadata_ignored(self):
        self.assertEqual(SemVer.parse("1.0.0+a"), SemVer.parse("1.0.0+b"))
        self.assertFalse(SemVer.parse("1.0.0+a") < SemVer.parse("1.0.0+b"))


class RangeTest(unittest.TestCase):
    V = lambda self, s: SemVer.parse(s)  # noqa: E731

    def check(self, spec, yes, no):
        r = Range(spec)
        for v in yes:
            self.assertTrue(r.matches(v), f"{spec} deve casar {v}")
        for v in no:
            self.assertFalse(r.matches(v), f"{spec} não deve casar {v}")

    def test_caret(self):
        self.check("^1.2.3",
                   ["1.2.3", "1.2.9", "1.9.9"],
                   ["1.2.2", "2.0.0", "0.9.0"])
        self.check("^0.2.3", ["0.2.3", "0.2.9"], ["0.3.0", "0.2.2", "1.0.0"])
        self.check("^0.0.3", ["0.0.3"], ["0.0.4", "0.0.2"])
        self.check("^1.2", ["1.2.0", "1.9.9"], ["2.0.0", "1.1.9"])

    def test_tilde(self):
        self.check("~1.2.3", ["1.2.3", "1.2.9"], ["1.3.0", "1.2.2"])
        self.check("~1.2", ["1.2.0", "1.2.9"], ["1.3.0", "1.1.9"])
        self.check("~1", ["1.0.0", "1.9.9"], ["2.0.0", "0.9.9"])

    def test_exact_and_equal(self):
        self.check("=1.2.3", ["1.2.3"], ["1.2.4", "1.2.3-beta"])
        self.check("1.2.3", ["1.2.3"], ["1.2.4"])
        self.check("1.2", ["1.2.0", "1.2.9"], ["1.3.0"])
        self.check("1", ["1.0.0", "1.9.9"], ["2.0.0"])

    def test_comparators(self):
        self.check(">=1.0.0", ["1.0.0", "2.0.0"], ["0.9.9"])
        self.check(">1.0.0", ["1.0.1"], ["1.0.0"])
        self.check("<=1.0.0", ["0.9.0", "1.0.0"], ["1.0.1"])
        self.check("<1.0.0", ["0.9.9"], ["1.0.0"])
        self.check(">=1.0.0 <2.0.0", ["1.5.0"], ["0.5.0", "2.0.0"])
        self.check(">=1.0.0,<1.5.0", ["1.4.9"], ["1.5.0"])

    def test_wildcards(self):
        self.check("*", ["0.0.1", "9.9.9"], [])
        self.check("1.x", ["1.0.0", "1.9.9"], ["2.0.0"])
        self.check("1.2.x", ["1.2.0", "1.2.7"], ["1.3.0"])

    def test_union(self):
        self.check("^1.0.0 || ^2.0.0",
                   ["1.5.0", "2.5.0"], ["0.9.0", "3.0.0"])

    def test_invalid_spec(self):
        for s in ("^", "~", "abc", "^1.x.3", ""):
            with self.assertRaises(PkgError):
                Range(s)

    def test_min_satisfying(self):
        vers = ["1.0.0", "1.2.0", "1.9.0", "2.0.0"]
        self.assertEqual(str(min_satisfying(vers, "^1.0.0")), "1.0.0")
        self.assertEqual(str(min_satisfying(vers, ">=1.5.0")), "1.9.0")
        self.assertIsNone(min_satisfying(vers, "^3.0.0"))


class LockfileTest(unittest.TestCase):
    def test_roundtrip(self):
        packages = [
            {"name": "foo", "version": "1.2.3",
             "sha256": "ab" * 32, "source": "registry:http://x",
             "deps": "bar@^1.0.0"},
            {"name": "bar", "version": "0.9.0",
             "sha256": "cd" * 32, "source": "cache"},
        ]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lumen.lock"
            write_lockfile(path, packages)
            got = read_lockfile(path)
        self.assertEqual(got["lockfile-version"], "2.0")
        self.assertEqual(len(got["packages"]), 2)
        self.assertEqual(got["packages"][0], packages[0])
        self.assertEqual(got["packages"][1], packages[1])

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(PkgError):
                read_lockfile(Path(td) / "nope.lock")

    def test_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lumen.lock"
            write_lockfile(path, [])
            got = read_lockfile(path)
        self.assertEqual(got["packages"], [])


class ResolverMVSTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Cache(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self, name, versions, deps=None):
        for v in versions:
            d = self.cache.package_dir(name, v)
            d.mkdir(parents=True, exist_ok=True)
            pkg_deps = ""
            if deps and v in deps:
                pkg_deps = "\n".join(
                    f'{k} = "{s}"' for k, s in deps[v].items())
            (d / "lumen.toml").write_text(
                f'[package]\nname = "{name}"\nversion = "{v}"\n\n'
                f"[dependencies]\n{pkg_deps}\n", encoding="utf-8")
            (d / f"{name}.py").write_text(f"# {name} {v}\n")

    def resolve(self, root_deps):
        return Resolver(root_deps, self.cache, registries=[]).solve()

    def test_mvs_bump(self):
        self.seed("a", ["1.0.0", "1.2.0"],
                  deps={"1.0.0": {"b": "^1.2.0"}})
        self.seed("b", ["1.0.0", "1.1.0", "1.2.0", "1.5.0"])
        # root: b >=1.0.0; a@1.0.0 exige b ^1.2.0 -> MVS sobe b para 1.2.0
        got = self.resolve({"a": "^1.0.0", "b": ">=1.0.0"})
        self.assertEqual(got, {"a": "1.0.0", "b": "1.2.0"})

    def test_conflicting_ceiling_unsatisfiable(self):
        self.seed("a", ["1.0.0"], deps={"1.0.0": {"b": "^1.2.0"}})
        self.seed("b", ["1.0.0", "1.1.0", "1.2.0", "1.5.0"])
        # root fixa b < 1.1.0; a@1.0.0 exige b >= 1.2.0 -> sem interseção
        with self.assertRaises(lumen_pkg.ResolutionError):
            self.resolve({"a": "^1.0.0", "b": "~1.0.0"})

    def test_min_selection(self):
        self.seed("a", ["1.0.0", "1.5.0", "2.0.0"])
        got = self.resolve({"a": "^1.0.0"})
        self.assertEqual(got, {"a": "1.0.0"})
        got = self.resolve({"a": ">=1.5.0"})
        self.assertEqual(got, {"a": "1.5.0"})
        got = self.resolve({"a": "*"})
        self.assertEqual(got, {"a": "1.0.0"})

    def test_transitive_chain(self):
        self.seed("a", ["1.0.0"], deps={"1.0.0": {"b": "^1.0.0"}})
        self.seed("b", ["1.0.0"], deps={"1.0.0": {"c": "~2.3.0"}})
        self.seed("c", ["2.3.0", "2.3.9", "2.4.0"])
        got = self.resolve({"a": "^1.0.0"})
        self.assertEqual(got, {"a": "1.0.0", "b": "1.0.0", "c": "2.3.0"})

    def test_unsatisfiable(self):
        self.seed("a", ["1.0.0"], deps={"1.0.0": {"b": ">=3.0.0"}})
        self.seed("b", ["2.0.0", "2.5.0"])
        with self.assertRaises(lumen_pkg.ResolutionError):
            self.resolve({"a": "^1.0.0"})

    def test_unavailable_root(self):
        self.seed("a", ["1.0.0"])
        with self.assertRaises(lumen_pkg.ResolutionError):
            self.resolve({"nope": "^1.0.0"})

    def test_root_unsatisfied(self):
        self.seed("a", ["1.0.0", "2.0.0"])
        with self.assertRaises(lumen_pkg.ResolutionError):
            self.resolve({"a": "^3.0.0"})


class PackVerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        self.proj.mkdir()
        (self.proj / "lumen.toml").write_text(
            '[package]\nname = "mini"\nversion = "1.0.0"\n\n'
            "[dependencies]\n", encoding="utf-8")
        (self.proj / "src").mkdir()
        (self.proj / "src" / "mod.lumen").write_text(
            "let x = 1\nprint(x)\n", encoding="utf-8")
        (self.proj / "src" / "__pycache__").mkdir()
        (self.proj / "src" / "__pycache__" / "junk.pyc").write_bytes(b"x")
        (self.proj / "dist").mkdir()
        (self.proj / "dist" / "velho.lumepkg").write_bytes(b"junk")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pack_excludes(self):
        out, manifest = pack_project(self.proj)
        self.assertTrue(out.is_file())
        self.assertEqual(manifest["name"], "mini")
        self.assertTrue(manifest["signature"])
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        self.assertIn("lumen.toml", names)
        self.assertIn("src/mod.lumen", names)
        self.assertNotIn("src/__pycache__/junk.pyc", names)
        self.assertNotIn("dist/velho.lumepkg", names)

    def test_verify_ok(self):
        out, manifest = pack_project(self.proj)
        rep = verify_archive(out)
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(rep["name"], "mini")
        self.assertEqual(rep["version"], "1.0.0")
        self.assertTrue(rep["digest_ok"])
        self.assertTrue(rep["signature_ok"])

    def test_verify_tampered_file(self):
        out, _ = pack_project(self.proj)
        with zipfile.ZipFile(out, "a") as zf:
            zf.writestr("src/mod.lumen", "tampered\n")
        rep = verify_archive(out)
        self.assertFalse(rep["ok"])
        self.assertTrue(any("sha256 divergente" in e
                            for e in rep["errors"]))

    def test_verify_wrong_key(self):
        out, _ = pack_project(self.proj, key="chave-correta")
        rep = verify_archive(out, key="chave-errada")
        self.assertFalse(rep["ok"])
        self.assertFalse(rep["signature_ok"])

    def test_verify_roundtrip_keyfile(self):
        out, _ = pack_project(self.proj)
        rep = verify_archive(out, key="chave-correta")
        self.assertFalse(rep["ok"])  # assinada com a chave demo
        out2, _ = pack_project(self.proj, key="chave-correta")
        rep2 = verify_archive(out2, key="chave-correta")
        self.assertTrue(rep2["ok"], rep2)

    # -- HMAC estrito + HTTPS (v0.2) --------------------------------
    def test_strict_hmac_sem_chave_falha(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("LUMEN_HMAC_KEY", "LUMEN_STRICT_HMAC")}
        with tempfile.TemporaryDirectory() as home:
            env["LUMEN_HOME"] = home  # sem ~/.lumen/hmac.key
            old = dict(os.environ)
            os.environ.clear()
            os.environ.update(env)
            try:
                with self.assertRaises(PkgError):
                    pack_project(self.proj, strict=True)
            finally:
                os.environ.clear()
                os.environ.update(old)

    def test_strict_hmac_com_chave_ok(self):
        out, _ = pack_project(self.proj, key="segredo-forte-123",
                              strict=True)
        rep = verify_archive(out, key="segredo-forte-123", strict=True)
        self.assertTrue(rep["ok"], rep)
        self.assertFalse(rep["demo_key"])

    def test_verify_marca_chave_demo(self):
        out, _ = pack_project(self.proj)
        rep = verify_archive(out)
        self.assertTrue(rep["ok"], rep)
        self.assertTrue(rep["demo_key"])

    def test_registry_http_nao_loopback_recusado(self):
        with self.assertRaises(RegistryError):
            RegistryClient("http://registry.exemplo.com:8765")

    def test_registry_loopback_ok(self):
        c = RegistryClient("http://127.0.0.1:8765")
        self.assertEqual(c.base, "http://127.0.0.1:8765")

    def test_registry_https_ok(self):
        c = RegistryClient("https://registry.exemplo.com")
        self.assertEqual(c.base, "https://registry.exemplo.com")

    def test_extract_rejects_traversal(self):
        evil = Path(self.tmp.name) / "evil.lumepkg"
        with zipfile.ZipFile(evil, "w") as zf:
            zf.writestr("ok.txt", "ok")
            zf.writestr("../escape.txt", "oops")
        cache = Cache(Path(self.tmp.name) / "cache2")
        cache.root.mkdir(parents=True, exist_ok=True)
        cache.archive_path("evil", "1.0.0").parent.mkdir(parents=True)
        shutil.copy(evil, cache.archive_path("evil", "1.0.0"))
        with self.assertRaises(PkgError):
            cache.extract("evil", "1.0.0")


class RegistryIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "registry_data"
        self.server = RegistryServer(("127.0.0.1", 0), RegistryHandler,
                                     self.data)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.client = RegistryClient(f"http://127.0.0.1:{self.port}")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def test_publish_fetch_index(self):
        proj = Path(self.tmp.name) / "pkgdir"
        proj.mkdir()
        (proj / "lumen.toml").write_text(
            '[package]\nname = "srv-lib"\nversion = "0.2.0"\n\n'
            "[dependencies]\n", encoding="utf-8")
        (proj / "srv.py").write_text("VALOR = 42\n")
        out, _ = pack_project(proj)
        data = out.read_bytes()

        rep = self.client.publish("srv-lib", "0.2.0", data)
        self.assertTrue(rep["ok"])

        idx = self.client.index()
        self.assertEqual(idx["packages"]["srv-lib"], ["0.2.0"])

        fetched = self.client.fetch("srv-lib", "0.2.0")
        self.assertEqual(fetched, data)

    def test_fetch_missing_404(self):
        with self.assertRaises(RegistryError):
            self.client.fetch("nao-existe", "1.0.0")

    def test_publish_invalid_name(self):
        proj = Path(self.tmp.name) / "pkgdir2"
        proj.mkdir()
        (proj / "lumen.toml").write_text(
            '[package]\nname = "x"\nversion = "1.0.0"\n\n'
            "[dependencies]\n", encoding="utf-8")
        (proj / "x.py").write_text("")
        out, _ = pack_project(proj)
        with self.assertRaises(RegistryError):
            self.client.publish("../../esc", "1.0.0", out.read_bytes())
        self.assertFalse((self.data / ".." / "esc").exists())


class InstallE2ETest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data = root / "registry_data"
        self.server = RegistryServer(("127.0.0.1", 0), RegistryHandler,
                                     self.data)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = RegistryClient(f"http://127.0.0.1:{self.port}")
        self.cache = Cache(root / "cache")
        self.proj = root / "app"
        self.proj.mkdir()
        (self.proj / "lumen.toml").write_text(
            '[package]\nname = "app"\nversion = "0.1.0"\n\n'
            '[dependencies]\nlib-utils = "^1.0.0"\n', encoding="utf-8")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def _publish_lib(self, version="1.0.0", deps=""):
        d = Path(self.tmp.name) / f"lib-{version}"
        d.mkdir(exist_ok=True)
        (d / "lumen.toml").write_text(
            f'[package]\nname = "lib-utils"\nversion = "{version}"\n\n'
            f"[dependencies]\n{deps}\n", encoding="utf-8")
        (d / "lib.py").write_text(f"VERSION = {version!r}\n")
        out, _ = pack_project(d)
        self.client.publish("lib-utils", version, out.read_bytes())

    def test_install_writes_lock_and_cache(self):
        self._publish_lib("1.0.0")
        packages = install_project(self.proj, cache=self.cache,
                                   registries=[self.client])
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0]["name"], "lib-utils")
        self.assertEqual(packages[0]["version"], "1.0.0")
        self.assertRegex(packages[0]["sha256"], r"^[0-9a-f]{64}$")
        lock = read_lockfile(self.proj / "lumen.lock")
        self.assertEqual(lock["packages"][0]["version"], "1.0.0")
        self.assertTrue(self.cache.has_dir("lib-utils", "1.0.0"))
        self.assertTrue((self.cache.package_dir("lib-utils", "1.0.0")
                         / "lib.py").is_file())

    def test_install_transitive(self):
        self._publish_lib("1.0.0", deps='dep-a = "^2.0.0"')
        d = Path(self.tmp.name) / "dep-a"
        d.mkdir()
        (d / "lumen.toml").write_text(
            '[package]\nname = "dep-a"\nversion = "2.5.0"\n\n'
            "[dependencies]\n", encoding="utf-8")
        (d / "a.py").write_text("")
        out, _ = pack_project(d)
        self.client.publish("dep-a", "2.5.0", out.read_bytes())

        packages = install_project(self.proj, cache=self.cache,
                                   registries=[self.client])
        names = {p["name"] for p in packages}
        self.assertEqual(names, {"lib-utils", "dep-a"})
        ver = {p["name"]: p["version"] for p in packages}
        self.assertEqual(ver["dep-a"], "2.5.0")

    # -- lockfile v2 (v0.2): arestas resolvidas + validação ------------
    def test_lock_v2_edges_resolved(self):
        self._publish_lib("1.0.0", deps='dep-a = "^2.0.0"')
        d = Path(self.tmp.name) / "dep-a"
        d.mkdir()
        (d / "lumen.toml").write_text(
            '[package]\nname = "dep-a"\nversion = "2.5.0"\n\n'
            "[dependencies]\n", encoding="utf-8")
        (d / "a.py").write_text("")
        out, _ = pack_project(d)
        self.client.publish("dep-a", "2.5.0", out.read_bytes())

        install_project(self.proj, cache=self.cache,
                        registries=[self.client])
        lock = read_lockfile(self.proj / "lumen.lock")
        self.assertEqual(lock["lockfile-version"], "2.0")
        by_name = {p["name"]: p for p in lock["packages"]}
        self.assertEqual(by_name["lib-utils"]["deps"], "dep-a@2.5.0")
        self.assertRegex(by_name["lib-utils"].get("artifact", ""),
                         r"^[0-9a-f]{64}$")

    def test_install_reuses_fresh_lock(self):
        self._publish_lib("1.0.0")
        install_project(self.proj, cache=self.cache,
                        registries=[self.client])
        raw1 = (self.proj / "lumen.lock").read_bytes()
        # registry fora do ar: com lock fresco, não precisa dele.
        self.server.shutdown()
        self.server.server_close()
        packages = install_project(self.proj, cache=self.cache,
                                   registries=[self.client])
        self.assertEqual(len(packages), 1)
        self.assertEqual((self.proj / "lumen.lock").read_bytes(), raw1)

    def test_install_frozen_stale_fails(self):
        self._publish_lib("1.0.0")
        install_project(self.proj, cache=self.cache,
                        registries=[self.client])
        (self.proj / "lumen.toml").write_text(
            '[package]\nname = "app"\nversion = "0.1.0"\n\n'
            '[dependencies]\nlib-utils = "^9.9.9"\n', encoding="utf-8")
        with self.assertRaises(PkgError):
            install_project(self.proj, cache=self.cache,
                            registries=[self.client], frozen=True)

    def test_validate_lock_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lumen.lock"
            path.write_text(
                'lockfile-version = "1.0"\n\n[[package]]\n'
                'name = "foo"\nversion = "1.0.0"\n'
                'deps = "bar@^1.0"\n', encoding="utf-8")
            ok, problems = validate_lock({"foo": "^1.0.0"}, path)
        self.assertFalse(ok)
        self.assertTrue(problems)


class AuditTest(unittest.TestCase):
    """Auditoria de lumen.lock: sha256 vs cache, HMAC dos arquivos, deps."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cache = Cache(root / "cache")
        self.proj = root / "proj"
        self.proj.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def seed_pkg(self, name="lib-utils", version="1.0.0", deps=""):
        """Cria pacote no cache (extraído) + .lumepkg; retorna (nome, ver, sha)."""
        d = self.cache.package_dir(name, version)
        d.mkdir(parents=True, exist_ok=True)
        (d / "lumen.toml").write_text(
            f'[package]\nname = "{name}"\nversion = "{version}"\n\n'
            f"[dependencies]\n{deps}\n", encoding="utf-8")
        (d / "lib.py").write_text(f"VERSION = {version!r}\n")
        files = collect_files(d)
        _, sha = manifest_for(d, name, version, files)
        # archive: a partir de um projeto idêntico ao conteúdo extraído
        src = Path(self.tmp.name) / f"src-{name}-{version}"
        src.mkdir(exist_ok=True)
        (src / "lumen.toml").write_text(
            f'[package]\nname = "{name}"\nversion = "{version}"\n\n'
            f"[dependencies]\n{deps}\n", encoding="utf-8")
        (src / "lib.py").write_text(f"VERSION = {version!r}\n")
        out, _ = pack_project(src)
        self.cache.store_archive(name, version, out.read_bytes())
        return name, version, sha

    def write_lock(self, packages):
        write_lockfile(self.proj / "lumen.lock", packages)

    def test_audit_lock_integro(self):
        name, version, sha = self.seed_pkg()
        self.write_lock([{"name": name, "version": version, "sha256": sha,
                          "source": "registry", "deps": ""}])
        res = audit_project(self.proj, cache_root=self.cache.root)
        self.assertTrue(res["lock_ok"])
        self.assertTrue(res["ok"], res)
        pkg = res["packages"][0]
        self.assertEqual(pkg["name"], name)
        self.assertEqual(pkg["version"], version)
        self.assertTrue(pkg["sha_ok"])
        self.assertTrue(pkg["archive_exists"])
        self.assertTrue(pkg["signature_ok"])

    def test_audit_sha_divergente_detectado(self):
        name, version, _ = self.seed_pkg()
        self.write_lock([{"name": name, "version": version,
                          "sha256": "00" * 32, "source": "registry",
                          "deps": ""}])
        res = audit_project(self.proj, cache_root=self.cache.root)
        self.assertFalse(res["ok"])
        self.assertTrue(res["lock_ok"])  # lock parseia; o conteúdo diverge
        pkg = res["packages"][0]
        self.assertFalse(pkg["sha_ok"])
        self.assertTrue(any("sha256 diverge" in e for e in pkg["errors"]))

    def test_audit_sem_lock_aviso_limpo(self):
        res = audit_project(self.proj, cache_root=self.cache.root)
        self.assertFalse(res["lock_ok"])
        self.assertTrue(res["ok"])  # aviso, não problema de integridade
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["packages"], [])
        self.assertTrue(any("lumen.lock não encontrado" in w
                            for w in res["warnings"]))

    def test_audit_lista_deps(self):
        name, version, sha = self.seed_pkg(deps='dep-a = "^2.0.0"')
        self.write_lock([{"name": name, "version": version, "sha256": sha,
                          "source": "registry",
                          "deps": "dep-a@2.5.0"}])
        res = audit_project(self.proj, cache_root=self.cache.root)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["packages"][0]["deps"],
                         [("dep-a", "2.5.0")])

    def test_audit_assinatura_adulterada_detectada(self):
        name, version, sha = self.seed_pkg()
        # reescreve o archive com manifesto adulterado (digest zerado)
        ap = self.cache.archive_path(name, version)
        with zipfile.ZipFile(ap) as zf:
            manifest = json.loads(zf.read(".lumepkg.json"))
            entries = [(i.filename, zf.read(i.filename))
                       for i in zf.infolist()
                       if i.filename != ".lumepkg.json"]
        manifest["digest"] = "00" * 32
        new_ap = ap.with_suffix(".tmp.lumepkg")
        with zipfile.ZipFile(new_ap, "w") as zf:
            zf.writestr(".lumepkg.json",
                        json.dumps(manifest, indent=1, sort_keys=True))
            for fn, data in entries:
                zf.writestr(fn, data)
        os.replace(new_ap, ap)
        self.write_lock([{"name": name, "version": version, "sha256": sha,
                          "source": "registry", "deps": ""}])
        res = audit_project(self.proj, cache_root=self.cache.root)
        self.assertFalse(res["ok"])
        pkg = res["packages"][0]
        self.assertFalse(pkg["signature_ok"])
        self.assertTrue(pkg["sha_ok"])  # árvore extraída continua intacta


class TlsDevTest(unittest.TestCase):
    """keygen --tls (cert DEV-ONLY loopback) + registry HTTPS local."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipUnless(shutil.which("openssl"),
                         "openssl indisponível (stdlib não assina X.509)")
    def test_keygen_tls_gera_cert_dev_only(self):
        rc = main(["keygen", "--tls", "--dir", self.tmp.name])
        self.assertEqual(rc, 0)
        cert = Path(self.tmp.name) / "cert.pem"
        key = Path(self.tmp.name) / "key.pem"
        self.assertTrue(cert.is_file(), "cert.pem gerado")
        self.assertTrue(key.is_file(), "key.pem gerado")
        self.assertEqual(key.stat().st_mode & 0o777, 0o600,
                         "chave privada restrita ao dono")
        pem = cert.read_text(encoding="utf-8")
        self.assertIn("BEGIN CERTIFICATE", pem)
        # SAN IP:127.0.0.1 aparece em DER (contexto 0x87, 4 bytes 7f 00 00 01)
        import base64
        der = base64.b64decode(
            "".join(pem.split("-----BEGIN CERTIFICATE-----")[1]
                    .split("-----END CERTIFICATE-----")[0].split()))
        self.assertIn(b"\x87\x04\x7f\x00\x00\x01", der, "SAN loopback")
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)  # par é TLS válido

    def test_keygen_tls_sem_openssl_fallback_limpo(self):
        with mock.patch.object(lumen_pkg.shutil, "which",
                               return_value=None):
            with self.assertRaises(PkgError) as cm:
                lumen_pkg.gen_tls_dev_cert(self.tmp.name)
        msg = str(cm.exception)
        self.assertIn("DEV-ONLY", msg)
        self.assertIn("openssl", msg)
        script = Path(self.tmp.name) / "gen_tls_dev.sh"
        self.assertTrue(script.is_file(), "script auxiliar gravado")
        self.assertIn("openssl", script.read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("openssl"),
                         "openssl indisponível (stdlib não assina X.509)")
    def test_registry_tls_inicia(self):
        import ssl
        from urllib.request import urlopen
        cert, key = lumen_pkg.gen_tls_dev_cert(self.tmp.name)
        data = Path(self.tmp.name) / "regdata"
        server = RegistryServer(("127.0.0.1", 0), RegistryHandler, data)
        server.socket = registry.tls_server_context(cert, key).wrap_socket(
            server.socket, server_side=True)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            cctx = ssl.create_default_context()
            cctx.check_hostname = False
            cctx.verify_mode = ssl.CERT_NONE  # self-signed dev-only
            with urlopen(f"https://127.0.0.1:{port}/index",
                         context=cctx, timeout=10) as r:
                self.assertEqual(json.loads(r.read()),
                                 {"ok": True, "packages": {}})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    @unittest.skipUnless(shutil.which("openssl"),
                         "openssl indisponível (stdlib não assina X.509)")
    def test_registry_tls_e2e_cliente_https(self):
        """RegistryClient(https://127.0.0.1, insecure=True): publish/fetch/
        index redondos contra RegistryServer TLS com cert dev-only."""
        cert, key = lumen_pkg.gen_tls_dev_cert(self.tmp.name)
        data = Path(self.tmp.name) / "tls-e2e-data"
        server = RegistryServer(("127.0.0.1", 0), RegistryHandler, data)
        server.socket = registry.tls_server_context(cert, key).wrap_socket(
            server.socket, server_side=True)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = RegistryClient(f"https://127.0.0.1:{port}",
                                    insecure=True)
            proj = Path(self.tmp.name) / "tls-proj"
            proj.mkdir()
            (proj / "lumen.toml").write_text(
                '[package]\nname = "tls-lib"\nversion = "0.3.0"\n\n'
                "[dependencies]\n", encoding="utf-8")
            (proj / "tls.py").write_text("TLS_OK = 1\n")
            out, _ = pack_project(proj)
            payload = out.read_bytes()

            rep = client.publish("tls-lib", "0.3.0", payload)
            self.assertTrue(rep["ok"])

            idx = client.index()
            self.assertEqual(idx["packages"]["tls-lib"], ["0.3.0"])

            fetched = client.fetch("tls-lib", "0.3.0")
            self.assertEqual(fetched, payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    @unittest.skipUnless(shutil.which("openssl"),
                         "openssl indisponível (stdlib não assina X.509)")
    def test_registry_tls_sem_insecure_falha(self):
        """Mesmo servidor TLS self-signed: cliente SEM insecure deve falhar
        (verificação padrão → RegistryError/SSL), não passar silencioso."""
        cert, key = lumen_pkg.gen_tls_dev_cert(self.tmp.name)
        data = Path(self.tmp.name) / "tls-fail-data"
        server = RegistryServer(("127.0.0.1", 0), RegistryHandler, data)
        server.socket = registry.tls_server_context(cert, key).wrap_socket(
            server.socket, server_side=True)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        old_insecure = os.environ.pop("LUMEN_ALLOW_INSECURE", None)
        try:
            client = RegistryClient(f"https://127.0.0.1:{port}")  # sem insecure
            with self.assertRaises(RegistryError) as cm:
                client.index()
            msg = str(cm.exception).lower()
            self.assertTrue(
                "certif" in msg or "ssl" in msg or "inacessível" in msg,
                f"erro deveria mencionar verificação TLS: {msg}")
        finally:
            if old_insecure is not None:
                os.environ["LUMEN_ALLOW_INSECURE"] = old_insecure
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_registry_flags_tls_parcial_erro(self):
        """--tls-cert sem --tls-key (e vice-versa), e --tls-only sem o par:
        erro explícito (exit 2), não HTTP silencioso."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                registry.main(["--tls-cert", "/tmp/cert-x.pem", "--port", "0"])
            self.assertEqual(cm.exception.code, 2)
            with self.assertRaises(SystemExit) as cm:
                registry.main(["--tls-key", "/tmp/key-x.pem", "--port", "0"])
            self.assertEqual(cm.exception.code, 2)
            with self.assertRaises(SystemExit) as cm:
                registry.main(["--tls-only", "--port", "0"])
            self.assertEqual(cm.exception.code, 2)
        err_text = err.getvalue()
        self.assertIn("tls-cert", err_text)
        self.assertIn("tls-only", err_text)
        self.assertIn("par", err_text)  # mensagem fala do par PEM, não de HTTP


class CliTest(unittest.TestCase):
    def test_init_add_remove(self):
        old = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as td:
                proj = Path(td) / "meu-app"
                self.assertEqual(main(["init", str(proj)]), 0)
                cfg = proj / "lumen.toml"
                self.assertTrue(cfg.is_file())
                self.assertIn('name = "meu-app"',
                              cfg.read_text(encoding="utf-8"))
                os.chdir(proj)
                self.assertEqual(main(["add", "foo@^1.2.3"]), 0)
                self.assertEqual(main(["add", "bar"]), 0)
                text = cfg.read_text(encoding="utf-8")
                self.assertIn('foo = "^1.2.3"', text)
                self.assertIn('bar = "*"', text)
                self.assertEqual(main(["remove", "foo"]), 0)
                text = cfg.read_text(encoding="utf-8")
                self.assertNotIn("foo", text)
                self.assertIn('bar = "*"', text)
                self.assertNotEqual(main(["remove", "foo"]), 0)
        finally:
            os.chdir(old)

    def test_edit_helpers(self):
        text = TEMPLATE.format(name="x", registry="http://r")
        t = add_dependency(text, "a", "^1.0.0")
        t = add_dependency(t, "b", "~2.0.0")
        self.assertIn('a = "^1.0.0"', t)
        self.assertIn('b = "~2.0.0"', t)
        t = add_dependency(t, "a", "=1.5.0")
        self.assertEqual(t.count('a = "'), 1)
        self.assertIn('a = "=1.5.0"', t)
        t = remove_dependency(t, "b")
        self.assertNotIn('b = "', t)

    def test_new_named(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(main(["new", "app-x", td]), 0)
            cfg = Path(td) / "lumen.toml"
            self.assertIn('name = "app-x"',
                          cfg.read_text(encoding="utf-8"))

    def test_pack_cli(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"
            init_project(proj, name="cli-p")
            old = os.getcwd()
            try:
                os.chdir(proj)
                self.assertEqual(main(["pack"]), 0)
            finally:
                os.chdir(old)
            art = proj / "dist" / "cli-p-0.1.0.lumepkg"
            self.assertTrue(art.is_file())
            rep = verify_archive(art)
            self.assertTrue(rep["ok"], rep)


if __name__ == "__main__":
    unittest.main()