# `examples/003_fibonacci.lum`

003 — Fibonacci iterativo e recursivo.

Compara as duas versões e mostra `while`, `let mut` e tuplas de
atribuição via variáveis temporárias.

## Índice

- `fn` [fib_rec](#fib-rec)
- `fn` [fib_iter](#fib-iter)
- `fn` [main](#main)
- `fn` [testa_fib](#testa-fib)

## `fn` fib_rec

```lum
fn fib_rec(n: i32) -> i32 {
```

Fibonacci recursivo (simples, lento para `n` grande).

## `fn` fib_iter

```lum
fn fib_iter(n: i32) -> i32 {
```

Fibonacci iterativo.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_fib

```lum
fn testa_fib() {
```

Atributos: `#[test]`

_Sem documentação `///`._
