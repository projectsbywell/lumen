# Releases — Lumen

> Histórico de versões. Formato: `lumen.toml [package] version` +
> git tag `vX.Y.Z`. Política: semver; spec congelada por minor.

## v0.5.4 — 2026-09-14 (integração: versões+docs+gates, semântica intacta)

- **Versões**: tudo em `0.5.4` (`lumen.toml`, `pyproject.toml` com
  `Repository` correto, `lumen_cli.py`, `conformance/suite.py`,
  `docs/gen.py`, `spec/*.md`); `docs/API.md` regenerado (diff só na
  versão); nota de honestidade em `SPEC.md` §8 (suíte 50/50 = subset
  v0.1: sem GC/async/traits macroscópicos).
- **Docs/release**: `LIMITACOES.md` virou v0.5.x (histórico congelado +
  fixes da leva); `README.md` com números reais (595+17) e comando
  `sha256sum -c` funcional; `infra/releases/NOTAS_v0.5.4.md` (nova);
  `SHA256SUMS.txt` com SHAs reais da tag v0.5.4 (publicada —
  sdist/wheel = build Windows, ver cabeçalho do arquivo).
- **CI**: gate novo `Run examples (001-004)` (idêntico nos 2 ymls,
  com diagnóstico GOT/WANT e tolerância a CRLF no Windows); passo
  `Testes unitários (v0.5)` inclui `tools.fmt.test_fmt`; smoke 70;
  `docker-entrypoint.py` = mesma lista do CI; `Dockerfile` v0.5.
- **Qualidade**: **595 testes unit OK + 17 boost OK**, **50/50
  conformidade**; Fix A (match `Result`/`?`, or-pattern/guard, builtins
  `Ok`/`Err`/`assert` reais na VM) + 2 testes e2e (002/004); tag
  `v0.5.4` publicada com Release + 8 assets, site HTTP 200.
- Breaking: **nenhum** — semântica e APIs intactas.
- Repo: https://github.com/projectsbywell/lumen (CI + Pages + releases em tags `v*`).

## v0.5.0 — 2026-09-14 (atual, runtime: Objeto+async+DAP gaps+fmt)

- **P5.1 — Wrapping `Objeto`**: STORE global aloca no Heap, LOAD desembrulha
  (igualdade preservada), 14 opcodes na borda, `envolver`/`desembrulhar` em
  `runtime/gc.py`. Não-tracked: locais de função, temps, `entrada`, compostos.
- **P5.2 — Async na VM**: `YIELD`/`SPAWN`/`AWAIT_FUT`/`AWAIT_CH`, coroutines
  round-robin rastreadas no Heap, lowering no `codegen_vm.py` (AST existente).
- **P5.3 — DAP gaps**: step por linha, eval seguro, attach, watchpoints,
  terminate cooperativo (17 testes DAP).
- **P5.4 — `lumen fmt`**: formatador idempotente + `lumen fmt [--check|--diff]`
  (8 testes).
- **Qualidade**: **576 unit + 17 boost OK**, **50/50 conformidade**.
- Breaking: nenhum.
- Repo: https://github.com/projectsbywell/lumen (CI + Pages + releases em tags `v*`).

## v0.4.0 — 2026-09-14 (ecossistema: GC+VM, TLS/audit, DAP, site/PDF, releases)

- **P1 — VM com GC**: `runtime/vm.py` wiring no `Heap` (`runtime/gc.py`):
  frames/globals registrados, GC periódico defensivo (512 opcodes),
  nunca quebra execução; valores continuam Python puros.
- **P2 — Pacotes com TLS + audit**: registry exige HTTPS (loopback ou
  `LUMEN_ALLOW_INSECURE=1`), contexto TLS dev-only, `--strict-hmac`,
  `lumen pkg audit` offline com detecção de `demo_key`
  (`tools/pkg/lumen_pkg.py`).
- **P3 — Debugger DAP + CI**: `ide/vscode/dap.py` (launch, breakpoints,
  condição, hit count, logpoints, eval) + `ide.vscode.test_dap` na
  matriz 3-OS do CI.
- **P4 — Site + playground + livro PDF**: `infra/site/index.html`,
  playground WASM, `docs/pdf.py` → `examples/book/LIVRO.pdf` (53 KB)
  no CI, job `pages` publica no GitHub Pages.
- **P5 — Releases binárias**: `pyproject.toml` (sdist+wheel, entry
  `lumen = lumen_cli:main`), `lumen_cli.py` (CLI unificada), job
  `build-release` 3-OS (`python -m build` + PyInstaller onefile + smoke
  `--help`/`001_hello.lum` + `sha256sum` + upload em tags `v*`),
  `tools/test/test_release.py`, `infra/releases/` (NOTAS + SHA256SUMS).
- **Qualidade**: **570 testes unit OK** (incl. 17 boost) + **50/50
  conformidade**; novos artefatos validados localmente
  (`python3 -m build --no-isolation` + PyInstaller onefile).
- Breaking: **nenhum** — código v0.3 compila e roda igual.
- Como lançar: ver "Como lançar a próxima" abaixo + `infra/releases/NOTAS_v0.4.0.md`.

## v0.3.0 — 2026-09-14 (linguagem: macros+keywords+async+GC+Channel)

