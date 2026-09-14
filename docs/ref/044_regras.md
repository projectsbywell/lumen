# `examples/001-050/044_regras.lum`

044 — Motor de regras com `match` e `if` guards.

Cada regra tem uma prioridade e uma condição. O motor
avalia todas as regras em ordem decrescente de prioridade
e aplica a primeira cuja condição é verdadeira.

## Índice

- `enum` [Regra](#regra)
- `fn` [satisfaz](#satisfaz)
- `fn` [aplicar](#aplicar)
- `fn` [main](#main)
- `fn` [testa_regras](#testa-regras)

## `enum` Regra

```lum
enum Regra {
```

Regra de negócio com prioridade e tipo.

## `fn` satisfaz

```lum
fn satisfaz(r: Regra, valor: i32) -> bool {
```

Avalia se o valor satisfaz a condição da regra.

## `fn` aplicar

```lum
fn aplicar(regras: Vec<Regra>, valor: i32) -> str {
```

Encontra a primeira regra aplicável.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_regras

```lum
fn testa_regras() {
```

Atributos: `#[test]`

_Sem documentação `///`._
