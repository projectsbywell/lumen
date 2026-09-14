# Lumen — Roadmap pós-v0.1

## v0.2 — Correção (entregue: 2026-09-13, 497 testes + 50/50)

- [x] `borrowck` NLL no front-end (expira no último uso; 17 testes).
- [x] Codegen real nos 3 targets com tracking de operandos
      (`verificar_dict` com pilha) + `test_e2e` ponta-a-ponta
      `.lum → .lbc → VM` com aritmética + C validado com `cc`.
      Bônus: cauda `if/match/expressão` vira `return` (era `ret 0`).
- [x] Lockfile v2 com grafo resolvido por aresta + sha do artefato;
      `install` valida e reutiliza o lock (`--frozen`/`--force`).
- [x] HMAC estrito opt-in (`--strict-hmac`/env) + HTTPS exigido
      (loopback ou `LUMEN_ALLOW_INSECURE=1`); `demo_key` auditado.
- [x] Checagem de traits (impl cobre required, aridade, impl de tipo
      fantasma, bounds `<T: Trait>`) + subtipagem estrutural
      (largura/profundidade, nominais como registros).
- [x] Cobertura 84% em `conformance/` como código (33 testes) +
      `ide/playground` com 6 testes (marcadores + `node --check`) no CI.

## v0.3 — Linguagem (entregue: 2026-09-14, 494+17 testes + 50/50)

- [x] Macros higiênicas fase-1 (3) — `compiler/frontend/higiene.py` com gensym,
      integrado ao parser; `vec!`/`map!` seguem builtins.
- [x] Keywords `const/type/self/Self/super/crate`; `module a.b`;
      atributos com args; literais com sufixo/raw/unicode (8–11) —
      `lexer.py` + `parser.py` (`IDENT_LIKE`, `module dotted`, `Attr(args)`,
      `r#ident`, `r"..."#`, `\u{...}`, `/* aninhado */`).
- [x] `async` real: `Future/poll` no runtime + executor (mimo M3) —
      `runtime/threads.py` (`Future`, `bloquear`, `block_on`, `Escalonador`).
- [x] GC com roots automáticos (frames+globals) (12) —
      `runtime/gc.py` (`registrar_frame`/`remover_frame`,
      `definir_global`/`remover_global` + `marcar_root` manual).
- [x] `Channel` bloqueante (13) — `Channel.receber()` sem timeout
      estaciona via `await_channel`; `timeout=0` mantém não-bloqueante.

## v0.4 — Ecossistema (entregue: 2026-09-14, 570 testes + 50/50)

- [x] **VM com GC** (P1) — `runtime/vm.py` wiring no `Heap` de
      `runtime/gc.py`: registro de frames/globals, GC periódico defensivo
      (`_gc_interval`=512 opcodes, nunca quebra execução). Evidência:
      `runtime/vm.py` (linhas 115–200, 337, 435–443), `runtime/test_runtime.py`.
- [x] **Pacotes com TLS + audit** (P2) — registry exige HTTPS (loopback ou
      `LUMEN_ALLOW_INSECURE=1`), contexto TLS dev-only self-signed,
      `--strict-hmac`/`LUMEN_STRICT_HMAC`, `lumen pkg audit` offline com
      detecção de `demo_key`. Evidência: `tools/pkg/lumen_pkg.py`
      (linhas 612–641, 767–836), `tools/pkg/test_pkg.py`.
- [x] **Debugger DAP + CI** (P3) — `ide/vscode/dap.py` (launch, breakpoints,
      condições, hit count, logpoints, eval) substitui o debugger mínimo;
      `ide.vscode.test_dap` na matriz 3-OS. Evidência: `ide/vscode/dap.py`,
      `ide/vscode/test_dap.py`, `infra/ci.yml`.
- [x] **Site + playground + livro PDF** (P4) — `infra/site/index.html`
      (+ `site_index.html`), playground WASM, `docs/pdf.py` gera
      `examples/book/LIVRO.pdf` (53 KB) no CI, job `pages` (GitHub
      Pages). Evidência: `infra/site/index.html`, `docs/pdf.py`,
      `examples/book/LIVRO.pdf`, `infra/ci.yml` (job `pages`).
- [x] **Releases binárias 3-OS** (P5) — `pyproject.toml` (sdist+wheel,
      entry `lumen = lumen_cli:main`, `requires-python>=3.8`),
      `lumen_cli.py` (CLI unificada), job `build-release` no `infra/ci.yml`
      (`python -m build` + PyInstaller onefile + smoke + checksums +
      upload em tags `v*`), `tools/test/test_release.py` (validação do
      pyproject + entry point), `infra/releases/` (NOTAS + SHA256SUMS).
      Evidência: `pyproject.toml`, `lumen_cli.py`, `infra/ci.yml`,
      `tools/test/test_release.py`, `infra/releases/NOTAS_v0.4.0.md`,
      `infra/releases/SHA256SUMS.txt`.

## v0.5 — Runtime async + GC total (entregue: 2026-09-14, 576+17 testes + 50/50)

- [x] **Wrapping `Objeto`** (P5.1) — `runtime/gc.py` (`envolver`/`desembrulhar`),
      STORE global aloca `Objeto`, LOAD desembrulha, 14 opcodes na borda,
      `TestVMGCWrapping` (4). Evidência: `outputs/lumen_v05_p1_wrapping.md`.
- [x] **Async na VM + lowering** (P5.2) — opcodes `YIELD`/`SPAWN`/`AWAIT_FUT`/
      `AWAIT_CH`/`CALL_NATIVE`, coroutines round-robin rastreadas no Heap,
      codegen emite `SPAWN`/`AWAIT_FUT` do AST existente, e2e imprime `777`.
      Evidência: `outputs/lumen_v05_p2a_vm_async.md`,
      `outputs/lumen_v05_p2b_compiler.md`.
- [x] **DAP gaps** (P5.3) — step por linha, eval seguro (AST restrita),
      attach, watchpoints, terminate cooperativo. DAP 12→17 OK.
- [x] **`lumen fmt` standalone** (P5.4) — `tools/fmt/lumen_fmt.py` (512L,
      idempotente, preserva strings/comentários), CLI `lumen fmt
      [--check|--diff]`, 8 testes. Evidência: `tools/fmt/`.

## Ideias (sem prazo)

- Self-hosting: reescrever o front-end em Lumen.
- Backend LLVM; LSP incremental.