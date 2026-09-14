# `examples/001-050/037_cache.lum`

037 — Cache: armazenamento em mapa com expiração.

Um cache simples que guarda valores com tempo de vida (TTL).
`cache_novo` cria; `cache_put` insere; `cache_get` busca;
`cache_limpar` remove expirados.

## Índice

- `struct` [EntradaCache](#entradacache)
- `struct` [Cache](#cache)
- `fn` [cache_novo](#cache-novo)
- `fn` [avanca_relogio](#avanca-relogio)
- `fn` [cache_put](#cache-put)
- `fn` [cache_get](#cache-get)
- `fn` [cache_limpar](#cache-limpar)
- `fn` [main](#main)
- `fn` [testa_cache_put_get](#testa-cache-put-get)
- `fn` [testa_cache_expiracao](#testa-cache-expiracao)

## `struct` EntradaCache

```lum
struct EntradaCache { valor: str, expira_em: i32 }
```

Entrada do cache: valor + tempo de expiração.

## `struct` Cache

```lum
struct Cache {
```

Cache chave=valor com expiração por.tick.

## `fn` cache_novo

```lum
fn cache_novo() -> Cache {
```

Cria um cache vazio.

## `fn` avanca_relogio

```lum
fn avanca_relogio(c: mut Cache, delta: i32) {
```

Avança o relógio interno do cache.

## `fn` cache_put

```lum
fn cache_put(c: mut Cache, chave: str, valor: str, ttl: i32) {
```

Insere um valor com TTL (em ticks).

## `fn` cache_get

```lum
fn cache_get(c: Cache, chave: str) -> Option {
```

Busca um valor; retorna None se ausente ou expirado.

## `fn` cache_limpar

```lum
fn cache_limpar(c: mut Cache) -> i32 {
```

Remove entradas expiradas e devolve quantas sobraram.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_cache_put_get

```lum
fn testa_cache_put_get() {
```

Atributos: `#[test]`

_Sem documentação `///`._

## `fn` testa_cache_expiracao

```lum
fn testa_cache_expiracao() {
```

Atributos: `#[test]`

_Sem documentação `///`._
