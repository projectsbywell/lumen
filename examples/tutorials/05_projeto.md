# Tutorial 05 — Projeto guiado: agregador HTTP + SQLite (~2h30)

> Nível 4. Exemplos: `011_http.lum`–`016_cli_json.lum`. Ao final: app
> concorrente com testes, macro e persistência — o "Lumen completo".

## 1. O que vamos montar

Um agregador que baixa itens de uma API (`http::get`), salva em
SQLite e responde consultas. Peças:

| Peça | Arquivo-guia |
|---|---|
| HTTP + JSON | `011_http.lum`, `016_cli_json.lum` |
| SQLite | `012_sqlite.lum` |
| Testes | `013_teste.lum` |
| Macro | `014_macro.lum` |
| Async | `015_async.lum` |

## 2. Passo 1 — macro de erro com contexto

```lum
macro garante_ok(res, msg) {
    match res {
        Ok(v) => v,
        Err(e) => panic(msg + ": " + e),
    }
}
```

Uso: `let db = garante_ok!(sqlite::abrir(":memory:"), "abrir");`

## 3. Passo 2 — sincronização async

```lum
async fn sincroniza(db: mut sqlite::Db, url: str) -> i32 {
    let r = garante_ok!(http::get(url), "falha http");
    return garante_ok!(sqlite::exec(db, r.corpo), "falha sql");
}

fn main() {
    let mut db = garante_ok!(sqlite::abrir(":memory:"), "abrir");
    garante_ok!(sqlite::exec(db, "CREATE TABLE item (id INT)"), "ddl");
    let h = spawn sincroniza(db, "https://api.exemplo.com/itens");
    println("sincronizados = " + str::from_int(await h));
}
```

`spawn` agenda a tarefa e devolve um "handle" (senha para buscar o
resultado depois); `await` usa essa senha uma vez. As tarefas terminam
na ordem em que foram criadas (executor de referência determinístico:
sempre o mesmo resultado na mesma ordem).

## 4. Passo 3 — testes (inclusive de banco em RAM)

```lum
#[test]
fn testa_sincroniza() {
    let mut db = garante_ok!(sqlite::abrir(":memory:"), "abrir");
    garante_ok!(sqlite::exec(db, "CREATE TABLE item (id INT)"), "ddl");
    assert_eq(sqlite::query(db, "SELECT * FROM item")?, vec![]);
}
```

`#[test]` pode usar `?`: se der `Err`, o teste falha. Banco `:memory:`
(na memória, sem arquivo) deixa o teste isolado — nada vaza de um
teste para outro — e rápido.

## 5. Passo 4 — CLI que amarra tudo (ver `016_cli_json.lum`)

`payload(args)` é a função que monta o texto de saída a partir dos
argumentos (definida em `016_cli_json.lum` com `json::stringify`).

```lum
use std::io;
use std::env;
use std::fs;

fn payload(args: Vec<String>) -> String {
    return json::stringify(args);
}

fn main() {
    let args = io::args();
    match env::var("SAIDA") {
        Some(caminho) => {
            let r = fs::write_arquivo(caminho, payload(args))?;
            println("salvo");
        },
        None => println(payload(args)),
    }
}
```

## 6. Checklist final

- [ ] `lumen fmt` limpo; `///` em todo item `pub`.
- [ ] `lumen test` verde; `python3 conformance/suite.py` 50/50.
- [ ] `docs/gen.py` regenerado se a API mudou.

Para onde ir: `examples/book/LIVRO.md` (capítulos 0→avançado) e
`docs/API.md` (referência completa).
