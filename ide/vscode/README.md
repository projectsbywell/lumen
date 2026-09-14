# Extensão Lumen para VS Code

Suporte à linguagem **Lumen**: gramática TextMate, snippets, LSP e depurador.

## Recursos

- **Gramática** (`syntaxes/lumen.tmGrammar.json`): keywords, strings, comentários `//` e `/* */`, números, funções, tipos.
- **Snippets** (`snippets/lumen.json`): `fn`, `match`, `struct`, `test`.
- **LSP**: servidor em `../lsp/server.py` (stdio JSON-RPC). Configure:
  - `lumen.server.path` (padrão: `python3`)
  - `lumen.server.args` (padrão: `["../lsp/server.py"]`)
- **Debugger** (`type: lumen`): configuração `launch` com `program: ${file}`.

## Uso

1. Abra um arquivo `.lumen`.
2. Snippets: digite `fn`, `match`, `struct` ou `test` + `Tab`.
3. Depuração: `F5` com a configuração *Depurar arquivo Lumen*.
4. Diagnósticos/completion/hover/definition/references/format/rename/codeAction via LSP:
   `python3 ../lsp/server.py`.

## Testes

```sh
cd ../lsp && python3 test_lsp.py
```
