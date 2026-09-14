# `examples/001-050/018_busca_binaria.lum`

018 — Busca binária iterativa em `Vec<i32>` ordenado.

A busca binária divide o intervalo ao meio a cada passo.
Retorna `Some(posição)` se encontrar o alvo e `None` caso
contrário. Mostra `while`, `match` e `Option`.

## Índice

- `fn` [busca_binaria](#busca-binaria)
- `fn` [busca_resultado](#busca-resultado)
- `fn` [esta_ordenado](#esta-ordenado)
- `fn` [main](#main)
- `fn` [testa_busca](#testa-busca)

## `fn` busca_binaria

```lum
fn busca_binaria(v: Vec<i32>, alvo: i32) -> Option<i32> {
```

Busca `alvo` em `v` ordenado. Devolve `Some(indice)` ou `None`.

## `fn` busca_resultado

```lum
fn busca_resultado(v: Vec<i32>, alvo: i32) -> Result<i32, str> {
```

Versão que devolve `Result` com mensagem em caso de falha.

## `fn` esta_ordenado

```lum
fn esta_ordenado(v: Vec<i32>) -> bool {
```

Verifica se o vetor está ordenado (pré-condição).

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_busca

```lum
fn testa_busca() {
```

Atributos: `#[test]`

_Sem documentação `///`._
