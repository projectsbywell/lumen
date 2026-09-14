# `examples/001-050/035_config.lum`

035 — Configuração: carregar e acessar chaves de um `Map`.

Um `Config` guarda pares chave=valor. `cfg_carrega` parseia
linhas `KEY=valor`; `cfg_obter` busca; `cfg_inteiro` converte.

## Índice

- `struct` [Config](#config)
- `fn` [cfg_novo](#cfg-novo)
- `fn` [cfg_carrega](#cfg-carrega)
- `fn` [cfg_obter](#cfg-obter)
- `fn` [cfg_inteiro](#cfg-inteiro)
- `fn` [main](#main)
- `fn` [testa_cfg_obter](#testa-cfg-obter)
- `fn` [testa_cfg_inteiro](#testa-cfg-inteiro)

## `struct` Config

```lum
struct Config { dados: Map }
```

Configuração chave=valor.

## `fn` cfg_novo

```lum
fn cfg_novo() -> Config {
```

Cria configuração vazia.

## `fn` cfg_carrega

```lum
fn cfg_carrega(c: mut Config, texto: str) {
```

Carrega linhas `chave=valor` separadas por `\n`.

## `fn` cfg_obter

```lum
fn cfg_obter(c: Config, chave: str) -> Option {
```

Busca o valor de uma chave.

## `fn` cfg_inteiro

```lum
fn cfg_inteiro(c: Config, chave: str) -> Result<i32, str> {
```

Converte o valor de uma chave para i32.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_cfg_obter

```lum
fn testa_cfg_obter() {
```

Atributos: `#[test]`

_Sem documentação `///`._

## `fn` testa_cfg_inteiro

```lum
fn testa_cfg_inteiro() {
```

Atributos: `#[test]`

_Sem documentação `///`._
