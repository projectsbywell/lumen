# `examples/001-050/019_pilha.lum`

019 — Pilha (LIFO) com `Vec` e `struct` + `impl`.

Pilha segue LIFO: `empilhar` adiciona no topo, `desempilhar`
remove do topo. `topo` espreita sem remover. Usa `Vec<i32>`,
`Option` e `Result` para tratar pilha vazia.

## Índice

- `struct` [Pilha](#pilha)
- `impl` [Pilha](#pilha)
- `fn` [nova](#nova)
- `fn` [de_vec](#de-vec)
- `fn` [tamanho](#tamanho)
- `fn` [vazia](#vazia)
- `fn` [empilhar](#empilhar)
- `fn` [desempilhar](#desempilhar)
- `fn` [sem_topo](#sem-topo)
- `fn` [topo](#topo)
- `fn` [desempilhar_ok](#desempilhar-ok)
- `fn` [main](#main)
- `fn` [testa_pilha](#testa-pilha)

## `struct` Pilha

```lum
struct Pilha {
```

Pilha de inteiros.

## `impl` Pilha

```lum
impl Pilha {
```

_Sem documentação `///`._

## `fn` nova

```lum
fn nova() -> Pilha {
```

Cria pilha vazia.

## `fn` de_vec

```lum
fn de_vec(v: Vec<i32>) -> Pilha {
```

Cria pilha a partir de vetor existente.

## `fn` tamanho

```lum
fn tamanho(p: Pilha) -> i32 {
```

Quantidade de elementos.

## `fn` vazia

```lum
fn vazia(p: Pilha) -> bool {
```

True se vazia.

## `fn` empilhar

```lum
fn empilhar(p: Pilha, valor: i32) -> Pilha {
```

Empilha `valor` e devolve nova pilha.

## `fn` desempilhar

```lum
fn desempilhar(p: Pilha) -> Option<i32> {
```

Desempilha: devolve `Some((valor, nova_pilha))` ou `None`.

## `fn` sem_topo

```lum
fn sem_topo(p: Pilha) -> Pilha {
```

Pilha após remover o topo.

## `fn` topo

```lum
fn topo(p: Pilha) -> Option<i32> {
```

Espreita o topo sem remover.

## `fn` desempilhar_ok

```lum
fn desempilhar_ok(p: Pilha) -> Result<i32, str> {
```

Desempilha com `Result` para mensagem de erro.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_pilha

```lum
fn testa_pilha() {
```

Atributos: `#[test]`

_Sem documentação `///`._
