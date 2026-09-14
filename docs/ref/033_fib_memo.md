# `examples/001-050/033_fib_memo.lum`

033 — Fibonacci com cache explícito.

Guarda resultados num vetor e reaproveita (memoização manual).

## Índice

- `fn` [fib_memo](#fib-memo)
- `fn` [fib](#fib)
- `fn` [main](#main)

## `fn` fib_memo

```lum
fn fib_memo(mut memo: vec, n: i32) -> i32 {
```

fib com tabela `memo` onde -1 significa "não calculado".

## `fn` fib

```lum
fn fib(n: i32) -> i32 {
```

Cria a tabela e calcula `fib(n)`.

## `fn` main

```lum
fn main() {
```

_Sem documentação `///`._
