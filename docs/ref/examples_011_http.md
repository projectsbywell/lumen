# `examples/011_http.lum`

011 — Cliente HTTP mínimo.

`http::get` devolve `Resposta { status, corpo }`. Aqui o corpo é
um JSON que fazemos parse com `std::json`.

## Índice

- `fn` [busca_titulo](#busca-titulo)
- `fn` [main](#main)
- `fn` [testa_busca_sync](#testa-busca-sync)

## `fn` busca_titulo

```lum
fn busca_titulo(url: str) -> Result<String, str> {
```

Busca o título de um item na API de exemplo.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_busca_sync

```lum
fn testa_busca_sync() {
```

Atributos: `#[test]`

_Sem documentação `///`._
