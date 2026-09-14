# `examples/001-050/017_bubble_sort.lum`

017 — Bubble sort com `Vec` e `while`.

Ordena um vetor de inteiros usando o algoritmo de bubble sort.
Repete varreduras trocando vizinhos fora de ordem até o vetor
ficar ordenado. Mostra `while`, `vec::len`, `vec::get` e `vec::push`.

## Índice

- `fn` [troca](#troca)
- `fn` [passo](#passo)
- `fn` [bubble_sort](#bubble-sort)
- `fn` [ordenado](#ordenado)
- `fn` [main](#main)
- `fn` [testa_bubble](#testa-bubble)

## `fn` troca

```lum
fn troca(v: Vec<i32>, i: i32, j: i32) -> Vec<i32> {
```

Troca os elementos nas posições `i` e `j` e devolve novo vetor.

## `fn` passo

```lum
fn passo(v: Vec<i32>) -> Vec<i32> {
```

Uma passada de bubble: empurra o maior para o final.

## `fn` bubble_sort

```lum
fn bubble_sort(v: Vec<i32>) -> Vec<i32> {
```

Bubble sort completo com `n` passadas.

## `fn` ordenado

```lum
fn ordenado(v: Vec<i32>) -> bool {
```

Verifica se o vetor está ordenado.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_bubble

```lum
fn testa_bubble() {
```

Atributos: `#[test]`

_Sem documentação `///`._
