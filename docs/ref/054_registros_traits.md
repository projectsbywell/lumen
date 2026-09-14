# `examples/054_registros_traits.lum`

054 — Tipos registro `{f: t}` e trait declarations da v0.3.

Demonstra structs com campos tipados, tipos registro anônimos
como assinaturas de função, e declaração de traits com métodos.

## Índice

- `struct` [Ponto](#ponto)
- `trait` [Area](#area)
- `fn` [area](#area)
- `trait` [Descricao](#descricao)
- `fn` [descricao](#descricao)
- `fn` [centro](#centro)
- `fn` [ponto_novo](#ponto-novo)
- `fn` [main](#main)
- `fn` [testa_centro](#testa-centro)
- `fn` [testa_ponto_novo](#testa-ponto-novo)

## `struct` Ponto

```lum
struct Ponto {
```

Struct com campos tipados.

## `trait` Area

```lum
trait Area {
```

Trait com métodos exigidos (declaração).

## `fn` area

```lum
fn area(self) -> f64;
```

_Sem documentação `///`._

## `trait` Descricao

```lum
trait Descricao {
```

Trait com métodos exigidos para descrição.

## `fn` descricao

```lum
fn descricao(self) -> str;
```

_Sem documentação `///`._

## `fn` centro

```lum
fn centro(rec: {x: f64, y: f64}) -> {x: f64, y: f64} {
```

Função que recebe e retorna registro anônimo como tipo.

## `fn` ponto_novo

```lum
fn ponto_novo(x: f64, y: f64) -> Ponto {
```

Construtor de Ponto.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_centro

```lum
fn testa_centro() {
```

Atributos: `#[test]`

_Sem documentação `///`._

## `fn` testa_ponto_novo

```lum
fn testa_ponto_novo() {
```

Atributos: `#[test]`

_Sem documentação `///`._
