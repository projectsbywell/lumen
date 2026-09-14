# `examples/001-050/021_tabela_hash.lum`

021 — Tabela hash com `Map` (hash map).

Usa `map!{}` e operações `map::insert`, `map::get`, `map::has`,
`map::remove`. Mostra colisões lógicas via chaves distintas,
`Option` e `match` com guards.

## Índice

- `fn` [tabela_inicial](#tabela-inicial)
- `fn` [inserir](#inserir)
- `fn` [buscar](#buscar)
- `fn` [remover](#remover)
- `fn` [contar_acima](#contar-acima)
- `fn` [main](#main)
- `fn` [testa_hash](#testa-hash)

## `fn` tabela_inicial

```lum
fn tabela_inicial() -> Map<str, i32> {
```

Cria tabela com alguns pares iniciais.

## `fn` inserir

```lum
fn inserir(t: Map<str, i32>, chave: str, valor: i32) -> Option<i32> {
```

Insere ou atualiza; devolve valor anterior se existia.

## `fn` buscar

```lum
fn buscar(t: Map<str, i32>, chave: str) -> Result<i32, str> {
```

Busca com `Result`: `Ok(valor)` ou `Err(mensagem)`.

## `fn` remover

```lum
fn remover(t: Map<str, i32>, chave: str) -> Option<i32> {
```

Remove e devolve `Some(valor)` se existia.

## `fn` contar_acima

```lum
fn contar_acima(t: Map<str, i32>, chaves: Vec<str>, limite: i32) -> i32 {
```

Conta quantas chaves possuem valor acima de `limite`.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_hash

```lum
fn testa_hash() {
```

Atributos: `#[test]`

_Sem documentação `///`._
