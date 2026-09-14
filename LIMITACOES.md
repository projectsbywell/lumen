# Lumen v0.5.x — Limitações conhecidas

> **Nota v0.5.4 (integração):** este documento nasceu na v0.2 como
> registro da revisão independente (8 revisores nativos). Tudo até a
> seção "Corrigidas nesta release", inclusive, é **histórico congelado**
> das eras v0.2–v0.4 — preservado como está, sem reedição.
> Fixes desta leva (v0.5.4, só integração/docs/CI, sem mudança de
> semântica): versões unificadas em `0.5.4` (manifestos, CLI, suíte,
> `gen.py`, specs); `docs/API.md` regenerado (diff só na versão);
> `SHA256SUMS.txt` com SHAs reais da tag v0.5.3 (placeholders
> removidos); gate CI `Run examples (001-004)` (vermelho em 002/004
> até o Fix A); smoke 66→70; `docker-entrypoint.py` com a mesma lista
> de testes do CI; notas da release em `infra/releases/NOTAS_v0.5.4.md`.

> Gerado na revisão independente (8 revisores nativos + tentativa de banca
> externa via OpenRouter). Itens 1, 2, 4, 5, 6, 7 e 14-parcial resolvidos
> na v0.2 (ver "Resolvidos na v0.2"). Restantes viram roadmap v0.3/v0.4.

## Resolvidos na v0.2 (2026-09-13)

- **NLL no `borrowck`** (`compiler/frontend/borrowck.py`, dois passes com
  ticks: expira empréstimos no último uso do referente; linear = NLL
  pleno, branches = conservador e sólido). Era o item 1.
- **Tracking de operandos + e2e** (`verificar_dict` com pilha e worklist
  de pcs; `validar_wat`; `compiler/backend/test_e2e.py` com 9 testes:
  `.lum → .lbc(JSON) → VM`, C compilado com `cc` e executado, WAT
  validado). Cauda `if`/`match`/expressão agora vira `return`
  (antes: `ret 0` silencioso). Era o item 2.
- **HMAC estrito + HTTPS** (`--strict-hmac`/`LUMEN_STRICT_HMAC=1` recusa
  a chave demo; `RegistryClient` exige `https://` fora de loopback;
  `verify_archive` marca `demo_key`). Era o item 4.
- **Lockfile v2** (`deps` por aresta `nome@versão-resolvida` + `artifact`
  sha256; `install` valida/reutiliza; `--frozen` p/ CI, `--force` p/
  re-resolver). Era o item 5.
- **Traits + subtipagem** (trait retém `required`; impl precisa cobrir
  métodos com mesma aridade; `impl` de tipo fantasma e bounds `<T: X>`
  p/ traits inexistentes viram erro; tipos registro `{f: t}` com
  subtipagem largura/profundidade; nominais valem como registros).
  Eram os itens 6 e 7. Fica p/ v0.3: enforcement de bounds em call-sites
  (exige inferência) e checagem de corpos default de trait.
- **Conformidade como código + playground no CI** (`conformance/`
  com 33 testes e 84% de cobertura; `ide/playground` com 6 testes;
  jobs no `infra/ci.yml`, incluindo `node --check`). Era o item 14-parcial
  (LSP) e o item de cobertura do roadmap.

## Resolvidos no turno da madrugada (2ª parte)

- **DAP mínimo** (`ide/vscode/dap.py` + teste): launch, breakpoints por
  função, continue/next, stack/scopes/variables/evaluate; manifesto
  VSCode aponta para `dap.py` (Python).
- **LSP incremental**: `apply_edit` com range + `version` no
  `publishDiagnostics`.
- **Registry TLS**: `--tls-cert/--tls-key` (HTTPS opt-in).

## Resolvidos na v0.4 (parte 2)

- **`lumen-pkg` contra registry TLS**: `--insecure`/`LUMEN_ALLOW_INSECURE=1`
  em https usa `ssl._create_unverified_context()` (dev-only loopback); sem
  insecure, cert self-signed falha com erro explícito (CERTIFICATE_VERIFY_FAILED).
- **`registry.py`**: par `--tls-cert`/`--tls-key` agora é obrigatório junto
  (apenas um → aborta com exit 2, sem HTTP silencioso); nova flag
  `--tls-only` recusa servir HTTP.
- **`lumen audit`**: offline por design — banner/help corrigidos (não há
  `--registry`; audita só o cache local).
- **Mocks/stubs** em `testingx` + **livro em PDF** via `docs/pdf.py`.
- **WASM executável**: dispatch por `pc`, i32, chamadas, `print`
  importado (validado com wasmtime; strings/floats limitados).
- **C executável**: `goto` direto, `lumen_rt.h`, validado com `cc`
  (ints/bools; floats truncados, resto 0).
- **`const` de módulo** (lexer/parser/semântica/borrowck/IR com inline).
- **Doc-fences 43/43** compilando; livro revisto para iniciantes.

