# Notas da release — Lumen v0.4.0 (2026-09-14)

Release do **ecossistema**: VM com GC, pacotes com TLS/audit, debugger
DAP, site + playground + livro PDF, e as **primeiras releases binárias**.

> Documento de apoio do GitHub Release v0.4.0 (a tag se cria/push manual).
> Resumo executivo em `../RELEASES.md`.

## Assets esperados por OS

| OS | Artefato | Origem |
|---|---|---|
| todos | `lumen-0.4.0.tar.gz` (sdist) | `python3 -m build` |
| todos | `lumen-0.4.0-py3-none-any.whl` (wheel) | `python3 -m build` |
| Linux (x86_64) | `lumen` | PyInstaller `--onefile` |
| Windows (x86_64) | `lumen.exe` | PyInstaller `--onefile` |
| macOS | `lumen` | PyInstaller `--onefile` |
| todos | `SHA256SUMS.txt` | `sha256sum dist/*` |

Todos com checksum em `SHA256SUMS.txt` (por OS, gerado no CI).

## Como instalar

### Via pip (Python 3.8+, sem dependências)

```sh
# a partir do repo:
pip install .                      # instala o script `lumen` no PATH
# ou direto do sdist/wheel baixado:
pip install lumen-0.4.0-py3-none-any.whl
```

### Binário nativo (sem Python instalado)

1. Baixar o binário do seu OS do GitHub Release v0.4.0.
2. Verificar o checksum: `sha256sum -c SHA256SUMS.txt` (Linux/macOS) ou
   `certutil -hashfile lumen.exe SHA256` (Windows).
3. Mover para o PATH e dar permissão (Linux/macOS):

```sh
chmod +x lumen
sudo mv lumen /usr/local/bin/
```

## Smoke da instalação

```sh
lumen --help                       # uso dos subcomandos
lumen version                      # lumen 0.4.0
lumen build examples/001_hello.lum ir   # .lum -> IR (stdout)
lumen run examples/001_hello.lum        # compila e executa na VM
lumen test                          # runner @test no diretório
lumen pkg audit                     # auditoria offline do lockfile
lumen conformance                   # suíte 50/50 (precisa do repo)
```

No binary, `run`/`build`/`test`/`pkg`/`repl` funcionam de qualquer
diretório; `doc`/`examples`/`conformance` precisam da árvore-fonte.

## O que veio antes (destaques P1–P5)

- **P1 — VM com GC**: `runtime/vm.py` wiring no `Heap` de `runtime/gc.py`
  (registro de frames/globals, GC periódico defensivo), valores continuam
  Python puros (wrapping `Objeto` fica para v0.5).
- **P2 — Pacotes com TLS/audit**: `tools/pkg/lumen_pkg.py` exige HTTPS
  (loopback ou `LUMEN_ALLOW_INSECURE=1`), `--strict-hmac`, `lumen pkg
  audit` offline com detecção de `demo_key`.
- **P3 — DAP + CI**: `ide/vscode/dap.py` (launch, breakpoints, condição,
  hit count, logpoints, eval) + `test_dap.py` no CI; suite unit 3-OS.
- **P4 — Site + playground + PDF**: `infra/site/index.html`, playground
  WASM, `examples/book/LIVRO.pdf` gerado por `docs/pdf.py`, job `pages`
  (deploy GitHub Pages).
- **P5 — Releases**: este diretório + `pyproject.toml` + job
  `build-release` (sdist+wheel+binário 3-OS+checksums+upload em `v*`).

## Breaking changes

Nenhum — código escrito para v0.3 compila e roda igual nesta versão.