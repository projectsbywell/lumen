# `examples/001-050/031_calculadora.lum`

031 — Calculadora com `match`.

Despacha a operação por string e trata divisão por zero.

## Índice

- `fn` [calcula](#calcula)
- `fn` [main](#main)

## `fn` calcula

```lum
fn calcula(a: f64, op: str, b: f64) -> Result<f64, str> {
```

Calcula `a op b` ou devolve `Err`.

## `fn` main

```lum
fn main() {
```

_Sem documentação `///`._
