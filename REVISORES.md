# Lumen v0.1 — Quem fez o quê

> **[HISTÓRICO v0.1, congelado em 2026-09-13]** — registro da
> implementação e das bancas de revisão originais. Preservado como
> está; números (testes, exemplos, placar) referem-se àquela época e
> foram superados pelas releases seguintes (ver `infra/RELEASES.md`).

Orquestrador: **Muse Spark 1.3** (Meta). Estratégia: 8 implementadores
nativos em paralelo → integração e correção pelo orquestrador → banca de
revisão (8 nativos) → correções → verificação final.

## Implementação

| Subsistema | Arquivos | Responsável | Status |
|---|---|---|---|
| Spec + EBNF + tipos + semântica + 5 ADRs | `spec/` | muse12 (Muse Spark 1.2) | entregue |
| Front-end (lexer/parser/AST/semântica) | `compiler/frontend/` | orquestrador (recuperação; agentes vazios) | refeito, 16/16 exemplos |
| Middle (IR SSA + 5 passes + verificador) | `compiler/middle/` | orquestrador | entregue |
| Backends VM/WASM/C + `lumenc` | `compiler/backend/`, `compiler/lumenc.py` | orquestrador | 16×4 targets OK |
| Runtime VM/GC/threads/rtlib (52 testes) | `runtime/` | mimo (MiMo-V2.5) | entregue + 1 fix |
| Stdlib pylumen + lum (175 testes) | `stdlib/` | ling-flash (Ling 3.0 Flash) | entregue + 8 fixes |
| Pkg + registry + build + REPL (59 testes) | `tools/{pkg,build,repl}` | big-pickle (Zen) | entregue + 3 fixes |
| Test-framework `lumen_test` | `tools/test/` | ling-flash/big-pickle | entregue + 2 fixes |
| LSP + VSCode + playground | `ide/` | general | entregue + 6 fixes |
| Docs + conformidade 50/50 + 16 exemplos + livro + infra | `docs/ conformance/ examples/ infra/ README LICENSE lumen.toml` | explore | entregue |

3 agentes nativos retornaram vazios na implementação (nemotron,
nemotron-lightning, ling-flash teve entrega parcial via arquivos);
o orquestrador reimplementou `compiler/` e aplicou 12 correções na stdlib.

## Revisão (todos os 8 nativos)

| Revisor | Alvo | Achados aplicados |
|---|---|---|
| muse12 | spec × implementação | 9 divergências → LIMITACOES/ROADMAP |
| nemotron | frontend | vazio (sem achados) |
| nemotron-lightning | middle+backends | 5 (codegen fino → limitação 2) |
| mimo | runtime | 5+3 → fix STORE/globals |
| ling-flash | stdlib | 5+3 → fix sqlitex/testingx/collections |
| big-pickle | pkg/build/repl/test | 5+3 → fix registry-tmp, REPL Ctrl-C, runner |
| general | LSP/VSCode/playground/docs | 5+3 → fix snippet, gramática, 4 no playground |
| explore | integração E2E | 333 OK, 50/50, 16/16 confirmado |

## Banca externa (OpenRouter free, 20 modelos)

Tentativa registrada em `.reviews/` (comando reproduzível abaixo). Resultado:
o runtime `opencode run` neste ambiente falha sob carga (crash do Bun
`Bus error`, `ENOSYS` sem `LANG=C.UTF-8`, `UnknownError` do servidor) e a
latência da fila free (>150 s por chamada) inviabilizou as 20 revisões na
sessão. Nenhuma revisão externa completou; a cobertura foi assumida pela
banca nativa (acima). Para reproduzir:

```sh
export LANG=C.UTF-8 LC_ALL=C.UTF-8
opencode run "MENSAGEM" --dir /root/scripts/lumen \
  --dangerously-skip-permissions -m "<model>" -f "<arquivo>"
```

Modelos alvo (20): `cohere/north-mini-code:free`,
`dots-studio/dots-3-note-preview:free`, `google/gemma-4-26b-a4b-it:free`,
`google/gemma-4-31b-it:free`, `inclusionai/ling-3.0-flash-fin:free`,
`ling-3.0-flash-sante:free`, `ling-3.0-flash-vl:free`,
`liquid/lfm-2.5-2.6b:free`, `nex-agi/nex-n2.5-mini:free`,
`nex-n2.5-pro:free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`,
`nemotron-3-super-120b-a12b:free`, `nemotron-3-ultra-550b-a55b:free`,
`nemotron-3.5-content-safety:free`, `nemotron-3.5-lightning:free`,
`openrouter/free`, `poolside/laguna-s-2.1:free`, `laguna-xs-2.1:free`,
`thinkingmachines/inkling-small:free`, `thinkingmachines/inkling:free`.

## Placar final (turno da madrugada, em andamento)

- `unittest`: **419 testes, OK** (+12 E2E VM, +10 borrowck, +3 const,
  +4 WASM exec, +4 C exec, +1 DAP, +2 mocks)
- `conformance/suite.py`: **50/50 (100%)**
- Doc-fences: **43/43 blocos ```lum compilam** (tutoriais + livro + docs)
- Livro revisto para iniciantes (21 arquivos) + PDF gerado (`docs/pdf.py`)
- `const` de módulo implementado (lexer/parser/semântica/borrowck/IR)
- `conformance/suite.py`: **50/50 (100%)**
- E2E VM (`compiler/run.py`): aritmética, `if/while/for`, chamadas,
  recursão (`fat(5)=120`, `fib(10)=55`), `match`, `&&/||/!`, strings
- E2E WASM (wasmtime): aritmética, `while`, `fib_rec(10)=55`, match+print
- E2E C (cc): aritmética, `while`, `fat(5)=120`, match+print
- DAP: breakpoint por função, step, stack/scopes/evaluate, continue
- Borrowck v0.2-lite integrado a `lumenc` e `run`
- Mocks/stubs (`Mock`, `mock`, `stub`) + livro em PDF (`docs/pdf.py`)
- LSP incremental + `version`; registry com `--tls-cert/--tls-key`
- Matriz: **50 exemplos × 4 targets = 200/200**
- Cobertura: compiler 95% · runtime 83% · stdlib 90% · tools 82% · ide 83%
- **Android (Termux, Python 3.14, aarch64): conformidade 50/50 + unittest
  383 OK** — 7 falhas iniciais eram paths `/tmp/opencode` chapados e
  suposição de UTC nos testes (corrigidos via `tempfile` + relógio
  local); nenhum bug da plataforma.
