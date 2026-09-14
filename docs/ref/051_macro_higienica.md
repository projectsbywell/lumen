# `examples/051_macro_higienica.lum`

051 — Macro higiênica que PROVA não-captura por shadowing.

A macro `soma_um!` tem binding local `n` (gensym'd para __hygN).
A `n` do chamador não é capturada nem movida: a expansão usa
`__hyg1` como nome interno, garantindo isolamento total.

## Índice

- `macro` [soma_um](#soma-um)
- `macro` [dobro](#dobro)
- `fn` [main](#main)
- `fn` [testa_soma_um_nao_captura](#testa-soma-um-nao-captura)
- `fn` [testa_dobro_nao_captura](#testa-dobro-nao-captura)

## `macro` soma_um

```lum
macro soma_um(x) {
```

Soma 1 ao argumento. O binding `n` é gensym'd para não capturar
a `n` do escopo do chamador.

## `macro` dobro

```lum
macro dobro(x) {
```

Macro que multiplica por 2, com binding `valor` gensym'd.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_soma_um_nao_captura

```lum
fn testa_soma_um_nao_captura() {
```

Atributos: `#[test]`

_Sem documentação `///`._

## `fn` testa_dobro_nao_captura

```lum
fn testa_dobro_nao_captura() {
```

Atributos: `#[test]`

_Sem documentação `///`._
