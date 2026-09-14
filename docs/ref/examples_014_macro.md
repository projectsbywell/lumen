# `examples/014_macro.lum`

014 — Macros higiênicas.

`macro` define uma expansão sintática; o uso leva `!`.
A expansão de `garante_ok!` extrai `Ok` ou aborta com contexto.

## Índice

- `macro` [garante_ok](#garante-ok)
- `fn` [main](#main)
- `fn` [testa_garante_ok](#testa-garante-ok)

## `macro` garante_ok

```lum
macro garante_ok(res, msg) {
```

Extrai `Ok(v)` ou `panic` com `msg` + erro.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_garante_ok

```lum
fn testa_garante_ok() {
```

Atributos: `#[test]`

_Sem documentação `///`._