- **Borrowck v0.2-lite** (`compiler/frontend/borrowck.py`, 10 testes).
  Move em `let`/`return`/arg, uso-após-move, `&`/`&mut` com exclusão,
  reatribuição encerra empréstimos. Conservador: tipos `?` são Copy;
  NLL pleno e erros de *stale borrow* ficam para a v0.3. 17 exemplos
  migrados para `&` idiomático.

- **E2E VM real.** `codegen_vm` agora emite o formato dict executável
  (consts/locals/bytecodes/entry + metas `__func__`); IR abaixa
  `if/while/for/match/return/calls/recursão`; VM ganhou `MOD/EQ/NEQ/LT/
  GT/LE/GE/NOT` e resolve CALL em todos os frames; `compiler/run.py`
  executa (`fib(10)=55`); 12 testes E2E. `.lbc` agora é o dict em JSON.
- Formato `.lbc` struct-packed virou legado (só `bytecode.py` + testes).

## Críticas (viram roadmap v0.2)

1. **Sem `borrowck`.** A spec promete ownership elidido com regras
   `Moved/BorrowMut`, mas o front-end não rastreia empréstimos. Programas
   com `&`/`&mut` passam sem checagem. *(muse12-7)*
2. **Codegens WASM/C finos.** `codegen_wasm` descarta valores com `drop`;
   `codegen_c` só declara constantes e retorna 0. VM dict é o target real;
   WASM/C geram esqueleto estrutural válido. *(nemotron-lightning 3,4)*
3. **Macros sem higiene.** `vec!`/`map!` são casos especiais no parser;
   macros de usuário (`macro!`) expandem sem higiene. *(muse12-9)*

## Altas

4. **Chave HMAC demo.** `lumen-pkg` assina/verifica com chave pública de
   demonstração se `LUMEN_HMAC_KEY` não estiver configurada; registry sem
   HTTPS aceito. Nunca usar em produção. *(big-pickle 1)*
5. **Lockfile parcial.** `lumen.lock` grava specs originais, não o grafo
   resolvido por aresta; `install` não valida o lock existente.
   *(big-pickle 4)*
6. **Traits/bounds não checados.** `trait`/`impl`/`where`/genéricos são
   aceitos sintaticamente; o verificador não impõe bounds. *(muse12-5)*
7. **Tipos estruturais sem subtipagem.** `{x: float}` parseia; largura/
   profundidade não são verificadas. *(muse12-1)*

## Médias

8. **Keywords faltantes.** `const`, `type`, `self`, `Self`, `super`,
   `crate` não são keywords (viram `IDENT`). *(muse12-3)*
9. **`module a.b` não suportado.** Nome de módulo é um `IDENT` único.
10. **`#[test(args)]` truncado.** Atributos guardam só o nome (`test`).
11. **Literais sem sufixo/raw.** `42int`, `r#"..."#`, `\u{...}`,
    comentários `/* aninhados */` não lexam. *(muse12-4)*
12. **GC com roots manuais.** `Heap.marcar_root` precisa ser chamado;
    objeto esquecido é coletado vivo. *(mimo M2)*
13. **Channel sem bloqueio.** `Channel.receber` retorna `None` em vez de
    bloquear a tarefa. *(mimo 5)*
14. **LSP simplificado.** Sem `version` em `publishDiagnostics`, sem
    incremental sync; `formatting` cobre o documento inteiro. *(general M1)*

## Baixas / cosméticas

15. `now_utc() == now()` (mesmo epoch). *(ling-flash 4)*
16. `lconvert` com branches redundantes. *(ling-flash 5)*
17. `lumen_test` sem cobertura de erros de load (parcialmente coberto).
18. Playground: `input` listener não atualiza `#c=` (share manual). *(general M3)*

## Corrigidas nesta release

- Recursão infinita em `Vec.pop/shift`, `Set.add`, `LumenString.*`.
- `lsub` colidia (strings × math) → polimórfico por tipo.
- Pool sqlite retornava conexões fechadas; `close()` agora idempotente.
- `STORE` da VM poluía globals a partir de funções.
- `execute()` do sqlitex executava DML duas vezes.
- `assert_almost_eq` com fronteira errada; `timedelta(days=)`.
- Parser: loop infinito em `sync()` com `}` perdido; hijack de `{` por
  struct-literal; `use`, genéricos, or-patterns, guards, `?`, `await`,
  `spawn`, `async fn`, `impl`, `macro`, `match`/`if` como expressão,
  chamadas de método, `assert` de `lumen_test` sobre `int`.
- Registry: tmp com colisão de pid → pid+thread+uuid.
- REPL: Ctrl-C durante eval agora cancela em vez de derrubar.
- LSP: `insertTextFormat: 2` nos builtins; lookbehind inválido no
  TextMate trocado por capturas.
- Playground: `0..10` tokenizava como número; `split(';')` quebrava
  blocos; `print(a,b)` avaliava 1 arg; `splitTop` fora de escopo.
