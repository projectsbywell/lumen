# Lumen v0.5

Linguagem pequena e estática, com `match` exaustivo, `Result`/`Option`,
macros higiênicas, `async`/`await` e três backends (**vm**, **c**, **wasm**).
v0.5: runtime — heap com `Objeto` (globais envolvidos, LOAD desembrulha),
`async` de verdade na VM (`SPAWN`/`AWAIT_FUT`/`AWAIT_CH`/`YIELD` + lowering
no codegen), DAP por linha + eval seguro + attach + watchpoints, e
`lumen fmt` standalone.
576 testes unit + 17 boost + 50/50 conformidade (ver ROADMAP).

```lum
fn main() {
    match fat(5) {
        Ok(v) => println("5! = " + str::from_int(v)),
        Err(e) => println("erro: " + e),
    }
}
```

## Instalação

**Via pip** (Python 3.8+, sem dependências — instala o comando `lumen`):

```sh
pip install .                    # a partir do repo (sdist+wheel via build)
```

**Binário nativo** (sem Python; baixe o do seu OS na release v0.4.0 —
Linux `lumen`, Windows `lumen.exe`, macOS `lumen`; verifique o sha256 em
`infra/releases/SHA256SUMS.txt`):

```sh
chmod +x lumen && sudo mv lumen /usr/local/bin/
lumen --help                     # smoke
```

## Build e uso (fonte)

```sh
# compilador: .lum -> IR / .lbc / .wat / .c
python3 compiler/lumenc.py examples/001_hello.lum ir
python3 compiler/lumenc.py examples/002_fatorial.lum lbc   # bytecode .lbc
python3 compiler/lumenc.py examples/002_fatorial.lum wat   # WebAssembly texto
python3 compiler/lumenc.py examples/002_fatorial.lum c     # C99 + lumen_rt.h

# testes (incl. 17 boost) + conformidade (50/50)
PYTHONPATH=. python3 -m unittest compiler.test_compiler compiler.backend.test_backends \
  compiler.backend.test_e2e compiler.test_front_extra compiler.test_borrow \
  runtime.test_runtime stdlib.test_stdlib tools.pkg.test_pkg \
  tools.build.test_build tools.test.test_runner_self tools.test.test_release \
  ide.lsp.test_lsp ide.lsp.test_server_extra ide.vscode.test_dap \
  ide.playground.test_playground conformance.test_conformance
PYTHONPATH=.:stdlib python3 test_boost.py
python3 conformance/suite.py

# CLI unificada (entry point do wheel/binário; roda também do checkout)
python3 lumen_cli.py --help
python3 lumen_cli.py run examples/001_hello.lum

# REPL / build / pacotes / registry / LSP / execução
python3 tools/repl/repl.py
python3 compiler/run.py examples/001_hello.lum   # compila e executa na VM
python3 tools/build/lumen_build.py --help
python3 tools/pkg/lumen_pkg.py --help
python3 tools/pkg/registry.py --port 8765
python3 ide/lsp/server.py
python3 docs/gen.py --src docs/stdlib_api.lum --merge docs/API.md
```

Ou Docker: `docker build -f infra/Dockerfile -t lumen .`

## Mapa do repo

| Pasta | Conteúdo |
|---|---|
| `spec/` | especificação (fonte da verdade) |
| `compiler/` | frontend → middle → backends `vm/c/wasm` |
| `runtime/` · `stdlib/` | VM + GC + biblioteca padrão (`docs/API.md`) |
| `docs/` | `gen.py`, `API.md`, `STYLE.md`, `CONTRIB.md`, `TUTORIAIS.md`, `ref/` |
| `conformance/` | `suite.py` + `conformance_report.json` |
| `examples/` | 50 `.lum` em `001-050/` + raiz + tutoriais + `book/` (livro + 3 vídeos) |
| `tests/` · `tools/` · `ide/` | integração, build/repl/test/pkg, LSP/VSCode (DAP) |
| `infra/` | `ci.yml`, `Dockerfile`, `site/`, `releases/`, `RELEASES.md` |
| raiz | `pyproject.toml` (sdist/wheel/binário), `lumen_cli.py` (CLI unificada), `lumen.toml` |

## Comece por aqui

1. `docs/TUTORIAIS.md` — roteiro 0→19 com 20 tutoriais (~20h).
2. `examples/001_hello.lum` → `016_cli_json.lum` (numerados por tema).
3. `docs/API.md` — referência da stdlib (gerada de `///`).
4. `docs/STYLE.md` + `docs/CONTRIB.md` — para contribuir.

## Conformidade

```sh
python3 conformance/suite.py                  # tudo (meta 100%)
python3 conformance/suite.py --filter match   # uma categoria
```

50 casos (lexer, parser, tipos, match, struct/enum, bytecode, backends,
runtime, stdlib) — cada feature da spec com resultado esperado, relatório
em `conformance/conformance_report.json`.

## Licença

MIT — ver `LICENSE`. Manifesto: `lumen.toml`. Release notes:
`infra/RELEASES.md` + `infra/releases/NOTAS_v0.4.0.md`.