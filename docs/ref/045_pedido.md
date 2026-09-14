# `examples/001-050/045_pedido.lum`

045 — Processamento de pedido com `Result` e `Option`.

Um pedido contém itens e tem status. Funções de validação
retornam `Result`, e a busca de itens usa `Option`.

## Índice

- `struct` [Item](#item)
- `enum` [Status](#status)
- `fn` [custo_item](#custo-item)
- `fn` [total_pedido](#total-pedido)
- `fn` [encontrar_item](#encontrar-item)
- `fn` [main](#main)
- `fn` [testa_pedido](#testa-pedido)

## `struct` Item

```lum
struct Item {
```

Item do pedido.

## `enum` Status

```lum
enum Status {
```

Status do pedido.

## `fn` custo_item

```lum
fn custo_item(nome: str, preco: f64, qty: i32) -> Result<f64, str> {
```

Custo total de um item.

## `fn` total_pedido

```lum
fn total_pedido(itens: Vec<Item>) -> Result<f64, str> {
```

Calcula o total do pedido.

## `fn` encontrar_item

```lum
fn encontrar_item(itens: Vec<Item>, nome: str) -> Option<Item> {
```

Procura item por nome; retorna `Option`.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_pedido

```lum
fn testa_pedido() {
```

Atributos: `#[test]`

_Sem documentação `///`._