- **Macros**: higiene fase-1 com gensym (`higiene.py`, 3 testes); `vec!`/`map!` intactos.
- **Léxico/sintaxe**: `self/Self/type/super/crate` keywords reais com fallback `IDENT_LIKE`,
  `module a.b.c`, `#[attr(args)]` retidos, `42i32`/`3.0f64`, `r#"raw"#`, `r#ident`,
  `\u{...}`/`\uXXXX`, `/* aninhados */` (16 testes `TestFrontendV03`).
- **Async**: `Future/poll` + `block_on` + `Escalonador` com `await_future`/`await_channel`
  (12 testes `TestAsyncV03`).
- **GC**: roots automáticos frames+globals + override manual (10 testes `TestGCRootsV03`);
  wiring VM↔Heap diferido para v0.4.
- **Channel**: bloqueante por padrão, `timeout=0` não-bloqueante (4 testes).
- **Qualidade**: **494 testes unit OK + 17 boost OK**, **50/50 conformidade**,
  spec `SEMANTICA.md §3.4/§4` + `EBNF.md` já normativos.
- Breaking: nenhum — código v0.2 compila igual (`self` antigo aceito via `IDENT_LIKE`/`r#`).

## v0.2.0 — 2026-09-13 (correção: NLL+traits+lock-v2+HMAC+e2e)

- **Front-end**: borrowck NLL (dois passes, expira no último uso),
  traits com `required` (impl cobre métodos+aridade), bounds `<T: Trait>`
  validados, tipos registro `{f: t}` com subtipagem largura/profundidade,
  cauda `if`/`match`/expressão vira `return`.
- **Back-ends**: `verificar_dict` (tracking de operandos) + `validar_wat`
  + `test_e2e` (`.lum → .lbc → VM`, C com `cc`, 9 testes).
- **Pacotes**: lockfile v2 (arestas + `artifact`), `install --frozen/--force`,
  HMAC estrito (`--strict-hmac`), HTTPS exigido, `demo_key` auditado.
- **Qualidade**: **497 testes OK** (+85), **50/50 conformidade**,
  `conformance/` com 33 testes e 84% de cobertura, playground com
  6 testes + `node --check` no CI.

## v0.1.0 — 2026-09-13 (docs+conformidade+exemplos+infra)

- **Docs**: `docs/gen.py` (gerador `///` → Markdown + índice, com paths
  relativos e desambiguação de basename), `API.md`
  (89 itens da stdlib, gerado), `STYLE.md`, `CONTRIB.md`, `TUTORIAIS.md`,
  `docs/ref/` (67 páginas, 385 itens) + `INDEX.md`.
- **Conformidade**: `conformance/suite.py` — 50 casos executáveis
  (lexer 5, parser 6, tipos 6, match 5, struct/enum 4, bytecode 5,
  backends 4, runtime 5, stdlib 10). **50/50 PASS (100%)** +
  `conformance_report.json`.
- **Exemplos**: 50 `.lum` em `examples/001-050/` (001_hello→050_chatbot,
  inclui espelho de `001_hello`→`016_cli_json` da raiz) + 20 tutoriais
  progressivos em `examples/tutorials/` (roteiro em `docs/TUTORIAIS.md`,
  ~20h); `book/LIVRO.md` (cap. 0–12 + apêndices) + `LIVRO.pdf`
  (regenerar exige `reportlab`, opcional) + 3 roteiros de vídeo.
  Smoke do front-end: 63/66 OK + 3 XFAIL documentados em
  `tools/test/smoke_allowlist.txt` (migração borrowck/enum em curso).
- **Infra**: `infra/ci.yml` (Python 3.12 nos 3 SO: 385 testes + 50/50 +
  smoke 66 exemplos + docs sincronizadas), `infra/Dockerfile`
  (imagem `python:3.12-slim`, sem toolchain externa) +
  `infra/docker-entrypoint.py` (shim `lumen run/build/test/conformance/
  doc/examples`), `infra/site_index.html` (+ cópia publicada em
  `infra/site/index.html`), este arquivo.
- **Implementação**: referência em Python 3.8+, sem dependências externas.
  Sem binário nativo nesta versão (ver `LIMITACOES.md`; binários no
  ROADMAP v0.4).
- **Raiz**: `README.md`, `LICENSE` (MIT), `lumen.toml`.
- Superfície da linguagem congelada: `fn/let/mut`, tipos `i32/f64/bool/
  char/str/String/Vec/Map/Option/Result`, `struct/enum/impl`, `match`
  exaustivo, `?`, `macro!`, `async/spawn/await`, `#[test]`.

## Como lançar a próxima

1. Bump em `lumen.toml` + `pyproject.toml` + seção nova aqui (data,
   destaques, breaking).
2. `python3 conformance/suite.py` 100% + `docs/gen.py` regenerado +
   `tools/test/test_release.py` OK (exige pyproject ≡ lumen.toml).
3. `git tag vX.Y.Z && git push --tags` — CI roda `build-test` + `build-release`
   (matriz 3-OS: sdist+wheel+binário+checksums) e o job `build-release`
   publica `dist/*` no GitHub Release (upload só em tag `v*`, `--clobber`).
4. Conferir artifacts + SHA256SUMS no release; copiar checksums finais
   para `infra/releases/SHA256SUMS.txt`; baixar os binários por OS.
