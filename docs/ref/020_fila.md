# `examples/001-050/020_fila.lum`

020 — Fila (FIFO) com `Vec` e `struct` + `impl`.

Fila segue FIFO: `enfileirar` insere no final, `desenfileirar`
remove do começo. `frente` espreita o primeiro. Usa `Vec`,
`Option` e `Result`.

## Índice

- `struct` [Fila](#fila)
- `impl` [Fila](#fila)
- `fn` [nova](#nova)
- `fn` [de_vec](#de-vec)
- `fn` [len](#len)
- `fn` [vazia](#vazia)
- `fn` [enfileirar](#enfileirar)
- `fn` [frente](#frente)
- `fn` [sem_frente](#sem-frente)
- `fn` [desenfileirar](#desenfileirar)
- `fn` [desenfileirar_ok](#desenfileirar-ok)
- `fn` [fila_para_str](#fila-para-str)
- `fn` [main](#main)
- `fn` [testa_fila](#testa-fila)

## `struct` Fila

```lum
struct Fila {
```

Fila de inteiros.

## `impl` Fila

```lum
impl Fila {
```

_Sem documentação `///`._

## `fn` nova

```lum
fn nova() -> Fila {
```

Cria fila vazia.

## `fn` de_vec

```lum
fn de_vec(v: Vec<i32>) -> Fila {
```

Cria fila a partir de vetor.

## `fn` len

```lum
fn len(f: Fila) -> i32 {
```

Quantidade de elementos.

## `fn` vazia

```lum
fn vazia(f: Fila) -> bool {
```

True se vazia.

## `fn` enfileirar

```lum
fn enfileirar(f: Fila, valor: i32) -> Fila {
```

Enfileira `valor` no final.

## `fn` frente

```lum
fn frente(f: Fila) -> Option<i32> {
```

Frente da fila sem remover.

## `fn` sem_frente

```lum
fn sem_frente(f: Fila) -> Fila {
```

Remove a frente e devolve nova fila.

## `fn` desenfileirar

```lum
fn desenfileirar(f: Fila) -> Option<i32> {
```

Desenfileira: `Some(valor)` ou `None` se vazia.

## `fn` desenfileirar_ok

```lum
fn desenfileirar_ok(f: Fila) -> Result<i32, str> {
```

Desenfileira com `Result`.

## `fn` fila_para_str

```lum
fn fila_para_str(f: Fila) -> str {
```

Converte fila em string para debug.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_fila

```lum
fn testa_fila() {
```

Atributos: `#[test]`

_Sem documentação `///`._
