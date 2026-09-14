# `examples/012_sqlite.lum`

012 — SQLite embarcado.

`sqlite::abrir(":memory:")` cria um banco em RAM — perfeito para
testes. `exec` roda DDL/DML, `query` devolve linhas.

## Índice

- `fn` [prepara](#prepara)
- `fn` [main](#main)
- `fn` [testa_prepara](#testa-prepara)

## `fn` prepara

```lum
fn prepara(db: mut sqlite::Db) -> Result<i32, str> {
```

Cria a tabela e insere dois usuários. Retorna linhas afetadas.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_prepara

```lum
fn testa_prepara() {
```

Atributos: `#[test]`

_Sem documentação `///`._
