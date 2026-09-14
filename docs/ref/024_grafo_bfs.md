# `examples/001-050/024_grafo_bfs.lum`

024 — Grafo e BFS com `Vec`, `Map` e `while`.

Grafo não-direcionado representado por lista de adjacência
`Map<i32, Vec<i32>>`. `bfs` percorre em largura usando fila
(`Vec` como fila), `vec::get`, `map::get`, `map::insert` e
`vec::push`.

## Índice

- `fn` [grafo_novo](#grafo-novo)
- `fn` [adicionar_vertice](#adicionar-vertice)
- `fn` [adicionar_aresta](#adicionar-aresta)
- `fn` [visitado](#visitado)
- `fn` [bfs](#bfs)
- `fn` [distancia](#distancia)
- `fn` [main](#main)
- `fn` [testa_bfs](#testa-bfs)

## `fn` grafo_novo

```lum
fn grafo_novo() -> Map<i32, Vec<i32>> {
```

Cria grafo vazio.

## `fn` adicionar_vertice

```lum
fn adicionar_vertice(g: Map<i32, Vec<i32>>, v: i32) -> Map<i32, Vec<i32>> {
```

Adiciona vértice isolado (sem arestas).

## `fn` adicionar_aresta

```lum
fn adicionar_aresta(g: Map<i32, Vec<i32>>, u: i32, v: i32) -> Map<i32, Vec<i32>> {
```

Adiciona aresta não-direcionada u—v.

## `fn` visitado

```lum
fn visitado(visitados: Vec<i32>, v: i32) -> bool {
```

Verifica se `v` está em `visitados`.

## `fn` bfs

```lum
fn bfs(g: Map<i32, Vec<i32>>, inicio: i32) -> Vec<i32> {
```

BFS a partir de `inicio`. Devolve ordem de visita.

## `fn` distancia

```lum
fn distancia(g: Map<i32, Vec<i32>>, origem: i32, destino: i32) -> i32 {
```

Distância (número de arestas) via BFS; -1 se inalcançável.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_bfs

```lum
fn testa_bfs() {
```

Atributos: `#[test]`

_Sem documentação `///`._
