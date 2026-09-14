# `examples/001-050/046_carrinho.lum`

046 — Carrinho de compras com `Vec` e `Map`.

Operações de adicionar, remover e calcular totais usando
`vec!`, `map!`, `vec::map`, `map::get` e `match`.

## Índice

- `struct` [Produto](#produto)
- `fn` [adicionar](#adicionar)
- `fn` [remover](#remover)
- `fn` [total](#total)
- `fn` [main](#main)
- `fn` [testa_carrinho](#testa-carrinho)

## `struct` Produto

```lum
struct Produto {
```

Produto do catálogo.

## `fn` adicionar

```lum
fn adicionar(carrinho: Map, id: i32) -> Map {
```

Adiciona uma unidade ao carrinho.

## `fn` remover

```lum
fn remover(carrinho: Map, id: i32) -> Map {
```

Remove uma unidade do carrinho.

## `fn` total

```lum
fn total(carrinho: Map, catalogo: Vec<Produto>) -> f64 {
```

Soma totais por categoria a partir do catálogo.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_carrinho

```lum
fn testa_carrinho() {
```

Atributos: `#[test]`

_Sem documentação `///`._
