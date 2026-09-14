# `examples/001-050/043_maquina_estado.lum`

043 — Máquina de estado finita com `enum` + `match`.

Estados possíveis de um pedido são representados como
enum. `transicao` avalia o estado atual e a ação para
produzir o próximo estado, com `match` exaustivo.

## Índice

- `enum` [Estado](#estado)
- `enum` [Acao](#acao)
- `fn` [transicao](#transicao)
- `fn` [main](#main)
- `fn` [testa_transicao](#testa-transicao)

## `enum` Estado

```lum
enum Estado {
```

Estados possíveis de um fluxo de pedido.

## `enum` Acao

```lum
enum Acao {
```

Ações disponíveis para avançar ou recuar no fluxo.

## `fn` transicao

```lum
fn transicao(e: Estado, a: Acao) -> Estado {
```

Avalia a transição de estado.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_transicao

```lum
fn testa_transicao() {
```

Atributos: `#[test]`

_Sem documentação `///`._
