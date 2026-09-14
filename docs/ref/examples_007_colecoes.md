# `examples/007_colecoes.lum`

007 — Coleções: `Vec<T>` e `Map<K, V>`.

`vec![...]` cria vetores, `map!{...}` cria mapas. `vec::map` e
`vec::filter` transformam coleções sem `mut`.

## Índice

- `fn` [dobra](#dobra)
- `fn` [dobrar_um](#dobrar-um)
- `fn` [main](#main)
- `fn` [eh_par](#eh-par)
- `fn` [testa_dobra](#testa-dobra)

## `fn` dobra

```lum
fn dobra(v: Vec<i32>) -> Vec<i32> {
```

Dobra cada elemento do vetor.

## `fn` dobrar_um

```lum
fn dobrar_um(x: i32) -> i32 {
```

Auxiliar de `dobra`.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` eh_par

```lum
fn eh_par(x: i32) -> bool {
```

Auxiliar de filtro.

## `fn` testa_dobra

```lum
fn testa_dobra() {
```

Atributos: `#[test]`

_Sem documentação `///`._
