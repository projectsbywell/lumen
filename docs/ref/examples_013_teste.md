# `examples/013_teste.lum`

013 — Testes com `#[test]`.

`lumen test` descobre toda `fn` marcada com `#[test]` e roda com
`assert`, `assert_eq` e `assert_ne`. Falha = panic com a diferença.

## Índice

- `fn` [soma](#soma)
- `fn` [main](#main)
- `fn` [testa_soma_basica](#testa-soma-basica)
- `fn` [testa_soma_zero](#testa-soma-zero)
- `fn` [testa_soma_negativa](#testa-soma-negativa)

## `fn` soma

```lum
fn soma(a: i32, b: i32) -> i32 {
```

Soma dois inteiros.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_soma_basica

```lum
fn testa_soma_basica() {
```

Atributos: `#[test]`

_Sem documentação `///`._

## `fn` testa_soma_zero

```lum
fn testa_soma_zero() {
```

Atributos: `#[test]`

_Sem documentação `///`._

## `fn` testa_soma_negativa

```lum
fn testa_soma_negativa() {
```

Atributos: `#[test]`

_Sem documentação `///`._
