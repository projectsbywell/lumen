# `examples/053_async_spawn.lum`

053 — Concorrência com `spawn`/`await` (runtime cooperativo).

O runtime/threads.py provê Future, poll, block_on, await cooperativo
e Channel.receber(timeout=0 = não-bloqueante).

ATENÇÃO: `channel`/`Channel` NÃO está disponível via .lum (não há
`use std::sync::channel` na stdlib). Veja docs/TUTORIAIS.md para
detalhes da limitação e alternativas.
Soma os inteiros de [inicio, fim).
Executa duas somas em concorrência via spawn e await.

## Índice

- `fn` [main](#main)
- `fn` [testa_soma_concorrente](#testa-soma-concorrente)
- `fn` [testa_soma_intervalo](#testa-soma-intervalo)

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_soma_concorrente

```lum
fn testa_soma_concorrente() {
```

Atributos: `#[test]`

_Sem documentação `///`._

## `fn` testa_soma_intervalo

```lum
fn testa_soma_intervalo() {
```

Atributos: `#[test]`

_Sem documentação `///`._
