# `examples/001-050/025_memoizacao.lum`

025 — Memoização com `Map` e recursão.

Fib recursivo memoizado guarda resultados em `Map<i32,i32>`.
`fib_memo` consulta o cache com `map::get` e armazena com
`map::insert`. Mostra `match`, `if-else`, `while` e `Result`
para n inválido.

## Índice

- `fn` [fib_memo](#fib-memo)
- `fn` [fib_result](#fib-result)
- `fn` [fib_iter](#fib-iter)
- `fn` [sequencia](#sequencia)
- `fn` [main](#main)
- `fn` [testa_memo](#testa-memo)

## `fn` fib_memo

```lum
fn fib_memo(n: i32, cache: Map<i32, i32>) -> i32 {
```

Fib com memoização; `cache` é `Map` de n → fib(n).

## `fn` fib_result

```lum
fn fib_result(n: i32, cache: Map<i32, i32>) -> Result<i32, str> {
```

Fib com `Result` para n negativo.

## `fn` fib_iter

```lum
fn fib_iter(n: i32) -> i32 {
```

Fib iterativo para comparação.

## `fn` sequencia

```lum
fn sequencia(n: i32) -> Vec<i32> {
```

Calcula sequência de fib até `n` usando memo.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_memo

```lum
fn testa_memo() {
```

Atributos: `#[test]`

_Sem documentação `///`._
