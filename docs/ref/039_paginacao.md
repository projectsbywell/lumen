# `examples/001-050/039_paginacao.lum`

039 — Paginação de vetor.

Devolve a fatia `[pagina * tam, ...]` sem sair dos limites.

## Índice

- `fn` [pagina](#pagina)
- `fn` [num_paginas](#num-paginas)
- `fn` [main](#main)

## `fn` pagina

```lum
fn pagina(v: vec, p: i32, tam: i32) -> vec {
```

Página `p` (base 0) de tamanho `tam`.

## `fn` num_paginas

```lum
fn num_paginas(v: vec, tam: i32) -> i32 {
```

Quantas páginas existem.

## `fn` main

```lum
fn main() {
```

_Sem documentação `///`._
