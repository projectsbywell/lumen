# `examples/001-050/038_retry.lum`

038 — Retry com backoff.

Tenta `n` vezes dobrando a espera (simulada por contador).

## Índice

- `fn` [instavel](#instavel)
- `fn` [com_retry](#com-retry)
- `fn` [main](#main)

## `fn` instavel

```lum
fn instavel(falhas: i32, tentativa: i32) -> Result<str, str> {
```

Simula operação que falha `falhas` vezes antes de dar `Ok`.

## `fn` com_retry

```lum
fn com_retry(falhas: i32, max: i32) -> Result<str, str> {
```

Tenta até `max` vezes; espera dobra a cada falha.

## `fn` main

```lum
fn main() {
```

_Sem documentação `///`._
