# `examples/001-050/022_ordenacao.lum`

022 — Ordenação comparativa: quicksort e insertion sort.

Mostra dois algoritmos sobre `Vec<i32>`: `quicksort` recursivo
e `insertion_sort` iterativo. Usa `match`, `if-else`, `while`
e `vec::push`/`vec::get`/`vec::len`.

## Índice

- `fn` [concat](#concat)
- `fn` [quicksort](#quicksort)
- `fn` [inserir_ordenado](#inserir-ordenado)
- `fn` [insertion_sort](#insertion-sort)
- `fn` [ordenado](#ordenado)
- `fn` [main](#main)
- `fn` [testa_ordenacao](#testa-ordenacao)

## `fn` concat

```lum
fn concat(a: Vec<i32>, b: Vec<i32>) -> Vec<i32> {
```

Concatena dois vetores.

## `fn` quicksort

```lum
fn quicksort(v: Vec<i32>) -> Vec<i32> {
```

Quicksort funcional: escolhe pivô e particiona.

## `fn` inserir_ordenado

```lum
fn inserir_ordenado(v: Vec<i32>, valor: i32) -> Vec<i32> {
```

Insere `valor` em vetor já ordenado.

## `fn` insertion_sort

```lum
fn insertion_sort(v: Vec<i32>) -> Vec<i32> {
```

Insertion sort iterativo.

## `fn` ordenado

```lum
fn ordenado(v: Vec<i32>) -> bool {
```

Verifica ordenação.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_ordenacao

```lum
fn testa_ordenacao() {
```

Atributos: `#[test]`

_Sem documentação `///`._
