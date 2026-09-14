# `examples/001-050/040_validador.lum`

040 — Validador com guards.

Usa `match` com guards para regras de negócio legíveis.

## Índice

- `fn` [categoria](#categoria)
- `fn` [senha_ok](#senha-ok)
- `fn` [main](#main)

## `fn` categoria

```lum
fn categoria(idade: i32) -> Result<str, str> {
```

Valida idade e devolve a categoria ou o erro.

## `fn` senha_ok

```lum
fn senha_ok(s: str) -> bool {
```

Senha precisa de 8+ caracteres.

## `fn` main

```lum
fn main() {
```

_Sem documentação `///`._
