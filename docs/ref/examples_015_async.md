# `examples/015_async.lum`

015 — Concorrência com `async`/`await`.

`async fn` suspende em IO; `spawn` agenda e devolve `Handle<T>`;
`await` consome o handle. O executor resolve na ordem do `spawn`.
Baixa o corpo de `url` (suspende sem bloquear o executor).
Baixa duas URLs em concorrência e concatena.

## Índice

- `fn` [main](#main)
- `fn` [testa_baixa_duas_assinatura](#testa-baixa-duas-assinatura)

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_baixa_duas_assinatura

```lum
fn testa_baixa_duas_assinatura() {
```

Atributos: `#[test]`

_Sem documentação `///`._
