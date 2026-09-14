# `examples/005_struct.lum`

005 — Structs e métodos `impl`.

Um `struct` agrupa campos; `impl` adiciona métodos. `self` é o
primeiro parâmetro dos métodos de instância.

## Índice

- `struct` [Ponto](#ponto)
- `impl` [Ponto](#ponto)
- `fn` [novo](#novo)
- `fn` [norma](#norma)
- `fn` [main](#main)
- `fn` [testa_norma](#testa-norma)

## `struct` Ponto

```lum
struct Ponto { x: f64, y: f64 }
```

Ponto no plano cartesiano.

## `impl` Ponto

```lum
impl Ponto {
```

_Sem documentação `///`._

## `fn` novo

```lum
fn novo(x: f64, y: f64) -> Ponto {
```

Construtor.

## `fn` norma

```lum
fn norma(self) -> f64 {
```

Distância até a origem.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_norma

```lum
fn testa_norma() {
```

Atributos: `#[test]`

_Sem documentação `///`._
