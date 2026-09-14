# `examples/052_keywords_records.lum`

052 — Keywords da v0.3, raw identifiers, atributos com args,
literais com sufixo, raw strings, \u{...}, comentários /* aninhados */.

## Índice

- `struct` [Ponto](#ponto)
- `struct` [r](#r)
- `fn` [atributo_com_args](#atributo-com-args)
- `fn` [msg_raw](#msg-raw)
- `fn` [main](#main)
- `fn` [testa_sufixos](#testa-sufixos)
- `fn` [testa_raw_identifier](#testa-raw-identifier)

## `struct` Ponto

```lum
struct Ponto {
```

Registros com campos tipados e literais com sufixo.

## `struct` r

```lum
struct r#type {
```

Raw identifier como nome de campo: r#value é tratado como IDENT "value".

## `fn` atributo_com_args

```lum
fn atributo_com_args() -> int {
```

Atributos: `#[test(should_panic)]`

Atributo com args.

## `fn` msg_raw

```lum
fn msg_raw() -> str {
```

Raw string com conteúdo que não interpreta escapes.

## `fn` main

```lum
fn main() {
```

_Sem documentação `///`._

## `fn` testa_sufixos

```lum
fn testa_sufixos() {
```

Atributos: `#[test]`

_Sem documentação `///`._

## `fn` testa_raw_identifier

```lum
fn testa_raw_identifier() {
```

Atributos: `#[test]`

_Sem documentação `///`._
