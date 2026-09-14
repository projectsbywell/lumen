# Guia de contribuição — Lumen

> Como contribuir com código, docs e exemplos. Leia também
> `STYLE.md` (estilo obrigatório) e `lumen.toml` (manifesto do projeto).

## 1. Visão rápida

```
lumen/               # raiz do projeto (ver lumen.toml)
├── spec/            # especificação da linguagem (fonte da verdade)
├── compiler/        # frontend (lexer/parser) · middle (tipos/HIR) · backend (vm/c/wasm)
├── runtime/         # runtime + VM
├── stdlib/          # biblioteca padrão (superfície em docs/stdlib_api.lum)
├── docs/            # gen.py + API.md + guias (ESTE time)
├── conformance/     # suite.py — porta de entrada de todo PR
├── examples/        # .lum numerados + tutorials/ + book/
├── tests/           # testes de integração
├── tools/           # build, repl, test, pkg
├── ide/             # lsp, vscode, playground
└── infra/           # ci.yml, Dockerfile, site, releases
```

## 2. Fluxo de trabalho

1. **Abra uma issue** (ou use a existente) descrevendo mudança e motivação.
2. **Fork + branch**: `git checkout -b feat/lex-match-guard` (tipos:
   `feat/`, `fix/`, `docs/`, `test/`, `refactor/`).
3. **Implemente** seguindo `STYLE.md` + a `spec/`.
4. ** Rode a suíte de conformidade** — ela precisa estar 100% verde:
   ```sh
   python3 conformance/suite.py
   ```
5. **Regenere docs** se mexeu em API pública:
   ```sh
   python3 docs/gen.py --src docs/stdlib_api.lum --merge docs/API.md
   ```
6. **Abra o PR** com: o quê/porquê, casos da suíte afetados, saída do
   `suite.py` colada na descrição.

## 3. Porta de entrada: `conformance/suite.py`

- Todo PR que muda semântica **deve** adicionar/atualizar casos na suíte
  (`lexer`, `parser`, `tipos`, `match`, `struct_enum`, `bytecode`,
  `backends`, `runtime`, `stdlib`).
- Cada caso = `{id, categoria, fonte .lum, resultado esperado}`.
- O runner imprime `PASS/FAIL` e gera `conformance_report.json`.
- **Meta: 100% dos casos passando.** PR com FAIL não mergeia.

```sh
python3 conformance/suite.py                  # tudo
python3 conformance/suite.py --filter match   # só uma categoria
python3 conformance/suite.py --json /tmp/r.json
```

## 4. Padrão de commit e PR

- Commits em português, imperativo, escopo prefixado:
  `feat(match): guards com if`, `fix(lexer): escape \n em str`,
  `docs(api): regenera API.md`, `test(conf): +3 casos de bytecode`.
- Um PR = uma feature. PR grande (>400 linhas) deve ser fatiado.
- PR precisa de: descrição, link da issue, `PASS: N/N` da suíte,
  e (se API pública) `API.md` regenerado.

## 5. Código Lumen — checklist

- [ ] `///` em todo item `pub` (o CI roda `gen.py` e falha se `API.md`
      estiver dessincronizado).
- [ ] `match` exaustivo; sem `panic!` em caminho de erro recuperável.
- [ ] `#[test]` para função nova (`testa_<comportamento>`).
- [ ] Exemplo `.lum` numerado se a feature for visível ao usuário
      (ver `examples/` — hello → async).
- [ ] `lumen fmt` aplicado; linha ≤ 100 colunas.

## 6. Reportando bugs

Inclua: versão (`lumen --version`), SO, `.lum` mínimo reprodutor,
comando rodado, saída obtida vs. esperada. Se for erro de tipo ou
de `match`, diga qual caso da suíte deveria ter pego.

## 7. Conduta

- Respeito acima de tudo; critique código, nunca pessoas.
- Português nas issues/PRs/docs; identificadores em português ou
  inglês conforme o módulo (stdlib nova: português, ex. `ler_arquivo`).
- Sem PL privativa no repo; dependências só MIT/Apache-2.0.

## 8. Primeiras issues (bom para começar)

1. Adicionar 3 casos `TIP-*` de genéricos em `conformance/suite.py`.
2. Documentar `std::time` com exemplos em `docs/stdlib_api.lum`.
3. Exemplo `017_*` usando `std::env` + `std::fs`.
4. Traduzir mensagens de erro do parser (ver `compiler/frontend/`).
