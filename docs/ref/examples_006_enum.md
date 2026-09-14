# `examples/006_enum.lum`

006 — Enums com payload + `match` exaustivo.

Cada variante pode carregar valores. O `match` destrutura a
variante e liga os campos a variáveis.

## Índice

- `enum` [Forma](#forma)
- `fn` [area](#area)
- `fn` [main](#main)
- `fn` [testa_area](#testa-area)

## `enum` Forma

```lum
enum Forma {
```

Forma geométrica.

## `fn` area

```lum
fn area(f: Forma) -> f64 {
```

Área da forma.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_area

```lum
fn testa_area() {
```

Atributos: `#[test]`

_Sem documentação `///`._
