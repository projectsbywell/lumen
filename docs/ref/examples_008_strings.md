# `examples/008_strings.lum`

008 — Strings UTF-8.

`str` é UTF-8 imutável; `str::len` conta caracteres (não bytes).
`+` concatena `str + str`.

## Índice

- `fn` [normaliza](#normaliza)
- `fn` [main](#main)
- `fn` [testa_normaliza](#testa-normaliza)

## `fn` normaliza

```lum
fn normaliza(nome: str) -> String {
```

Normaliza um nome: tira espaços e padroniza maiúsculas.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_normaliza

```lum
fn testa_normaliza() {
```

Atributos: `#[test]`

_Sem documentação `///`._
