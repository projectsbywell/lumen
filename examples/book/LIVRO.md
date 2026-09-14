# O Livro Lumen — v0.1 (esqueleto)

> Da primeira linha ao async. Cada capítulo combina teoria curta,
> código rodável em `examples/` e exercícios com gabarito.
> Convenções de código: `docs/STYLE.md`. Referência: `docs/API.md`.

## Como ler

- Capítulos 0–3: leia em ordem (~3h). É o "Lumen essencial".
- Capítulos 4–7: aprofunde por interesse; cada um é autocontido.
- Capítulos 8–12: avançado — compiler, backends e contribuição.
- Símbolo `▶ rode`: execute o arquivo indicado com `lumen run`.

---

## Capítulo 0 — Boas-vindas e instalação

- O que é Lumen: linguagem com tipos verificados antes de rodar
  ("estática"), `match` que obriga a cobrir todos os casos
  ("exaustivo") e 3 formas de executar ("backends": vm/c/wasm).
- Instalação (script, Docker, fonte) + `lumen --version`.
- ▶ rode `examples/001_hello.lum`. Anatomia do hello (linha por linha).
- Tour do repo: `spec/` (regras), `compiler/` (compilador), `stdlib/`
  (biblioteca pronta), `conformance/` (testes das regras).
- Exercícios: 3 (ver tutorial 01).

## Capítulo 1 — Funções e tipos

- `fn`, parâmetros/retorno com tipo escrito ("anotados"), `return`,
  `let` (não muda) / `mut` (muda).
- Tipos: `i32` (inteiro), `f64` (decimal), `bool` (verdadeiro/falso),
  `char` (uma letra, `'x'`), `str`/`String` (texto), `()` ("nada").
- Operadores, ordem de cálculo ("precedência": `*` antes de `+`),
  `+` em `str` (junta), divisão `i32` (trunca) vs `f64` (com fração).
- ▶ `002_fatorial.lum`, `003_fibonacci.lum`, `010_math.lum`.
- Exercícios: `div` com `Result`, conversões `str::to_int/from_int`.

## Capítulo 2 — Controle de fluxo

- `if/else` (escolhe um de dois caminhos), `while` (repete enquanto
  verdade), `for in` (repete para cada item do intervalo).
- Intervalos ("ranges") `0..n` (exclui `n`) / `0..=n` (inclui `n`).
  Sem `loop`/`break`/`continue`: use `while` com condição.
- Erros como valor: `Result` (`Ok`/`Err`), `Option` (`Some`/`None`),
  `?` (repassa o erro), `panic` (só para bugs, encerra o programa).
- ▶ estender `002` com `match` em `fat`.
- Exercícios: validador com `?` encadeado em 3 funções.

## Capítulo 3 — Structs, enums e `match`

- `struct` (agrupa dados), `impl` (funções do tipo), `self` (o próprio
  valor); função da "fábrica" (`::`) vs. método do valor (`.`).
- Enums (um valor entre N opções) com/sem dados junto ("payload");
  `Option`/`Result` como enums.
- `match`: valor fixo ("literal"), apelido ("binding"), `|` (ou),
  condição extra ("guard"), `_` (coringa), cobrir tudo ("exaustividade").
- ▶ `004_match.lum`, `005_struct.lum`, `006_enum.lum`.
- Exercícios: `Moeda`, `Triangulo`, exaustividade quebrada de propósito.

## Capítulo 4 — Coleções e strings

- `vec!` (cria lista), `map!` (cria dicionário), `vec::map/filter/len/push`,
  `map::get/has` (ler/testar chave).
- Quem é dono do valor ("ownership") em uma página: `str` (texto
  emprestado) vs `String` (texto próprio), `mut` (permite mudar), `+` junta.
- `std::str`: split (quebrar), join (juntar), trim (aparar), upper
  (maiúsculas), conversões; UTF-8 e caracteres.
- ▶ `007_colecoes.lum`, `008_strings.lum`.
- Exercícios: contador de palavras com `Map`.

## Capítulo 5 — IO, arquivos e CLI

- `io::{print, println, read_line, args}`, `fs::{read, write, existe}`.
- `env::var/cwd`, códigos de saída, `?` no `main`.
- ▶ `009_io.lum`, `016_cli_json.lum`.
- Exercícios: `cat` mínimo; CLI com flag `--saida`.

## Capítulo 6 — Testes e macros

- `#[test]`, `assert*`, `lumen test`, testes de `Result` com `?`.
- `macro`, higiene, `!` no uso; quando macro vs. `fn`.
- ▶ `013_teste.lum`, `014_macro.lum`.
- Exercícios: macro `garante_algum!` para `Option`.

## Capítulo 7 — HTTP, JSON, SQLite e async

- `http::get/post`, `json::parse/stringify`, `sqlite::{abrir, exec, query}`.
- `async fn`, `spawn`, `await`, `Handle`, executor determinístico.
- Projeto guiado completo (tutorial 05).
- ▶ `011_http.lum`, `012_sqlite.lum`, `015_async.lum`.
- Exercícios: cache SQLite para o agregador.

## Capítulo 8 — Tipos avançados e genéricos

- Genéricos (`Vec<T>` = lista de qualquer tipo `T`, `Map<K, V>`,
  `fn`s que servem para vários tipos), `trait` (só assinatura, sem corpo).
- `match` em tipos aninhados; erro como valor (`Result` encadeado).
- Erros comuns do checker e como ler cada mensagem.

## Capítulo 9 — Bytecode e a VM

- Opcodes (`CONST/ADD/.../PRINT/HALT`), pool de constantes, `disasm`.
- `compile_expr` + `vm_run`: do AST ao resultado (ver `suite.py`, `BC-*`).
- Escrevendo seu primeiro opcode (receita passo a passo).

## Capítulo 10 — Backends C e WASM

- `codegen_c` (i32 ↔ `int32_t`), `codegen_wasm` (`i32.*`).
- `lumen build --target`, FFI mínima, medindo binários.
- Casos `BE-*` da suíte como especificação executável.

## Capítulo 11 — Stdlib por dentro

- Anatomia de um módulo `std::*`; documentando com `///`.
- Regenerando `API.md` com `docs/gen.py` (pipeline de docs).
- Receita: propor, implementar, testar e documentar função nova.

## Capítulo 12 — Contribuindo e lançando

- Fluxo de PR, suíte 100% verde, `conformance_report.json`.
- Versionamento (`lumen.toml`), `infra/ci.yml`, `RELEASES.md`.
- Para onde levar o Lumen: roadmap e "boas primeiras issues".

---

## Apêndices

- A — Gramática de bolso (tokens, expressões, precedência).
- B — Mensagens de erro mais comuns (tabela causa→correção).
- C — Diferenças Lumen × Rust × Python (mapa mental).
- D — Gabaritos dos exercícios.
