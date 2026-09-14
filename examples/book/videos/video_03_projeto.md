# Vídeo 03 — Projeto: agregador async HTTP + SQLite (~20 min)

> Público: viu vídeos 01–02. Meta: montar o app completo do tutorial
> 05. Arquivos: `011_http`, `012_sqlite`, `014_macro`, `015_async`, `016_cli_json`.

## 0:00–2:30 — O que vamos construir

- [TELA] diagrama: API → `http::get` → SQLite → consulta.
- [FALA] "Três ingredientes novos: macro, banco em RAM e async."

## 2:30–6:30 — Macro `garante_ok!`

- [TELA] `014_macro.lum`; expande mentalmente para o `match`.
- [FALA] "Macro é atalho sintático: `Ok` passa, `Err` aborta com contexto."

## 6:30–11:00 — SQLite em memória

- [TELA] `012_sqlite.lum`: `abrir(":memory:")`, `exec`, `query`.
- [TELA] roda `#[test]` — "banco em RAM = teste hermético".

## 11:00–16:30 — Async de verdade

- [TELA] `015_async.lum`: `spawn` ×2 + `await`; mostra concorrência.
- [FALA] "`spawn` agenda e devolve o handle; `await` consome uma vez."
- [TELA] monta `sincroniza` do tutorial 05 e roda end-to-end.

## 16:30–20:00 — CLI + encerramento da série

- [TELA] `016_cli_json.lum` com `SAIDA=` setado e sem setar.
- [FALA] "Série completa na descrição: livro, tutoriais e a suíte de
  conformidade — 50 casos, 100% verde. Até a próxima."
