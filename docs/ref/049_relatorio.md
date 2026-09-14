# `examples/001-050/049_relatorio.lum`

049 — Geração de relatório com `Map` e `Vec`.

Agrupa dados por categoria, calcula totais e formata
um relatório textual usando `map!`, `vec!`, `match`
e `str::join`.

## Índice

- `struct` [Venda](#venda)
- `fn` [agrupar](#agrupar)
- `fn` [formatar_relatorio](#formatar-relatorio)
- `fn` [main](#main)
- `fn` [testa_relatorio](#testa-relatorio)

## `struct` Venda

```lum
struct Venda {
```

Registro de venda.

## `fn` agrupar

```lum
fn agrupar(vendas: Vec<Venda>) -> Map {
```

Agrupa vendas por categoria e soma valores.

## `fn` formatar_relatorio

```lum
fn formatar_relatorio(agrupado: Map) -> str {
```

Formata o relatório como string.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_relatorio

```lum
fn testa_relatorio() {
```

Atributos: `#[test]`

_Sem documentação `///`._
