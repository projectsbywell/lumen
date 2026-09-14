# `examples/001-050/023_arvore.lum`

023 — Árvore binária de busca com `struct`, `enum` e `match`.

Implementa BST simplificada sobre `Vec` ordenado (representação
por array). `Arvore` guarda `dados: Vec` e `n: i32`. `Ordem` é
o enum de percurso. `inserir` mantém ordenação, `buscar` usa
busca binária, `percorrer` usa `match`.

## Índice

- `enum` [Ordem](#ordem)
- `struct` [Arvore](#arvore)
- `impl` [Arvore](#arvore)
- `fn` [nova](#nova)
- `fn` [de_vec](#de-vec)
- `fn` [inserir_ord](#inserir-ord)
- `fn` [inserir](#inserir)
- `fn` [buscar](#buscar)
- `fn` [minimo](#minimo)
- `fn` [maximo](#maximo)
- `fn` [altura](#altura)
- `fn` [percorrer](#percorrer)
- `fn` [reverso](#reverso)
- `fn` [main](#main)
- `fn` [testa_arvore](#testa-arvore)

## `enum` Ordem

```lum
enum Ordem {
```

Ordem de percurso.

## `struct` Arvore

```lum
struct Arvore {
```

Árvore binária de busca (array ordenado).

## `impl` Arvore

```lum
impl Arvore {
```

_Sem documentação `///`._

## `fn` nova

```lum
fn nova() -> Arvore {
```

Cria árvore vazia.

## `fn` de_vec

```lum
fn de_vec(v: Vec<i32>) -> Arvore {
```

Cria a partir de vetor (copia).

## `fn` inserir_ord

```lum
fn inserir_ord(v: Vec<i32>, valor: i32) -> Vec<i32> {
```

Insere mantendo ordenação.

## `fn` inserir

```lum
fn inserir(a: Arvore, valor: i32) -> Arvore {
```

Insere valor na árvore.

## `fn` buscar

```lum
fn buscar(a: Arvore, alvo: i32) -> bool {
```

Busca valor (binária).

## `fn` minimo

```lum
fn minimo(a: Arvore) -> Option<i32> {
```

Mínimo (primeiro elemento).

## `fn` maximo

```lum
fn maximo(a: Arvore) -> Option<i32> {
```

Máximo (último elemento).

## `fn` altura

```lum
fn altura(a: Arvore) -> i32 {
```

Altura estimada (log2).

## `fn` percorrer

```lum
fn percorrer(a: Arvore, ordem: Ordem) -> Vec<i32> {
```

Percurso segundo `ordem`.

## `fn` reverso

```lum
fn reverso(v: Vec<i32>) -> Vec<i32> {
```

Inverte vetor.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_arvore

```lum
fn testa_arvore() {
```

Atributos: `#[test]`

_Sem documentação `///`._
